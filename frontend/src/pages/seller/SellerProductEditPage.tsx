import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { api, ApiError } from "../../api";
import ErrorBox from "../../components/ErrorBox";
import ProductForm from "./ProductForm";
import type { Product } from "../../types";

export default function SellerProductEditPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [product, setProduct] = useState<Product | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    api
      .get<Product>(`/api/seller/products/${id}`)
      .then(setProduct)
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Ошибка загрузки."));
  }, [id]);

  if (error && !product) {
    return (
      <section className="section">
        <div className="container">
          <h1>Не удалось открыть редактор</h1>
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
  if (product.status !== "pending") {
    return (
      <section className="section">
        <div className="container">
          <h1>Редактирование недоступно</h1>
          <p className="muted">
            Редактировать можно только заявки в статусе «На модерации». Текущий статус: {product.status_label}.
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className="section">
      <div className="container narrow">
        <div className="section-header">
          <span className="eyebrow">Редактирование заявки</span>
          <h2>{product.name}</h2>
        </div>
        <ProductForm
          submitLabel="Сохранить изменения"
          showRemoveImage
          initial={{
            name: product.name,
            price: product.price,
            stock: product.stock,
            description: product.description,
            imageUrl: product.image_url,
          }}
          onSubmit={async (form) => {
            await api.postForm(`/api/seller/products/${product.id}/edit`, form);
            navigate("/seller/products");
          }}
        />
      </div>
    </section>
  );
}
