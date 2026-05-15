import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, ApiError } from "../../api";
import ErrorBox from "../../components/ErrorBox";
import StatusTag from "../../components/StatusTag";
import { formatDateTime, formatPrice } from "../../utils";
import type { Order } from "../../types";

export default function OrdersListPage() {
  const [orders, setOrders] = useState<Order[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<Order[]>("/api/orders")
      .then(setOrders)
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Ошибка."));
  }, []);

  return (
    <section className="section">
      <div className="container">
        <div className="section-header">
          <span className="eyebrow">Заказы</span>
          <h2>Мои заказы</h2>
        </div>
        <ErrorBox message={error} />
        {orders === null ? (
          <p className="muted">Загрузка…</p>
        ) : orders.length === 0 ? (
          <div className="empty-state">
            <p>Заказов пока нет.</p>
            <Link to="/catalog" className="btn btn--primary">
              Перейти в каталог
            </Link>
          </div>
        ) : (
          <div className="orders-list">
            {orders.map((o) => (
              <Link key={o.id} to={`/orders/${o.id}`} className="order-row">
                <div>
                  <div className="muted small">№ {o.id} • {formatDateTime(o.created_at)}</div>
                  <div className="order-row__title">
                    {o.items.map((it) => it.product_name).join(", ")}
                  </div>
                </div>
                <div className="order-row__tags">
                  <StatusTag status={o.status} label={o.status_label} kind="order" />
                  {o.delivery_visible && (
                    <StatusTag
                      status={o.delivery_status}
                      label={o.delivery_status_label}
                      kind="delivery"
                    />
                  )}
                </div>
                <div className="order-row__total">{formatPrice(o.total)} ₽</div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
