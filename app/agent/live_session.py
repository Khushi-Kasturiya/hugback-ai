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
            # Be explicit here. The google-genai SDK otherwise lets an inherited
            # GOOGLE_GENAI_USE_VERTEXAI=true override API-key mode. Voice-key
            # provisioning and the Gemini Developer API must use this transport.
            vertexai=False,
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


def create_live_config(
    memory_context: str = "",
    enable_memory_tool: bool = False,
) -> types.LiveConnectConfig:
    """Construct LiveConnectConfig for native bidirectional audio conversation."""
    system_instruction = ELARA_SYSTEM_INSTRUCTION
    if memory_context:
        system_instruction = f"{system_instruction}\n\n{memory_context}"

    tools = None
    if enable_memory_tool:
        tools = [
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name="recall_memory",
                        description=(
                            "Search this user's private long-term memories when a past "
                            "detail would make the current reply more caring or precise. "
                            "Do not call for ordinary small talk or facts already present "
                            "in the trusted user memory section."
                        ),
                        behavior=types.Behavior.NON_BLOCKING,
                        parameters_json_schema={
                            "type": "object",
                            "properties": {
                                "topic": {
                                    "type": "string",
                                    "description": (
                                        "A concise description of the current topic, "
                                        "such as knee pain, daughter's visit, or sleep."
                                    ),
                                }
                            },
                            "required": ["topic"],
                            "additionalProperties": False,
                        },
                    )
                ]
            )
        ]

    print(f"\n==================================================")
    print(f"🎤 [VOICE CONFIG] Using DEFAULT PREBUILT VOICE: {settings.ELARA_VOICE_NAME}")
    print(f"==================================================\n", flush=True)
    logger.info(f"Using DEFAULT PREBUILT VOICE: {settings.ELARA_VOICE_NAME}")
    voice_config = types.VoiceConfig(
        prebuilt_voice_config=types.PrebuiltVoiceConfig(
            voice_name=settings.ELARA_VOICE_NAME
        )
    )


    return types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=voice_config
        ),
        system_instruction=types.Content(
            parts=[types.Part.from_text(text=system_instruction)]
        ),
        tools=tools,
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
