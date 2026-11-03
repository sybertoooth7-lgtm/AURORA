"""Assistant request/reply schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

AssistantRoleKey = Literal["operator", "agronomist", "analyst", "responder"]


class AssistantAskRequest(BaseModel):
    """One natural-language question from the console.

    ``role`` selects the lens the answer is composed in. It changes framing
    and suggested follow-ups only -- never the underlying figures.
    """

    message: str = Field(min_length=1, max_length=500)
    role: AssistantRoleKey = "operator"


class AssistantFact(BaseModel):
    """A single measured figure that backs the reply."""

    label: str
    value: str


class AssistantLink(BaseModel):
    """A deep link into the page that shows the same data."""

    label: str
    href: str


class AssistantRole(BaseModel):
    """The persona/lens an answer was composed in."""

    key: AssistantRoleKey
    label: str
    focus: str


class AssistantStep(BaseModel):
    """One visible stage of the deterministic pipeline."""

    name: str
    detail: str
    status: Literal["ok", "blocked"] = "ok"


class AssistantReply(BaseModel):
    """A grounded answer: prose plus the figures it was built from."""

    intent: str
    role: AssistantRole
    steps: list[AssistantStep]
    answer: str
    facts: list[AssistantFact]
    suggestions: list[str]
    links: list[AssistantLink]
    generated_at: datetime


class AssistantRoleList(BaseModel):
    """The role lenses the console can assign."""

    roles: list[AssistantRole]
