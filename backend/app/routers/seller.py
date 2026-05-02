"""Роутер продавца. UC-6: добавление и редактирование товара (пока pending)."""
from __future__ import annotations

import re
import secrets
import shutil
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..dependencies import get_current_user
from ..models import (
    Order,
    OrderItem,
    OrderStatus,
    Product,
    ProductStatus,
    User,
    UserRole,
)
from ..services.delivery import advance_delivery_status
from ..templating import templates

router = APIRouter(prefix="/seller", tags=["seller"])

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

NAME_MAX_LENGTH = 160
DESCRIPTION_MAX_LENGTH = 4000
SIZES_MAX_COUNT = 20
SIZE_MIN_LENGTH = 1
SIZE_MAX_LENGTH = 8
# Допускаем латиницу/кириллицу/цифры/точку/дефис и пробел внутри (например "L Tall").
_SIZE_PATTERN = re.compile(r"^[A-Za-zА-Яа-яЁё0-9\.\- ]+$")


class _RedirectToLogin(Exception):
    """Контроллер вернёт RedirectResponse на /login, если пользователь не авторизован."""


def _require_seller(user: User | None) -> User:
    if user is None:
        raise _RedirectToLogin
    if user.role != UserRole.SELLER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Доступ только для продавцов.")
    return user


def _save_upload(upload: UploadFile) -> tuple[str | None, str | None]:
    """Сохраняет загруженное фото и возвращает (filename, error)."""
    if upload is None or upload.filename in (None, ""):
        return None, None

    suffix = Path(upload.filename).suffix.lower()
    if suffix not in ALLOWED_IMAGE_EXTENSIONS:
        return None, "Файл должен быть изображением (.jpg, .jpeg, .png, .webp, .gif)."
    if upload.content_type and upload.content_type not in settings.allowed_image_types:
        return None, "Поддерживаются только изображения JPEG, PNG, WebP, GIF."

    upload.file.seek(0, 2)
    size = upload.file.tell()
    upload.file.seek(0)
    if size > settings.max_image_size_bytes:
        max_mb = settings.max_image_size_bytes // (1024 * 1024)
        return None, f"Файл слишком большой (максимум {max_mb} МБ)."
    if size == 0:
        return None, "Файл пуст."

    target_name = f"{secrets.token_hex(16)}{suffix}"
    target_path = settings.uploads_dir / target_name
    with target_path.open("wb") as out:
        shutil.copyfileobj(upload.file, out)
    return target_name, None


def _parse_price(raw: str) -> tuple[Decimal | None, str | None]:
    raw = raw.replace(",", ".").strip()
    try:
        value = Decimal(raw)
    except (InvalidOperation, ValueError):
        return None, "Цена должна быть числом."
    if value <= 0:
        return None, "Цена должна быть больше 0."
    quantized = value.quantize(Decimal("0.01"))
    return quantized, None


def _validate_sizes(raw: str) -> tuple[str, list[str]]:
    """Валидирует и нормализует строку размеров вида 'S, M, L'.

    Возвращает (нормализованная строка через ', ', список ошибок).
    """
    errors: list[str] = []
    items = [s.strip() for s in raw.split(",")]
    items = [s for s in items if s != ""]

    if len(items) > SIZES_MAX_COUNT:
        errors.append(f"Слишком много размеров — максимум {SIZES_MAX_COUNT}.")
        return "", errors

    seen: set[str] = set()
    cleaned: list[str] = []
    for s in items:
        if len(s) < SIZE_MIN_LENGTH or len(s) > SIZE_MAX_LENGTH:
            errors.append(
                f"Размер «{s}» должен быть от {SIZE_MIN_LENGTH} до {SIZE_MAX_LENGTH} символов."
            )
            continue
        if not _SIZE_PATTERN.match(s):
            errors.append(
                f"Размер «{s}» может содержать только буквы, цифры, точку, дефис и пробел."
            )
            continue
        key = s.upper()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(s)

    return ", ".join(cleaned), errors


@dataclass
class _ProductInput:
    name: str
    price: Decimal | None
    sizes: str
    description: str


