"""Error tracking (Sentry), initialized only when SENTRY_DSN is configured.

Kept separate from app.logging_conf: logging is "what happened" (always
on, structured, goes to stdout for the platform to collect), this is
"someone should be paged about this" (opt-in, needs a Sentry account).
"""

from app.config import get_settings
from app.logging_conf import get_logger

logger = get_logger(__name__)

_initialized = False


def init_error_tracking() -> None:
    """Call once at startup. No-op if SENTRY_DSN isn't set."""
    global _initialized
    if _initialized:
        return

    settings = get_settings()
    if not settings.SENTRY_DSN:
        logger.info("SENTRY_DSN not set -- error tracking disabled")
        return

    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        release=settings.APP_VERSION,
        # Sample a small fraction of normal request traces (performance
        # monitoring), but every error is always captured regardless of
        # this setting -- it doesn't affect error reporting.
        traces_sample_rate=0.1 if settings.ENVIRONMENT == "production" else 1.0,
    )
    _initialized = True
    logger.info("Error tracking initialized", extra_keys={"environment": settings.ENVIRONMENT})


def capture_exception(exc: BaseException) -> None:
    """Report an exception to Sentry if it's configured; always safe to
    call even when it isn't (becomes a no-op)."""
    if not _initialized:
        return
    import sentry_sdk

    sentry_sdk.capture_exception(exc)
