"""Create Hugback's managed semantic Memory Bank and structured care profile.

Run from the backend directory after ADC authentication:
    python scripts/create_memory_bank.py
Then copy the printed resource name to MEMORY_BANK_NAME.
"""

import agentplatform
from pydantic import BaseModel, Field

from app.config import settings


class MemoryBankCareProfile(BaseModel):
    """Flat schema because Agent Platform does not accept JSON Schema $ref/$defs."""

    names_and_relationships: list[str] = Field(
        description=(
            "Names, preferred forms of address, languages, and important people as "
            "concise facts; include only details explicitly shared by the user."
        )
    )
    preferences: list[str] = Field(
        description="Hobbies, foods, activities, and other explicit preferences."
    )
    routines: list[str] = Field(description="Stable daily or weekly routines.")
    concerns_and_status: list[str] = Field(
        description=(
            "User-reported concerns with open/resolved status; never infer diagnoses."
        )
    )
    events_and_followups: list[str] = Field(
        description="Upcoming events, appointments, visits, and follow-up topics."
    )
    communication_preferences: list[str] = Field(
        description="How the user prefers Hugback to communicate and offer support."
    )


def main() -> None:
    client = agentplatform.Client(
        project=settings.GOOGLE_CLOUD_PROJECT,
        location=settings.GOOGLE_CLOUD_LOCATION,
    )
    embedding_model = (
        f"projects/{settings.GOOGLE_CLOUD_PROJECT}/locations/"
        f"{settings.GOOGLE_CLOUD_LOCATION}/publishers/google/models/gemini-embedding-001"
    )
    display_name = "Hugback User Memory"
    existing = next(
        (
            bank
            for bank in client.memory_banks.list()
            if getattr(bank, "display_name", "") == display_name
        ),
        None,
    )

    if existing is not None:
        print(f"MEMORY_BANK_NAME={existing.name}")
        return

    bank = client.memory_banks.create(
        config={"display_name": display_name},
        managed_semantic_memory_config={
            "structured_memory_configs": [
                {
                    "scope_keys": ["user_id"],
                    "schema_configs": [
                        {
                            "id": "hugback-care-profile",
                            "memory_schema": MemoryBankCareProfile.model_json_schema(),
                        }
                    ]
                }
            ],
            "unstructured_memory_configs": [
                {
                    "scope_keys": ["user_id"],
                    "memory_topics": [
                        {
                            "managed_memory_topic": {
                                "managed_topic_enum": "USER_PERSONAL_INFO"
                            }
                        },
                        {
                            "managed_memory_topic": {
                                "managed_topic_enum": "USER_PREFERENCES"
                            }
                        },
                        {
                            "managed_memory_topic": {
                                "managed_topic_enum": "KEY_CONVERSATION_DETAILS"
                            }
                        },
                        {
                            "managed_memory_topic": {
                                "managed_topic_enum": "EXPLICIT_INSTRUCTIONS"
                            }
                        },
                    ],
                    "enable_third_person_memories": True,
                    "consolidation_config": {"revisions_per_candidate_count": 3},
                }
            ],
            "similarity_search_config": {"embedding_model": embedding_model},
            # A repeated fact is reinforced because GenerateMemories updates it
            # and refreshes the TTL. Inactive episodic details naturally decay.
            "ttl_config": {
                "granular_ttl_config": {
                    "generate_created_ttl": f"{365 * 24 * 60 * 60}s",
                    "generate_updated_ttl": f"{2 * 365 * 24 * 60 * 60}s",
                },
                "memory_revision_default_ttl": f"{365 * 24 * 60 * 60}s",
            },
            "disable_memory_revisions": False,
        },
    )
    print(f"MEMORY_BANK_NAME={bank.name}")


if __name__ == "__main__":
    main()
