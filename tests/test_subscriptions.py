from fastapi.testclient import TestClient

from app.main import app


def test_subscribe_page_loads():
    with TestClient(app) as client:
        response = client.get("/subscribe")

    assert response.status_code == 200
    assert "Start SMS Alerts" in response.text
    assert "/static/smokesignal-logo.png" in response.text


def test_subscription_logo_asset_loads():
    with TestClient(app) as client:
        response = client.get("/static/smokesignal-logo.png")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"


def test_subscribe_json_seeds_watchlist_and_unsubscribes():
    phone_number = "+15550000001"
    with TestClient(app) as client:
        subscribe_response = client.post(
            "/subscribe",
            json={
                "name": "Test User",
                "phone_number": phone_number,
                "voice_mode": "atl_homie",
            },
        )
        data = subscribe_response.json()
        watchlist_response = client.get(f"/users/{data['user']['id']}/watchlist")
        unsubscribe_response = client.post("/unsubscribe", json={"phone_number": phone_number})

    assert subscribe_response.status_code == 200
    assert data["message"] == "Subscription active."
    assert len(data["watchlist"]) > 0
    assert watchlist_response.status_code == 200
    assert unsubscribe_response.json()["unsubscribed"] is True
