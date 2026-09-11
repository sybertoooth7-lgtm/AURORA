"""Application error hierarchy with HTTP mapping.

Route handlers and services raise these; a single set of exception handlers
in main.py converts them into consistent, documented JSON responses with an
request-id that ties the error back to the structured logs.
"""



class AuroraError(Exception):
    """Base class for expected, user-facing application errors."""

    status_code = 400
    log_level = "warning"
    code = "aurora_error"

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_response(self) -> dict:
        payload: dict[str, object] = {"detail": self.message, "code": self.code}
        if self.details:
            payload["details"] = self.details
        return payload


class NotFoundError(AuroraError):
    status_code = 404
    code = "not_found"


class ConflictError(AuroraError):
    status_code = 409
    code = "conflict"


class ValidationFailedError(AuroraError):
    status_code = 422
    code = "validation_failed"


class RateLimitedError(AuroraError):
    status_code = 429
    code = "rate_limited"


class SatelliteDataUnavailableError(AuroraError):
    """Raised by the analysis runner when no usable observation is available."""
    status_code = 502
    code = "satellite_data_unavailable"


class PipelineUnavailableError(AuroraError):
    """Raised when no pipeline handles the requested analysis type."""
    status_code = 422
    code = "pipeline_unavailable"


class ModelRegistryError(AuroraError):
    status_code = 422
    code = "model_registry"
