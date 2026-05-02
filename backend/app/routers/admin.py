"""Роутер администратора. Реализует UC-7: модерация заявок на товары."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import desc, func
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..dependencies import get_current_user
from ..models import (
    PRODUCT_STATUS_LABELS_RU,
    Order,
    OrderStatus,
    Product,
    ProductStatus,
    User,
    UserRole,
)
from ..services.delivery import advance_delivery_status
from ..templating import templates
from .seller import _RedirectToLogin

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(user: User | None) -> User:
    if user is None:
        raise _RedirectToLogin
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ только для администраторов.",
        )
    return user


def _status_counts(db: Session) -> dict[ProductStatus, int]:
    rows = (
        db.query(Product.status, func.count(Product.id))
        .group_by(Product.status)
        .all()
    )
    counts = {s: 0 for s in ProductStatus}
    for status_value, count in rows:
        counts[status_value] = count
    return counts


@router.get("", response_class=HTMLResponse)
def dashboard(
    request: Request,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    admin = _require_admin(user)
    counts = _status_counts(db)
    total_users = db.query(func.count(User.id)).scalar() or 0
    return templates.TemplateResponse(
        request,
        "admin/dashboard.html",
        {"user": admin, "counts": counts, "total_users": total_users},
    )


@router.get("/products", response_class=HTMLResponse)
def list_products(
    request: Request,
    status_filter: str = Query("pending", alias="status"),
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    admin = _require_admin(user)

    valid_filters = {s.value for s in ProductStatus} | {"all"}
    if status_filter not in valid_filters:
        status_filter = "pending"

    query = db.query(Product).options(selectinload(Product.seller))
    if status_filter != "all":
        query = query.filter(Product.status == ProductStatus(status_filter))
    products = query.order_by(desc(Product.created_at)).all()

    counts = _status_counts(db)
    return templates.TemplateResponse(
        request,
        "admin/products_list.html",
        {
            "user": admin,
            "products": products,
            "counts": counts,
            "current_filter": status_filter,
            "filters": [
                ("pending", PRODUCT_STATUS_LABELS_RU[ProductStatus.PENDING]),
                ("published", PRODUCT_STATUS_LABELS_RU[ProductStatus.PUBLISHED]),
                ("rejected", PRODUCT_STATUS_LABELS_RU[ProductStatus.REJECTED]),
                ("all", "Все"),
            ],
        },
    )


@router.get("/products/{product_id}", response_class=HTMLResponse)
def product_detail(
    request: Request,
    product_id: int,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    admin = _require_admin(user)
    product = (
        db.query(Product)
        .options(selectinload(Product.seller))
        .filter(Product.id == product_id)
        .first()
    )
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Товар не найден.")
    return templates.TemplateResponse(
        request,
        "admin/product_detail.html",
        {"user": admin, "product": product, "errors": []},
    )


@router.post("/products/{product_id}/approve")
def approve_product(
    product_id: int,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(user)
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Товар не найден.")
    if product.status != ProductStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Можно одобрять только заявки в статусе «На модерации».",
        )
    product.status = ProductStatus.PUBLISHED
    product.rejection_reason = None
    db.commit()
    return RedirectResponse(url="/admin/products?status=pending", status_code=303)


@router.post("/products/{product_id}/reject", response_class=HTMLResponse)
def reject_product(
    request: Request,
    product_id: int,
    reason: str = Form(...),
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    admin = _require_admin(user)
    product = (
        db.query(Product)
        .options(selectinload(Product.seller))
        .filter(Product.id == product_id)
        .first()
    )
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Товар не найден.")
    if product.status != ProductStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Можно отклонять только заявки в статусе «На модерации».",
        )

    reason_clean = reason.strip()
    if not reason_clean:
        return templates.TemplateResponse(
            request,
            "admin/product_detail.html",
            {
                "user": admin,
                "product": product,
                "errors": ["Укажите причину отказа."],
            },
            status_code=400,
        )
    if len(reason_clean) > 500:
        return templates.TemplateResponse(
            request,
            "admin/product_detail.html",
            {
                "user": admin,
                "product": product,
                "errors": ["Причина не должна быть длиннее 500 символов."],
            },
            status_code=400,
        )

    product.status = ProductStatus.REJECTED
    product.rejection_reason = reason_clean
    db.commit()
    return RedirectResponse(url="/admin/products?status=pending", status_code=303)


# ---------- UC-5: управление доставкой админом ----------


@router.get("/orders", response_class=HTMLResponse)
def list_admin_orders(
    request: Request,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    admin = _require_admin(user)
    orders = (
        db.query(Order)
        .options(selectinload(Order.buyer), selectinload(Order.items))
        .filter(Order.status == OrderStatus.PAID)
        .order_by(desc(Order.created_at))
        .all()
    )
    return templates.TemplateResponse(
        request,
        "admin/orders_list.html",
        {"user": admin, "orders": orders},
    )


@router.post("/orders/{order_id}/delivery")
def update_admin_order_delivery(
    order_id: int,
    delivery_status_value: str = Form(..., alias="delivery_status"),
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(user)
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заказ не найден.")
    advance_delivery_status(order, delivery_status_value)
    db.commit()
    return RedirectResponse(url="/admin/orders", status_code=303)
