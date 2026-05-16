from .conftest import create_published_product, register


def test_empty_catalog(client):
    assert client.get("/api/catalog").json() == []


def test_published_product_visible_in_catalog(client):
    seller = register(client, username="vendor", email="v@example.com", role="seller")
    pid = create_published_product(seller_id=seller["id"], stock={"S": 3, "M": 5})

    items = client.get("/api/catalog").json()
    assert len(items) == 1
    assert items[0]["id"] == pid
    assert items[0]["stock"] == {"S": 3, "M": 5}
    assert items[0]["sizes"] == ["S", "M"]


def test_catalog_detail_includes_stock(client):
    seller = register(client, username="vendor2", email="v2@example.com", role="seller")
    pid = create_published_product(seller_id=seller["id"], stock={"L": 7})

    r = client.get(f"/api/catalog/{pid}")
    assert r.status_code == 200
    assert r.json()["stock"] == {"L": 7}


def test_catalog_search_case_insensitive(client):
    seller = register(client, username="vendor3", email="v3@example.com", role="seller")
    create_published_product(seller_id=seller["id"], name="Шёлковая блуза", stock={"M": 1})
    create_published_product(seller_id=seller["id"], name="Хлопковая футболка", stock={"M": 1})

    r = client.get("/api/catalog", params={"q": "блуза"})
    names = [p["name"] for p in r.json()]
    assert names == ["Шёлковая блуза"]
