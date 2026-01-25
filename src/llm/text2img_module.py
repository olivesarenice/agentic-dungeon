"""
Text-to-image generation module using Google's Gemini API.
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types

from llm.prompt_optimizer import get_prompt_optimizer
from llm.request_logger import LLMRequestLogger, detect_error_status

load_dotenv()

# Global list to store pending image generation logs
_pending_image_logs = []


def get_pending_image_logs():
    """Get all pending image generation log entries and clear the list."""
    global _pending_image_logs
    logs = _pending_image_logs.copy()
    _pending_image_logs = []
    return logs


def add_pending_image_log(log_entry):
    """Add a log entry to the pending list."""
    global _pending_image_logs
    _pending_image_logs.append(log_entry)


class Text2ImageGenerator:
    """Generator for creating images from text prompts using Google Gemini."""

    def __init__(
        self,
        api_key: str = os.getenv("GEMINI_API_KEY"),
        model_name: str = os.getenv("IMAGE_MODEL_NAME"),
        output_dir: str = "generated_images",
    ):
        """
        Initialize the text-to-image generator.

        Args:
            api_key: Google API key (uses GOOGLE_API_KEY env var if not provided)
            model_name: Model to use for image generation (default: gemini-2.5-flash-image or from .env)
            output_dir: Directory to save generated images
        """
        # self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        # if not self.api_key:
        #     raise ValueError(
        #         "API key not provided and GOOGLE_API_KEY environment variable not set."
        #     )

        self.model_name = model_name or os.environ.get(
            "IMAGE_MODEL_NAME", "gemini-2.5-flash-image"
        )
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Initialize Google genai client
        self.client = genai.Client(
            # api_key=self.api_key,
            vertexai=True,
            location="global",
            http_options={"api_version": "v1"},
        )

        print(f"Text2Image generator initialized with model: {self.model_name}")

    def generate_image(
        self,
        prompt: str,
        output_filename: str,
        aspect_ratio: str = "16:9",
        image_size: str = "2K",
        reference_images: Optional[list[str]] = None,
        max_retries: int = 6,
    ) -> str:
        """
        Generate an image from a text prompt and save it to a file.

        Args:
            prompt: Text prompt for image generation
            output_filename: Name of the output file (without extension)
            aspect_ratio: Aspect ratio for the image (e.g., "16:9", "1:1", "9:16", "5:4", "4:3", "3:2", "2:3", "3:4", "4:5", "9:16", "21:9")
            image_size: Size of the image ("1K", "2K", or "4K")
            reference_images: Optional list of image file paths to use as reference (only supported for pro models)
            max_retries: Maximum number of retry attempts (default: 6)

        Returns:
            Absolute path to the saved image file

        Raises:
            Exception: If image generation fails after all retries
        """
        import random
        import time

        from PIL import Image

        last_error = None

        retry_count = 0
        start_time = time.time()

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    retry_count = attempt
                    # Exponential backoff with jitter for rate limiting
                    # Base: 5, 10, 20, 40, 60, 60 seconds (capped at 60)
                    base_wait = min(5 * (2**attempt), 60)
                    # Add random jitter (0-50% of base wait) to prevent thundering herd
                    jitter = random.uniform(0, base_wait * 0.5)
                    wait_time = base_wait + jitter
                    print(
                        f"Retry attempt {attempt + 1}/{max_retries} after {wait_time:.1f}s (rate limit backoff)..."
                    )
                    time.sleep(wait_time)

                print(f"Generating image with prompt: {prompt[:100]}...")

                # Build contents list
                contents = [prompt]

                # Check if this is a flash or pro model
                is_flash_model = "flash" in self.model_name.lower()
                is_pro_model = "pro" in self.model_name.lower()

                # Handle reference images differently based on model
                if reference_images:
                    if is_flash_model:
                        # Flash model supports only 1 reference image for editing
                        if len(reference_images) > 1:
                            print(
                                f"Warning: Flash model only supports 1 reference image, using first one"
                            )

                        img_path = reference_images[0]
                        if Path(img_path).exists():
                            contents.append(Image.open(img_path))
                            print(f"Using reference image for editing: {img_path}")
                        else:
                            print(f"Warning: Reference image not found: {img_path}")
                    elif is_pro_model:
                        # Pro model supports up to 14 reference images
                        print(
                            f"Using {len(reference_images)} reference image(s) for grounding"
                        )
                        for img_path in reference_images[:14]:
                            if Path(img_path).exists():
                                contents.append(Image.open(img_path))
                            else:
                                print(f"Warning: Reference image not found: {img_path}")

                # Generate content - API differs between flash and pro
                if is_flash_model:
                    # Flash model: simpler API without config
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=contents,
                    )
                elif is_pro_model:
                    # Pro model: supports advanced config
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            response_modalities=["TEXT", "IMAGE"],
                            image_config=types.ImageConfig(
                                aspect_ratio=aspect_ratio,
                                image_size=image_size,
                            ),
                        ),
                    )
                else:
                    # Default to simple API for unknown models
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=contents,
                    )

                # Extract image from response parts
                image_saved = False
                output_path = self.output_dir / f"{output_filename}.png"

                for part in response.parts:
                    if part.text is not None:
                        print(f"Model response text: {part.text}")
                    elif image := part.as_image():
                        image.save(str(output_path))
                        image_saved = True
                        break

                if not image_saved:
                    raise Exception("No image generated in response")

                absolute_path = str(output_path.absolute())
                print(f"Image saved to: {absolute_path}")

                # Log successful image generation
                end_time = time.time()
                log_entry = LLMRequestLogger.create_log_entry(
                    function_call="image_generate",
                    provider="google",
                    model_id=self.model_name,
                    prompt=prompt[:2000],  # Truncate long prompts
                    status=200,
                    response=absolute_path,  # Store file path for media
                    retry_count=retry_count,
                    latency_ms=int((end_time - start_time) * 1000),
                    error_message=None,
                )
                add_pending_image_log(log_entry)

                return absolute_path

            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Check if this is a rate limit error (429)
                is_rate_limit = (
                    "429" in str(e)
                    or "rate" in error_str
                    or "quota" in error_str
                    or "resource_exhausted" in error_str
                )

                if is_rate_limit:
                    print(
                        f"⚠️  Rate limit hit on attempt {attempt + 1}/{max_retries}: {e}"
                    )
                else:
                    print(f"Error on attempt {attempt + 1}/{max_retries}: {e}")

                if attempt == max_retries - 1:
                    # Last attempt failed - log the failure
                    print(f"❌ All {max_retries} attempts failed")

                    end_time = time.time()
                    status = detect_error_status(e)
                    log_entry = LLMRequestLogger.create_log_entry(
                        function_call="image_generate",
                        provider="google",
                        model_id=self.model_name,
                        prompt=prompt[:2000],
                        status=status,
                        response=None,
                        retry_count=retry_count,
                        latency_ms=int((end_time - start_time) * 1000),
                        error_message=str(last_error),
                    )
                    add_pending_image_log(log_entry)

                    raise Exception(
                        f"Image generation failed after {max_retries} attempts: {last_error}"
                    )
                # Continue to next retry

        # Should never reach here, but just in case
        raise Exception(f"Image generation failed: {last_error}")

    def generate_room_scene(
        self,
        room_name: str,
        room_description: str,
        player_info: str,
        art_style: str,
        room_id: str,
        reference_image_path: Optional[str] = None,
        use_optimization: bool = True,
    ) -> str:
        """
        Generate a room scene image for the game.

        Args:
            room_name: Name of the room
            room_description: Description of the room
            player_info: Information about players in the room
            art_style: Art style to use (e.g., "2000s SAMURAI CHAMPLOO, COWBOY BEBOP [nostalgic, 90s anime]")
            room_id: Unique room ID for filename
            reference_image_path: Optional path to existing room image for grounding/consistency
            use_optimization: Whether to use LLM-based prompt optimization (default: True)

        Returns:
            Absolute path to the saved image file
        """
        # Build the base structured prompt (used for Pro models or as fallback)
        if reference_image_path:
            base_prompt = f"""You are an artist for a D&D game. You are EDITING an existing scene.

