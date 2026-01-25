import json
import logging
import os
import time
from abc import ABC, abstractmethod
from typing import Optional

import boto3
import requests
from dotenv import load_dotenv
from google import genai
from google.genai import types
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from llm.request_logger import LLMRequestLogger, RequestTimer, detect_error_status

load_dotenv()

# Global list to store pending log entries (flushed by caller when they have a DB session)
_pending_llm_logs = []


def get_pending_llm_logs():
    """Get all pending LLM log entries and clear the list."""
    global _pending_llm_logs
    logs = _pending_llm_logs.copy()
    _pending_llm_logs = []
    return logs


def add_pending_llm_log(log_entry):
    """Add a log entry to the pending list."""
    global _pending_llm_logs
    _pending_llm_logs.append(log_entry)


# Configure debug logging for LLM calls
LLM_DEBUG = os.environ.get("LLM_DEBUG", "false").lower() == "true"

# Set up logger
logger = logging.getLogger("llm_module")
if LLM_DEBUG:
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "\n%(asctime)s - %(name)s - %(levelname)s\n%(message)s\n",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
else:
    logger.setLevel(logging.WARNING)

# Determine the LLM provider
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "gemini").lower()


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, system_prompt: str):
        self.system_prompt = system_prompt

    @abstractmethod
    def generate(self, prompt: str, temperature: Optional[float] = None) -> str:
        """Generate a response from the LLM.

        Args:
            prompt: The user's prompt.
            temperature: Optional temperature override (0.0-1.0). If None, uses default.

        Returns:
            The text response from the LLM.

        Raises:
            Exception: If the API call fails.
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the name of the provider."""
        pass


class GeminiProvider(LLMProvider):
    """Provider for Google Gemini models using the new google-genai library."""

    # Retryable exception types - using base Exception for now as the new library
    # may have different exception structure
    RETRYABLE_EXCEPTIONS = (Exception,)

    def __init__(
        self,
        system_prompt: str,
        api_key: str,
        model_name: str,
    ):
        super().__init__(system_prompt)

        # Use GEMINI_API_KEY for Vertex AI
        # self.api_key = api_key
        # if not self.api_key:
        #     raise ValueError(
        #         "API key not provided and GEMINI_API_KEY environment variable not set. "
        #         "Make sure GOOGLE_GENAI_USE_VERTEXAI=True is also set for Vertex AI."
        #     )

        self.model_name = model_name

        # Print environment variables
        print("\n" + "=" * 80)
        print("[GEMINI] Environment Variables:")
        print(
            f"  GEMINI_API_KEY: {'SET' if os.getenv('GEMINI_API_KEY') else 'NOT SET'}"
        )
        print(
            f"  GOOGLE_CLOUD_LOCATION: {os.getenv('GOOGLE_CLOUD_LOCATION', 'NOT SET')}"
        )
        print(f"  LLM_PROVIDER: {os.getenv('LLM_PROVIDER', 'NOT SET')}")
        print(f"  Model: {self.model_name}")
        print("=" * 80)

        self.client = genai.Client(
            vertexai=True,
            location="global",
            # api_key=self.api_key,
            http_options={"api_version": "v1"},
        )

        # Print client configuration
        print(f"\n[GEMINI] Client Configuration:")
        print(f"  Client type: {type(self.client).__name__}")
        if hasattr(self.client, "location"):
            print(f"  client.location: {self.client.location}")
        print(f"  Location from env: {os.getenv('GOOGLE_CLOUD_LOCATION', 'NOT SET')}")
        print("=" * 80 + "\n")

    def get_provider_name(self) -> str:
        return "gemini"

    def _is_retriable_error(self, exception: Exception) -> bool:
        """Check if an exception is retriable based on error message or type."""
        error_str = str(exception).lower()
        retriable_keywords = ["429", "503", "504", "timeout", "deadline", "resource"]
        return any(keyword in error_str for keyword in retriable_keywords)

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=20),
        before_sleep=lambda retry_state: print(
            f"Retriable error: {retry_state.outcome.exception()}. "
            f"Retrying in {retry_state.next_action.sleep}s... "
            f"(Attempt {retry_state.attempt_number})"
        ),
    )
    def generate(self, prompt: str, temperature: Optional[float] = None) -> str:
        try:
            # Use provided temperature or default to 0.7
            temp = temperature if temperature is not None else 0.7

            # Build config - only add thinking_config for models that support it
            config_kwargs = {
                "temperature": temp,
                "system_instruction": self.system_prompt,
            }

            # Only add thinking_config for pro models that support it
            # Flash models don't support thinking_config
            if (
                "pro" in self.model_name.lower()
                and "flash" not in self.model_name.lower()
            ):
                config_kwargs["thinking_config"] = types.ThinkingConfig(
                    thinking_level="low"
                )

            # Use the new API with GenerateContentConfig
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(**config_kwargs),
            )

            # Extract text from response
            if not response.text:
                raise Exception("Request returned no content")

            return response.text

        except Exception as e:
            error_message = str(e)
            if LLM_DEBUG:
                logger.debug(f"GEMINI ERROR: {error_message}")

            # Check if this is a retriable error
            if self._is_retriable_error(e):
                if LLM_DEBUG:
                    logger.debug(f"RETRIABLE ERROR: {e}")
                raise e
            else:
                if LLM_DEBUG:
                    logger.debug(f"NON-RETRIABLE ERROR: {e}")
                raise Exception(f"A non-retriable error occurred: {e}")


