"""Hugback agent definition using Google ADK."""

from google.adk.agents import Agent
from app.config import settings
from app.agent.prompts import HUGBACK_SYSTEM_INSTRUCTION

hugback_agent = Agent(
    name="hugback",
    model=settings.HUGBACK_MODEL,
    instruction=HUGBACK_SYSTEM_INSTRUCTION,
)
