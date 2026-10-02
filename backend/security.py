"""Small, dependency-free request protections for the Flask API."""
import hmac
import os
import time
from collections import defaultdict, deque
from functools import wraps

from flask import jsonify, request

AUTH_REQUIRED = os.getenv("RESQ_REQUIRE_AUTH", "0").lower() in {"1", "true", "yes"}
_WINDOW_SECONDS = 60
_REQUESTS = defaultdict(deque)


def require_role(role):
    """Require a role-specific bearer token when production auth is enabled."""
    expected = os.getenv(f"RESQ_{role.upper()}_TOKEN", "")

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not AUTH_REQUIRED:
                return view(*args, **kwargs)
            supplied = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            if not expected or not hmac.compare_digest(supplied, expected):
                return jsonify({"error": "Valid credentials required"}), 401
            return view(*args, **kwargs)
        return wrapped
    return decorator


def role_from_socket_auth(auth):
    """Return the authenticated operational role for a Socket.IO handshake."""
    if not AUTH_REQUIRED:
        return "development"
    token = (auth or {}).get("token", "") if isinstance(auth, dict) else ""
    for role in ("dispatcher", "responder"):
        expected = os.getenv(f"RESQ_{role.upper()}_TOKEN", "")
        if expected and hmac.compare_digest(str(token), expected):
            return role
    return "civilian"


def has_operator_token():
    """Check a dispatcher or responder bearer token for protected read APIs."""
    if not AUTH_REQUIRED:
        return True
    supplied = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    return any(
        expected and hmac.compare_digest(supplied, expected)
        for expected in (os.getenv("RESQ_DISPATCHER_TOKEN", ""), os.getenv("RESQ_RESPONDER_TOKEN", ""))
    )


def is_rate_limited(limit):
    now = time.monotonic()
    key = f"{request.remote_addr}:{request.path}"
    bucket = _REQUESTS[key]
    while bucket and bucket[0] <= now - _WINDOW_SECONDS:
        bucket.popleft()
    if len(bucket) >= limit:
        return True
    bucket.append(now)
    return False
