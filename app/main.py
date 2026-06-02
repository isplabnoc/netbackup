from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from html import escape

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import HTMLResponse, JSONResponse

from app.api import auth, backups, credentials, devices, diffs, health, reports, web
from app.core.config import get_settings
from app.core.logging import app_logger
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
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    same_site="lax",
    https_only=settings.secure_cookies,
)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(_request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(status_code=429, content={"detail": f"Rate limit exceeded: {exc.detail}"})


@app.exception_handler(Exception)
def internal_error_handler(request: Request, exc: Exception) -> HTMLResponse | JSONResponse:
    app_logger.exception("unhandled_request_error", extra={"path": request.url.path})
    if request.url.path.startswith("/api/") or request.headers.get("accept") == "application/json":
        return JSONResponse(status_code=500, content={"detail": str(exc)})
    error_message = escape(str(exc))
    content = f"""
    <!doctype html>
    <html lang="pt-BR">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Erro - NetBackup Pro</title>
        <link href="/static/css/app.css?v=20260602-4" rel="stylesheet">
      </head>
      <body class="login-body">
        <main class="login-panel">
          <h1 class="h4 mb-3">Erro interno</h1>
          <p class="text-secondary">A aplicacao encontrou uma falha ao processar esta pagina.</p>
          <pre class="integration-log">{error_message}</pre>
          <a class="btn btn-primary w-100 mt-3" href="/">Voltar ao dashboard</a>
        </main>
      </body>
    </html>
    """
    return HTMLResponse(status_code=500, content=content)


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
app.include_router(health.router)
app.include_router(web.router)
