"""Bounded structured Google calls; explicit caller gating, no paid retry loop."""
import json
from google import genai
from google.genai import types
from app.config import settings
from app.google_structured import json_response_config

class GoogleStructuredProvider:
    async def generate(self, instruction, payload, schema, *, timeout_ms=10_000):
        options = types.HttpOptions(
            api_version="v1beta" if settings.GEMINI_API_KEY else "v1",
            timeout=timeout_ms, retry_options=types.HttpRetryOptions(attempts=1),
        )
        client = (genai.Client(api_key=settings.GEMINI_API_KEY, vertexai=False, http_options=options)
                  if settings.GEMINI_API_KEY else genai.Client(
                      vertexai=True, project=settings.GOOGLE_CLOUD_PROJECT,
                      location=settings.GOOGLE_CLOUD_LOCATION, http_options=options))
        try:
            response = await client.aio.models.generate_content(
                model=settings.FOLLOWUP_EXTRACTION_MODEL,
                contents=json.dumps(payload, ensure_ascii=False),
                config=json_response_config(instruction, schema),
            )
            if not response.text or len(response.text) > 12_000:
                raise ValueError("Missing or oversized structured output")
            return schema.model_validate_json(response.text)
        finally:
            await client.aio.aclose()
            client.close()
