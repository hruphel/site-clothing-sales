import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api, ApiError } from "../../api";
import ErrorBox from "../../components/ErrorBox";
import { formatPrice } from "../../utils";
import type { Cart } from "../../types";

export default function CartPage() {
  const navigate = useNavigate();
  const [cart, setCart] = useState<Cart | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<number | null>(null);

  useEffect(() => {
    api.get<Cart>("/api/cart").then(setCart).catch((err) => {
      setError(err instanceof ApiError ? err.detail : "Не удалось загрузить корзину.");
    });
  }, []);

  async function update(itemId: number, quantity: number) {
    setBusy(itemId);
    setError(null);
    try {
      const updated = await api.post<Cart>(`/api/cart/${itemId}/update`, { quantity });
      setCart(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Не удалось обновить.");
    } finally {
      setBusy(null);
    }
  }

  async function remove(itemId: number) {
    setBusy(itemId);
    setError(null);
    try {
      const updated = await api.post<Cart>(`/api/cart/${itemId}/remove`);
      setCart(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Не удалось удалить.");
    } finally {
      setBusy(null);
    }
  }

  if (!cart && !error) {
    return (
      <section className="section">
        <div className="container">
          <p className="muted">Загрузка корзины…</p>
        </div>
      </section>
    );
  }

  const isEmpty = !cart || cart.items.length === 0;

  return (
    <section className="section">
      <div className="container">
        <div className="section-header">
          <span className="eyebrow">Корзина</span>
          <h2>Корзина</h2>
        </div>

        <ErrorBox message={error} />

        {isEmpty ? (
          <div className="empty-state">
            <p>В корзине пока пусто.</p>
            <Link to="/catalog" className="btn btn--primary">
              Перейти в каталог
            </Link>
          </div>
        ) : (
          <>
            <div className="cart-list">
              {cart!.items.map((item) => (
                <div className="cart-row" key={item.id}>
                  <div className="cart-row__image">
                    {item.product.image_url ? (
                      <img src={item.product.image_url} alt={item.product.name} />
                    ) : (
                      <div className="product-card__placeholder">Без фото</div>
                    )}
                  </div>
                  <div className="cart-row__body">
                    <Link to={`/catalog/${item.product.id}`} className="cart-row__title">
                      {item.product.name}
                    </Link>
                    {item.size && (
                      <div className="muted small">Размер: <strong>{item.size}</strong></div>
                    )}
                    <div className="muted small">{formatPrice(item.product.price)} ₽ за шт.</div>
                  </div>
                  <div className="cart-row__qty">
                    {(() => {
                      const stockForSize = item.size
                        ? item.product.stock[item.size] ?? 0
                        : 99;
                      const max = Math.max(1, Math.min(99, stockForSize || 1));
                      return (
                        <>
                          <input
                            type="number"
                            min={1}
                            max={max}
                            value={item.quantity}
                            disabled={busy === item.id || stockForSize <= 0}
                            onChange={(e) => {
                              const q = Math.max(1, Math.min(max, Number(e.target.value) || 1));
                              if (q !== item.quantity) {
                                void update(item.id, q);
                              }
                            }}
                          />
                          <div className="muted small">из {stockForSize}</div>
                        </>
                      );
                    })()}
                  </div>
                  <div className="cart-row__total">{formatPrice(item.line_total)} ₽</div>
                  <button
                    type="button"
                    className="btn btn--ghost btn--small"
                    onClick={() => void remove(item.id)}
                    disabled={busy === item.id}
                  >
                    Убрать
                  </button>
                </div>
              ))}
            </div>
            <div className="cart-summary">
              <div>
                <div className="muted small">Итого</div>
                <div className="cart-summary__total">{formatPrice(cart!.total)} ₽</div>
              </div>
              <button
                className="btn btn--primary"
                type="button"
                onClick={() => navigate("/checkout")}
              >
                Оформить заказ
              </button>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
