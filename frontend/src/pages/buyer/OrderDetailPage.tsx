import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, ApiError } from "../../api";
import DeliveryTrack from "../../components/DeliveryTrack";
import ErrorBox from "../../components/ErrorBox";
import StatusTag from "../../components/StatusTag";
import { formatDateTime, formatPrice } from "../../utils";
import type { Order } from "../../types";

export default function OrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!id) return;
    api.get<Order>(`/api/orders/${id}`).then(setOrder).catch((err) => {
      setError(err instanceof ApiError ? err.detail : "Не удалось загрузить заказ.");
    });
  }, [id]);

  async function cancel() {
    if (!order) return;
    if (!confirm("Отменить этот заказ?")) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await api.post<Order>(`/api/orders/${order.id}/cancel`);
      setOrder(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Не удалось отменить.");
    } finally {
      setBusy(false);
    }
  }

  if (error && !order) {
    return (
      <section className="section">
        <div className="container">
          <h1>Заказ недоступен</h1>
          <ErrorBox message={error} />
        </div>
      </section>
    );
  }

  if (!order) {
    return (
      <section className="section">
        <div className="container">
          <p className="muted">Загрузка…</p>
        </div>
      </section>
    );
  }

  return (
    <section className="section">
      <div className="container">
        <div className="section-header">
          <span className="eyebrow">Заказ № {order.id}</span>
          <h2>{order.status_label}</h2>
        </div>

        <ErrorBox message={error} />

        <div className="grid grid--2 grid--gap">
          <div className="card">
            <h3>Состав заказа</h3>
            <ul className="order-items">
              {order.items.map((it) => (
                <li key={it.id}>
                  <div>
                    <div>{it.product_name}</div>
                    {it.sizes.length > 0 && (
                      <div className="muted small">Размеры: {it.sizes.join(", ")}</div>
                    )}
                  </div>
                  <div className="muted small">{it.quantity} × {formatPrice(it.product_price)} ₽</div>
                  <div>{formatPrice(it.line_total)} ₽</div>
                </li>
              ))}
            </ul>
            <div className="order-total">
              <span>Итого</span>
              <strong>{formatPrice(order.total)} ₽</strong>
            </div>
            {order.status === "created" && (
              <div className="form-actions">
                <Link to={`/pay/${order.id}`} className="btn btn--primary">
                  Оплатить
                </Link>
                <button className="btn btn--ghost" type="button" onClick={cancel} disabled={busy}>
                  {busy ? "Отменяем…" : "Отменить заказ"}
                </button>
              </div>
            )}
          </div>

          <div className="card">
            <h3>Доставка</h3>
            <p className="muted small">
              Создан: {formatDateTime(order.created_at)}<br />
              {order.paid_at && <>Оплачен: {formatDateTime(order.paid_at)}<br /></>}
            </p>
            <p>
              <strong>Получатель:</strong> {order.recipient_name}, {order.recipient_phone}
              <br />
              <strong>Адрес:</strong> {order.delivery_address}
            </p>
            {order.comment && (
              <p>
                <strong>Комментарий:</strong> {order.comment}
              </p>
            )}

            {order.delivery_visible ? (
              <>
                <div style={{ margin: "16px 0" }}>
                  <StatusTag
                    status={order.delivery_status}
                    label={order.delivery_status_label}
                    kind="delivery"
                  />
                </div>
                <DeliveryTrack order={order} />
              </>
            ) : (
              <p className="muted">
                Статус доставки появится после оплаты заказа.
              </p>
            )}

            {order.receipt && (
              <div className="form-actions" style={{ marginTop: 16 }}>
                <a
                  className="btn btn--ghost"
                  href={order.receipt.pdf_url}
                  target="_blank"
                  rel="noreferrer noopener"
                >
                  Скачать чек (PDF) — № {order.receipt.receipt_number}
                </a>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
