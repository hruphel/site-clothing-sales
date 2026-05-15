import { Link } from "react-router-dom";

import { homeForRole, useAuth } from "../auth";

export default function HomePage() {
  const { user } = useAuth();
  return (
    <>
      <section className="hero">
        <div className="container hero__inner">
          <div className="eyebrow">Couture House • Sale Edition</div>
          <h1>
            Изысканная одежда —<br />
            ограниченные коллекции, продуманный отбор.
          </h1>
          <p className="lead">
            Maison Couture — небольшая площадка, где независимые продавцы публикуют свои коллекции
            после проверки командой модерации. Без шума, без массовости — только то, что мы готовы
            рекомендовать.
          </p>
          <div className="hero__cta">
            {user ? (
              <Link to={homeForRole(user.role)} className="btn btn--primary">
                В личный кабинет
              </Link>
            ) : (
              <>
                <Link to="/register" className="btn btn--primary">
                  Создать аккаунт
                </Link>
                <Link to="/login" className="btn btn--ghost">
                  Войти
                </Link>
              </>
            )}
            <Link to="/catalog" className="btn btn--ghost">
              Открыть каталог
            </Link>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="section-header">
            <span className="eyebrow">Кому это</span>
            <h2>Три кабинета, одна площадка</h2>
          </div>
          <div className="grid grid--3">
            <article className="card">
              <h3>Покупатель</h3>
              <p>Создаёт аккаунт, формирует корзину, оформляет заказ, оплачивает и получает чек.</p>
              <Link to="/register" className="card-link">
                Зарегистрироваться
              </Link>
            </article>
            <article className="card">
              <h3>Продавец</h3>
              <p>Подаёт заявки на размещение товара. После одобрения товар появляется в каталоге.</p>
              <Link to="/register" className="card-link">
                Подать заявку
              </Link>
            </article>
            <article className="card">
              <h3>Администратор</h3>
              <p>Проверяет заявки продавцов, одобряет или возвращает на доработку с комментарием.</p>
              <Link to="/login" className="card-link">
                Войти как админ
              </Link>
            </article>
          </div>
        </div>
      </section>
    </>
  );
}
