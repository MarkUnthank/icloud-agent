class AgentError(Exception):
    """An error with a safe, user-facing message."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def error_result(exc: Exception) -> dict:
    if isinstance(exc, AgentError):
        return {"ok": False, "error": {"code": exc.code, "message": str(exc)}}
    # Protocol libraries can embed message contents, URLs, and credentials in exceptions.
    return {
        "ok": False,
        "error": {
            "code": "operation_failed",
            "message": "Operation failed. Check connectivity and run icloud-agent auth status --check. "
            "If this was a write, read back its state before retrying.",
            "type": type(exc).__name__,
        },
    }
