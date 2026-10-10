"""Gemini Multimodal Live API session manager using official google-genai SDK."""

import base64
import json
import logging
from google import genai
from google.genai import types

from app.config import settings
from app.agent.prompts import ELARA_SYSTEM_INSTRUCTION

logger = logging.getLogger("elara.live_session")


def create_genai_client() -> genai.Client:
    """Create a google-genai Client supporting either API Key or Vertex AI ADC."""
    if settings.GEMINI_API_KEY:
        logger.info("Initializing Google GenAI Client using GEMINI_API_KEY")
        return genai.Client(
            api_key=settings.GEMINI_API_KEY,
            http_options={"api_version": "v1alpha"},
        )

    logger.info(
        f"Initializing Google GenAI Client using Vertex AI (project={settings.GOOGLE_CLOUD_PROJECT}, location={settings.GOOGLE_CLOUD_LOCATION})"
    )
    return genai.Client(
        vertexai=True,
        project=settings.GOOGLE_CLOUD_PROJECT,
        location=settings.GOOGLE_CLOUD_LOCATION,
        http_options={"api_version": "v1alpha"},
    )


def create_live_config() -> types.LiveConnectConfig:
    """Construct LiveConnectConfig for native bidirectional audio conversation."""
    return types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name=settings.ELARA_VOICE_NAME
                )
            )
        ),
        system_instruction=types.Content(
            parts=[types.Part.from_text(text=ELARA_SYSTEM_INSTRUCTION)]
        ),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(
                disabled=False,
                end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_LOW,
                silence_duration_ms=800,
            )
        ),
    )
