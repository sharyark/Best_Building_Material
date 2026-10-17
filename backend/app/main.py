from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse

import app.models  # noqa: F401  (register all tables)
from app.accounting import router as accounting_router
from app.audit import router as audit_router
from app.audit.hooks import install_audit_hooks
from app.core.config import get_settings
from app.core.db import Base, SessionLocal, engine
from app.core.errors import Forbidden, install_error_handlers
from app.core.security import decode_access_token
from app.modules.auth import router as auth_router
from app.modules.deliveries import router as deliveries_router
from app.modules.expenses import router as expenses_router
from app.modules.invoices import router as invoices_router
from app.modules.labour import router as labour_router
from app.modules.masters import router as masters_router
from app.modules.payments import router as payments_router
from app.modules.purchases import router as purchases_router
from app.modules.rentals import router as rentals_router
from app.modules.reports import router as reports_router
from app.modules.stock import router as stock_router

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    if settings.auto_create_tables:
        Base.metadata.create_all(engine)
        from app.bootstrap import bootstrap

        with SessionLocal() as db:
            bootstrap(db)
    yield


def _docs_guard(token: str | None) -> None:
    """OpenAPI docs are open in dev, admin-only (?token=<access token>) in production."""
    if get_settings().env != "prod":
        return
    if not token or decode_access_token(token).get("role") != "admin":
        raise Forbidden("API docs are admin-only")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )
    install_error_handlers(app)
    install_audit_hooks()

    api = APIRouter(prefix=API_PREFIX)
    for module in (
        auth_router.router,
        auth_router.users_router,
        masters_router.router,
        purchases_router.router,
        stock_router.router,
        deliveries_router.router,
        rentals_router.router,
        invoices_router.router,
        payments_router.router,
        expenses_router.router,
        labour_router.router,
        accounting_router.router,
        reports_router.router,
        audit_router.router,
    ):
        api.include_router(module)
    app.include_router(api)

    @app.get("/api/health", include_in_schema=False)
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/api/openapi.json", include_in_schema=False)
    def openapi_json(token: str | None = Query(default=None)) -> JSONResponse:
        _docs_guard(token)
        return JSONResponse(app.openapi())

    @app.get("/api/docs", include_in_schema=False)
    def docs(request: Request, token: str | None = Query(default=None)) -> HTMLResponse:
        _docs_guard(token)
        suffix = f"?token={token}" if token else ""
        return get_swagger_ui_html(openapi_url=f"/api/openapi.json{suffix}", title=f"{settings.app_name} API")

    return app


app = create_app()
