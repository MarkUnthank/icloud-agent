from filelock import Timeout as LockTimeout
from niquests.exceptions import Timeout as RequestTimeout


class AgentError(Exception):
    """An error with a safe, user-facing message."""

    def __init__(self, code: str, message: str, **details):
        super().__init__(message)
        self.code = code
        self.details = details


def error_result(exc: Exception, *, operation: str | None = None, write: bool = False) -> dict:
    context = {"operation": operation} if operation else {}
    if isinstance(exc, LockTimeout):
        error = {
            "code": "operation_busy",
            "message": "Another iCloud Agent operation is running.",
            "stage": "lock",
            "retryable": True,
            "recovery": "Wait for it to finish, then retry this operation.",
            **context,
        }
        if operation:
            error["executed"] = False
        return {"ok": False, "error": error}
    if isinstance(exc, (TimeoutError, RequestTimeout)):
        exc = AgentError("operation_timeout", "The iCloud request timed out.", stage="request")
    if isinstance(exc, AgentError):
        error = {"code": exc.code, "message": str(exc), **exc.details, **context}
        if exc.code == "operation_timeout":
            error["retryable"] = not write
            if write:
                error["recovery"] = (
                    "Read back the affected item before retrying; the write may have completed."
                )
            elif operation == "mail_search" and error.get("stage") in ("search", "fetch_headers"):
                error["recovery"] = (
                    "Narrow the date range or use sender/subject filters, then retry. This failed search does not establish that there are no matches."
                )
            else:
                error["recovery"] = (
                    "Check connectivity, then retry. A timeout does not establish that authentication failed."
                )
        return {"ok": False, "error": error}
    # Protocol libraries can embed message contents, URLs, and credentials in exceptions.
    return {
        "ok": False,
        "error": {
            "code": "operation_failed",
            "message": "Operation failed. Check connectivity and run icloud-agent auth status --check. "
            "If this was a write, read back its state before retrying.",
            "type": type(exc).__name__,
            **context,
        },
    }
