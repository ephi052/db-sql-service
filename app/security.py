import os
import logging
from ipaddress import ip_address, ip_network

from fastapi import HTTPException, Request, Security
from fastapi.security.api_key import APIKeyHeader

logger = logging.getLogger(__name__)

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def require_api_key(api_key: str = Security(api_key_header)) -> str:
    expected = os.getenv("API_KEY", "CaJx3nOo9sKZfW7Rl5c4T")
    if not api_key or api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return api_key


def parse_allowed_ips() -> list[str]:
    allowed_ips = os.getenv("ALLOWED_IPS", "")
    return [item.strip() for item in allowed_ips.split(",") if item.strip()]


def is_demo_mode_enabled() -> bool:
    return os.getenv("DEMO_MODE", "false").strip().lower() in {"1", "true", "yes", "on"}


def get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    return request.client.host if request.client else ""


def is_ip_allowed(client_ip: str, allowed_ips: list[str]) -> bool:
    if not allowed_ips:
        return True

    try:
        parsed_client_ip = ip_address(client_ip)
    except ValueError:
        return False

    for allowed_ip in allowed_ips:
        try:
            if "/" in allowed_ip:
                if parsed_client_ip in ip_network(allowed_ip, strict=False):
                    return True
            elif parsed_client_ip == ip_address(allowed_ip):
                return True
        except ValueError:
            continue

    return False


def require_allowed_ip(request: Request) -> str:
    if is_demo_mode_enabled():
        logger.warning("DEMO_MODE enabled: bypassing IP allowlist")
        return "demo-mode"

    client_ip = get_client_ip(request)
    allowed_ips = parse_allowed_ips()

    if not is_ip_allowed(client_ip, allowed_ips):
        raise HTTPException(status_code=403, detail="IP address is not allowed")

    return client_ip
