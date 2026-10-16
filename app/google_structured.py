"""JSON Schema transport for bounded Google proposals, not a memory validator."""

from google.genai import types
from pydantic import BaseModel


def response_json_schema(model: type[BaseModel]) -> dict:
    """Keep JSON Schema out of the legacy OpenAPI `responseSchema` message.

    In particular, Pydantic's extra="forbid" emits additionalProperties=False,
    which belongs in responseJsonSchema, not the Developer API's legacy Schema.
    Keep local Pydantic validation: Google supports only a JSON Schema subset.
    """
    schema = model.model_json_schema()

    def normalize(node: dict) -> None:
        # Defaults and string lengths aren't in generateContent's documented
        # JSON Schema subset. Length bounds remain mandatory in local validation.
        for key in ("default", "minLength", "maxLength"):
            node.pop(key, None)
        if "const" in node:
            node["enum"] = [node.pop("const")]
        # Traverse schema nodes only, not arbitrary property names/enum values.
        for key in ("properties", "$defs"):
            for child in node.get(key, {}).values():
                normalize(child)
        for key in ("items", "additionalProperties"):
            if isinstance(node.get(key), dict):
                normalize(node[key])
        for key in ("anyOf", "oneOf", "prefixItems"):
            for child in node.get(key, []):
                normalize(child)

    normalize(schema)
    return schema


def json_response_config(instruction: str, model: type[BaseModel]) -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        system_instruction=instruction,
        response_mime_type="application/json",
        response_json_schema=response_json_schema(model),
        temperature=0,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