class OllamaProvider(LLMProvider):
    """Provider for Ollama models."""

    def __init__(
        self,
        system_prompt: str,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        super().__init__(system_prompt)

        self.base_url = base_url or os.environ.get(
            "OLLAMA_BASE_URL", "http://localhost:11434"
        )
        self.model_name = model_name or os.environ.get("OLLAMA_MODEL_NAME", "qwen3:8b")

        print(f"Using Ollama at {self.base_url} with model {self.model_name}")

    def get_provider_name(self) -> str:
        return "ollama"

    def generate(self, prompt: str, temperature: Optional[float] = None) -> str:
        try:
            # Use provided temperature or default to 0.7
            temp = temperature if temperature is not None else 0.7
            headers = {"Content-Type": "application/json"}
            data = {
                "model": self.model_name,
                "prompt": f"{self.system_prompt}\n{prompt}",
                "stream": False,
                "think": False,
                "options": {
                    "temperature": temp,
                },
            }
            response = requests.post(
                f"{self.base_url}/api/generate",
                headers=headers,
                data=json.dumps(data),
            )
            response.raise_for_status()
            return response.json()["response"]

        except requests.exceptions.RequestException as e:
            if LLM_DEBUG:
                logger.debug(f"OLLAMA ERROR: {e}")
            raise Exception(f"Ollama API call failed: {e}")


class BedrockProvider(LLMProvider):
    """Provider for AWS Bedrock models."""

    def __init__(
        self,
        system_prompt: str,
        model_id: Optional[str] = None,
        aws_profile: Optional[str] = None,
    ):
        super().__init__(system_prompt)

        # Model ID should be the global inference profile
        # e.g., "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
        self.model_id = model_id or os.environ.get(
            "BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
        )

        # AWS profile to use (e.g., "rai")
        self.aws_profile = aws_profile or os.environ.get("AWS_PROFILE")

        # Create a session with the specified profile
        session_kwargs = {}
        if self.aws_profile:
            session_kwargs["profile_name"] = self.aws_profile

        session = boto3.Session(**session_kwargs)

        # Create bedrock-runtime client
        self.client = session.client(
            service_name="bedrock-runtime",
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
        )

        print(
            f"Using Bedrock with model {self.model_id}, profile: {self.aws_profile or 'default'}"
        )

    def get_provider_name(self) -> str:
        return "bedrock"

    def generate(self, prompt: str, temperature: Optional[float] = None) -> str:
        try:
            # Use provided temperature or default to 0.7
            temp = temperature if temperature is not None else 0.7

            # Detect model type based on model_id
            is_claude = (
                "anthropic" in self.model_id.lower()
                or "claude" in self.model_id.lower()
            )
            is_nova = "nova" in self.model_id.lower()

            if is_claude:
                # Claude models use Messages API format
                messages = [{"role": "user", "content": prompt}]
                request_body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 4096,
                    "temperature": temp,
                    "messages": messages,
                    "system": self.system_prompt,
                }
            elif is_nova:
                # Nova models use a different format (no max_tokens, different structure)
                # Combine system prompt with user prompt
                full_prompt = f"{self.system_prompt}\n\n{prompt}"
                request_body = {
                    "messages": [{"role": "user", "content": [{"text": full_prompt}]}],
                    "inferenceConfig": {
                        "temperature": temp,
                    },
                }
            else:
                # Fallback to Claude format for unknown models
                messages = [{"role": "user", "content": prompt}]
                request_body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 4096,
                    "temperature": temp,
                    "messages": messages,
                    "system": self.system_prompt,
                }

            # Invoke the model
            response = self.client.invoke_model(
                modelId=self.model_id, body=json.dumps(request_body)
            )

            # Parse the response
            response_body = json.loads(response["body"].read())

            # Extract text based on model type
            if is_claude:
                if "content" in response_body and len(response_body["content"]) > 0:
                    return response_body["content"][0]["text"]
            elif is_nova:
                # Nova response format
                if "output" in response_body and "message" in response_body["output"]:
                    message = response_body["output"]["message"]
                    if "content" in message and len(message["content"]) > 0:
                        return message["content"][0]["text"]
            else:
                # Try Claude format for unknown models
                if "content" in response_body and len(response_body["content"]) > 0:
                    return response_body["content"][0]["text"]

            raise Exception("No content in Bedrock response")

        except Exception as e:
            if LLM_DEBUG:
                logger.debug(f"BEDROCK ERROR: {e}")
            raise Exception(f"Bedrock API call failed: {e}")


