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

    assert response.status_code == 501
    assert response.json()["detail"]["code"] == "SOLVER_UNAVAILABLE"


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
        "Cross", "F2L-1", "F2L-2", "F2L-3", "F2L-4", "OLL", "PLL"
    ]
