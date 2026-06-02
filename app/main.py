from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse

from app.api import auth, backups, credentials, devices, diffs, reports, web
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.rate_limit import limiter
from app.workers.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging()
    start_scheduler()
    yield
    stop_scheduler()


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Enterprise network device backup and audit platform.",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, same_site="lax", https_only=False)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(_request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(status_code=429, content={"detail": f"Rate limit exceeded: {exc.detail}"})


@app.middleware("http")
async def add_client_ip_to_scope(request, call_next):
    request.scope["client_ip"] = get_remote_address(request)
    return await call_next(request)


app.include_router(auth.router)
app.include_router(credentials.router)
app.include_router(devices.router)
app.include_router(backups.router)
app.include_router(diffs.router)
app.include_router(reports.router)
app.include_router(web.router)
