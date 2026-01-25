"""
Text-to-Speech module using ElevenLabs API.
"""

import os
import time
from io import BytesIO
from typing import Optional

from elevenlabs.client import ElevenLabs

from llm.request_logger import LLMRequestLogger, detect_error_status

# Global list to store pending TTS logs
_pending_tts_logs = []


def get_pending_tts_logs():
    """Get all pending TTS log entries and clear the list."""
    global _pending_tts_logs
    logs = _pending_tts_logs.copy()
    _pending_tts_logs = []
    return logs


def add_pending_tts_log(log_entry):
    """Add a log entry to the pending list."""
    global _pending_tts_logs
    _pending_tts_logs.append(log_entry)


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

    def generate_speech(
        self, text: str, voice_id: Optional[str] = None, speed: float = 1.0
    ) -> bytes:
        """
        Generate speech audio from text.

        Args:
            text: The narration text to convert to speech
            voice_id: Optional voice override
            speed: Speech speed multiplier (0.5 to 2.0, default 1.0)
                   1.0 = normal speed, 1.3 = 30% faster

        Returns:
            MP3 audio data as bytes
        """
        voice = voice_id or self.voice_id

        # Clamp speed to valid range
        speed = max(0.5, min(2.0, speed))

        start_time = time.time()
        audio_bytes = None
        error_msg = None
        status = 200

        # Generate audio using ElevenLabs with voice settings
        # Note: ElevenLabs API may not support speed directly in all versions
        # If speed parameter is not supported, it will be ignored gracefully
        try:
            try:
                audio_generator = self.client.text_to_speech.convert(
                    text=text,
                    voice_id=voice,
                    model_id=self.model_id,
                    output_format="mp3_44100_128",
                    voice_settings={
                        "stability": 0.5,
                        "similarity_boost": 0.75,
                        "speed": speed,
                    },
                )
            except Exception as e:
                # Fallback without speed parameter if not supported
                print(f"[TTS] Speed parameter not supported, using default: {e}")
                audio_generator = self.client.text_to_speech.convert(
                    text=text,
                    voice_id=voice,
                    model_id=self.model_id,
                    output_format="mp3_44100_128",
                )

            # Collect all audio chunks into bytes
            audio_bytes = b"".join(audio_generator)

        except Exception as e:
            error_msg = str(e)
            status = detect_error_status(e)
            raise
        finally:
            end_time = time.time()
            latency_ms = int((end_time - start_time) * 1000)

            # Log the TTS request
            log_entry = LLMRequestLogger.create_log_entry(
                function_call="tts_generate",
                provider="elevenlabs",
                model_id=self.model_id,
                prompt=text[:2000],  # Store the text being converted
                status=status,
                response=f"audio_bytes:{len(audio_bytes) if audio_bytes else 0}",
                retry_count=0,
                latency_ms=latency_ms,
                error_message=error_msg,
            )
            add_pending_tts_log(log_entry)

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
        self,
        text: str,
        filename: str,
        voice_id: Optional[str] = None,
        speed: float = 1.0,
    ) -> str:
        """
        Generate speech and save to an MP3 file.

        Args:
            text: The narration text to convert to speech
            filename: Output filename (will add .mp3 if not present)
            voice_id: Optional voice override
            speed: Speech speed multiplier (0.5 to 2.0, default 1.0)

        Returns:
            Path to the saved file
        """
        if not filename.endswith(".mp3"):
            filename += ".mp3"

        audio_data = self.generate_speech(text, voice_id, speed)

        # Write MP3 file
        with open(filename, "wb") as f:
            f.write(audio_data)

        # Update the most recent log entry with the file path
        global _pending_tts_logs
        if _pending_tts_logs:
            _pending_tts_logs[-1].response = filename

        return filename


def create_tts_module() -> TTSModule:
    """
    Create and return a TTS module instance.
    """
    return TTSModule()
