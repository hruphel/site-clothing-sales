"""Публичный каталог опубликованных товаров (UC-2)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy import desc, func
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..dependencies import get_current_user
from ..models import Product, ProductStatus, User
from ..templating import templates

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("", response_class=HTMLResponse)
def list_catalog(
    request: Request,
    q: str = Query("", description="Поиск по названию"),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    query = (
        db.query(Product)
        .options(selectinload(Product.seller))
        .filter(Product.status == ProductStatus.PUBLISHED)
    )
    q_clean = q.strip()
    if q_clean:
        # Используем lower() явно: SQLite LIKE/ILIKE регистронезависим
        # только для ASCII; lower() корректно работает с кириллицей.
        needle = f"%{q_clean.lower()}%"
        query = query.filter(func.lower(Product.name).like(needle))
    products = query.order_by(desc(Product.created_at)).all()
    return templates.TemplateResponse(
        request,
        "catalog/list.html",
        {"user": user, "products": products, "query": q_clean},
    )


@router.get("/{product_id}", response_class=HTMLResponse)
def catalog_detail(
    request: Request,
    product_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    product = (
        db.query(Product)
        .options(selectinload(Product.seller))
        .filter(Product.id == product_id, Product.status == ProductStatus.PUBLISHED)
        .first()
    )
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Товар не найден.")
    return templates.TemplateResponse(
        request,
        "catalog/detail.html",
        {"user": user, "product": product},
    )
