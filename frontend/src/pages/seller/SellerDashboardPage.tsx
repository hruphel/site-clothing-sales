import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, ApiError } from "../../api";
import { useAuth } from "../../auth";
import ErrorBox from "../../components/ErrorBox";
import StatusTag from "../../components/StatusTag";
import { formatPrice } from "../../utils";
import type { SellerDashboard } from "../../types";

export default function SellerDashboardPage() {
  const { user } = useAuth();
  const [data, setData] = useState<SellerDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<SellerDashboard>("/api/seller/dashboard")
      .then(setData)
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Ошибка."));
  }, []);

  return (
    <section className="section">
      <div className="container">
        <div className="section-header">
          <span className="eyebrow">Кабинет продавца</span>
          <h2>Здравствуйте, {user?.username}</h2>
        </div>
        <ErrorBox message={error} />

        <div className="grid grid--3">
          <article className="card">
            <h3>Мои товары</h3>
            <p>Заявки и опубликованные товары — добавляйте, редактируйте, удаляйте pending.</p>
            <Link to="/seller/products" className="card-link">
              Открыть список
            </Link>
          </article>
          <article className="card">
            <h3>Новая заявка</h3>
            <p>Заполните форму — после модерации товар появится в каталоге.</p>
            <Link to="/seller/products/new" className="card-link">
              Добавить товар
            </Link>
          </article>
          <article className="card">
            <h3>Заказы и доставка</h3>
            <p>Меняйте статус доставки заказов, в которых есть ваши товары.</p>
            <Link to="/seller/orders" className="card-link">
              К заказам
            </Link>
          </article>
        </div>

        {data && (
          <>
            <div className="counters">
              <div className="counters__item">
                <div className="muted small">На модерации</div>
                <div className="counters__value">{data.counts.pending ?? 0}</div>
              </div>
              <div className="counters__item">
                <div className="muted small">Опубликовано</div>
                <div className="counters__value">{data.counts.published ?? 0}</div>
              </div>
              <div className="counters__item">
                <div className="muted small">Отклонено</div>
                <div className="counters__value">{data.counts.rejected ?? 0}</div>
              </div>
            </div>

            {data.recent.length > 0 && (
              <div className="grid grid--3 grid--gap" style={{ marginTop: 24 }}>
                {data.recent.map((p) => (
                  <article key={p.id} className="product-card">
                    <div className="product-card__image">
                      {p.image_url ? (
                        <img src={p.image_url} alt={p.name} />
                      ) : (
                        <div className="product-card__placeholder">Без фото</div>
                      )}
                    </div>
                    <div className="product-card__body">
                      <h3>{p.name}</h3>
                      <div className="product-card__price">{formatPrice(p.price)} ₽</div>
                      <StatusTag status={p.status} label={p.status_label} kind="product" />
                    </div>
                  </article>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}
