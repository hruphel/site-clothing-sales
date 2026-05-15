import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api, ApiError } from "../../api";
import ErrorBox from "../../components/ErrorBox";
import { formatPrice } from "../../utils";
import type { Order } from "../../types";

export default function PayPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [number, setNumber] = useState("");
  const [holder, setHolder] = useState("");
  const [expiry, setExpiry] = useState("");
  const [cvc, setCvc] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!id) return;
    api
      .get<Order>(`/api/orders/${id}`)
      .then((o) => {
        if (o.status !== "created") {
          navigate(`/orders/${o.id}`, { replace: true });
        } else {
          setOrder(o);
        }
      })
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Ошибка."));
  }, [id, navigate]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!order) return;
    setSubmitting(true);
    setError(null);
    try {
      const updated = await api.post<Order>(`/api/orders/${order.id}/pay`, {
        card_number: number,
        card_holder: holder,
        card_expiry: expiry,
        card_cvc: cvc,
      });
      navigate(`/orders/${updated.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Платёж не прошёл.");
    } finally {
      setSubmitting(false);
    }
  }

  if (!order) {
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
          <span className="eyebrow">Имитация оплаты</span>
          <h2>Оплата заказа №{order.id}</h2>
        </div>
        <div className="cart-summary cart-summary--inline">
          <div className="muted small">К оплате</div>
          <div className="cart-summary__total">{formatPrice(order.total)} ₽</div>
        </div>
        <p className="muted small">
          Это учебная имитация платёжного шлюза. Реальные деньги не списываются.
        </p>
        <form className="form" onSubmit={onSubmit}>
          <ErrorBox message={error} />
          <label className="form-row">
            <span>Номер карты</span>
            <input
              type="text"
              required
              inputMode="numeric"
              autoComplete="off"
              value={number}
              placeholder="4242 4242 4242 4242"
              onChange={(e) => setNumber(e.target.value)}
            />
          </label>
          <label className="form-row">
            <span>Владелец карты</span>
            <input
              type="text"
              required
              value={holder}
              placeholder="IVAN IVANOV"
              onChange={(e) => setHolder(e.target.value)}
            />
          </label>
          <div className="form-row form-row--double">
            <label>
              <span>Срок (MM/YY)</span>
              <input
                type="text"
                required
                value={expiry}
                placeholder="08/29"
                onChange={(e) => setExpiry(e.target.value)}
              />
            </label>
            <label>
              <span>CVC</span>
              <input
                type="text"
                required
                inputMode="numeric"
                autoComplete="off"
                value={cvc}
                placeholder="123"
                onChange={(e) => setCvc(e.target.value)}
              />
            </label>
          </div>
          <div className="form-actions">
            <button className="btn btn--primary" type="submit" disabled={submitting}>
              {submitting ? "Оплачиваем…" : `Оплатить ${formatPrice(order.total)} ₽`}
            </button>
            <Link to={`/orders/${order.id}`} className="btn btn--ghost">
              Отложить
            </Link>
          </div>
        </form>
      </div>
    </section>
  );
}
