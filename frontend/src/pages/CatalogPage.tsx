import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { api, ApiError } from "../api";
import ErrorBox from "../components/ErrorBox";
import { formatPrice } from "../utils";
import type { Product } from "../types";

type SortKey =
  | "newest"
  | "name_asc"
  | "name_desc"
  | "price_asc"
  | "price_desc"
  | "stock_asc"
  | "stock_desc";

const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: "newest", label: "Сначала новые" },
  { value: "name_asc", label: "Название: А → Я" },
  { value: "name_desc", label: "Название: Я → А" },
  { value: "price_asc", label: "Цена: по возрастанию" },
  { value: "price_desc", label: "Цена: по убыванию" },
  { value: "stock_desc", label: "Сначала где больше в наличии" },
  { value: "stock_asc", label: "Сначала где меньше в наличии" },
];

function totalStock(p: Product): number {
  return Object.values(p.stock).reduce((acc, v) => acc + (Number(v) || 0), 0);
}

export default function CatalogPage() {
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const sortParam = (params.get("sort") ?? "newest") as SortKey;
  const sort: SortKey = SORT_OPTIONS.some((o) => o.value === sortParam) ? sortParam : "newest";
  const [draft, setDraft] = useState(q);
  const [products, setProducts] = useState<Product[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    setProducts(null);
    const qs = new URLSearchParams();
    if (q) qs.set("q", q);
    qs.set("sort", sort);
    api
      .get<Product[]>(`/api/catalog?${qs.toString()}`)
      .then(setProducts)
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Ошибка загрузки."));
  }, [q, sort]);

  function updateParams(next: { q?: string; sort?: SortKey }) {
    const obj: Record<string, string> = {};
    const newQ = next.q !== undefined ? next.q : q;
    const newSort = next.sort !== undefined ? next.sort : sort;
    if (newQ) obj.q = newQ;
    if (newSort !== "newest") obj.sort = newSort;
    setParams(obj);
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    updateParams({ q: draft.trim() });
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
                updateParams({ q: "" });
              }}
            >
              Сбросить
            </button>
          )}
          <label className="search-bar__sort">
            <span className="muted small">Сортировка</span>
            <select
              value={sort}
              onChange={(e) => updateParams({ sort: e.target.value as SortKey })}
            >
              {SORT_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
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
              const stockTotal = totalStock(p);
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
                          <>
                            В наличии: {availableSizes.join(", ")} · всего {stockTotal} шт.
                          </>
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
