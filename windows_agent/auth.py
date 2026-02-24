"""
Token-based authentication middleware for the FastAPI agent.
"""
from fastapi import Request, HTTPException, Security
from fastapi.security import APIKeyHeader
from config import AUTH_TOKEN

api_key_header = APIKeyHeader(name="X-Auth-Token", auto_error=False)


async def verify_token(request: Request, api_key: str = Security(api_key_header)):
    """Validate the auth token from the request header."""
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing X-Auth-Token header")
    if api_key != AUTH_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid auth token")
    return api_key
