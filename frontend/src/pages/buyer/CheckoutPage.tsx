import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api, ApiError } from "../../api";
import { useAuth } from "../../auth";
import ErrorBox from "../../components/ErrorBox";
import { formatPrice } from "../../utils";
import type { Cart, Order } from "../../types";

export default function CheckoutPage() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [cart, setCart] = useState<Cart | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [recipientName, setRecipientName] = useState(user?.username ?? "");
  const [recipientPhone, setRecipientPhone] = useState("");
  const [deliveryAddress, setDeliveryAddress] = useState("");
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.get<Cart>("/api/cart")
      .then((c) => {
        setCart(c);
        if (c.items.length === 0) navigate("/cart", { replace: true });
      })
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Ошибка."));
  }, [navigate]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const order = await api.post<Order>("/api/orders/checkout", {
        recipient_name: recipientName,
        recipient_phone: recipientPhone,
        delivery_address: deliveryAddress,
        comment,
      });
      navigate(`/pay/${order.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Не удалось оформить заказ.");
    } finally {
      setSubmitting(false);
    }
  }

  if (!cart) {
    return (
      <section className="section">
        <div className="container">
          <p className="muted">Загрузка…</p>
          <ErrorBox message={error} />
        </div>
      </section>
    );
  }

  return (
    <section className="section">
      <div className="container narrow">
        <div className="section-header">
          <span className="eyebrow">Оформление заказа</span>
          <h2>Оформление заказа</h2>
        </div>

        <div className="cart-summary cart-summary--inline">
          <div className="muted small">К оплате</div>
          <div className="cart-summary__total">{formatPrice(cart.total)} ₽</div>
          <Link to="/cart" className="btn btn--ghost btn--small">
            Назад в корзину
          </Link>
        </div>

        <form className="form" onSubmit={onSubmit}>
          <ErrorBox message={error} />
          <label className="form-row">
            <span>Имя получателя</span>
            <input
              type="text"
              required
              maxLength={160}
              value={recipientName}
              onChange={(e) => setRecipientName(e.target.value)}
            />
          </label>
          <label className="form-row">
            <span>Телефон</span>
            <input
              type="tel"
              required
              value={recipientPhone}
              placeholder="+7 (000) 000-00-00"
              onChange={(e) => setRecipientPhone(e.target.value)}
            />
          </label>
          <label className="form-row">
            <span>Адрес доставки</span>
            <textarea
              required
              maxLength={500}
              rows={3}
              value={deliveryAddress}
              onChange={(e) => setDeliveryAddress(e.target.value)}
            />
          </label>
          <label className="form-row">
            <span>Комментарий (необязательно)</span>
            <textarea
              maxLength={1000}
              rows={3}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
            />
          </label>
          <div className="form-actions">
            <button className="btn btn--primary" type="submit" disabled={submitting}>
              {submitting ? "Создаём заказ…" : "Перейти к оплате"}
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}
