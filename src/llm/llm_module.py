import json
import logging
import os
import time
from abc import ABC, abstractmethod
from typing import Optional

import boto3
import google.generativeai as genai
import requests
from dotenv import load_dotenv
from google.api_core import exceptions as google_exceptions
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

load_dotenv()

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
    """Provider for Google Gemini models."""

    # Retryable exceptions for Gemini
    RETRYABLE_EXCEPTIONS = (
        google_exceptions.ResourceExhausted,  # 429 Too Many Requests
        google_exceptions.DeadlineExceeded,  # 504 Timeout
        google_exceptions.InternalServerError,  # 500 Internal Server Error
        google_exceptions.ServiceUnavailable,  # 503 Service Unavailable
    )

    def __init__(
        self,
        system_prompt: str,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        super().__init__(system_prompt)

        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "API key not provided and GOOGLE_API_KEY environment variable not set."
            )

        self.model_name = model_name or os.environ.get(
            "GEMINI_MODEL_NAME", "gemini-2.5-flash"
        )

        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=self.system_prompt,
        )

    def get_provider_name(self) -> str:
        return "gemini"

    @retry(
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
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
            generation_config = genai.types.GenerationConfig(
                temperature=temp,
            )
            response = self.model.generate_content(
                prompt, generation_config=generation_config
            )

            # Check for empty or blocked responses
            if not response.candidates or not response.candidates[0].content.parts:
                block_reason = "Unknown"
                if response.prompt_feedback:
                    block_reason = response.prompt_feedback.block_reason.name
                raise Exception(
                    f"Request was blocked or returned no content. Reason: {block_reason}"
                )

            return response.text

        except self.RETRYABLE_EXCEPTIONS as e:
            if LLM_DEBUG:
                logger.debug(f"RETRIABLE ERROR: {e}")
            raise e

        except Exception as e:
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

            # Construct the messages for Claude format
            messages = [{"role": "user", "content": prompt}]

            # Prepare the request body for Claude models
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

            # Extract the text from the response
            if "content" in response_body and len(response_body["content"]) > 0:
                return response_body["content"][0]["text"]
            else:
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
            provider_type = kwargs.get("provider_type", LLM_PROVIDER)

            if provider_type == "gemini":
                self.provider = GeminiProvider(
                    system_prompt=system_prompt,
                    api_key=kwargs.get("api_key"),
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
        # Log the prompt if debug mode is enabled
        if LLM_DEBUG:
            logger.debug("=" * 80)
            logger.debug(f"LLM PROMPT ({self.provider.get_provider_name()}):")
            logger.debug("-" * 80)
            logger.debug(
                f"SYSTEM: {self.system_prompt[:200]}..."
                if len(self.system_prompt) > 200
                else f"SYSTEM: {self.system_prompt}"
            )
            logger.debug("-" * 80)
            logger.debug(f"USER PROMPT:\n{prompt}")
            if temperature is not None:
                logger.debug(f"TEMPERATURE: {temperature}")
            logger.debug("-" * 80)

        # Time the LLM request
        start_time = time.perf_counter()
        response_text = self.provider.generate(prompt, temperature=temperature)
        end_time = time.perf_counter()

        # Calculate duration in milliseconds
        duration_ms = (end_time - start_time) * 1000

        # Log the response time
        print(
            f"[{self.provider.get_provider_name()}] Response time: {duration_ms:.2f}ms"
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


# --- Example Usage ---
if __name__ == "__main__":
    provider = LLM_PROVIDER
    print(f"Running LLM module example (using {provider})...")

    # Example configurations for each provider:
    #
    # For Gemini:
    # export LLM_PROVIDER="gemini"
    # export GOOGLE_API_KEY="your-api-key"
    # export GEMINI_MODEL_NAME="gemini-2.5-flash"
    #
    # For Ollama:
    # export LLM_PROVIDER="ollama"
    # export OLLAMA_BASE_URL="http://localhost:11434"
    # export OLLAMA_MODEL_NAME="qwen3:8b"
    #
    # For Bedrock:
    # export LLM_PROVIDER="bedrock"
    # export BEDROCK_MODEL_ID="us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    # export AWS_PROFILE="rai"
    # export AWS_REGION="us-east-1"

    try:
        translator_module = create_llm_module(
            system_prompt="You are a helpful assistant that translates English to French. "
            "Only provide the French translation and nothing else."
        )

        french_translation = translator_module.get_response(
            prompt="Hello, how are you?"
        )
        print(f"English: Hello, how are you?")
        print(f"French: {french_translation}")

        poet_module = create_llm_module(
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
