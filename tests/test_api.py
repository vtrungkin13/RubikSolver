from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_solve_endpoint_returns_verified_solution() -> None:
    response = client.post(
        "/api/solve",
        json={"scramble": "R U", "method": "kociemba"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["method"] == "kociemba"
    assert payload["verified"] is True
    assert payload["move_count"] > 0


def test_solve_endpoint_accepts_extended_notation() -> None:
    response = client.post(
        "/api/solve",
        json={"scramble": "Rw U Rw' U' M2", "method": "kociemba"},
    )

    assert response.status_code == 200
    assert response.json()["verified"] is True


def test_solve_endpoint_rejects_invalid_scramble() -> None:
    response = client.post(
        "/api/solve",
        json={"scramble": "R X U", "method": "kociemba"},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_SCRAMBLE"


def test_solve_endpoint_reports_unavailable_solver() -> None:
    response = client.post(
        "/api/solve",
        json={"scramble": "R U", "method": "roux"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["method"] == "roux"
    assert payload["verified"] is True
    assert payload["phases"][0]["name"] == "First Block"


def test_solve_endpoint_roux_falls_back_for_hard_scramble() -> None:
    response = client.post(
        "/api/solve",
        json={
            "scramble": "L2 F2 R2 F' U2 R2 F' L2 B2 U2 F R' D U2 F U B2 F' R' F2",
            "method": "roux",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["method"] == "kociemba"
    assert payload["verified"] is True
    assert payload["metadata"]["fallback_from"] == "roux"
    assert "Roux" in payload["metadata"]["fallback_reason"]


def test_solve_endpoint_supports_cfop() -> None:
    response = client.post(
        "/api/solve",
        json={"scramble": "R U R' F2 D", "method": "cfop"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["method"] == "cfop"
    assert payload["verified"] is True
    assert [phase["name"] for phase in payload["phases"]] == [
        "Orientation", "Cross", "F2L-1", "F2L-2", "F2L-3", "F2L-4", "OLL", "PLL"
    ]


def test_solve_endpoint_supports_long_cfop_scramble() -> None:
    response = client.post(
        "/api/solve",
        json={
            "scramble": "R B2 L2 D L2 D2 B2 L2 D R2 U' B2 L2 F' D' R U R U2 F' R2",
            "method": "cfop",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["verified"] is True
