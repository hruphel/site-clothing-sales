"""Тесты используют отдельный SQLite в tmp_path + изолированную сессию."""
from __future__ import annotations

import json
import os
import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Iterator

import pytest


@pytest.fixture(scope="session", autouse=True)
def _isolated_env() -> Iterator[Path]:
    """Подменяем БД/uploads/receipts на изолированные tmp до импорта приложения."""
    tmp = Path(tempfile.mkdtemp(prefix="maison-tests-"))
    (tmp / "uploads").mkdir(parents=True, exist_ok=True)
    (tmp / "receipts").mkdir(parents=True, exist_ok=True)
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp / 'test.db'}"
    os.environ["UPLOADS_DIR"] = str(tmp / "uploads")
    os.environ["RECEIPTS_DIR"] = str(tmp / "receipts")
    os.environ["SECRET_KEY"] = "test-secret-please-change-please-change"
    yield tmp


@pytest.fixture()
def client(_isolated_env):
    """Свежий TestClient на каждый тест: чистая БД и независимая сессия cookie."""
    from app.database import Base, engine, init_db  # type: ignore  # noqa: PLC0415
    from app.main import app  # type: ignore  # noqa: PLC0415
    from fastapi.testclient import TestClient  # type: ignore  # noqa: PLC0415

    Base.metadata.drop_all(bind=engine)
    init_db()
    with TestClient(app) as c:
        yield c


def register(client, *, username: str, email: str, password: str = "passw0rd", role: str = "buyer"):
    r = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
            "password_confirm": password,
            "role": role,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def login(client, *, identifier: str, password: str = "passw0rd"):
    r = client.post("/api/auth/login", json={"identifier": identifier, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


def logout(client):
    r = client.post("/api/auth/logout")
    assert r.status_code == 200


def _make_admin(username: str = "admin", password: str = "passw0rd") -> int:
    from app.database import SessionLocal  # type: ignore  # noqa: PLC0415
    from app.models import User, UserRole  # type: ignore  # noqa: PLC0415
    from app.security import hash_password  # type: ignore  # noqa: PLC0415

    with SessionLocal() as db:
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            return existing.id
        u = User(
            username=username,
            email=f"{username}@example.com",
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
        )
        db.add(u)
        db.commit()
        db.refresh(u)
        return u.id


def make_admin(_isolated_env=None) -> int:
    """Создать админа напрямую в БД (через UI нельзя)."""
    return _make_admin()


def create_published_product(
    *,
    seller_id: int,
    name: str = "Test tee",
    price: str = "1500.00",
    stock: dict[str, int] | None = None,
):
    """Минуя API создаём опубликованный товар с заданным stock."""
    from app.database import SessionLocal  # type: ignore  # noqa: PLC0415
    from app.models import Product, ProductStatus  # type: ignore  # noqa: PLC0415

    stock_data = stock or {"S": 2, "M": 0}
    with SessionLocal() as db:
        p = Product(
            name=name,
            description="",
            price=Decimal(price),
            sizes=", ".join(stock_data.keys()),
            stock_json=json.dumps(stock_data, ensure_ascii=False),
            status=ProductStatus.PUBLISHED,
            seller_id=seller_id,
        )
        db.add(p)
        db.commit()
        db.refresh(p)
        return p.id
