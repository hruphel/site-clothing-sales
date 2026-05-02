"""Корзина покупателя (UC-2)."""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..dependencies import get_current_user
from ..models import CartItem, Product, ProductStatus, User, UserRole
from ..templating import templates
from .seller import _RedirectToLogin

router = APIRouter(prefix="/cart", tags=["cart"])

MAX_QUANTITY = 99


def _require_buyer(user: User | None) -> User:
    if user is None:
        raise _RedirectToLogin
    if user.role != UserRole.BUYER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Корзина доступна только покупателям.",
        )
    return user


def _get_active_cart(db: Session, buyer_id: int) -> list[CartItem]:
    """Возвращает только позиции с актуальными опубликованными товарами."""
    items = (
        db.query(CartItem)
        .options(selectinload(CartItem.product))
        .filter(CartItem.buyer_id == buyer_id)
        .all()
    )
    return [item for item in items if item.product.status == ProductStatus.PUBLISHED]


@router.get("", response_class=HTMLResponse)
def view_cart(
    request: Request,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    buyer = _require_buyer(user)
    items = _get_active_cart(db, buyer.id)
    total = sum((item.line_total for item in items), Decimal("0.00"))
    return templates.TemplateResponse(
        request,
        "cart/view.html",
        {"user": buyer, "items": items, "total": total},
    )


@router.post("/add")
def add_to_cart(
    product_id: int = Form(...),
    quantity: int = Form(1),
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    buyer = _require_buyer(user)
    if quantity < 1 or quantity > MAX_QUANTITY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Количество должно быть от 1 до {MAX_QUANTITY}.",
        )

    product = db.get(Product, product_id)
    if product is None or product.status != ProductStatus.PUBLISHED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Товар не найден.")

    existing = (
        db.query(CartItem)
        .filter(CartItem.buyer_id == buyer.id, CartItem.product_id == product_id)
        .first()
    )
    if existing is None:
        db.add(CartItem(buyer_id=buyer.id, product_id=product_id, quantity=quantity))
    else:
        existing.quantity = min(existing.quantity + quantity, MAX_QUANTITY)
    db.commit()
    return RedirectResponse(url="/cart", status_code=303)


@router.post("/{item_id}/update")
def update_quantity(
    item_id: int,
    quantity: int = Form(...),
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    buyer = _require_buyer(user)
    if quantity < 1 or quantity > MAX_QUANTITY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Количество должно быть от 1 до {MAX_QUANTITY}.",
        )
    item = db.get(CartItem, item_id)
    if item is None or item.buyer_id != buyer.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Позиция не найдена.")
    item.quantity = quantity
    db.commit()
    return RedirectResponse(url="/cart", status_code=303)


@router.post("/{item_id}/remove")
def remove_item(
    item_id: int,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    buyer = _require_buyer(user)
    item = db.get(CartItem, item_id)
    if item is None or item.buyer_id != buyer.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Позиция не найдена.")
    db.delete(item)
    db.commit()
    return RedirectResponse(url="/cart", status_code=303)
