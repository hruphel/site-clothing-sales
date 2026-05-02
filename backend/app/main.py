from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .config import settings
from .database import init_db
from .routers import admin as admin_router
from .routers import auth as auth_router
from .routers import cart as cart_router
from .routers import catalog as catalog_router
from .routers import orders as orders_router
from .routers import pages as pages_router
from .routers import seller as seller_router
from .routers.seller import _RedirectToLogin

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    max_age=settings.session_max_age,
    same_site="lax",
    https_only=False,
)

@app.exception_handler(_RedirectToLogin)
async def _redirect_to_login_handler(_request, _exc):  # noqa: ANN001
    return RedirectResponse(url="/login", status_code=303)


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/uploads", StaticFiles(directory=str(settings.uploads_dir)), name="uploads")

app.include_router(pages_router.router)
app.include_router(auth_router.router)
app.include_router(catalog_router.router)
app.include_router(cart_router.router)
app.include_router(orders_router.router)
app.include_router(seller_router.router)
app.include_router(admin_router.router)
