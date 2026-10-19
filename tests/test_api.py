from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cube_state_endpoint_returns_54_facelets() -> None:
    response = client.post("/api/cube/state", json={"scramble": ""})

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is True
    assert len(payload["stickers"]) == 54
    assert payload["stickers"] == "U" * 9 + "R" * 9 + "F" * 9 + "D" * 9 + "L" * 9 + "B" * 9
    assert payload["is_solved"] is True


def test_cube_state_endpoint_rejects_invalid_scramble() -> None:
    response = client.post("/api/cube/state", json={"scramble": "R X U"})

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_SCRAMBLE"


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
    assert len(payload["initial_state"]) == 54
    # Playback still has one state per executable token, including x/y/z
    # rotations, even though those rotations are excluded from move_count.
    assert len(payload["step_states"]) == len(payload["moves"].split()) + 1
    assert payload["step_states"][0] == payload["initial_state"]
    assert payload["step_states"][-1] == payload["final_state"]
    assert payload["final_is_solved"] is True


def test_cfop_final_state_accepts_a_rotated_whole_cube_frame() -> None:
    response = client.post("/api/solve", json={"scramble": "R U", "method": "cfop"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["verified"] is True
    assert payload["final_is_solved"] is True
    rotations = {"x", "x2", "x'", "y", "y2", "y'", "z", "z2", "z'"}
    assert payload["move_count"] == sum(
        move not in rotations for move in payload["moves"].split()
    )


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
    assert payload["phases"][1]["name"] == "Second Block"
    assert [phase["name"] for phase in payload["phases"]] == [
        "First Block", "Second Block", "CMLL", "EO", "ULUR", "L4E"
    ]
    assert payload["metadata"]["verification_scope"] == "first_block+second_block+cmll+eo+ulur+l4e"
    assert payload["metadata"]["status"] == "l4e"


def test_solve_endpoint_does_not_fallback_when_roux_phase_search_fails() -> None:
    response = client.post(
        "/api/solve",
        json={
            "scramble": "L2 F2 R2 F' U2 R2 F' L2 B2 U2 F R' D U2 F U B2 F' R' F2",
            "method": "roux",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "ROUX_PHASE_FAILED"


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
