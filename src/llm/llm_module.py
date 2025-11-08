import json
import os
import time

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

# Configuration for Gemini
GEMINI_MODEL_NAME = os.environ.get("GEMINI_MODEL_NAME", "gemini-2.5-flash")
GEMINI_RETRYABLE_EXCEPTIONS = (
    google_exceptions.ResourceExhausted,  # 429 Too Many Requests
    google_exceptions.DeadlineExceeded,  # 504 Timeout
    google_exceptions.InternalServerError,  # 500 Internal Server Error
    google_exceptions.ServiceUnavailable,  # 503 Service Unavailable
)

# Configuration for Ollama
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL_NAME = os.environ.get("OLLAMA_MODEL_NAME", "qwen3:8b")

# Determine the LLM provider
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "gemini").lower()


class LLMModule:
    """
    A reusable module for interacting with various LLMs (Gemini, Ollama)
    configured with a specific system prompt.

    This module handles API calls and automatic retries for Gemini.
    """

    def __init__(self, system_prompt: str, api_key: str = ""):
        """
        Initializes the LLM module with a system prompt.

        Args:
            system_prompt: The system-level instruction for the model.
            api_key: The API key. If empty, it attempts to use the
                     'GOOGLE_API_KEY' environment variable.
        """
        self.system_prompt = system_prompt
        self.provider = LLM_PROVIDER

        if self.provider == "gemini":
            # Use provided api_key or fall back to environment variable
            self.api_key = api_key if api_key else os.environ.get("GOOGLE_API_KEY")

            if not self.api_key:
                raise ValueError(
                    "API key not provided and GOOGLE_API_KEY environment variable not set."
                )

            genai.configure(api_key=self.api_key)

            self.model = genai.GenerativeModel(
                model_name=GEMINI_MODEL_NAME,
                system_instruction=self.system_prompt,
            )
        elif self.provider == "ollama":
            self.ollama_url = OLLAMA_BASE_URL
            self.ollama_model = OLLAMA_MODEL_NAME
            print(f"Using Ollama at {self.ollama_url} with model {self.ollama_model}")
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

    # Use tenacity to handle retries
    @retry(
        # Retry only on the specific exceptions we defined
        retry=retry_if_exception_type(GEMINI_RETRYABLE_EXCEPTIONS),
        # Stop after 5 attempts total
        stop=stop_after_attempt(5),
        # Use exponential backoff, starting at 1s, maxing at 60s
        wait=wait_exponential(multiplier=1, min=1, max=20),
        # Print a message before retrying
        before_sleep=lambda retry_state: print(
            f"Retriable error: {retry_state.outcome.exception()}. "
            f"Retrying in {retry_state.next_action.sleep}s... "
            f"(Attempt {retry_state.attempt_number})"
        ),
    )
    def get_response(self, prompt: str) -> str:
        """
        Gets a response from the LLM based on the user prompt.

        This method does not maintain conversation history. It handles
        retries with exponential backoff for common transient errors.

        Args:
            prompt: The user's prompt.

        Returns:
            The text response from the LLM.

        Raises:
            Exception: If the API call fails after all retries or if a
                       non-retriable error occurs.
        """
        if self.provider == "gemini":
            try:
                # Generate content using the provided prompt
                response = self.model.generate_content(prompt)

                # Check for empty or blocked responses
                if not response.candidates or not response.candidates[0].content.parts:
                    block_reason = "Unknown"
                    if response.prompt_feedback:
                        block_reason = response.prompt_feedback.block_reason.name
                    # This is a non-retriable error (e.g., safety block)
                    raise Exception(
                        f"Request was blocked or returned no content. Reason: {block_reason}"
                    )

                # Successfully got a response
                return response.text

            except GEMINI_RETRYABLE_EXCEPTIONS as e:
                # Re-raise the retriable exceptions so tenacity can catch them
                raise e

            except Exception as e:
                # Non-retriable errors (e.g., auth, bad request, or our block reason)
                raise Exception(f"A non-retriable error occurred: {e}")
        elif self.provider == "ollama":
            try:
                headers = {"Content-Type": "application/json"}
                data = {
                    "model": self.ollama_model,
                    "prompt": f"{self.system_prompt}\n{prompt}",
                    "stream": False,
                    "think": False,
                }
                response = requests.post(
                    f"{self.ollama_url}/api/generate",
                    headers=headers,
                    data=json.dumps(data),
                )
                response.raise_for_status()  # Raise an exception for HTTP errors
                return response.json()["response"]
            except requests.exceptions.RequestException as e:
                raise Exception(f"Ollama API call failed: {e}")
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

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


def create_llm_module(system_prompt: str, provider: str = LLM_PROVIDER) -> LLMModule:
    """
    Factory function to create a new LLMModule instance.

    Args:
        system_prompt: The system-level instruction for the model.
        provider: The LLM provider to use ("gemini" or "ollama").

    Returns:
        An instance of the LLMModule class.
    """
    # The LLMModule constructor will handle API key/URL based on the provider
    return LLMModule(system_prompt, api_key=os.environ.get("GOOGLE_API_KEY", ""))


# --- Example Usage ---
if __name__ == "__main__":
    print(f"Running LLM module example (using {LLM_PROVIDER})...")

    # 1. Create a module with a specific persona
    # Set LLM_PROVIDER environment variable to "ollama" to use Ollama
    # export LLM_PROVIDER="ollama"
    # If using Gemini, ensure GOOGLE_API_KEY is set.
    # If using Ollama, ensure Ollama server is running and model is pulled.
    try:
        translator_module = create_llm_module(
            system_prompt="You are a helpful assistant that translates English to French. "
            "Only provide the French translation and nothing else."
        )

        # 2. Get a response
        french_translation = translator_module.get_response(
            prompt="Hello, how are you?"
        )
        print(f"English: Hello, how are you?")
        print(f"French: {french_translation}")

        # 3. Create another, separate module
        poet_module = create_llm_module(
            system_prompt="You are a poet. You respond with a short, 2-line rhyming poem."
        )

        poem = poet_module.get_response(prompt="Write me a poem about a cat.")
        print("\n--- Poet Module ---")
        print(poem)

    except (Exception, ValueError) as e:
        print(f"\nAn error occurred: {e}")
        if LLM_PROVIDER == "gemini":
            print(
                "Please ensure your GOOGLE_API_KEY is set as an environment variable if running locally."
            )
        elif LLM_PROVIDER == "ollama":
            print(
                f"Please ensure your Ollama server is running at {OLLAMA_BASE_URL} "
                f"and the model '{OLLAMA_MODEL_NAME}' is available."
            )
