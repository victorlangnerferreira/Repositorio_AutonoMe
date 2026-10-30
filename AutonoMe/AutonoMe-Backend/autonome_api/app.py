import logging
import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse


async def validation_error_handler(_request: Request, exc: RequestValidationError):
    detail = [
        {
            "loc": error.get("loc", []),
            "msg": error.get("msg", "Invalid input"),
            "type": error.get("type", "value_error"),
        }
        for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": detail})


def create_app(ambiente: str | None = None) -> FastAPI:
    ambiente = (ambiente or os.getenv("AUTONOME_ENV", "development")).strip().lower()
    app = FastAPI(
        title="AutonoMe API",
        docs_url=None if ambiente == "production" else "/docs",
        redoc_url=None if ambiente == "production" else "/redoc",
        openapi_url=None if ambiente == "production" else "/openapi.json",
    )
    logging.basicConfig(
        level=os.getenv("AUTONOME_LOG_LEVEL", "WARNING" if ambiente == "production" else "INFO")
    )
    origins = [
        origin.strip()
        for origin in os.getenv(
            "AUTONOME_CORS_ORIGINS",
            "http://localhost:5500,http://127.0.0.1:5500,http://localhost:8000",
        ).split(",")
        if origin.strip()
    ]
    if ambiente == "production" and (not origins or "*" in origins):
        raise RuntimeError("Configure explicit CORS origins in production.")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.add_exception_handler(RequestValidationError, validation_error_handler)

    from autonome_api.routes import router

    app.include_router(router)
    return app
