import enum
import json
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


# Использовать как «по умолчанию хватает на всех» для данных, у которых нет
# явно проставленного запаса (например, продукты, созданные до появления
# колонки `stock_json`).
LEGACY_STOCK_DEFAULT = 99


class UserRole(str, enum.Enum):
    """Роли пользователей в системе."""

    BUYER = "buyer"
    SELLER = "seller"
    ADMIN = "admin"


ROLE_LABELS_RU: dict[UserRole, str] = {
    UserRole.BUYER: "Покупатель",
    UserRole.SELLER: "Продавец",
    UserRole.ADMIN: "Администратор",
}


class ProductStatus(str, enum.Enum):
    """Статус заявки на публикацию товара (UC-6 / UC-7)."""

    PENDING = "pending"
    PUBLISHED = "published"
    REJECTED = "rejected"


PRODUCT_STATUS_LABELS_RU: dict[ProductStatus, str] = {
    ProductStatus.PENDING: "На модерации",
    ProductStatus.PUBLISHED: "Опубликован",
    ProductStatus.REJECTED: "Отклонён",
}


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False, length=16),
        nullable=False,
        default=UserRole.BUYER,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    products: Mapped[list["Product"]] = relationship(
        back_populates="seller",
        cascade="all, delete-orphan",
    )
    cart_items: Mapped[list["CartItem"]] = relationship(
        back_populates="buyer",
        cascade="all, delete-orphan",
    )
    orders: Mapped[list["Order"]] = relationship(
        back_populates="buyer",
        cascade="all, delete-orphan",
    )

    @property
    def role_label(self) -> str:
        return ROLE_LABELS_RU.get(self.role, self.role.value)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    # 20 размеров * 8 символов + 19 разделителей ", " = 198, берём 200 с запасом.
    sizes: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    # JSON-словарь {"S": 5, "M": 10, ...}: запас на складе по каждому размеру.
    stock_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    image_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[ProductStatus] = mapped_column(
        Enum(ProductStatus, native_enum=False, length=16),
        nullable=False,
        default=ProductStatus.PENDING,
        index=True,
    )
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    seller_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    seller: Mapped[User] = relationship(back_populates="products")

    @property
    def status_label(self) -> str:
        return PRODUCT_STATUS_LABELS_RU.get(self.status, self.status.value)

    @property
    def sizes_list(self) -> list[str]:
        return [s.strip() for s in self.sizes.split(",") if s.strip()]

    @property
    def sizes_stock(self) -> dict[str, int]:
        """Запас по размерам. Для старых записей без stock_json — fallback на LEGACY_STOCK_DEFAULT."""
        try:
            raw = json.loads(self.stock_json or "{}")
        except (ValueError, TypeError):
            raw = {}
        parsed: dict[str, int] = {}
        for key, value in raw.items():
            try:
                parsed[str(key)] = max(0, int(value))
            except (ValueError, TypeError):
                continue
        # Легаси: продукт, у которого ещё не проставлен stock, но есть sizes.
        if not parsed:
            return {s: LEGACY_STOCK_DEFAULT for s in self.sizes_list}
        return parsed


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (
        UniqueConstraint("buyer_id", "product_id", "size", name="uq_cart_buyer_product_size"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    buyer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    size: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    buyer: Mapped[User] = relationship(back_populates="cart_items")
    product: Mapped[Product] = relationship()

    @property
    def line_total(self) -> Decimal:
        return (self.product.price * self.quantity).quantize(Decimal("0.01"))


class OrderStatus(str, enum.Enum):
    """Статус заказа (UC-3 / UC-4)."""

    CREATED = "created"  # оформлен, ожидает оплаты
    PAID = "paid"  # оплачен (UC-4)
    CANCELLED = "cancelled"  # отменён до оплаты


ORDER_STATUS_LABELS_RU: dict[OrderStatus, str] = {
    OrderStatus.CREATED: "Ожидает оплаты",
    OrderStatus.PAID: "Оплачен",
    OrderStatus.CANCELLED: "Отменён",
}


class DeliveryStatus(str, enum.Enum):
    """Статус доставки заказа (UC-5). Имеет смысл только после оплаты."""

    PROCESSING = "processing"  # ждёт отправки
    SHIPPED = "shipped"  # передан в доставку
    IN_TRANSIT = "in_transit"  # в пути
    DELIVERED = "delivered"  # доставлен


# Допустимые переходы вперёд по конвейеру; назад двигаться нельзя.
DELIVERY_STATUS_ORDER: list[DeliveryStatus] = [
    DeliveryStatus.PROCESSING,
    DeliveryStatus.SHIPPED,
    DeliveryStatus.IN_TRANSIT,
    DeliveryStatus.DELIVERED,
]


DELIVERY_STATUS_LABELS_RU: dict[DeliveryStatus, str] = {
    DeliveryStatus.PROCESSING: "Готовится к отправке",
    DeliveryStatus.SHIPPED: "Передан в доставку",
    DeliveryStatus.IN_TRANSIT: "В пути",
    DeliveryStatus.DELIVERED: "Доставлен",
}


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    buyer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, native_enum=False, length=16),
        nullable=False,
        default=OrderStatus.CREATED,
        index=True,
    )
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    # Снапшот адреса доставки (на момент оформления).
    recipient_name: Mapped[str] = mapped_column(String(160), nullable=False)
    recipient_phone: Mapped[str] = mapped_column(String(40), nullable=False)
    delivery_address: Mapped[str] = mapped_column(String(500), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # UC-5: статус доставки. Активен после перехода заказа в PAID.
    delivery_status: Mapped[DeliveryStatus] = mapped_column(
        Enum(DeliveryStatus, native_enum=False, length=16),
        nullable=False,
        default=DeliveryStatus.PROCESSING,
        index=True,
    )
    delivery_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    buyer: Mapped[User] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderItem.id",
    )
    receipt: Mapped["Receipt | None"] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        uselist=False,
    )

    @property
    def status_label(self) -> str:
        return ORDER_STATUS_LABELS_RU.get(self.status, self.status.value)

    @property
    def delivery_status_label(self) -> str:
        return DELIVERY_STATUS_LABELS_RU.get(self.delivery_status, self.delivery_status.value)

    @property
    def delivery_visible(self) -> bool:
        """Имеет смысл показывать доставку только после оплаты."""
        return self.status == OrderStatus.PAID


class OrderItem(Base):
    """Позиция заказа: снапшот товара (имя, цена) + количество."""

    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    product_name: Mapped[str] = mapped_column(String(160), nullable=False)
    product_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    sizes: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    order: Mapped[Order] = relationship(back_populates="items")
    product: Mapped[Product | None] = relationship()

    @property
    def line_total(self) -> Decimal:
        return (self.product_price * self.quantity).quantize(Decimal("0.01"))


class Receipt(Base):
    """Чек об оплате заказа (UC-4)."""

    __tablename__ = "receipts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    receipt_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    transaction_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    pdf_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    order: Mapped[Order] = relationship(back_populates="receipt")

    @property
    def pdf_url(self) -> str:
        """Относительный URL для скачивания PDF (см. /receipts/{filename})."""
        return f"/receipts/{self.pdf_filename}"
