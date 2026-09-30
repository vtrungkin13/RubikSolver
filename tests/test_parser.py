import pytest

from rubik_solver.cube.parser import inverse_sequence, normalize_scramble, parse_scramble


def test_parse_scramble() -> None:
    assert parse_scramble(" R  U R' F2 ") == ["R", "U", "R'", "F2"]


def test_invalid_token() -> None:
    with pytest.raises(ValueError):
        parse_scramble("R X U")


def test_inverse_sequence() -> None:
    assert inverse_sequence(["R", "U", "R'", "F2"]) == ["F2", "R", "U'", "R'"]


def test_normalize_scramble() -> None:
    assert normalize_scramble("  R   U  R'  F2 ") == "R U R' F2"


@pytest.mark.parametrize("scramble", ["", "U", "R2 F' B D L U'"])
def test_parse_accepts_all_moves_in_scope(scramble: str) -> None:
    assert parse_scramble(scramble) == scramble.split()


@pytest.mark.parametrize(
    ("scramble", "expected"),
    [
        ("r U r'", ["r", "U", "r'"]),
        ("Rw U Rw'", ["r", "U", "r'"]),
        ("M E' S2", ["M", "E'", "S2"]),
        ("x y' z2", ["x", "y'", "z2"]),
        ("u d f b l", ["u", "d", "f", "b", "l"]),
    ],
)
def test_parse_extended_notation(scramble: str, expected: list[str]) -> None:
    assert parse_scramble(scramble) == expected


def test_parse_rejects_unsupported_extended_notation() -> None:
    with pytest.raises(ValueError):
        parse_scramble("R3")
