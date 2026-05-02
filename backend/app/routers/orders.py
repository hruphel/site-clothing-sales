"""UC-3 (оформление заказа) + UC-4 (имитация оплаты + чек+PDF)."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session, selectinload

from ..config import settings
from ..database import get_db
from ..dependencies import get_current_user
from ..models import (
    CartItem,
    Order,
    OrderItem,
    OrderStatus,
    Product,
    ProductStatus,
    Receipt,
    User,
    UserRole,
)
from ..services.receipts import (
    generate_receipt_number,
    generate_transaction_id,
    render_receipt_pdf,
)
from ..templating import templates
from .seller import _RedirectToLogin

router = APIRouter(tags=["orders"])

NAME_MAX = 160
ADDRESS_MAX = 500
COMMENT_MAX = 1000
PHONE_PATTERN = re.compile(r"^[\d\+\-\(\) ]{6,40}$")


def _require_buyer(user: User | None) -> User:
    if user is None:
        raise _RedirectToLogin
    if user.role != UserRole.BUYER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Оформление заказа доступно только покупателям.",
        )
    return user


def _active_cart(db: Session, buyer_id: int) -> list[CartItem]:
    items = (
        db.query(CartItem)
        .options(selectinload(CartItem.product))
        .filter(CartItem.buyer_id == buyer_id)
        .all()
    )
    return [i for i in items if i.product.status == ProductStatus.PUBLISHED]


def _own_order_or_404(db: Session, buyer: User, order_id: int) -> Order:
    order = (
        db.query(Order)
        .options(
            selectinload(Order.items),
            selectinload(Order.receipt),
        )
        .filter(Order.id == order_id, Order.buyer_id == buyer.id)
        .first()
    )
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заказ не найден.")
    return order


# --- UC-3: оформление заказа ---


@router.get("/checkout", response_class=HTMLResponse)
def checkout_form(
    request: Request,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    buyer = _require_buyer(user)
    items = _active_cart(db, buyer.id)
    if not items:
        # Корзина пустая — на форме оформления делать нечего.
        return RedirectResponse(url="/cart", status_code=303)
    total = sum((i.line_total for i in items), Decimal("0.00"))
    return templates.TemplateResponse(
        request,
        "checkout/address.html",
        {
            "user": buyer,
            "items": items,
            "total": total,
            "errors": [],
            "form": {
                "recipient_name": buyer.username,
                "recipient_phone": "",
                "delivery_address": "",
                "comment": "",
            },
        },
    )


@router.post("/checkout", response_class=HTMLResponse)
def checkout_submit(
    request: Request,
    recipient_name: str = Form(...),
    recipient_phone: str = Form(...),
    delivery_address: str = Form(...),
    comment: str = Form(""),
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    buyer = _require_buyer(user)
    items = _active_cart(db, buyer.id)
    if not items:
        return RedirectResponse(url="/cart", status_code=303)

    errors: list[str] = []
    name = recipient_name.strip()
    phone = recipient_phone.strip()
    address = delivery_address.strip()
    comment_clean = comment.strip()

    if not name:
        errors.append("Укажите имя получателя.")
    elif len(name) > NAME_MAX:
        errors.append(f"Имя получателя не должно быть длиннее {NAME_MAX} символов.")
    if not phone:
        errors.append("Укажите телефон.")
    elif not PHONE_PATTERN.match(phone):
        errors.append("Телефон должен содержать 6–40 символов: цифры, пробелы, +, -, (, ).")
    if not address:
        errors.append("Укажите адрес доставки.")
    elif len(address) > ADDRESS_MAX:
        errors.append(f"Адрес не должен быть длиннее {ADDRESS_MAX} символов.")
    if len(comment_clean) > COMMENT_MAX:
        errors.append(f"Комментарий не должен быть длиннее {COMMENT_MAX} символов.")

    if errors:
        total = sum((i.line_total for i in items), Decimal("0.00"))
        return templates.TemplateResponse(
            request,
            "checkout/address.html",
            {
                "user": buyer,
                "items": items,
                "total": total,
                "errors": errors,
                "form": {
                    "recipient_name": name,
                    "recipient_phone": phone,
                    "delivery_address": address,
                    "comment": comment_clean,
                },
            },
            status_code=400,
        )

    total = sum((i.line_total for i in items), Decimal("0.00"))
    order = Order(
        buyer_id=buyer.id,
        status=OrderStatus.CREATED,
        total=total,
        recipient_name=name,
        recipient_phone=phone,
        delivery_address=address,
        comment=comment_clean,
    )
    db.add(order)
    db.flush()

    for ci in items:
        db.add(OrderItem(
            order_id=order.id,
            product_id=ci.product.id,
            product_name=ci.product.name,
            product_price=ci.product.price,
            sizes=ci.product.sizes,
            quantity=ci.quantity,
        ))

    # Корзина очищается при создании заказа (как у большинства магазинов).
    db.query(CartItem).filter(CartItem.buyer_id == buyer.id).delete()
    db.commit()

    return RedirectResponse(url=f"/pay/{order.id}", status_code=303)


# --- UC-4: имитация оплаты ---


@router.get("/pay/{order_id}", response_class=HTMLResponse)
def pay_form(
    request: Request,
    order_id: int,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    buyer = _require_buyer(user)
    order = _own_order_or_404(db, buyer, order_id)
    if order.status != OrderStatus.CREATED:
        # Уже оплачен/отменён — переходим на детальную страницу заказа.
        return RedirectResponse(url=f"/orders/{order.id}", status_code=303)
    return templates.TemplateResponse(
        request,
        "checkout/pay.html",
        {"user": buyer, "order": order, "errors": []},
    )


@router.post("/pay/{order_id}")
def pay_submit(
    order_id: int,
    card_number: str = Form(""),
    card_holder: str = Form(""),
    card_expiry: str = Form(""),
    card_cvc: str = Form(""),
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    buyer = _require_buyer(user)
    order = _own_order_or_404(db, buyer, order_id)
    if order.status != OrderStatus.CREATED:
        return RedirectResponse(url=f"/orders/{order.id}", status_code=303)

    # Имитация оплаты: валидируем поля очень мягко, никакого реального шлюза нет.
    digits_only = re.sub(r"\s+", "", card_number)
    if not digits_only.isdigit() or not (12 <= len(digits_only) <= 19):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Номер карты должен содержать 12–19 цифр.",
        )
    if not card_holder.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Укажите владельца карты.",
        )
    if not re.match(r"^\d{2}/\d{2}$", card_expiry.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Срок действия — в формате MM/YY.",
        )
    if not re.match(r"^\d{3,4}$", card_cvc.strip()):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CVC — 3 или 4 цифры.")

    issued_at = datetime.now(timezone.utc)
    receipt_number = generate_receipt_number(issued_at)
    transaction_id = generate_transaction_id()

    # Меняем статус и фиксируем чек.
    order.status = OrderStatus.PAID
    order.paid_at = issued_at
    # UC-5: после оплаты конвейер доставки активен; стартуем с PROCESSING.
    order.delivery_updated_at = issued_at
    pdf_filename = render_receipt_pdf(order, receipt_number, transaction_id, issued_at)
    receipt = Receipt(
        order_id=order.id,
        receipt_number=receipt_number,
        transaction_id=transaction_id,
        pdf_filename=pdf_filename,
    )
    db.add(receipt)
    db.commit()

    return RedirectResponse(url=f"/orders/{order.id}", status_code=303)


# --- Просмотр заказов ---


@router.get("/orders", response_class=HTMLResponse)
def list_orders(
    request: Request,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    buyer = _require_buyer(user)
    orders = (
        db.query(Order)
        .options(selectinload(Order.items), selectinload(Order.receipt))
        .filter(Order.buyer_id == buyer.id)
        .order_by(desc(Order.created_at))
        .all()
    )
    return templates.TemplateResponse(
        request,
        "orders/list.html",
        {"user": buyer, "orders": orders},
    )


@router.get("/orders/{order_id}", response_class=HTMLResponse)
def order_detail(
    request: Request,
    order_id: int,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    buyer = _require_buyer(user)
    order = _own_order_or_404(db, buyer, order_id)
    return templates.TemplateResponse(
        request,
        "orders/detail.html",
        {"user": buyer, "order": order},
    )


@router.post("/orders/{order_id}/cancel")
def cancel_order(
    order_id: int,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    buyer = _require_buyer(user)
    order = _own_order_or_404(db, buyer, order_id)
    if order.status != OrderStatus.CREATED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Отменить можно только неоплаченный заказ.",
        )
    order.status = OrderStatus.CANCELLED
    db.commit()
    return RedirectResponse(url=f"/orders/{order.id}", status_code=303)


# --- Скачивание чека (UC-4) ---


@router.get("/receipts/{filename}")
def download_receipt(
    filename: str,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Отдаёт PDF чека только покупателю-владельцу заказа.

    Имя файла валидируется как RCP-YYYYMMDD-XXXXXX.pdf, чтобы не было
    обхода каталога.
    """
    if not re.match(r"^RCP-\d{8}-[A-F0-9]{6}\.pdf$", filename):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Чек не найден.")
    if user is None:
        raise _RedirectToLogin
    receipt = (
        db.query(Receipt)
        .options(selectinload(Receipt.order))
        .filter(Receipt.pdf_filename == filename)
        .first()
    )
    if receipt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Чек не найден.")
    if receipt.order.buyer_id != user.id and user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Доступ запрещён.")
    path = settings.receipts_dir / filename
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Файл чека отсутствует.")
    return FileResponse(
        path=str(path),
        media_type="application/pdf",
        filename=filename,
    )
