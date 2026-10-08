from __future__ import annotations

import hmac
import os
from functools import wraps
from typing import Callable, TypeVar
from flask import Response, request

F = TypeVar("F", bound=Callable)


def auth_enabled() -> bool:
    return bool(os.environ.get("PI_CAMERA_PASSWORD"))


def check_auth(user: str, password: str) -> bool:
    expected_user = os.environ.get("PI_CAMERA_USER", "admin")
    expected_password = os.environ.get("PI_CAMERA_PASSWORD", "")
    return hmac.compare_digest(user, expected_user) and hmac.compare_digest(password, expected_password)


def require_auth(fn: F) -> F:
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not auth_enabled():
            return fn(*args, **kwargs)
        auth = request.authorization
        if not auth or not check_auth(auth.username or "", auth.password or ""):
            return Response("Authentication required", 401, {"WWW-Authenticate": "Basic realm=pi-camera"})
        return fn(*args, **kwargs)

    return wrapper  # type: ignore[return-value]
