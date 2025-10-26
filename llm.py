import os
import time

import google.generativeai as genai
from dotenv import load_dotenv
from google.api_core import exceptions as google_exceptions
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

load_dotenv()
# Using gemini-2.5-flash-preview-09-2025 as the model
MODEL_NAME = "gemini-2.5-pro"  # "gemini-2.5-flash-preview-09-2025"

# Define which Google API exceptions we want to retry on
RETRYABLE_EXCEPTIONS = (
    google_exceptions.ResourceExhausted,  # 429 Too Many Requests
    google_exceptions.DeadlineExceeded,  # 504 Timeout
    google_exceptions.InternalServerError,  # 500 Internal Server Error
    google_exceptions.ServiceUnavailable,  # 503 Service Unavailable
)


class LLMModule:
    """
    A reusable module for interacting with a Gemini LLM via the
    google.generativeai library, configured with a specific system prompt.

    This module handles API calls and automatic retries.
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

        # Use provided api_key or fall back to environment variable
        self.api_key = api_key if api_key else os.environ.get("GOOGLE_API_KEY")

        if not self.api_key:
            raise ValueError(
                "API key not provided and GOOGLE_API_KEY environment variable not set."
            )

        genai.configure(api_key=self.api_key)

        self.model = genai.GenerativeModel(
            model_name=MODEL_NAME,
            system_instruction=self.system_prompt,
        )

    # Use tenacity to handle retries
    @retry(
        # Retry only on the specific exceptions we defined
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
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
        -            max_retries: The maximum number of retry attempts.

                Returns:
                    The text response from the LLM.

                Raises:
                    Exception: If the API call fails after all retries or if a
                               non-retriable error occurs.
        """

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

        except RETRYABLE_EXCEPTIONS as e:
            # Re-raise the retriable exceptions so tenacity can catch them
            raise e

        except Exception as e:
            # Non-retriable errors (e.g., auth, bad request, or our block reason)
            raise Exception(f"A non-retriable error occurred: {e}")


def create_llm_module(system_prompt: str) -> LLMModule:
    """
    Factory function to create a new LLMModule instance.

    Args:
        system_prompt: The system-level instruction for the model.

    Returns:
        An instance of the LLMModule class.
    """
    # Note: Assumes GOOGLE_API_KEY is set in the environment
    # or an API key will be passed if this module is imported.
    # For this example, we rely on the environment variable.
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    return LLMModule(system_prompt, api_key=api_key)


# --- Example Usage ---
if __name__ == "__main__":
    print("Running LLM module example (using google.generativeai and tenacity)...")

    # 1. Create a module with a specific persona
    # Note: Set GOOGLE_API_KEY environment variable if not running in Canvas
    # export GOOGLE_API_KEY="YOUR_API_KEY_HERE"
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
        print(
            "Please ensure your GOOGLE_API_KEY is set as an environment variable if running locally."
        )
