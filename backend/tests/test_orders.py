"""Чекаут, оплата, генерация PDF-чека и переход в PAID."""
from .conftest import create_published_product, login, logout, register


def _prepare_cart(client, qty=1):
    seller = register(client, username="seller_ord", email="seller_ord@example.com", role="seller")
    pid = create_published_product(seller_id=seller["id"], stock={"S": 5})
    logout(client)
    register(client, username="buyer_ord", email="buyer_ord@example.com", role="buyer")
    r = client.post("/api/cart/add", json={"product_id": pid, "size": "S", "quantity": qty})
    assert r.status_code == 200
    return pid


def _checkout_payload(**overrides):
    base = {
        "recipient_name": "Иван Иванов",
        "recipient_phone": "+7 999 123-45-67",
        "delivery_address": "Москва, ул. Тверская, д. 1",
        "comment": "",
    }
    base.update(overrides)
    return base


def _card_payload(**overrides):
    base = {
        "card_number": "4111 1111 1111 1111",
        "card_holder": "IVAN IVANOV",
        "card_expiry": "12/30",
        "card_cvc": "123",
    }
    base.update(overrides)
    return base


def test_full_checkout_pay_flow_creates_paid_order_with_receipt(client):
    _prepare_cart(client, qty=2)
    r = client.post("/api/orders/checkout", json=_checkout_payload())
    assert r.status_code == 201, r.text
    order = r.json()
    assert order["status"] == "created"
    assert len(order["items"]) == 1
    assert order["items"][0]["sizes"] == ["S"]

    paid = client.post(f"/api/orders/{order['id']}/pay", json=_card_payload())
    assert paid.status_code == 200, paid.text
    body = paid.json()
    assert body["status"] == "paid"
    assert body["receipt"] is not None
    assert body["receipt"]["pdf_url"].startswith("/receipts/")

    # Корзина после чекаута пустая
    assert client.get("/api/cart").json()["items"] == []


def test_checkout_requires_non_empty_cart(client):
    register(client, username="empty_buyer", email="eb@example.com", role="buyer")
    r = client.post("/api/orders/checkout", json=_checkout_payload())
    assert r.status_code == 400


def test_pay_with_bad_card_returns_400(client):
    _prepare_cart(client)
    o = client.post("/api/orders/checkout", json=_checkout_payload()).json()
    bad = client.post(f"/api/orders/{o['id']}/pay", json=_card_payload(card_number="abc"))
    assert bad.status_code == 400


def test_cancel_unpaid_order(client):
    _prepare_cart(client)
    o = client.post("/api/orders/checkout", json=_checkout_payload()).json()
    r = client.post(f"/api/orders/{o['id']}/cancel")
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"


def test_cannot_pay_already_paid_order(client):
    _prepare_cart(client)
    o = client.post("/api/orders/checkout", json=_checkout_payload()).json()
    client.post(f"/api/orders/{o['id']}/pay", json=_card_payload())
    r = client.post(f"/api/orders/{o['id']}/pay", json=_card_payload())
    assert r.status_code == 409
