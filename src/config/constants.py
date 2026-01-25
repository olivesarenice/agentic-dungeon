"""
Constants and configuration values for the game.
Centralizes magic numbers and configuration parameters.
"""


class GameConstants:
    """Game-related constants."""

    # Room generation
    MAX_ROOM_PATHS = 3
    DEFAULT_DESCRIPTION_WORDS = (
        40  # Reduced from 100 for concise D&D-style descriptions
    )

    # CLI rendering
    CLI_CELL_HEIGHT = 5
    CLI_CELL_WIDTH = 9

    # Player limits
    MAX_PLAYERS = 10
    MAX_ACTION_DETAIL_LENGTH = 200
    N_NPCS = 1
    N_HUMANS = 0

    # NPC behavior
    NPC_MOVE_PROBABILITY = 0.2  # 0.0 = never move, 1.0 = always move (vs TALK/INTERACT)

    # Memory limits
    MAX_MEMORY_EVENTS = 50
    MAX_INTERACTION_HISTORY = 20


class LLMConstants:
    """LLM-related constants."""

    # Response limits
    MIN_RESPONSE_WORDS = 1
    MAX_RESPONSE_WORDS = 1000
    DEFAULT_DESCRIPTION_WORDS = 20

    # Retry settings
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0


class ImageGenerationConstants:
    """Image generation constants."""

    # Enable/disable image generation
    ENABLED = True

    # Enable LLM-based prompt optimization for Flash models
    # When True, uses a fast LLM to convert structured prompts to dense narrative format
    # When False, uses traditional structured prompts for all models
    USE_PROMPT_OPTIMIZATION = True

    # Art style presets for room scenes
    ART_STYLES = {
        "retro_anime": """Retro 90s anime style screenshot. Hand-painted background textures with visible brushstrokes, distinct high-contrast white highlights, VHS film grain effect, slight color bleeding, muted color palette with occasional vibrant accents. The style should evoke nostalgia for classic anime like Cowboy Bebop and Samurai Champloo. 4:3 aspect ratio aesthetic.""",
        "pixel_art": """detailed 16-bit isometric pixel art aesthetic, reminiscent of classic 1990s console RPGs. The style features a rich, naturalistic color palette. Texturing relies heavily on extensive dithering techniques to create gradients, complex shadows, and weathered surfaces. The lighting is dramatic and moody, characterized by strong directional light sources, distinct highlights, and pixelated particle effects for atmosphere. Pixel edges are sharp and defined, without anti-aliasing.""",
        "photorealistic": """Cinematic photorealistic still with film camera aesthetics. 35mm lens equivalent, f/2.8 aperture for shallow depth of field. Dramatic three-point lighting: harsh key light creating strong shadows, soft fill light to reduce contrast, subtle rim/back light for depth. Include environmental details like atmospheric haze, light rays, floating dust particles. Teal and orange color grade, slightly desaturated for cinematic tension. 4K resolution quality, 2.39:1 cinematic framing.""",
        "low_poly": """Stylized Flat-Shaded Low Poly. The scene is rendered with sharp, angular geometric planes that look like folded paper or cut crystal. No pixel textures or noise—only solid, flat colors used to define depth. Objects blocky with sharp edges. The lighting is soft and atmospheric, using pastel gradients rather than harsh black shadows. The aesthetic is clean, serene, and minimalist, resembling high-quality indie game concept art.""",
        # "high_fantasy": """Vintage Dark Fantasy Etching. Intricate black ink line work onSleepywood  aged, off-white paper. Style mimicking 19th-century engravings (Gustave Doré style). Heavy use of cross-hatching to create deep shadows and volume. Monochromatic, gritty, and macabre.""",
    }

    # Current selected style (change this to switch styles)
    # Options: "retro_anime", "pixel_art", "photorealistic", "low_poly"
    SELECTED_STYLE = "retro_anime"

    @classmethod
    def get_art_style(cls) -> str:
        """Get the currently selected art style prompt."""
        return cls.ART_STYLES.get(cls.SELECTED_STYLE, cls.ART_STYLES["retro_anime"])

    # Convenience property to maintain backward compatibility
    DEFAULT_ART_STYLE = ART_STYLES["retro_anime"]

    # Image configuration
    ASPECT_RATIO = "16:9"
    IMAGE_SIZE = "2K"

    # Output directory for generated images
    OUTPUT_DIR = "generated_images"


class TTSConstants:
    """Text-to-Speech (TTS) generation constants."""

    # Enable/disable TTS generation (ElevenLabs)
    ENABLED = True  # Set to True to enable voice narration

    # Output directory for generated audio files
    OUTPUT_DIR = "generated_narrations"
