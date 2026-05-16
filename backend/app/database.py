from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


connect_args: dict = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(settings.database_url, connect_args=connect_args, future=True)


if settings.database_url.startswith("sqlite"):
    # SQLite по умолчанию знает lower() только для ASCII. Регистрируем
    # Python-овский str.lower(), чтобы поиск был регистронезависимым для
    # кириллицы и других не-ASCII символов.
    @event.listens_for(Engine, "connect")
    def _register_unicode_lower(dbapi_connection, connection_record):  # noqa: ARG001
        try:
            dbapi_connection.create_function(
                "lower", 1, lambda x: x.lower() if isinstance(x, str) else x, deterministic=True
            )
        except TypeError:
            # старые версии sqlite3 без аргумента deterministic
            dbapi_connection.create_function(
                "lower", 1, lambda x: x.lower() if isinstance(x, str) else x
            )
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    """Базовый класс для всех ORM моделей."""


def get_db():
    """Зависимость FastAPI: создаёт сессию БД на запрос."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Создаёт таблицы при первом запуске. Используется как dev-миграция."""
    from . import models  # noqa: F401  гарантируем регистрацию моделей

    Base.metadata.create_all(bind=engine)
    _apply_inline_migrations()


def _apply_inline_migrations() -> None:
    """Идемпотентные ALTER TABLE для столбцов, добавленных после первого релиза.

    Используем там, где Alembic избыточен (учебный проект). Работает для
    SQLite и PostgreSQL: оба понимают `ALTER TABLE ... ADD COLUMN`.
    """
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    with engine.begin() as conn:
        if "products" in tables:
            cols = {c["name"] for c in insp.get_columns("products")}
            if "stock_json" not in cols:
                conn.execute(
                    text("ALTER TABLE products ADD COLUMN stock_json TEXT NOT NULL DEFAULT '{}'")
                )
        if "cart_items" in tables:
            cols = {c["name"] for c in insp.get_columns("cart_items")}
            if "size" not in cols:
                conn.execute(
                    text("ALTER TABLE cart_items ADD COLUMN size VARCHAR(16) NOT NULL DEFAULT ''")
                )

    if "cart_items" in tables:
        _migrate_cart_unique_constraint()


def _migrate_cart_unique_constraint() -> None:
    """Заменяет старый UNIQUE (buyer_id, product_id) на (buyer_id, product_id, size).

    До PR с раздельным учётом размеров в корзине нельзя было класть один и тот
    же товар разных размеров. На старых volume'ах (docker SQLite, прод-postgres)
    осталась прежняя уникальность — без этой миграции `INSERT` второй позиции
    падает с IntegrityError → 500.
    """
    insp = inspect(engine)
    uniques = insp.get_unique_constraints("cart_items")
    has_old = any(u.get("name") == "uq_cart_buyer_product" for u in uniques)
    has_new = any(u.get("name") == "uq_cart_buyer_product_size" for u in uniques)
    if has_new and not has_old:
        return

    dialect = engine.dialect.name
    if dialect == "postgresql":
        with engine.begin() as conn:
            if has_old:
                conn.execute(
                    text("ALTER TABLE cart_items DROP CONSTRAINT IF EXISTS uq_cart_buyer_product")
                )
            if not has_new:
                conn.execute(
                    text(
                        "ALTER TABLE cart_items "
                        "ADD CONSTRAINT uq_cart_buyer_product_size "
                        "UNIQUE (buyer_id, product_id, size)"
                    )
                )
        return

    if dialect == "sqlite":
        # SQLite не умеет DROP CONSTRAINT по имени — пересобираем таблицу.
        from .models import CartItem

        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE cart_items RENAME TO _cart_items_old"))
            CartItem.__table__.create(conn)
            conn.execute(
                text(
                    "INSERT INTO cart_items (id, buyer_id, product_id, size, quantity, created_at) "
                    "SELECT id, buyer_id, product_id, COALESCE(size, ''), quantity, created_at "
                    "FROM _cart_items_old"
                )
            )
            conn.execute(text("DROP TABLE _cart_items_old"))
