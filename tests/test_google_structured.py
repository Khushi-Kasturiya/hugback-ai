"""Actual SDK wire contracts with synthetic data; no network or Google charges."""

import json
import unittest
from typing import Literal
from unittest.mock import patch

import httpx
from google import genai
from google.auth.credentials import AnonymousCredentials
from google.genai import errors
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.config import settings
from app.google_structured import response_json_schema
from app.memory.followup_extractor import GoogleFollowupExtractor
from app.memory.followups import CallPlan, ObservationBatch
from app.memory.models import TranscriptTurn
from app.workflows.contracts import ConversationPlan, CritiqueReport
from app.workflows.provider import GoogleStructuredProvider


def assert_json_contract(test, generation):
    """Check the documented generateContent JSON Schema subset, not model quality."""
    test.assertEqual(generation["responseMimeType"], "application/json")
    test.assertNotIn("responseSchema", generation)
    allowed = {
        "$id", "$defs", "$ref", "$anchor", "type", "format", "title", "description",
        "enum", "items", "prefixItems", "minItems", "maxItems", "minimum", "maximum",
        "anyOf", "oneOf", "properties", "additionalProperties", "required", "propertyOrdering",
    }

    def check(node):
        test.assertFalse(set(node) - allowed)
        if "type" in node:
            test.assertIn(node["type"], {"object", "array", "string", "integer", "number", "boolean", "null"})
        for key in ("properties", "$defs"):
            for child in node.get(key, {}).values():
                check(child)
        for key in ("items", "additionalProperties"):
            if isinstance(node.get(key), dict):
                check(node[key])
        for key in ("anyOf", "oneOf", "prefixItems"):
            for child in node.get(key, []):
                check(child)

    check(generation["responseJsonSchema"])
    test.assertFalse(generation["responseJsonSchema"]["additionalProperties"])


class GoogleStructuredTests(unittest.IsolatedAsyncioTestCase):
    def client(self, respond, *, vertex=False):
        options = {
            "api_version": "v1" if vertex else "v1beta",
            "retry_options": {"attempts": 1},
            "async_client_args": {"transport": httpx.MockTransport(respond)},
        }
        if vertex:
            credentials = AnonymousCredentials()
            credentials.token = "synthetic-offline-token"
            return genai.Client(
                vertexai=True, project="demo-synthetic", location="us-central1",
                credentials=credentials, http_options=options,
            )
        return genai.Client(api_key="synthetic-offline-key", vertexai=False, http_options=options)

    async def invoke(self, schema):
        if schema is ObservationBatch:
            return await GoogleFollowupExtractor().extract(
                [TranscriptTurn(role="user", turn_index=0, text="I have fever today.")],
                CallPlan(session_id="synthetic", generation=1, consent=True, time_zone="UTC"),
            )
        return await GoogleStructuredProvider().generate("Synthetic instruction", {"synthetic": True}, schema)

    async def test_all_three_proposals_use_json_schema_on_both_endpoints(self):
        cases = [
            (ObservationBatch, {"observations": [{
                "topic": "fever", "action": "open", "source_turn": 0, "evidence": "I have fever today.",
            }]}),
            (ConversationPlan, {"language": "en", "background_refs": [0]}),
            (CritiqueReport, {"findings": [], "uncertain": False}),
        ]
        for vertex in (False, True):
            for schema, output in cases:
                with self.subTest(vertex=vertex, schema=schema.__name__):
                    requests = []

                    def respond(request):
                        body = json.loads(request.content)
                        requests.append(body)
                        assert_json_contract(self, body["generationConfig"])
                        self.assertNotIn("tools", body)
                        return httpx.Response(200, json={"candidates": [{
                            "content": {"role": "model", "parts": [{"text": json.dumps(output)}]},
                            "finishReason": "STOP",
                        }]})

                    client = self.client(respond, vertex=vertex)
                    with (
                        patch.multiple(settings, FOLLOWUPS_ENABLED=True,
                                       GEMINI_API_KEY=None if vertex else "synthetic-offline-key"),
                        patch("app.memory.followup_extractor.genai.Client", return_value=client),
                    ):
                        result = await self.invoke(schema)
                    self.assertEqual(result, schema.model_validate(output))
                    self.assertEqual(len(requests), 1)
                    self.assertEqual(requests[0]["generationConfig"]["responseJsonSchema"],
                                     response_json_schema(schema))

    async def test_invalid_proposals_still_fail_local_validation(self):
        observation = {"topic": "fever", "action": "open", "source_turn": 0, "evidence": "I have fever today."}
        cases = [
            (ObservationBatch, {"observations": [observation | {"unexpected": True}]}),
            (ObservationBatch, {"observations": [observation | {"evidence": ""}]}),
            (ObservationBatch, {"observations": [observation | {"evidence": "x" * 501}]}),
            (ObservationBatch, {"observations": [observation | {"subject": "someone_else"}]}),
            (ObservationBatch, {"observations": [observation | {"source_turn": -1}]}),
            (ObservationBatch, {"observations": [observation] * 21}),
            (ConversationPlan, {"background_refs": [0, 1, 2]}),
            (ConversationPlan, {"owner_id": "not-model-authority"}),
            (CritiqueReport, {"findings": [{"code": "impersonation", "severity": "warning",
                                           "source_turn": 1, "evidence": "x" * 201}]}),
        ]
        for index, (schema, output) in enumerate(cases):
            with self.subTest(schema=schema.__name__, case=index):
                def respond(request):
                    return httpx.Response(200, json={"candidates": [{
                        "content": {"role": "model", "parts": [{"text": json.dumps(output)}]},
                    }]})
                client = self.client(respond)
                with (
                    patch.multiple(settings, FOLLOWUPS_ENABLED=True, GEMINI_API_KEY="synthetic-offline-key"),
                    patch("app.memory.followup_extractor.genai.Client", return_value=client),
                    self.assertRaises(ValidationError),
                ):
                    await self.invoke(schema)

    async def test_rejected_request_is_not_retried_or_downgraded(self):
        for schema in (ObservationBatch, ConversationPlan, CritiqueReport):
            with self.subTest(schema=schema.__name__):
                requests = []
                def respond(request):
                    requests.append(json.loads(request.content))
                    return httpx.Response(400, json={"error": {
                        "code": 400, "status": "INVALID_ARGUMENT", "message": "Synthetic rejection",
                    }})
                client = self.client(respond)
                with (
                    patch.multiple(settings, FOLLOWUPS_ENABLED=True, GEMINI_API_KEY="synthetic-offline-key"),
                    patch("app.memory.followup_extractor.genai.Client", return_value=client),
                    self.assertRaises(errors.APIError),
                ):
                    await self.invoke(schema)
                self.assertEqual(len(requests), 1)
                assert_json_contract(self, requests[0]["generationConfig"])

    def test_normalizer_preserves_property_names_and_local_model(self):
        class Synthetic(BaseModel):
            model_config = ConfigDict(extra="forbid")
            default: str = Field(min_length=1, max_length=5)
            const: Literal["self"] = "self"

        original = Synthetic.model_json_schema()
        wire = response_json_schema(Synthetic)
        self.assertEqual(set(wire["properties"]), {"default", "const"})
        self.assertEqual(wire["properties"]["const"]["enum"], ["self"])
        self.assertNotIn("default", wire["properties"]["const"])
        self.assertNotIn("maxLength", wire["properties"]["default"])
        self.assertEqual(Synthetic.model_json_schema(), original)
        with self.assertRaises(ValidationError):
            Synthetic(default="too long")
