import pytest

from rubik_solver.cube.parser import inverse_sequence, parse_scramble


def test_parse_scramble() -> None:
    assert parse_scramble(" R  U R' F2 ") == ["R", "U", "R'", "F2"]


def test_invalid_token() -> None:
    with pytest.raises(ValueError):
        parse_scramble("R X U")


def test_inverse_sequence() -> None:
    assert inverse_sequence(["R", "U", "R'", "F2"]) == ["F2", "R", "U'", "R'"]
