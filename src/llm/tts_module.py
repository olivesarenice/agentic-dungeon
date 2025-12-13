"""
Text-to-Speech module using ElevenLabs API.
"""

import os
from io import BytesIO
from typing import Optional

from elevenlabs.client import ElevenLabs


class TTSModule:
    """
    Text-to-Speech module for generating voiceover narrations.
    Uses ElevenLabs API for high-quality voice synthesis.
    """

    def __init__(self):
        """Initialize ElevenLabs TTS client."""
        api_key = os.getenv("ELEVENLABS_API_KEY")
        if not api_key:
            raise ValueError("ELEVENLABS_API_KEY not found in environment")

        self.client = ElevenLabs(api_key=api_key)

        # Voice configuration from environment
        self.voice_id = os.getenv(
            "ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB"
        )  # Default: Adam
        self.model_id = os.getenv(
            "ELEVENLABS_MODEL_ID", "eleven_turbo_v2_5"
        )  # Fast model

    def generate_speech(self, text: str, voice_id: Optional[str] = None) -> bytes:
        """
        Generate speech audio from text.

        Args:
            text: The narration text to convert to speech
            voice_id: Optional voice override

        Returns:
            MP3 audio data as bytes
        """
        voice = voice_id or self.voice_id

        # Generate audio using ElevenLabs
        audio_generator = self.client.text_to_speech.convert(
            text=text,
            voice_id=voice,
            model_id=self.model_id,
            output_format="mp3_44100_128",
        )

        # Collect all audio chunks into bytes
        audio_bytes = b"".join(audio_generator)

        return audio_bytes

    def generate_speech_stream(
        self, text: str, voice_id: Optional[str] = None
    ) -> BytesIO:
        """
        Generate speech audio as a BytesIO stream.

        Args:
            text: The narration text to convert to speech
            voice_id: Optional voice override

        Returns:
            BytesIO stream containing MP3 audio data
        """
        audio_data = self.generate_speech(text, voice_id)
        return BytesIO(audio_data)

    def save_to_file(
        self, text: str, filename: str, voice_id: Optional[str] = None
    ) -> str:
        """
        Generate speech and save to an MP3 file.

        Args:
            text: The narration text to convert to speech
            filename: Output filename (will add .mp3 if not present)
            voice_id: Optional voice override

        Returns:
            Path to the saved file
        """
        if not filename.endswith(".mp3"):
            filename += ".mp3"

        audio_data = self.generate_speech(text, voice_id)

        # Write MP3 file
        with open(filename, "wb") as f:
            f.write(audio_data)

        return filename


def create_tts_module() -> TTSModule:
    """
    Create and return a TTS module instance.
    """
    return TTSModule()