class LLMModule:
    """
    A reusable module for interacting with various LLMs (Gemini, Ollama, Bedrock)
    configured with a specific system prompt.

    This module handles API calls and automatic retries for supported providers.
    """

    def __init__(
        self, system_prompt: str, provider: Optional[LLMProvider] = None, **kwargs
    ):
        """
        Initializes the LLM module with a system prompt and provider.

        Args:
            system_prompt: The system-level instruction for the model.
            provider: An LLMProvider instance. If None, creates one based on LLM_PROVIDER env var.
            **kwargs: Additional arguments passed to the provider constructor.
        """
        self.system_prompt = system_prompt

        if provider is not None:
            self.provider = provider
        else:
            # Auto-detect provider from environment
            provider_type = kwargs.get("provider_type")

            if provider_type == "gemini":
                self.provider = GeminiProvider(
                    system_prompt=system_prompt,
                    api_key=os.getenv("GEMINI_API_KEY"),
                    model_name=kwargs.get("model_name"),
                )
            elif provider_type == "ollama":
                self.provider = OllamaProvider(
                    system_prompt=system_prompt,
                    base_url=kwargs.get("base_url"),
                    model_name=kwargs.get("model_name"),
                )
            elif provider_type == "bedrock":
                self.provider = BedrockProvider(
                    system_prompt=system_prompt,
                    model_id=kwargs.get("model_id"),
                    aws_profile=kwargs.get("aws_profile"),
                )
            else:
                raise ValueError(f"Unsupported LLM provider: {provider_type}")

    def get_response(self, prompt: str, temperature: Optional[float] = None) -> str:
        """
        Gets a response from the LLM based on the user prompt.

        This method does not maintain conversation history.

        Args:
            prompt: The user's prompt.
            temperature: Optional temperature override (0.0-1.0). If None, uses provider default.

        Returns:
            The text response from the LLM.

        Raises:
            Exception: If the API call fails.
        """
        # Get caller information
        import inspect

        frame = inspect.currentframe()
        caller_frame = frame.f_back
        caller_name = caller_frame.f_code.co_name
        caller_file = caller_frame.f_code.co_filename.split("/")[-1]

        # Print caller info
        print(
            f"[LLM_CALL] {caller_file}::{caller_name}() → {self.provider.get_provider_name()}"
        )

        # Log the prompt if debug mode is enabled
        if LLM_DEBUG:
            logger.debug("=" * 80)
            logger.debug(f"LLM PROMPT ({self.provider.get_provider_name()}):")
            logger.debug("-" * 80)
            # Show FULL system prompt to see if theme is included
            logger.debug(f"SYSTEM PROMPT ({len(self.system_prompt)} chars):")
            logger.debug(self.system_prompt)
            logger.debug("-" * 80)
            logger.debug(f"USER PROMPT:\n{prompt}")
            if temperature is not None:
                logger.debug(f"TEMPERATURE: {temperature}")
            logger.debug("-" * 80)

        # Get model name for logging
        model_name = getattr(self.provider, "model_name", None) or getattr(
            self.provider, "model_id", "unknown"
        )

        # Time the LLM request
        start_time = time.perf_counter()
        response_text = None
        error_msg = None
        status = 200

        try:
            response_text = self.provider.generate(prompt, temperature=temperature)
        except Exception as e:
            error_msg = str(e)
            status = detect_error_status(e)
            # Re-raise after logging
            raise
        finally:
            end_time = time.perf_counter()
            duration_ms = int((end_time - start_time) * 1000)

            # Create log entry
            log_entry = LLMRequestLogger.create_log_entry(
                function_call="llm_get_response",
                provider=self.provider.get_provider_name(),
                model_id=model_name,
                prompt=f"[SYSTEM]: {self.system_prompt[:500]}...\n[USER]: {prompt}",
                status=status,
                response=response_text,
                retry_count=0,  # Retries handled internally by tenacity
                latency_ms=duration_ms,
                error_message=error_msg,
            )
            add_pending_llm_log(log_entry)

            # Log the response time
            print(
                f"[{self.provider.get_provider_name()}] Response time: {duration_ms}ms"
            )

        # Log the response if debug mode is enabled
        if LLM_DEBUG:
            logger.debug(f"LLM RESPONSE ({self.provider.get_provider_name()}):")
            logger.debug("-" * 80)
            logger.debug(f"{response_text}")
            logger.debug("=" * 80)

        return response_text

    def get_validated_response(
        self, prompt: str, max_words: int = None, min_words: int = 1
    ) -> str:
        """
        Get a response with validation.

        Args:
            prompt: The prompt to send
            max_words: Maximum number of words (None for no limit)
            min_words: Minimum number of words

        Returns:
            Validated response text

        Raises:
            ValueError: If response doesn't meet validation criteria
        """
        response = self.get_response(prompt)

        if not response or len(response.strip()) == 0:
            raise ValueError("Empty LLM response")

        words = response.split()

        if min_words and len(words) < min_words:
            raise ValueError(
                f"Response too short: {len(words)} words (min: {min_words})"
            )

        if max_words and len(words) > max_words:
            response = " ".join(words[:max_words])

        return response.strip()

    def get_response_with_fallback(
        self, prompt: str, fallback: str = "Unable to generate response"
    ) -> str:
        """
        Get a response with a fallback value on error.

        Args:
            prompt: The prompt to send
            fallback: Fallback text if LLM fails

        Returns:
            LLM response or fallback text
        """
        try:
            return self.get_validated_response(prompt)
        except Exception as e:
            print(f"LLM error: {e}, using fallback")
            return fallback


