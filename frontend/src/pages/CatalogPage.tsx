import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { api, ApiError } from "../api";
import ErrorBox from "../components/ErrorBox";
import { formatPrice } from "../utils";
import type { Product } from "../types";

export default function CatalogPage() {
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const [draft, setDraft] = useState(q);
  const [products, setProducts] = useState<Product[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    setProducts(null);
    api
      .get<Product[]>(`/api/catalog${q ? `?q=${encodeURIComponent(q)}` : ""}`)
      .then(setProducts)
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Ошибка загрузки."));
  }, [q]);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = draft.trim();
    if (trimmed) {
      setParams({ q: trimmed });
    } else {
      setParams({});
    }
  }

  return (
    <section className="section">
      <div className="container">
        <div className="section-header">
          <span className="eyebrow">Каталог</span>
          <h2>Опубликованные коллекции</h2>
        </div>

        <form className="search-bar" onSubmit={onSubmit}>
          <input
            type="search"
            placeholder="Найти по названию"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
          />
          <button type="submit" className="btn btn--primary">
            Найти
          </button>
          {q && (
            <button
              type="button"
              className="btn btn--ghost"
              onClick={() => {
                setDraft("");
                setParams({});
              }}
            >
              Сбросить
            </button>
          )}
        </form>

        <ErrorBox message={error} />

        {products === null ? (
          <p className="muted">Загрузка…</p>
        ) : products.length === 0 ? (
          <p className="muted">
            {q ? `Ничего не нашлось по запросу «${q}».` : "Пока нет опубликованных товаров."}
          </p>
        ) : (
          <div className="grid grid--3 grid--gap">
            {products.map((p) => {
              const hasSizes = p.sizes.length > 0;
              const allOut =
                hasSizes && p.sizes.every((s) => (p.stock[s] ?? 0) <= 0);
              const availableSizes = p.sizes.filter((s) => (p.stock[s] ?? 0) > 0);
              return (
                <Link key={p.id} to={`/catalog/${p.id}`} className="product-card">
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
                    {hasSizes && (
                      <div className="muted small">
                        {allOut ? (
                          <em>Нет в наличии</em>
                        ) : (
                          <>В наличии: {availableSizes.join(", ")}</>
                        )}
                      </div>
                    )}
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
