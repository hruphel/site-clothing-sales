import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, ApiError } from "../../api";
import ErrorBox from "../../components/ErrorBox";
import StatusTag from "../../components/StatusTag";
import { formatPrice } from "../../utils";
import type { Product } from "../../types";

export default function SellerProductsPage() {
  const [products, setProducts] = useState<Product[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<number | null>(null);

  function load() {
    api
      .get<Product[]>("/api/seller/products")
      .then(setProducts)
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Ошибка."));
  }
  useEffect(load, []);

  async function remove(p: Product) {
    if (!confirm("Удалить эту заявку на товар? Действие нельзя отменить.")) return;
    setBusy(p.id);
    setError(null);
    try {
      await api.post(`/api/seller/products/${p.id}/delete`);
      setProducts((prev) => (prev ? prev.filter((it) => it.id !== p.id) : prev));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Не удалось удалить.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="section">
      <div className="container">
        <div className="section-header">
          <span className="eyebrow">Мои товары</span>
          <h2>Мои товары</h2>
          <Link to="/seller/products/new" className="btn btn--primary btn--small">
            Добавить товар
          </Link>
        </div>

        <ErrorBox message={error} />

        {products === null ? (
          <p className="muted">Загрузка…</p>
        ) : products.length === 0 ? (
          <div className="empty-state">
            <p>Заявок пока нет.</p>
            <Link to="/seller/products/new" className="btn btn--primary">
              Добавить первый товар
            </Link>
          </div>
        ) : (
          <div className="grid grid--3 grid--gap">
            {products.map((p) => (
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
                  {p.sizes.length > 0 && (
                    <div className="muted small">
                      Запасы:{" "}
                      {p.sizes
                        .map((s) => `${s} — ${p.stock[s] ?? 0}`)
                        .join(", ")}
                    </div>
                  )}
                  {p.status === "rejected" && p.rejection_reason && (
                    <p className="muted small">Причина отказа: {p.rejection_reason}</p>
                  )}
                  {p.status === "pending" && (
                    <div className="form-actions" style={{ marginTop: 12 }}>
                      <Link to={`/seller/products/${p.id}/edit`} className="btn btn--ghost btn--small">
                        Редактировать
                      </Link>
                      <button
                        type="button"
                        className="btn btn--ghost btn--small btn--danger"
                        onClick={() => void remove(p)}
                        disabled={busy === p.id}
                      >
                        {busy === p.id ? "Удаляем…" : "Удалить"}
                      </button>
                    </div>
                  )}
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