def create_llm_module(system_prompt: str, **kwargs) -> LLMModule:
    """
    Factory function to create a new LLMModule instance.

    Args:
        system_prompt: The system-level instruction for the model.
        **kwargs: Additional arguments:
            - provider_type: The LLM provider to use ("gemini", "ollama", or "bedrock")
            - For Gemini: api_key, model_name
            - For Ollama: base_url, model_name
            - For Bedrock: model_id, aws_profile

    Returns:
        An instance of the LLMModule class.
    """
    return LLMModule(system_prompt, **kwargs)


def create_fast_llm(system_prompt: str) -> LLMModule:
    """
    Create an LLM module optimized for speed (fast, cheap model).
    Use for: extraction, summarization, simple transformations.

    Uses LLM_PROVIDER to determine provider, then FAST_MODEL for the specific model.

    Args:
        system_prompt: The system-level instruction for the model.

    Returns:
        An instance of the LLMModule class configured with fast model.
    """
    provider = LLM_PROVIDER
    fast_model = os.environ.get("FAST_MODEL")

    print(f"[FAST_LLM] Provider: {provider}, Model: {fast_model}")

    # Use LLM_PROVIDER to determine which provider to use
    if provider == "gemini":
        return LLMModule(
            system_prompt,
            provider_type="gemini",
            model_name=fast_model,
        )
    elif provider == "bedrock":
        return LLMModule(
            system_prompt,
            provider_type="bedrock",
            model_id=fast_model,
        )
    elif provider == "ollama":
        return LLMModule(
            system_prompt,
            provider_type="ollama",
            model_name=fast_model,
        )
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")


