"""Корзина покупателя."""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from ...database import get_db
from ...models import CartItem, Product, ProductStatus, User
from ...schemas import (
    CartAddIn,
    CartItemOut,
    CartOut,
    CartUpdateIn,
    MessageResponse,
    ProductOut,
)
from ._common import require_buyer

router = APIRouter(prefix="/cart", tags=["cart"])


def _active_cart(db: Session, buyer_id: int) -> list[CartItem]:
    items = (
        db.query(CartItem)
        .options(selectinload(CartItem.product).selectinload(Product.seller))
        .filter(CartItem.buyer_id == buyer_id)
        .all()
    )
    return [item for item in items if item.product.status == ProductStatus.PUBLISHED]


def _build_cart(items: list[CartItem]) -> CartOut:
    total = sum((item.line_total for item in items), Decimal("0.00"))
    return CartOut(
        items=[
            CartItemOut(
                id=i.id,
                product=ProductOut.from_model(i.product),
                size=i.size,
                quantity=i.quantity,
                line_total=i.line_total,
            )
            for i in items
        ],
        total=total,
        item_count=sum(i.quantity for i in items),
    )


def _resolve_size(product: Product, requested_size: str) -> str:
    """Возвращает валидный размер из stock товара.

    Если у товара нет ни одного размера — пустая строка (товар без размеров).
    Иначе требует явного выбора одного из доступных вариантов.
    """
    available = list(product.sizes_stock.keys())
    if not available:
        # Товар без размеров: пустой выбор допустим.
        return ""
    chosen = requested_size.strip()
    if not chosen:
        raise HTTPException(status_code=400, detail="Выберите размер.")
    if chosen not in product.sizes_stock:
        raise HTTPException(status_code=400, detail=f"Размер «{chosen}» недоступен.")
    return chosen


@router.get("", response_model=CartOut)
def view_cart(buyer: User = Depends(require_buyer), db: Session = Depends(get_db)):
    return _build_cart(_active_cart(db, buyer.id))


@router.post("/add", response_model=CartOut)
def add_to_cart(
    payload: CartAddIn,
    buyer: User = Depends(require_buyer),
    db: Session = Depends(get_db),
):
    product = db.get(Product, payload.product_id)
    if product is None or product.status != ProductStatus.PUBLISHED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Товар не найден.")

    size = _resolve_size(product, payload.size)
    stock = product.sizes_stock
    available = stock.get(size, 0) if size else _no_size_available(stock)

    existing = (
        db.query(CartItem)
        .filter(
            CartItem.buyer_id == buyer.id,
            CartItem.product_id == payload.product_id,
            CartItem.size == size,
        )
        .first()
    )
    current_in_cart = existing.quantity if existing else 0
    desired_total = current_in_cart + payload.quantity

    if available <= 0:
        raise HTTPException(
            status_code=409,
            detail=_out_of_stock_message(product, size),
        )
    if desired_total > available:
        raise HTTPException(
            status_code=409,
            detail=_not_enough_message(product, size, available, current_in_cart),
        )
    capped = min(desired_total, 99)
    if existing is None:
        db.add(
            CartItem(
                buyer_id=buyer.id,
                product_id=payload.product_id,
                size=size,
                quantity=capped,
            )
        )
    else:
        existing.quantity = capped
    db.commit()
    return _build_cart(_active_cart(db, buyer.id))


@router.post("/{item_id}/update", response_model=CartOut)
def update_quantity(
    item_id: int,
    payload: CartUpdateIn,
    buyer: User = Depends(require_buyer),
    db: Session = Depends(get_db),
):
    item = db.get(CartItem, item_id)
    if item is None or item.buyer_id != buyer.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Позиция не найдена.")
    stock = item.product.sizes_stock
    available = stock.get(item.size, 0) if item.size else _no_size_available(stock)
    if payload.quantity > available:
        raise HTTPException(
            status_code=409,
            detail=_not_enough_message(item.product, item.size, available, 0),
        )
    item.quantity = payload.quantity
    db.commit()
    return _build_cart(_active_cart(db, buyer.id))


@router.post("/{item_id}/remove", response_model=CartOut)
def remove_item(
    item_id: int,
    buyer: User = Depends(require_buyer),
    db: Session = Depends(get_db),
):
    item = db.get(CartItem, item_id)
    if item is None or item.buyer_id != buyer.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Позиция не найдена.")
    db.delete(item)
    db.commit()
    return _build_cart(_active_cart(db, buyer.id))


@router.post("/clear", response_model=MessageResponse)
def clear_cart(buyer: User = Depends(require_buyer), db: Session = Depends(get_db)):
    db.query(CartItem).filter(CartItem.buyer_id == buyer.id).delete()
    db.commit()
    return MessageResponse()


def _no_size_available(stock: dict[str, int]) -> int:
    """Если размеров нет вообще, общий запас не определён."""
    if not stock:
        return 99
    return sum(stock.values())


def _out_of_stock_message(product: Product, size: str) -> str:
    if size:
        return f"Размера «{size}» нет в наличии."
    return "Товара нет в наличии."


def _not_enough_message(product: Product, size: str, available: int, in_cart: int) -> str:
    base = (
        f"Недостаточно товара на складе: доступно {available} шт."
        if not size
        else f"Размер «{size}»: на складе {available} шт."
    )
    if in_cart > 0:
        return f"{base} В корзине уже {in_cart}."
    return base
