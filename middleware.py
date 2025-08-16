from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import List
import security  # senin security.py dosyan

class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: FastAPI, exempt_paths: List[str] = None):
        super().__init__(app)
        self.exempt_paths = exempt_paths or []

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Token kontrolü yapılmayacak yollar
        if any(path.startswith(exempt) for exempt in self.exempt_paths):
            return await call_next(request)

        # Authorization header al
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Yetkilendirme gerekli."}
            )

        token = auth_header.split(" ")[1]
        decoded = security.validate_token(token)
        if not decoded:
            return JSONResponse(
                status_code=401,
                content={"detail": "Geçersiz veya süresi dolmuş token."}
            )

        # Token geçerliyse request'e ekle (opsiyonel)
        request.state.user = decoded

        return await call_next(request)
