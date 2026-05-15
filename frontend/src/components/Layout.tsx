import type { ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";

import { homeForRole, useAuth } from "../auth";

export default function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();

  return (
    <>
      <header className="site-header">
        <div className="container site-header__inner">
          <Link to="/" className="brand">
            <span className="brand-mark">M</span>
            <span>Maison Couture</span>
          </Link>
          <nav className="nav">
            <NavLink to="/catalog">Каталог</NavLink>
            {user ? (
              <>
                {user.role === "buyer" && <NavLink to="/cart">Корзина</NavLink>}
                {user.role === "buyer" && <NavLink to="/orders">Мои заказы</NavLink>}
                {user.role === "seller" && <NavLink to="/seller/products">Мои товары</NavLink>}
                {user.role === "seller" && <NavLink to="/seller/orders">Заказы на доставку</NavLink>}
                {user.role === "admin" && <NavLink to="/admin/products">Модерация</NavLink>}
                {user.role === "admin" && <NavLink to="/admin/orders">Доставка</NavLink>}
                <NavLink to={homeForRole(user.role)} title={user.role_label}>
                  {user.username}
                </NavLink>
                <button
                  type="button"
                  className="btn btn--ghost"
                  onClick={() => {
                    void logout();
                  }}
                >
                  Выйти
                </button>
              </>
            ) : (
              <>
                <NavLink to="/login">Войти</NavLink>
                <Link to="/register" className="btn btn--primary">
                  Регистрация
                </Link>
              </>
            )}
          </nav>
        </div>
      </header>
      <main>{children}</main>
      <footer className="site-footer">
        <div className="container site-footer__inner">
          <span>© 2025 Maison Couture</span>
          <span className="muted">Учебный проект</span>
        </div>
      </footer>
    </>
  );
}
