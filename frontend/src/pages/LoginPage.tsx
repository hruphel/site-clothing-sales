import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "../api";
import { homeForRole, useAuth } from "../auth";
import ErrorBox from "../components/ErrorBox";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const u = await login(identifier, password);
      navigate(homeForRole(u.role), { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Не удалось войти.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="section">
      <div className="container narrow">
        <div className="section-header">
          <span className="eyebrow">Вход</span>
          <h2>Авторизация</h2>
        </div>
        <form className="form" onSubmit={onSubmit}>
          <ErrorBox message={error} />
          <label className="form-row">
            <span>Логин или email</span>
            <input
              type="text"
              required
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              autoFocus
            />
          </label>
          <label className="form-row">
            <span>Пароль</span>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          <div className="form-actions">
            <button className="btn btn--primary" type="submit" disabled={submitting}>
              {submitting ? "Входим…" : "Войти"}
            </button>
            <Link to="/register" className="btn btn--ghost">
              Создать аккаунт
            </Link>
          </div>
        </form>
      </div>
    </section>
  );
}
