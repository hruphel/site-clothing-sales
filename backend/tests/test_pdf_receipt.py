"""PDF-чек содержит реальный шрифт DejaVu (если есть в системе), а не fallback в Helvetica."""
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest


def test_render_receipt_pdf_writes_file_with_cyrillic_font(_isolated_env):
    from app.database import SessionLocal, init_db  # type: ignore  # noqa: PLC0415
    from app.models import (  # type: ignore  # noqa: PLC0415
        DeliveryStatus,
        Order,
        OrderItem,
        OrderStatus,
        User,
        UserRole,
    )
    from app.services.receipts import (  # type: ignore  # noqa: PLC0415
        _register_unicode_font,
        render_receipt_pdf,
    )

    init_db()
    regular, _ = _register_unicode_font()
    # На большинстве Linux-машин (включая Docker-образ с fonts-dejavu-core) ожидается DejaVu.
    # На системах без шрифта тест пропустим — он защищает только от «случайного» fallback в Docker.
    if regular != "DejaVuSans":
        pytest.skip(f"Шрифт DejaVu в системе недоступен (registered={regular})")

    with SessionLocal() as db:
        u = User(username="buy_pdf", email="bp@example.com", password_hash="x", role=UserRole.BUYER)
        db.add(u)
        db.commit()
        db.refresh(u)
        order = Order(
            buyer_id=u.id,
            recipient_name="Алишер Кириллов",
            recipient_phone="+7 999 000-00-00",
            delivery_address="Москва, ул. Тверская, д. 1",
            comment="Звонить заранее, спасибо!",
            total=Decimal("1500.00"),
            status=OrderStatus.PAID,
            delivery_status=DeliveryStatus.PROCESSING,
        )
        db.add(order)
        db.commit()
        db.refresh(order)
        db.add(
            OrderItem(
                order_id=order.id,
                product_id=None,
                product_name="Платье «Весна»",
                product_price=Decimal("1500.00"),
                sizes="S",
                quantity=1,
            )
        )
        db.commit()
        db.refresh(order)

        fn = render_receipt_pdf(order, "RCP-20251115-TEST00", "TXN-DEADBEEF", datetime.now(timezone.utc))

    path = Path(_isolated_env) / "receipts" / fn
    assert path.exists()
    raw = path.read_bytes()
    assert b"DejaVu" in raw
