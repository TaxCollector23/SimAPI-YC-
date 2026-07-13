"""
SimAPI — Consistent error contract.

Every error the API returns follows a single JSON envelope so that SDKs and
clients can branch on a stable, machine-readable ``code`` rather than parsing
free-text messages:

    {
      "error": {
        "code": "validation_failed",
        "message": "Human-readable summary.",
        "details": {...},          # optional, structured
        "request_id": "3f9c..."    # correlates with server logs
      }
    }
"""
from __future__ import annotations

from typing import Any


class ErrorCode:
    """Stable, documented error codes. Additive only — never repurpose a code."""

    BAD_REQUEST = "bad_request"
    VALIDATION_FAILED = "validation_failed"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    PAYLOAD_TOO_LARGE = "payload_too_large"
    RATE_LIMITED = "rate_limited"
    UNSUPPORTED_FORMAT = "unsupported_format"
    INTERNAL = "internal_error"


class SimAPIError(Exception):
    """Base class for errors that map cleanly onto the HTTP error contract."""

    status_code: int = 400
    code: str = ErrorCode.BAD_REQUEST

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.details = details or {}


class BadRequestError(SimAPIError):
    status_code = 400
    code = ErrorCode.BAD_REQUEST


class UnauthorizedError(SimAPIError):
    status_code = 401
    code = ErrorCode.UNAUTHORIZED


class NotFoundError(SimAPIError):
    status_code = 404
    code = ErrorCode.NOT_FOUND


class PayloadTooLargeError(SimAPIError):
    status_code = 413
    code = ErrorCode.PAYLOAD_TOO_LARGE


class RateLimitedError(SimAPIError):
    status_code = 429
    code = ErrorCode.RATE_LIMITED


def error_body(
    code: str,
    message: str,
    *,
    request_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the canonical error envelope."""
    body: dict[str, Any] = {"code": code, "message": message}
    if details:
        body["details"] = details
    if request_id:
        body["request_id"] = request_id
    return {"error": body}
