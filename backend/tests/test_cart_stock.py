"""Главные сценарии валидации остатков по размеру."""
from .conftest import create_published_product, login, logout, register


def _setup(client, *, stock):
    seller = register(client, username="seller_cs", email="seller_cs@example.com", role="seller")
    pid = create_published_product(seller_id=seller["id"], stock=stock)
    logout(client)
    register(client, username="buyer_cs", email="buyer_cs@example.com", role="buyer")
    return pid


def test_add_requires_size(client):
    pid = _setup(client, stock={"S": 5, "M": 3})
    r = client.post("/api/cart/add", json={"product_id": pid, "quantity": 1})
    assert r.status_code == 400
    assert "размер" in r.json()["detail"].lower()


def test_add_rejects_unknown_size(client):
    pid = _setup(client, stock={"S": 5})
    r = client.post("/api/cart/add", json={"product_id": pid, "size": "XXL", "quantity": 1})
    assert r.status_code == 400


def test_add_rejects_zero_stock(client):
    pid = _setup(client, stock={"S": 2, "M": 0})
    r = client.post("/api/cart/add", json={"product_id": pid, "size": "M", "quantity": 1})
    assert r.status_code == 409


def test_add_rejects_above_available(client):
    pid = _setup(client, stock={"S": 2})
    r = client.post("/api/cart/add", json={"product_id": pid, "size": "S", "quantity": 3})
    assert r.status_code == 409


def test_add_accumulates_up_to_stock(client):
    pid = _setup(client, stock={"S": 2})
    r1 = client.post("/api/cart/add", json={"product_id": pid, "size": "S", "quantity": 1})
    assert r1.status_code == 200
    # ещё одну — суммарно ровно 2, должно пройти
    r2 = client.post("/api/cart/add", json={"product_id": pid, "size": "S", "quantity": 1})
    assert r2.status_code == 200
    cart = r2.json()
    assert len(cart["items"]) == 1
    assert cart["items"][0]["quantity"] == 2
    # ещё одну — превышение, 409
    r3 = client.post("/api/cart/add", json={"product_id": pid, "size": "S", "quantity": 1})
    assert r3.status_code == 409


def test_same_product_different_sizes_become_separate_items(client):
    pid = _setup(client, stock={"S": 2, "M": 2})
    client.post("/api/cart/add", json={"product_id": pid, "size": "S", "quantity": 1})
    r = client.post("/api/cart/add", json={"product_id": pid, "size": "M", "quantity": 1})
    cart = r.json()
    sizes = sorted(item["size"] for item in cart["items"])
    assert sizes == ["M", "S"]


def test_guest_cannot_use_cart(client):
    """Без логина — 401."""
    seller = register(client, username="seller_guest", email="sg@example.com", role="seller")
    pid = create_published_product(seller_id=seller["id"], stock={"S": 1})
    logout(client)

    r = client.post("/api/cart/add", json={"product_id": pid, "size": "S", "quantity": 1})
    assert r.status_code == 401


def test_update_caps_at_available(client):
    pid = _setup(client, stock={"S": 3})
    r = client.post("/api/cart/add", json={"product_id": pid, "size": "S", "quantity": 1})
    item_id = r.json()["items"][0]["id"]
    # обновление до 5 при stock=3 — 409
    bad = client.post(f"/api/cart/{item_id}/update", json={"quantity": 5})
    assert bad.status_code == 409
    # обновление до 3 — ок
    ok = client.post(f"/api/cart/{item_id}/update", json={"quantity": 3})
    assert ok.status_code == 200
    assert ok.json()["items"][0]["quantity"] == 3
