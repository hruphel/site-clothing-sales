from .conftest import login, logout, register


def test_register_login_me_logout(client):
    register(client, username="alice", email="alice@example.com")
    me = client.get("/api/auth/me").json()
    assert me["username"] == "alice"
    assert me["role"] == "buyer"

    logout(client)
    assert client.get("/api/auth/me").json() is None

    login(client, identifier="alice")
    assert client.get("/api/auth/me").json()["username"] == "alice"


def test_login_with_email(client):
    register(client, username="bob", email="bob@example.com")
    logout(client)
    login(client, identifier="bob@example.com")
    assert client.get("/api/auth/me").json()["username"] == "bob"


def test_login_wrong_password(client):
    register(client, username="carol", email="carol@example.com")
    logout(client)
    r = client.post(
        "/api/auth/login",
        json={"identifier": "carol", "password": "wrong-password"},
    )
    assert r.status_code == 401


def test_cannot_register_admin_via_api(client):
    r = client.post(
        "/api/auth/register",
        json={
            "username": "rogue",
            "email": "rogue@example.com",
            "password": "passw0rd",
            "password_confirm": "passw0rd",
            "role": "admin",
        },
    )
    assert r.status_code == 400


def test_register_duplicate_username(client):
    register(client, username="dupe", email="d1@example.com")
    logout(client)
    r = client.post(
        "/api/auth/register",
        json={
            "username": "dupe",
            "email": "d2@example.com",
            "password": "passw0rd",
            "password_confirm": "passw0rd",
            "role": "buyer",
        },
    )
    assert r.status_code == 400
