"""API продавца: товары (CRUD pending) и заказы/доставка."""
from __future__ import annotations

import json
import re
import secrets
import shutil
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import desc
from sqlalchemy.orm import Session, selectinload

from ...config import settings
from ...database import get_db
from ...models import (
    Order,
    OrderItem,
    OrderStatus,
    Product,
    ProductStatus,
    User,
)
from ...schemas import DeliveryUpdateIn, MessageResponse, OrderOut, ProductOut
from ...services.delivery import advance_delivery_status
from ._common import require_seller

router = APIRouter(prefix="/seller", tags=["seller"])

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

NAME_MAX_LENGTH = 160
DESCRIPTION_MAX_LENGTH = 4000
SIZES_MAX_COUNT = 20
SIZE_MIN_LENGTH = 1
SIZE_MAX_LENGTH = 8
STOCK_PER_SIZE_MAX = 9999
_SIZE_PATTERN = re.compile(r"^[A-Za-zА-Яа-яЁё0-9\.\- ]+$")


def _save_upload(upload: UploadFile | None) -> str | None:
    """Сохраняет загруженное фото и возвращает имя файла либо бросает 400."""
    if upload is None or not upload.filename:
        return None
    suffix = Path(upload.filename).suffix.lower()
    if suffix not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Файл должен быть изображением (.jpg, .jpeg, .png, .webp, .gif).")
    if upload.content_type and upload.content_type not in settings.allowed_image_types:
        raise HTTPException(status_code=400, detail="Поддерживаются только изображения JPEG, PNG, WebP, GIF.")

    upload.file.seek(0, 2)
    size = upload.file.tell()
    upload.file.seek(0)
    if size > settings.max_image_size_bytes:
        max_mb = settings.max_image_size_bytes // (1024 * 1024)
        raise HTTPException(status_code=400, detail=f"Файл слишком большой (максимум {max_mb} МБ).")
    if size == 0:
        raise HTTPException(status_code=400, detail="Файл пуст.")

    target_name = f"{secrets.token_hex(16)}{suffix}"
    target_path = settings.uploads_dir / target_name
    with target_path.open("wb") as out:
        shutil.copyfileobj(upload.file, out)
    return target_name


def _parse_price(raw: str) -> Decimal:
    raw = raw.replace(",", ".").strip()
    try:
        value = Decimal(raw)
    except (InvalidOperation, ValueError):
        raise HTTPException(status_code=400, detail="Цена должна быть числом.") from None
    if value <= 0:
        raise HTTPException(status_code=400, detail="Цена должна быть больше 0.")
    return value.quantize(Decimal("0.01"))


def _validate_single_size(raw: str) -> str:
    s = raw.strip()
    if len(s) < SIZE_MIN_LENGTH or len(s) > SIZE_MAX_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Размер «{s}» должен быть от {SIZE_MIN_LENGTH} до {SIZE_MAX_LENGTH} символов.",
        )
    if not _SIZE_PATTERN.match(s):
        raise HTTPException(
            status_code=400,
            detail=f"Размер «{s}» может содержать только буквы, цифры, точку, дефис и пробел.",
        )
    return s


def _validate_stock(raw: str) -> dict[str, int]:
    """Принимает JSON-строку `{"S": 5, "M": 10}` и возвращает очищенный dict.

    Пустая строка / пустой объект означают «у товара нет размеров со складским учётом».
    """
    raw_clean = (raw or "").strip()
    if not raw_clean:
        return {}
    try:
        data = json.loads(raw_clean)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Запасы по размерам должны быть валидным JSON.") from None
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Запасы по размерам должны быть объектом «размер → количество».")
    if len(data) > SIZES_MAX_COUNT:
        raise HTTPException(status_code=400, detail=f"Слишком много размеров — максимум {SIZES_MAX_COUNT}.")
    cleaned: dict[str, int] = {}
    seen: set[str] = set()
    for key, value in data.items():
        size = _validate_single_size(str(key))
        upper = size.upper()
        if upper in seen:
            continue
        seen.add(upper)
        try:
            qty = int(value)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail=f"Количество для размера «{size}» должно быть целым числом.",
            ) from None
        if qty < 0 or qty > STOCK_PER_SIZE_MAX:
            raise HTTPException(
                status_code=400,
                detail=f"Количество для размера «{size}» должно быть в диапазоне 0..{STOCK_PER_SIZE_MAX}.",
            )
        cleaned[size] = qty
    return cleaned


@dataclass
class _ProductInput:
    name: str
    price: Decimal
    stock: dict[str, int]
    sizes: str
    description: str


def _validate_basic(name: str, price: str, stock_raw: str, description: str) -> _ProductInput:
    name_clean = name.strip()
    if not name_clean:
        raise HTTPException(status_code=400, detail="Название не может быть пустым.")
    if len(name_clean) > NAME_MAX_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Название не должно быть длиннее {NAME_MAX_LENGTH} символов.",
        )
    price_value = _parse_price(price)
    stock_clean = _validate_stock(stock_raw)
    sizes_str = ", ".join(stock_clean.keys())
    description_clean = description.strip()
    if len(description_clean) > DESCRIPTION_MAX_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Описание не должно быть длиннее {DESCRIPTION_MAX_LENGTH} символов.",
        )
    return _ProductInput(name_clean, price_value, stock_clean, sizes_str, description_clean)


