import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api, ApiError } from "../../api";
import ErrorBox from "../../components/ErrorBox";
import StatusTag from "../../components/StatusTag";
import { formatDateTime, formatPrice } from "../../utils";
import type { Product } from "../../types";

export default function AdminProductDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [product, setProduct] = useState<Product | null>(null);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!id) return;
    api
      .get<Product>(`/api/admin/products/${id}`)
      .then(setProduct)
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Не удалось загрузить."));
  }, [id]);

  if (error && !product) {
    return (
      <section className="section">
        <div className="container">
          <h1>Не удалось открыть</h1>
          <ErrorBox message={error} />
        </div>
      </section>
    );
  }
  if (!product) {
    return (
      <section className="section">
        <div className="container">
          <p className="muted">Загрузка…</p>
        </div>
      </section>
    );
  }

  async function approve() {
    if (!product) return;
    setBusy(true);
    setError(null);
    try {
      await api.post(`/api/admin/products/${product.id}/approve`);
      navigate("/admin/products?status=pending");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Не удалось одобрить.");
    } finally {
      setBusy(false);
    }
  }

  async function reject(e: React.FormEvent) {
    e.preventDefault();
    if (!product) return;
    setBusy(true);
    setError(null);
    try {
      await api.post(`/api/admin/products/${product.id}/reject`, { reason });
      navigate("/admin/products?status=pending");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Не удалось отклонить.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="section">
      <div className="container">
        <div className="section-header">
          <span className="eyebrow">Модерация</span>
          <h2>{product.name}</h2>
          <StatusTag status={product.status} label={product.status_label} kind="product" />
        </div>

        <ErrorBox message={error} />

        <div className="product-detail">
          <div className="product-detail__image">
            {product.image_url ? (
              <img src={product.image_url} alt={product.name} />
            ) : (
              <div className="product-card__placeholder large">Без фото</div>
            )}
          </div>
          <div className="product-detail__body">
            <div className="muted small">Продавец: {product.seller_username ?? "—"}</div>
            <div className="muted small">Создан: {formatDateTime(product.created_at)}</div>
            <div className="product-detail__price">{formatPrice(product.price)} ₽</div>
            {product.sizes.length > 0 && (
              <div className="muted">Размеры: {product.sizes.join(", ")}</div>
            )}
            {product.description && <p>{product.description}</p>}

            {product.status === "rejected" && product.rejection_reason && (
              <div className="alert alert--info">
                <strong>Причина отказа:</strong> {product.rejection_reason}
              </div>
            )}

            {product.status === "pending" ? (
              <>
                <div className="form-actions">
                  <button className="btn btn--primary" type="button" onClick={approve} disabled={busy}>
                    {busy ? "Применяем…" : "Одобрить"}
                  </button>
                </div>
                <form className="form" onSubmit={reject}>
                  <label className="form-row">
                    <span>Причина отказа</span>
                    <textarea
                      maxLength={500}
                      rows={3}
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                    />
                  </label>
                  <div className="form-actions">
                    <button
                      className="btn btn--ghost btn--danger"
                      type="submit"
                      disabled={busy || !reason.trim()}
                    >
                      Отклонить
                    </button>
                  </div>
                </form>
              </>
            ) : (
              <p>
                <Link to="/admin/products" className="btn btn--ghost">
                  К списку
                </Link>
              </p>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
