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

load_dotenv()


class Text2ImageGenerator:
    """Generator for creating images from text prompts using Google Gemini."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        output_dir: str = "generated_images",
    ):
        """
        Initialize the text-to-image generator.

        Args:
            api_key: Google API key (uses GOOGLE_API_KEY env var if not provided)
            model_name: Model to use for image generation (default: gemini-2.5-flash-image or from .env)
            output_dir: Directory to save generated images
        """
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "API key not provided and GOOGLE_API_KEY environment variable not set."
            )

        self.model_name = model_name or os.environ.get(
            "IMAGE_MODEL_NAME", "gemini-2.5-flash-image"
        )
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Initialize Google genai client
        self.client = genai.Client(api_key=self.api_key)

        print(f"Text2Image generator initialized with model: {self.model_name}")

    def generate_image(
        self,
        prompt: str,
        output_filename: str,
        aspect_ratio: str = "16:9",
        image_size: str = "2K",
        reference_images: Optional[list[str]] = None,
        max_retries: int = 3,
    ) -> str:
        """
        Generate an image from a text prompt and save it to a file.

        Args:
            prompt: Text prompt for image generation
            output_filename: Name of the output file (without extension)
            aspect_ratio: Aspect ratio for the image (e.g., "16:9", "1:1", "9:16", "5:4", "4:3", "3:2", "2:3", "3:4", "4:5", "9:16", "21:9")
            image_size: Size of the image ("1K", "2K", or "4K")
            reference_images: Optional list of image file paths to use as reference (only supported for pro models)
            max_retries: Maximum number of retry attempts (default: 3)

        Returns:
            Absolute path to the saved image file

        Raises:
            Exception: If image generation fails after all retries
        """
        import time

        from PIL import Image

        last_error = None

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    wait_time = 2**attempt  # Exponential backoff: 2, 4, 8 seconds
                    print(
                        f"Retry attempt {attempt + 1}/{max_retries} after {wait_time}s..."
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
                return absolute_path

            except Exception as e:
                last_error = e
                print(f"Error on attempt {attempt + 1}/{max_retries}: {e}")
                if attempt == max_retries - 1:
                    # Last attempt failed
                    print(f"All {max_retries} attempts failed")
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
            base_prompt = f"""You are an artist for a D&D game.

You draw scenes in the style of: {art_style}

--- Room Scene Update ---
Room: {room_name}
Updated description: {room_description}

{player_info}

PERSPECTIVE: First-person POV from the center of the room, looking out at the scene. The viewer is standing in the middle of the room with a wide field of view capturing the entire space.

IMPORTANT: Use the reference image provided to maintain visual consistency. Keep the same overall composition, lighting, and architectural elements, but update the scene to reflect the new description. The room should feel like the same location, just with modifications based on the updated description."""
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
        generator = create_text2img_generator()

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