def _own_product_or_404(db: Session, seller: User, product_id: int) -> Product:
    product = db.get(Product, product_id)
    if product is None or product.seller_id != seller.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Товар не найден.")
    return product


@router.get("/dashboard")
def dashboard(seller: User = Depends(require_seller), db: Session = Depends(get_db)):
    counts = {ProductStatus.PENDING: 0, ProductStatus.PUBLISHED: 0, ProductStatus.REJECTED: 0}
    for status_value, in db.query(Product.status).filter(Product.seller_id == seller.id).all():
        counts[status_value] = counts.get(status_value, 0) + 1
    recent = (
        db.query(Product)
        .filter(Product.seller_id == seller.id)
        .order_by(desc(Product.created_at))
        .limit(6)
        .all()
    )
    return {
        "counts": {k.value: v for k, v in counts.items()},
        "recent": [ProductOut.from_model(p) for p in recent],
    }


@router.get("/products", response_model=list[ProductOut])
def list_products(seller: User = Depends(require_seller), db: Session = Depends(get_db)):
    products = (
        db.query(Product)
        .filter(Product.seller_id == seller.id)
        .order_by(desc(Product.created_at))
        .all()
    )
    return [ProductOut.from_model(p) for p in products]


@router.get("/products/{product_id}", response_model=ProductOut)
def get_product(product_id: int, seller: User = Depends(require_seller), db: Session = Depends(get_db)):
    product = _own_product_or_404(db, seller, product_id)
    return ProductOut.from_model(product)


@router.post("/products", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(
    name: str = Form(...),
    price: str = Form(...),
    stock: str = Form(""),
    description: str = Form(""),
    image: UploadFile = File(None),
    seller: User = Depends(require_seller),
    db: Session = Depends(get_db),
):
    data = _validate_basic(name, price, stock, description)
    saved_filename = _save_upload(image)

    product = Product(
        name=data.name,
        description=data.description,
        price=data.price,
        sizes=data.sizes,
        stock_json=json.dumps(data.stock, ensure_ascii=False),
        image_filename=saved_filename,
        status=ProductStatus.PENDING,
        seller_id=seller.id,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return ProductOut.from_model(product)


@router.post("/products/{product_id}/edit", response_model=ProductOut)
def edit_product(
    product_id: int,
    name: str = Form(...),
    price: str = Form(...),
    stock: str = Form(""),
    description: str = Form(""),
    image: UploadFile = File(None),
    remove_image: str = Form(""),
    seller: User = Depends(require_seller),
    db: Session = Depends(get_db),
):
    product = _own_product_or_404(db, seller, product_id)
    if product.status != ProductStatus.PENDING:
        raise HTTPException(status_code=409, detail="Редактировать можно только товары в статусе «На модерации».")

    data = _validate_basic(name, price, stock, description)
    new_filename = _save_upload(image)

    old_filename = product.image_filename
    product.name = data.name
    product.price = data.price
    product.sizes = data.sizes
    product.stock_json = json.dumps(data.stock, ensure_ascii=False)
    product.description = data.description
    image_changed = False
    if new_filename is not None:
        product.image_filename = new_filename
        image_changed = True
    elif remove_image == "1":
        product.image_filename = None
        image_changed = True
    db.commit()
    if image_changed and old_filename:
        (settings.uploads_dir / old_filename).unlink(missing_ok=True)
    db.refresh(product)
    return ProductOut.from_model(product)


@router.post("/products/{product_id}/delete", response_model=MessageResponse)
def delete_product(
    product_id: int,
    seller: User = Depends(require_seller),
    db: Session = Depends(get_db),
):
    product = _own_product_or_404(db, seller, product_id)
    if product.status != ProductStatus.PENDING:
        raise HTTPException(status_code=409, detail="Удалять можно только товары в статусе «На модерации».")
    old_filename = product.image_filename
    db.delete(product)
    db.commit()
    if old_filename:
        (settings.uploads_dir / old_filename).unlink(missing_ok=True)
    return MessageResponse()


# ---------- UC-5 ----------


def _orders_with_seller_items(db: Session, seller_id: int) -> list[Order]:
    return (
        db.query(Order)
        .options(selectinload(Order.items), selectinload(Order.receipt), selectinload(Order.buyer))
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


@router.get("/orders", response_model=list[OrderOut])
def list_seller_orders(seller: User = Depends(require_seller), db: Session = Depends(get_db)):
    orders = _orders_with_seller_items(db, seller.id)
    return [OrderOut.from_model(o, include_buyer=True) for o in orders]


@router.post("/orders/{order_id}/delivery", response_model=OrderOut)
def update_seller_delivery(
    order_id: int,
    payload: DeliveryUpdateIn,
    seller: User = Depends(require_seller),
    db: Session = Depends(get_db),
):
    order = (
        db.query(Order)
        .options(selectinload(Order.items), selectinload(Order.receipt), selectinload(Order.buyer))
        .filter(Order.id == order_id)
        .first()
    )
    if order is None or not _seller_owns_order(db, seller.id, order):
        raise HTTPException(status_code=404, detail="Заказ не найден.")
    advance_delivery_status(order, payload.delivery_status.value)
    db.commit()
    db.refresh(order)
    return OrderOut.from_model(order, include_buyer=True)
