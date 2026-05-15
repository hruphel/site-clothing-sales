import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api, ApiError } from "../api";
import { useAuth } from "../auth";
import ErrorBox from "../components/ErrorBox";
import { formatPrice } from "../utils";
import type { Product } from "../types";

export default function CatalogDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [product, setProduct] = useState<Product | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [quantity, setQuantity] = useState(1);
  const [selectedSize, setSelectedSize] = useState<string>("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!id) return;
    setError(null);
    setProduct(null);
    api
      .get<Product>(`/api/catalog/${id}`)
      .then((p) => {
        setProduct(p);
        // Автоматически выбираем первый размер с положительным запасом.
        const firstAvailable = p.sizes.find((s) => (p.stock[s] ?? 0) > 0);
        setSelectedSize(firstAvailable ?? "");
      })
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Не удалось загрузить."));
  }, [id]);

  const availableForSize = useMemo(() => {
    if (!product) return 0;
    if (product.sizes.length === 0) return 99;
    return product.stock[selectedSize] ?? 0;
  }, [product, selectedSize]);

  useEffect(() => {
    if (quantity > availableForSize) {
      setQuantity(Math.max(1, availableForSize));
    }
  }, [availableForSize, quantity]);

  async function addToCart() {
    if (!product) return;
    if (product.sizes.length > 0 && !selectedSize) {
      setError("Выберите размер.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.post("/api/cart/add", {
        product_id: product.id,
        size: selectedSize,
        quantity,
      });
      navigate("/cart");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Не удалось добавить в корзину.");
    } finally {
      setBusy(false);
    }
  }

  if (error && !product) {
    return (
      <section className="section">
        <div className="container">
          <h1>Товар недоступен</h1>
          <ErrorBox message={error} />
          <p>
            <Link to="/catalog" className="btn btn--ghost">
              Вернуться в каталог
            </Link>
          </p>
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

  const canBuy = user === null || user.role === "buyer";
  const hasSizes = product.sizes.length > 0;
  const noStockAtAll = hasSizes && product.sizes.every((s) => (product.stock[s] ?? 0) <= 0);
  const qtyMax = Math.max(1, availableForSize || 1);
  const addDisabled =
    busy || availableForSize <= 0 || (hasSizes && !selectedSize);

  return (
    <section className="section">
      <div className="container">
        <div className="product-detail">
          <div className="product-detail__image">
            {product.image_url ? (
              <img src={product.image_url} alt={product.name} />
            ) : (
              <div className="product-card__placeholder large">Без фото</div>
            )}
          </div>
          <div className="product-detail__body">
            <span className="eyebrow">{product.seller_username ?? "Продавец"}</span>
            <h1>{product.name}</h1>
            <div className="product-detail__price">{formatPrice(product.price)} ₽</div>

            {hasSizes && (
              <div className="size-picker">
                <div className="muted small">Размеры</div>
                <div className="size-picker__list">
                  {product.sizes.map((size) => {
                    const qty = product.stock[size] ?? 0;
                    const disabled = qty <= 0;
                    const active = selectedSize === size;
                    return (
                      <button
                        type="button"
                        key={size}
                        className={
                          "size-chip" +
                          (active ? " size-chip--active" : "") +
                          (disabled ? " size-chip--disabled" : "")
                        }
                        disabled={disabled}
                        title={disabled ? "Нет в наличии" : `В наличии: ${qty} шт.`}
                        onClick={() => setSelectedSize(size)}
                      >
                        <span className="size-chip__label">{size}</span>
                        <span className="size-chip__qty">
                          {disabled ? "нет" : `${qty} шт.`}
                        </span>
                      </button>
                    );
                  })}
                </div>
                {selectedSize && availableForSize > 0 && (
                  <div className="muted small">
                    Доступно к покупке: {availableForSize} шт.
                  </div>
                )}
                {noStockAtAll && (
                  <div className="alert alert--info">Сейчас нет в наличии ни одного размера.</div>
                )}
              </div>
            )}

            {product.description && <p>{product.description}</p>}

            <ErrorBox message={error} />

            {canBuy ? (
              <div className="form-actions">
                <label className="qty-input">
                  <span>Количество</span>
                  <input
                    type="number"
                    min={1}
                    max={qtyMax}
                    value={quantity}
                    onChange={(e) =>
                      setQuantity(Math.max(1, Math.min(qtyMax, Number(e.target.value) || 1)))
                    }
                    disabled={availableForSize <= 0}
                  />
                </label>
                {user ? (
                  <button
                    className="btn btn--primary"
                    type="button"
                    onClick={addToCart}
                    disabled={addDisabled}
                  >
                    {busy ? "Добавляем…" : "В корзину"}
                  </button>
                ) : (
                  <Link to={`/login?next=/catalog/${product.id}`} className="btn btn--primary">
                    Войти, чтобы добавить
                  </Link>
                )}
              </div>
            ) : (
              <p className="muted">
                Покупка доступна только из аккаунта покупателя.
              </p>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
