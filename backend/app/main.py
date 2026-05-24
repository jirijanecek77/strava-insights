from contextlib import asynccontextmanager
from datetime import datetime
import base64
import json
import logging
import time
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from itsdangerous import BadSignature, TimestampSigner
from starlette.middleware.sessions import SessionMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_log_user_name, reset_log_user_name, set_log_user_name
from app.infrastructure.db.bootstrap import upgrade_database


configure_logging(
    log_level=settings.log_level,
)
logger = logging.getLogger("app.main")


def _emit_console_log(message: str) -> None:
    timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S%z")
    print(f"{timestamp} INFO [be] [user={get_log_user_name()}] [app.main] {message}", flush=True)


def _get_session_user_for_logging(request: Request) -> dict:
    session = request.scope.get("session")
    if isinstance(session, dict):
        session_user = session.get("user")
        if isinstance(session_user, dict):
            return session_user

    raw_cookie = request.cookies.get(settings.session_cookie_name)
    if not raw_cookie:
        return {}

    signer = TimestampSigner(str(settings.session_secret_key))
    try:
        data = signer.unsign(raw_cookie, max_age=settings.session_max_age_seconds)
        session_payload = json.loads(base64.b64decode(data))
    except (BadSignature, ValueError, json.JSONDecodeError):
        return {}

    session_user = session_payload.get("user")
    return session_user if isinstance(session_user, dict) else {}


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Starting backend application.")
    _emit_console_log("Starting backend application.")
    upgrade_database()
    logger.info("Database migrations checked.")
    _emit_console_log("Database migrations checked.")
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret_key,
    session_cookie=settings.session_cookie_name,
    max_age=settings.session_max_age_seconds,
    same_site="lax",
    https_only=settings.session_https_only,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_public_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    session_user = _get_session_user_for_logging(request)
    log_user_token = set_log_user_name(session_user.get("display_name"))
    start_time = time.perf_counter()
    request_id = request.headers.get("x-request-id") or str(uuid4())
    request.state.request_id = request_id
    started_message = (
        f"request_id={request_id} "
        f"Request started method={request.method} "
        f"path={request.url.path} "
        f"query={request.url.query} "
        f"client={request.client.host if request.client else 'unknown'} "
        f"origin={request.headers.get('origin', '')} "
        f"referer={request.headers.get('referer', '')}"
    )
    logger.info(
        "Request started request_id=%s method=%s path=%s query=%s client=%s origin=%s referer=%s",
        request_id,
        request.method,
        request.url.path,
        request.url.query,
        request.client.host if request.client else "unknown",
        request.headers.get("origin", ""),
        request.headers.get("referer", ""),
        extra={
            "request.id": request_id,
            "http.method": request.method,
            "url.path": request.url.path,
            "url.query": request.url.query,
            "client.address": request.client.host if request.client else "unknown",
            "http.origin": request.headers.get("origin", ""),
            "http.referer": request.headers.get("referer", ""),
        },
    )
    _emit_console_log(started_message)
    try:
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start_time) * 1000
            failed_message = (
                f"request_id={request_id} "
                f"Request failed method={request.method} "
                f"path={request.url.path} "
                f"duration_ms={duration_ms:.2f}"
            )
            logger.exception(
                "Request failed request_id=%s method=%s path=%s duration_ms=%.2f",
                request_id,
                request.method,
                request.url.path,
                duration_ms,
                extra={
                    "request.id": request_id,
                    "http.method": request.method,
                    "url.path": request.url.path,
                    "duration_ms": round(duration_ms, 2),
                },
            )
            _emit_console_log(failed_message)
            raise

        duration_ms = (time.perf_counter() - start_time) * 1000
        completed_message = (
            f"request_id={request_id} "
            f"Request completed method={request.method} "
            f"path={request.url.path} "
            f"status={response.status_code} "
            f"duration_ms={duration_ms:.2f}"
        )
        logger.info(
            "Request completed request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            extra={
                "request.id": request_id,
                "http.method": request.method,
                "url.path": request.url.path,
                "http.status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
            },
        )
        response.headers["X-Request-ID"] = request_id
        _emit_console_log(completed_message)
        return response
    finally:
        reset_log_user_name(log_user_token)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None) or request.headers.get("x-request-id") or str(uuid4())
    _emit_console_log(f"request_id={request_id} Unhandled exception on path={request.url.path}")
    logger.exception(
        "Unhandled exception request_id=%s on path=%s",
        request_id,
        request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__),
        extra={
            "request.id": request_id,
            "http.method": request.method,
            "url.path": request.url.path,
        },
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error."},
        headers={"X-Request-ID": request_id},
    )