def create_quality_llm(system_prompt: str) -> LLMModule:
    """
    Create an LLM module optimized for quality (thinking model).
    Use for: creative generation, new descriptions, complex reasoning.

    Uses LLM_PROVIDER to determine provider, then QUALITY_MODEL for the specific model.

    Args:
        system_prompt: The system-level instruction for the model.

    Returns:
        An instance of the LLMModule class configured with quality model.
    """
    provider = LLM_PROVIDER
    quality_model = os.environ.get("QUALITY_MODEL")

    print(f"[QUALITY_LLM] Provider: {provider}, Model: {quality_model}")

    # Use LLM_PROVIDER to determine which provider to use
    if provider == "gemini":
        return LLMModule(
            system_prompt,
            provider_type="gemini",
            model_name=quality_model,
        )
    elif provider == "bedrock":
        return LLMModule(
            system_prompt,
            provider_type="bedrock",
            model_id=quality_model,
        )
    elif provider == "ollama":
        return LLMModule(
            system_prompt,
            provider_type="ollama",
            model_name=quality_model,
        )
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")


# --- Example Usage ---
if __name__ == "__main__":
    provider = LLM_PROVIDER
    print(f"Running LLM module example (using {provider})...")
    try:
        translator_module = create_fast_llm(
            system_prompt="You are a helpful assistant that translates English to French. "
            "Only provide the French translation and nothing else."
        )

        french_translation = translator_module.get_response(
            prompt="Hello, how are you?"
        )
        print(f"English: Hello, how are you?")
        print(f"French: {french_translation}")

        poet_module = create_quality_llm(
            system_prompt="You are a poet. You respond with a short, 2-line rhyming poem."
        )

        poem = poet_module.get_response(prompt="Write me a poem about a cat.")
        print("\n--- Poet Module ---")
        print(poem)

    except (Exception, ValueError) as e:
        print(f"\nAn error occurred: {e}")
        if provider == "gemini":
            print(
                "Please ensure your GOOGLE_API_KEY is set as an environment variable."
            )
        elif provider == "ollama":
            print(
                f"Please ensure your Ollama server is running and the model is available."
            )
        elif provider == "bedrock":
            print(
                "Please ensure your AWS credentials are configured and you have access to Bedrock."
            )
