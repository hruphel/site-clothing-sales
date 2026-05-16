"""Создание товара продавцом и модерация админом."""
from .conftest import login, logout, make_admin, register


def _seller_create(client, *, stock_json: str = '{"S": 5, "M": 3}'):
    return client.post(
        "/api/seller/products",
        data={
            "name": "Платье",
            "price": "2500",
            "stock": stock_json,
            "description": "тест",
        },
    )


def test_seller_create_product_with_stock(client):
    register(client, username="vendor_a", email="va@example.com", role="seller")
    r = _seller_create(client)
    assert r.status_code == 201, r.text
    product = r.json()
    assert product["status"] == "pending"
    assert product["stock"] == {"S": 5, "M": 3}
    assert product["sizes"] == ["S", "M"]


def test_seller_create_rejects_bad_stock_json(client):
    register(client, username="vendor_b", email="vb@example.com", role="seller")
    r = _seller_create(client, stock_json="not-json")
    assert r.status_code == 400


def test_admin_approve_publishes_product(client):
    # 1. продавец создаёт товар (pending)
    register(client, username="vendor_c", email="vc@example.com", role="seller")
    pid = _seller_create(client).json()["id"]
    # каталог пуст: товар ещё не опубликован
    logout(client)
    assert client.get("/api/catalog").json() == []

    # 2. админ одобряет
    make_admin()
    login(client, identifier="admin")
    r = client.post(f"/api/admin/products/{pid}/approve")
    assert r.status_code == 200
    assert r.json()["status"] == "published"

    # 3. товар появляется в публичном каталоге
    logout(client)
    items = client.get("/api/catalog").json()
    assert [p["id"] for p in items] == [pid]


def test_admin_reject_requires_reason(client):
    register(client, username="vendor_d", email="vd@example.com", role="seller")
    pid = _seller_create(client).json()["id"]
    logout(client)

    make_admin()
    login(client, identifier="admin")
    no_reason = client.post(f"/api/admin/products/{pid}/reject", json={"reason": ""})
    assert no_reason.status_code == 400

    ok = client.post(f"/api/admin/products/{pid}/reject", json={"reason": "Нет фото."})
    assert ok.status_code == 200
    assert ok.json()["status"] == "rejected"
    assert ok.json()["rejection_reason"] == "Нет фото."


def test_buyer_cannot_access_seller_routes(client):
    register(client, username="just_buyer", email="jb@example.com", role="buyer")
    r = client.get("/api/seller/products")
    assert r.status_code in (401, 403)
