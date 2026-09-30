"""
Mathematical utility functions for the Rubik's Cube solver.
"""

from typing import List


def cnk(n: int, k: int) -> int:
    """Compute binomial coefficient C(n, k)."""
    if n < k:
        return 0
    if k > n // 2:
        k = n - k
    s, i, j = 1, n, 1
    while i != n - k:
        s *= i
        s //= j
        i -= 1
        j += 1
    return s


def factorial(n: int) -> int:
    """Compute n!"""
    f = 1
    for i in range(2, n + 1):
        f *= i
    return f


def rotate_left(array: bytearray, l: int, r: int) -> None:
    """Rotate array slice [l..r] left by one position (in-place)."""
    tmp = array[l]
    for i in range(l, r):
        array[i] = array[i + 1]
    array[r] = tmp


def rotate_right(array: bytearray, l: int, r: int) -> None:
    """Rotate array slice [l..r] right by one position (in-place)."""
    tmp = array[r]
    for i in range(r, l, -1):
        array[i] = array[i - 1]
    array[l] = tmp