def _validate_basic_fields(name: str, price: str, sizes: str, description: str) -> tuple[_ProductInput, list[str]]:
    errors: list[str] = []

    name_clean = name.strip()
    if not name_clean:
        errors.append("Название не может быть пустым.")
    elif len(name_clean) > NAME_MAX_LENGTH:
        errors.append(f"Название не должно быть длиннее {NAME_MAX_LENGTH} символов.")

    price_value, price_err = _parse_price(price)
    if price_err:
        errors.append(price_err)

    sizes_clean, sizes_errs = _validate_sizes(sizes)
    errors.extend(sizes_errs)

    description_clean = description.strip()
    if len(description_clean) > DESCRIPTION_MAX_LENGTH:
        errors.append(f"Описание не должно быть длиннее {DESCRIPTION_MAX_LENGTH} символов.")

    return _ProductInput(name_clean, price_value, sizes_clean, description_clean), errors


def _own_product_or_404(db: Session, seller: User, product_id: int) -> Product:
    product = db.get(Product, product_id)
    if product is None or product.seller_id != seller.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Товар не найден.")
    return product


@router.get("", response_class=HTMLResponse)
def dashboard(
    request: Request,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    seller = _require_seller(user)
    products = (
        db.query(Product)
        .filter(Product.seller_id == seller.id)
        .order_by(desc(Product.created_at))
        .limit(6)
        .all()
    )
    counts = {
        ProductStatus.PENDING: 0,
        ProductStatus.PUBLISHED: 0,
        ProductStatus.REJECTED: 0,
    }
    for status_value, in db.query(Product.status).filter(Product.seller_id == seller.id).all():
        counts[status_value] = counts.get(status_value, 0) + 1
    return templates.TemplateResponse(
        request,
        "seller/dashboard.html",
        {"user": seller, "recent_products": products, "counts": counts},
    )


@router.get("/products", response_class=HTMLResponse)
def list_products(
    request: Request,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    seller = _require_seller(user)
    products = (
        db.query(Product)
        .filter(Product.seller_id == seller.id)
        .order_by(desc(Product.created_at))
        .all()
    )
    return templates.TemplateResponse(
        request,
        "seller/products.html",
        {"user": seller, "products": products},
    )


@router.get("/products/new", response_class=HTMLResponse)
def new_product_form(
    request: Request,
    user: User | None = Depends(get_current_user),
):
    seller = _require_seller(user)
    return templates.TemplateResponse(
        request,
        "seller/new_product.html",
        {
            "user": seller,
            "errors": [],
            "form": {"name": "", "price": "", "sizes": "", "description": ""},
        },
    )


@router.post("/products/new", response_class=HTMLResponse)
def create_product(
    request: Request,
    name: str = Form(...),
    price: str = Form(...),
    sizes: str = Form(""),
    description: str = Form(""),
    image: UploadFile = File(None),
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    seller = _require_seller(user)

    data, errors = _validate_basic_fields(name, price, sizes, description)

    saved_filename: str | None = None
    if image is not None and image.filename:
        saved_filename, image_err = _save_upload(image)
        if image_err:
            errors.append(image_err)

    if errors:
        return templates.TemplateResponse(
            request,
            "seller/new_product.html",
            {
                "user": seller,
                "errors": errors,
                "form": {
                    "name": data.name,
                    "price": price,
                    "sizes": sizes,
                    "description": data.description,
                },
            },
            status_code=400,
        )

    assert data.price is not None
    product = Product(
        name=data.name,
        description=data.description,
        price=data.price,
        sizes=data.sizes,
        image_filename=saved_filename,
        status=ProductStatus.PENDING,
        seller_id=seller.id,
    )
    db.add(product)
    db.commit()
    db.refresh(product)

    return RedirectResponse(url="/seller/products", status_code=303)


@router.get("/products/{product_id}/edit", response_class=HTMLResponse)
def edit_product_form(
    request: Request,
    product_id: int,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    seller = _require_seller(user)
    product = _own_product_or_404(db, seller, product_id)
    if product.status != ProductStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Редактировать можно только товары в статусе «На модерации».",
        )
    return templates.TemplateResponse(
        request,
        "seller/edit_product.html",
        {
            "user": seller,
            "product": product,
            "errors": [],
            "form": {
                "name": product.name,
                "price": f"{product.price:.2f}",
                "sizes": product.sizes,
                "description": product.description or "",
            },
        },
    )


@router.post("/products/{product_id}/edit", response_class=HTMLResponse)
def edit_product_submit(
    request: Request,
    product_id: int,
    name: str = Form(...),
    price: str = Form(...),
    sizes: str = Form(""),
    description: str = Form(""),
    image: UploadFile = File(None),
    remove_image: str = Form(""),
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    seller = _require_seller(user)
    product = _own_product_or_404(db, seller, product_id)
    if product.status != ProductStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Редактировать можно только товары в статусе «На модерации».",
        )

    data, errors = _validate_basic_fields(name, price, sizes, description)

    new_filename: str | None = None
    if image is not None and image.filename:
        new_filename, image_err = _save_upload(image)
        if image_err:
            errors.append(image_err)

    if errors:
        return templates.TemplateResponse(
            request,
            "seller/edit_product.html",
            {
                "user": seller,
                "product": product,
                "errors": errors,
                "form": {
                    "name": data.name,
                    "price": price,
                    "sizes": sizes,
                    "description": data.description,
                },
            },
            status_code=400,
        )

    assert data.price is not None
    old_filename = product.image_filename
    product.name = data.name
    product.price = data.price
    product.sizes = data.sizes
    product.description = data.description
    image_changed = False
    if new_filename is not None:
        product.image_filename = new_filename
        image_changed = True
    elif remove_image == "1":
        product.image_filename = None
        image_changed = True
    db.commit()

    # Удаляем старый файл с диска уже после коммита, чтобы при сбое БД
    # не остаться без оригинала. missing_ok=True — на случай ручной чистки.
    if image_changed and old_filename:
        (settings.uploads_dir / old_filename).unlink(missing_ok=True)

    return RedirectResponse(url="/seller/products", status_code=303)


@router.post("/products/{product_id}/delete")
def delete_product(
    product_id: int,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Удаление заявки на товар. Доступно только владельцу и только пока pending."""
    seller = _require_seller(user)
    product = _own_product_or_404(db, seller, product_id)
    if product.status != ProductStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Удалять можно только товары в статусе «На модерации».",
        )
    old_filename = product.image_filename
    db.delete(product)
    db.commit()
    if old_filename:
        (settings.uploads_dir / old_filename).unlink(missing_ok=True)
    return RedirectResponse(url="/seller/products", status_code=303)


# ---------- UC-5: заказы и доставка глазами продавца ----------


def _orders_with_seller_items(db: Session, seller_id: int) -> list[Order]:
    """Заказы (paid+), в которых есть хотя бы одна позиция продавца."""
    return (
        db.query(Order)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .join(Product, OrderItem.product_id == Product.id)
        .filter(Product.seller_id == seller_id)
        .filter(Order.status == OrderStatus.PAID)
        .order_by(desc(Order.created_at))
        .distinct()
        .all()
    )


def _seller_owns_order(db: Session, seller_id: int, order: Order) -> bool:
    return (
        db.query(OrderItem)
        .join(Product, OrderItem.product_id == Product.id)
        .filter(OrderItem.order_id == order.id, Product.seller_id == seller_id)
        .first()
        is not None
    )


@router.get("/orders", response_class=HTMLResponse)
def list_seller_orders(
    request: Request,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    seller = _require_seller(user)
    orders = _orders_with_seller_items(db, seller.id)
    return templates.TemplateResponse(
        request,
        "seller/orders_list.html",
        {"user": seller, "orders": orders},
    )


@router.post("/orders/{order_id}/delivery")
def update_seller_order_delivery(
    order_id: int,
    delivery_status_value: str = Form(..., alias="delivery_status"),
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    seller = _require_seller(user)
    order = db.get(Order, order_id)
    # 404 — и для несуществующего заказа, и для заказа без позиций продавца
    # (не палим само существование чужого заказа).
    if order is None or not _seller_owns_order(db, seller.id, order):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заказ не найден.")
    advance_delivery_status(order, delivery_status_value)
    db.commit()
    return RedirectResponse(url="/seller/orders", status_code=303)
