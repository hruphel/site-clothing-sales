import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { api, ApiError } from "../../api";
import ErrorBox from "../../components/ErrorBox";
import StatusTag from "../../components/StatusTag";
import { formatPrice } from "../../utils";
import type { Product } from "../../types";

const FILTERS: { value: string; label: string }[] = [
  { value: "pending", label: "На модерации" },
  { value: "published", label: "Опубликован" },
  { value: "rejected", label: "Отклонён" },
  { value: "all", label: "Все" },
];

export default function AdminProductsPage() {
  const [params, setParams] = useSearchParams();
  const status = params.get("status") ?? "pending";
  const [products, setProducts] = useState<Product[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setProducts(null);
    setError(null);
    api
      .get<Product[]>(`/api/admin/products?status=${encodeURIComponent(status)}`)
      .then(setProducts)
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Ошибка."));
  }, [status]);

  return (
    <section className="section">
      <div className="container">
        <div className="section-header">
          <span className="eyebrow">Модерация</span>
          <h2>Модерация заявок</h2>
        </div>

        <div className="filters">
          {FILTERS.map((f) => (
            <button
              key={f.value}
              type="button"
              className={`filter-pill${f.value === status ? " filter-pill--active" : ""}`}
              onClick={() => setParams({ status: f.value })}
            >
              {f.label}
            </button>
          ))}
        </div>

        <ErrorBox message={error} />

        {products === null ? (
          <p className="muted">Загрузка…</p>
        ) : products.length === 0 ? (
          <p className="muted">Список пуст.</p>
        ) : (
          <div className="grid grid--3 grid--gap">
            {products.map((p) => (
              <Link to={`/admin/products/${p.id}`} key={p.id} className="product-card">
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
                  <div className="muted small">Продавец: {p.seller_username ?? "—"}</div>
                  <StatusTag status={p.status} label={p.status_label} kind="product" />
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
