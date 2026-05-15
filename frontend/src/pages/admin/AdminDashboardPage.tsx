import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, ApiError } from "../../api";
import { useAuth } from "../../auth";
import ErrorBox from "../../components/ErrorBox";
import type { AdminCounts } from "../../types";

export default function AdminDashboardPage() {
  const { user } = useAuth();
  const [counts, setCounts] = useState<AdminCounts | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<AdminCounts>("/api/admin/dashboard")
      .then(setCounts)
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Ошибка."));
  }, []);

  return (
    <section className="section">
      <div className="container">
        <div className="section-header">
          <span className="eyebrow">Админ-панель</span>
          <h2>Здравствуйте, {user?.username}</h2>
        </div>
        <ErrorBox message={error} />

        {counts && (
          <div className="counters">
            <div className="counters__item">
              <div className="muted small">На модерации</div>
              <div className="counters__value">{counts.pending}</div>
              <Link to="/admin/products?status=pending" className="card-link">К модерации</Link>
            </div>
            <div className="counters__item">
              <div className="muted small">Опубликовано</div>
              <div className="counters__value">{counts.published}</div>
              <Link to="/admin/products?status=published" className="card-link">Список</Link>
            </div>
            <div className="counters__item">
              <div className="muted small">Отклонено</div>
              <div className="counters__value">{counts.rejected}</div>
              <Link to="/admin/products?status=rejected" className="card-link">Список</Link>
            </div>
            <div className="counters__item">
              <div className="muted small">Всего пользователей</div>
              <div className="counters__value">{counts.total_users}</div>
            </div>
          </div>
        )}

        <div className="grid grid--2 grid--gap" style={{ marginTop: 32 }}>
          <article className="card">
            <h3>Модерация заявок</h3>
            <p>Одобрение и отклонение заявок продавцов.</p>
            <Link to="/admin/products" className="card-link">Открыть</Link>
          </article>
          <article className="card">
            <h3>Доставка заказов</h3>
            <p>Передвигайте статусы доставки оплаченных заказов.</p>
            <Link to="/admin/orders" className="card-link">Открыть</Link>
          </article>
        </div>
      </div>
    </section>
  );
}
