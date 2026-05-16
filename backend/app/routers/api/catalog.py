"""Публичный каталог опубликованных товаров."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import asc, desc, func
from sqlalchemy.orm import Session, selectinload

from ...database import get_db
from ...models import Product, ProductStatus
from ...schemas import ProductOut

router = APIRouter(prefix="/catalog", tags=["catalog"])

# Поддерживаемые ключи сортировки. Совпадают с тем, что отдаём фронту.
ALLOWED_SORTS = {"newest", "name_asc", "name_desc", "price_asc", "price_desc", "stock_asc", "stock_desc"}


@router.get("", response_model=list[ProductOut])
def list_catalog(
    q: str = Query("", description="Поиск по названию"),
    sort: str = Query("newest", description="Сортировка: newest|name_asc|name_desc|price_asc|price_desc|stock_asc|stock_desc"),
    db: Session = Depends(get_db),
):
    if sort not in ALLOWED_SORTS:
        sort = "newest"

    query = (
        db.query(Product)
        .options(selectinload(Product.seller))
        .filter(Product.status == ProductStatus.PUBLISHED)
    )
    q_clean = q.strip()
    if q_clean:
        needle = f"%{q_clean.lower()}%"
        query = query.filter(func.lower(Product.name).like(needle))

    # Сортировки по столбцам делаем в БД; в БД нет хорошего способа упорядочить
    # по сумме JSON, поэтому stock_* досортировываем в Python после выборки.
    if sort == "name_asc":
        query = query.order_by(func.lower(Product.name).asc(), Product.id.asc())
    elif sort == "name_desc":
        query = query.order_by(func.lower(Product.name).desc(), Product.id.desc())
    elif sort == "price_asc":
        query = query.order_by(asc(Product.price), Product.id.asc())
    elif sort == "price_desc":
        query = query.order_by(desc(Product.price), Product.id.desc())
    else:
        # newest и заглушка для stock_* — стабильный порядок до досортировки.
        query = query.order_by(desc(Product.created_at), Product.id.desc())

    products = query.all()

    if sort in ("stock_asc", "stock_desc"):
        def total_stock(p: Product) -> int:
            return sum(int(v) for v in p.sizes_stock.values() if isinstance(v, (int, float)))
        products.sort(key=total_stock, reverse=(sort == "stock_desc"))

    return [ProductOut.from_model(p) for p in products]


@router.get("/{product_id}", response_model=ProductOut)
def catalog_detail(product_id: int, db: Session = Depends(get_db)):
    product = (
        db.query(Product)
        .options(selectinload(Product.seller))
        .filter(Product.id == product_id, Product.status == ProductStatus.PUBLISHED)
        .first()
    )
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Товар не найден.")
    return ProductOut.from_model(product)
