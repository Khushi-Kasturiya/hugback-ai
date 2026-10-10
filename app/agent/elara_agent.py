"""Elara agent definition using Google ADK."""

from google.adk.agents import Agent
from app.config import settings
from app.agent.prompts import ELARA_SYSTEM_INSTRUCTION

elara_agent = Agent(
    name="elara",
    model=settings.ELARA_MODEL,
    instruction=ELARA_SYSTEM_INSTRUCTION,
)
