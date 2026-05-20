import hmac


class InternalAuthError(Exception):
    """Raised when X-Internal-Token verification fails."""


def verify_internal_token(token: str, expected: str) -> None:
    """Constant-time comparison to prevent timing attacks.

    Raises InternalAuthError if token does not match expected.
    """
    if not hmac.compare_digest(token, expected):
        raise InternalAuthError("Invalid internal auth token")
