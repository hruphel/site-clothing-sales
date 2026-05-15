# Maison Couture — интернет-магазин одежды

Учебный проект: разделён на **backend (FastAPI, JSON-API)** и
**frontend (React + TypeScript, SPA)**. Авторизация — сессионная (cookie).
По умолчанию используется **SQLite** для удобства запуска; легко
переключается на **PostgreSQL** через `DATABASE_URL`.

## Что реализовано

- **UC-1** — регистрация и вход для трёх ролей (`buyer`, `seller`, `admin`).
  Админ создаётся через CLI-скрипт.
- **UC-2** — публичный каталог опубликованных товаров с поиском по
  названию (регистронезависимый, работает с кириллицей) и корзина
  покупателя (добавить, изменить количество, удалить).
- **UC-3** — оформление заказа со снапшотом товаров, валидацией адреса
  и очисткой корзины.
- **UC-4** — имитация оплаты + PDF-чек (`receipt_number`,
  `transaction_id`, `pdf_url`), скачивание защищено ACL (владелец или
  админ).
- **UC-5** — статусы доставки `processing → shipped → in_transit →
  delivered`. Меняют вперёд админ (любой оплаченный заказ) и продавец
  (только заказы со своими товарами). Покупатель видит трекер на
  странице заказа.
- **UC-6** — добавление товара продавцом (multipart-загрузка фото,
  валидация имени, цены, размеров, описания), редактирование и удаление
  заявки, пока она в статусе `pending`.
- **UC-7** — модерация заявок администратором (одобрение / отказ с
  обязательной причиной).

## Структура репозитория

```
backend/                       # FastAPI: только JSON API + раздача SPA
├── app/
│   ├── main.py                # включает /api/* роутеры и SPA-fallback
│   ├── config.py              # настройки + uploads_dir, receipts_dir
│   ├── database.py            # engine + SessionLocal + init_db
│   ├── models.py              # User, Product, CartItem, Order, OrderItem, Receipt
│   ├── schemas.py             # Pydantic DTO для API
│   ├── security.py            # passlib/bcrypt
│   ├── dependencies.py        # get_current_user (по сессии)
│   ├── routers/api/
│   │   ├── auth.py            # /api/auth/{register,login,logout,me}
│   │   ├── catalog.py         # /api/catalog
│   │   ├── cart.py            # /api/cart
│   │   ├── orders.py          # /api/orders + /receipts/{file}
│   │   ├── seller.py          # /api/seller/*
│   │   └── admin.py           # /api/admin/*
│   └── services/
│       ├── delivery.py        # переходы статусов доставки
│       └── receipts.py        # PDF чека (reportlab)
├── scripts/create_admin.py
├── uploads/                   # фото товаров (раздаётся через /uploads)
├── receipts/                  # PDF-чеки (раздаётся через /receipts ACL)
└── requirements.txt

frontend/                      # Vite + React + TypeScript SPA
├── src/
│   ├── main.tsx, App.tsx
│   ├── auth.tsx               # AuthContext, useAuth
│   ├── api.ts                 # fetch-обёртка с обработкой ошибок
│   ├── types.ts               # mirror of backend/app/schemas.py
│   ├── components/            # Layout, RequireRole, DeliveryTrack, …
│   └── pages/                 # public, buyer, seller, admin
├── vite.config.ts             # dev-прокси /api, /uploads, /receipts → :8000
├── package.json
└── tsconfig.json
```

## Запуск через Docker Compose (быстрый путь)

Подходит, если нужно поднять всё одной командой и не возиться с
Python/Node локально. Требуется только Docker Desktop (Windows/macOS) или
Docker Engine + `docker compose` (Linux).

```powershell
cd path\to\site-clothing-sales

# 1) Создать .env из примера (можно отредактировать порт/секрет)
copy .env.example .env

# 2) Поднять backend + frontend
docker compose up -d --build

# 3) Создать администратора (один раз; пароль поменяйте)
docker compose exec backend `
  python -m scripts.create_admin --username admin --email admin@example.com --password "changeme123"