Art style: {art_style}

--- SCENE EDIT REQUEST ---
Room: {room_name}
Updated description: {room_description}

{player_info}

CRITICAL INSTRUCTIONS FOR EDITING:
1. COPY the reference image's composition, camera angle, and overall layout EXACTLY
2. PRESERVE 90% of the original scene - same walls, floor, major objects, lighting direction
3. ONLY modify the specific element mentioned in the description change
4. The edited image should feel like the SAME location with a SMALL change
5. If the reference shows a door, keep the door in the same place
6. If the reference shows furniture, keep furniture in the same positions
7. Match the color palette and atmosphere of the reference

DO NOT generate a completely new scene. This is a MINOR EDIT to the reference image."""
        else:
            base_prompt = f"""You are an artist for a D&D game.

You draw scenes in the style of: {art_style}

--- Room Scene ---
Room: {room_name}
Room description: {room_description}

{player_info}

PERSPECTIVE: First-person POV from the center of the room, looking out at the scene. The viewer is standing in the middle of the room with a wide field of view capturing the entire space. Maximum scene visibility.

Create a cinematic, atmospheric scene that captures the essence of this room."""

        # Apply model-specific optimization if enabled
        if use_optimization:
            optimizer = get_prompt_optimizer()
            prompt = optimizer.optimize_prompt(
                model_name=self.model_name,
                original_prompt=base_prompt,
                art_style=art_style,
                room_name=room_name,
                room_description=room_description,
                player_info=player_info,
            )
        else:
            prompt = base_prompt

        # Use room_id as the filename
        filename = f"room_{room_id}"

        # Pass reference image if provided
        reference_images = [reference_image_path] if reference_image_path else None

        return self.generate_image(
            prompt=prompt,
            output_filename=filename,
            aspect_ratio="16:9",
            image_size="2K",
            reference_images=reference_images,
        )


def create_text2img_generator(**kwargs) -> Text2ImageGenerator:
    """
    Factory function to create a Text2ImageGenerator instance.

    Args:
        **kwargs: Arguments to pass to Text2ImageGenerator constructor

    Returns:
        An instance of Text2ImageGenerator
    """
    return Text2ImageGenerator(**kwargs)


# --- Example Usage ---
if __name__ == "__main__":
    try:
        generator = create_text2img_generator(api_key=os.getenv("GEMINI_API_KEY"))

        # Test image generation
        test_prompt = "A mystical forest with glowing mushrooms and ancient ruins"
        output_path = generator.generate_image(
            prompt=test_prompt, output_filename="test_image"
        )

        print(f"\nGenerated test image at: {output_path}")

        # Test room scene generation
        room_scene_path = generator.generate_room_scene(
            room_name="The Ancient Library",
            room_description="Towering bookshelves stretch into darkness, filled with dusty tomes. Ethereal light filters through stained glass windows.",
            player_info="Brandon the Shadow Assassin is the only player in this room.",
            art_style="retro 80s anime",
            room_id="ancient-library-test",
        )

        print(f"\nGenerated room scene at: {room_scene_path}")

    except Exception as e:
        print(f"\nError: {e}")
        print("Please ensure your GOOGLE_API_KEY is set as an environment variable.")
