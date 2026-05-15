import { Link } from "react-router-dom";

import { useAuth } from "../../auth";

export default function BuyerDashboardPage() {
  const { user } = useAuth();
  return (
    <section className="section">
      <div className="container">
        <div className="section-header">
          <span className="eyebrow">Кабинет покупателя</span>
          <h2>Здравствуйте, {user?.username}</h2>
        </div>
        <div className="grid grid--3">
          <article className="card">
            <h3>Каталог</h3>
            <p>Просмотр опубликованных товаров и поиск по названию.</p>
            <Link to="/catalog" className="card-link">
              Открыть каталог
            </Link>
          </article>
          <article className="card">
            <h3>Корзина</h3>
            <p>Добавленные товары и оформление заказа.</p>
            <Link to="/cart" className="card-link">
              Перейти в корзину
            </Link>
          </article>
          <article className="card">
            <h3>Мои заказы</h3>
            <p>История заказов, оплата, чеки и статус доставки.</p>
            <Link to="/orders" className="card-link">
              К заказам
            </Link>
          </article>
        </div>
      </div>
    </section>
  );
}
