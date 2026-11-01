"""Assistant request/reply schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class AssistantAskRequest(BaseModel):
    """One natural-language question from the console."""

    message: str = Field(min_length=1, max_length=500)


class AssistantFact(BaseModel):
    """A single measured figure that backs the reply."""

    label: str
    value: str


class AssistantLink(BaseModel):
    """A deep link into the page that shows the same data."""

    label: str
    href: str


class AssistantReply(BaseModel):
    """A grounded answer: prose plus the figures it was built from."""

    intent: str
    answer: str
    facts: list[AssistantFact]
    suggestions: list[str]
    links: list[AssistantLink]
    generated_at: datetime