```

Откройте **http://127.0.0.1:8080** — это nginx, который раздаёт SPA и
проксирует `/api`, `/uploads`, `/receipts` на FastAPI. Порт настраивается
в `.env` через `FRONTEND_PORT`.

Полезные команды:

```powershell
docker compose ps                 # статус контейнеров
docker compose logs -f backend    # логи бэка
docker compose logs -f frontend   # логи nginx
docker compose restart backend    # рестарт после изменений в .env
docker compose down               # остановить (volumes сохранятся)
docker compose down -v            # остановить и стереть БД/uploads/receipts
docker compose pull && docker compose up -d --build   # обновить образы
```

Файлы и БД лежат в Docker-volumes:
- `backend_data` — SQLite-БД (`clothing_sales.db`).
- `backend_uploads` — фото товаров.
- `backend_receipts` — PDF-чеки.

Чтобы переключиться на PostgreSQL — в `.env` поправьте `DATABASE_URL`,
раскомментируйте `POSTGRES_*` и поднимите профиль:

```powershell
docker compose --profile postgres up -d --build
```

### Как подтянуть из git и переподнять

```powershell
cd path\to\site-clothing-sales
git fetch origin
git checkout main                 # или нужную ветку
git pull
docker compose up -d --build      # пересобрать образы и перезапустить
```

### Откат, если что-то сломалось

1. **Просто вернуться на main** (если разрабатывали в ветке):
   ```powershell
   docker compose down
   git checkout main
   git pull
   docker compose up -d --build
   ```
2. **Откатить уже мерженный PR** — в GitHub нажать «Revert» на PR
   (создастся обратный PR), либо локально:
   ```powershell
   git checkout main
   git pull
   git revert -m 1 <merge-commit-sha>
   git push origin main
   docker compose up -d --build
   ```
3. **Совсем чистый сброс** (удалит данные):
   ```powershell
   docker compose down -v --rmi all      # стереть контейнеры, volumes и образы
   git checkout main
   git pull
   docker compose up -d --build
   ```
4. **Старая SSR-версия** (до разделения backend/frontend) — это коммит
   `9f1f57a` на `main` (мерж PR #8). Если этот PR ещё не смержен, просто
   `git checkout main` и работайте с прошлой версией:
   ```powershell
   git checkout main
   git pull
   ```
   Если уже смержен и нужно полностью вернуться к SSR — сделайте «Revert»
   через GitHub-UI. Силой ресетить master на старый коммит можно, но
   только если вы уверены, что никто другой не зависит от истории.

## Запуск без Docker (Windows / PowerShell)

> На macOS/Linux замените `python` → `python3` и используйте
> `source .venv/bin/activate` вместо `.\.venv\Scripts\Activate.ps1`.

### 1. Подтянуть код

```powershell
cd path\to\site-clothing-sales
git checkout main             # или любую другую ветку
git pull origin main
```

### 2. Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install --upgrade pip
pip install -r requirements.txt

# По желанию пересоздать БД (после изменения схемы)
del clothing_sales.db

# Создать администратора (нужно один раз)
python -m scripts.create_admin --username admin --email admin@example.com --password "changeme123"

uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Backend поднимется на `http://127.0.0.1:8000` и будет отдавать только
JSON-API + статику (`/uploads`, `/receipts`). Если фронт ещё не
собран и обращаются к корню `/`, вернётся 503 с подсказкой.

### 3. Frontend (новый второй терминал)

```powershell
cd path\to\site-clothing-sales\frontend
npm install
npm run dev
```

Vite поднимется на `http://127.0.0.1:5173` и будет проксировать
`/api`, `/uploads`, `/receipts` на backend `:8000`. Открывать
приложение нужно по адресу Vite: <http://127.0.0.1:5173>.


