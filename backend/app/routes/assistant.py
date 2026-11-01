"""Console assistant endpoint (grounded, read-only).

See ``app.assistant`` for the routing engine: it answers from the caller's
own rows, not from a language model, so the console cannot be told a fact
that is not in the account.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.assistant import answer_question
from app.config import get_settings
from app.database import get_db
from app.exceptions import RateLimitedError
from app.models.user import User
from app.rate_limiter import is_rate_limited
from app.schemas.assistant import AssistantAskRequest, AssistantReply
from app.security import get_current_user

router = APIRouter(prefix="/assistant", tags=["Assistant"])


@router.post("/ask", response_model=AssistantReply)
def ask_assistant(
    request: AssistantAskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Answer one question from the caller's own account data.

    Read-only on purpose: no jobs are launched and no rows change. The
    throttle is per account rather than per IP so it holds with several
    workers behind a proxy that hides the client address.
    """
    limit = get_settings().ASSISTANT_RATE_LIMIT_PER_MINUTE
    if is_rate_limited(f"assistant:{current_user.id}", limit=limit, window_seconds=60):
        raise RateLimitedError(
            "Too many assistant questions in a minute. Give it a moment.",
            details={"limit": limit, "window_seconds": 60},
        )
    return answer_question(db, current_user, request.message)
