import { useEffect, useState } from "react";

import { api, ApiError } from "../../api";
import DeliveryControl from "../../components/DeliveryControl";
import ErrorBox from "../../components/ErrorBox";
import StatusTag from "../../components/StatusTag";
import { formatDateTime, formatPrice } from "../../utils";
import type { Order } from "../../types";

export default function SellerOrdersPage() {
  const [orders, setOrders] = useState<Order[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<Order[]>("/api/seller/orders")
      .then(setOrders)
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Ошибка."));
  }, []);

  function replace(updated: Order) {
    setOrders((prev) => (prev ? prev.map((o) => (o.id === updated.id ? updated : o)) : prev));
  }

  return (
    <section className="section">
      <div className="container">
        <div className="section-header">
          <span className="eyebrow">Доставка</span>
          <h2>Заказы со своими товарами</h2>
        </div>
        <ErrorBox message={error} />
        {orders === null ? (
          <p className="muted">Загрузка…</p>
        ) : orders.length === 0 ? (
          <p className="muted">Заказов с вашими товарами пока нет.</p>
        ) : (
          <div className="orders-list">
            {orders.map((o) => (
              <div key={o.id} className="order-card">
                <div className="order-card__head">
                  <div>
                    <div className="muted small">№ {o.id} • {formatDateTime(o.paid_at ?? o.created_at)}</div>
                    <div className="order-row__title">
                      Покупатель: {o.buyer_username ?? "—"}
                    </div>
                  </div>
                  <div className="order-row__tags">
                    <StatusTag status={o.status} label={o.status_label} kind="order" />
                    <StatusTag
                      status={o.delivery_status}
                      label={o.delivery_status_label}
                      kind="delivery"
                    />
                  </div>
                  <div className="order-row__total">{formatPrice(o.total)} ₽</div>
                </div>
                <div className="order-card__body">
                  <p className="muted small">
                    {o.recipient_name}, {o.recipient_phone}, {o.delivery_address}
                  </p>
                  <ul className="order-items">
                    {o.items.map((it) => (
                      <li key={it.id}>
                        <div>{it.product_name}</div>
                        <div className="muted small">{it.quantity} × {formatPrice(it.product_price)} ₽</div>
                        <div>{formatPrice(it.line_total)} ₽</div>
                      </li>
                    ))}
                  </ul>
                  <DeliveryControl
                    order={o}
                    onUpdated={replace}
                    endpoint={(id) => `/api/seller/orders/${id}/delivery`}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
