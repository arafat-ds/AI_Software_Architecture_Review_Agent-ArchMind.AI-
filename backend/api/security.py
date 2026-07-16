"""Authentication dependency for ArchMind AI API.

Exposes require_auth — the stable public contract used in router wiring.
Internal implementation (_check_api_key) is private to this module.

Abstraction contract:
  - main.py wires: dependencies=[Depends(require_auth)]
  - Tests bypass:  app.dependency_overrides[require_auth] = lambda: None
  - Routers never import anything from this module directly.

To evolve authentication (JWT, OAuth, RBAC) in a future milestone:
  1. Add the new internal verification function to this module.
  2. Replace Depends(_check_api_key) inside require_auth's signature.
  3. No changes to main.py, routers, or any test that overrides require_auth.
"""

from __future__ import annotations

import hmac

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from config.settings import get_settings
from shared.logging.logger import get_logger

logger = get_logger(__name__)

_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

_AUTH_STATUS_CODE = 401
_AUTH_DETAIL = "Authentication required."
_AUTH_HEADERS: dict[str, str] = {"WWW-Authenticate": 'ApiKey realm="ArchMind AI"'}


async def _check_api_key(
    request: Request,
    api_key_value: str | None = Security(_API_KEY_HEADER),
) -> str:
    """Validate X-API-Key header against the configured key.

    Both missing and invalid keys raise the same HTTPException to avoid
    leaking authentication state to callers. Failure reason is logged
    internally at WARNING level for operator visibility only.

    Uses hmac.compare_digest for timing-safe key comparison.
    """
    settings = get_settings()
    provided = (api_key_value or "").strip()

    if not provided:
        logger.warning(
            "Authentication failed",
            extra={
                "reason": "missing_credentials",
                "path": request.url.path,
                "client_ip": request.client.host if request.client else "unknown",
            },
        )
        raise HTTPException(
            status_code=_AUTH_STATUS_CODE,
            detail=_AUTH_DETAIL,
            headers=_AUTH_HEADERS,
        )

    if not hmac.compare_digest(settings.api_key, provided):
        logger.warning(
            "Authentication failed",
            extra={
                "reason": "invalid_credentials",
                "path": request.url.path,
                "client_ip": request.client.host if request.client else "unknown",
            },
        )
        raise HTTPException(
            status_code=_AUTH_STATUS_CODE,
            detail=_AUTH_DETAIL,
            headers=_AUTH_HEADERS,
        )

    return provided


async def require_auth(_verified: str = Depends(_check_api_key)) -> None:
    """Stable authentication gate for all protected routes.

    This is the sole symbol routers and main.py reference for auth.
    The internal implementation (_check_api_key) is an opaque detail.

    Future auth schemes replace the Depends() in this signature only;
    all router wiring and test overrides remain unchanged.
    """
