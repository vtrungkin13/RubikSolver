"""
Constants: coordinate sizes, facelet mappings, move definitions.
"""

from .types import Center, Edge, CubeState

# ── Coordinate sizes ──────────────────────────────────────────────
N_TWIST     = 2187
N_FLIP      = 2048
N_PARITY    = 2
N_FRtoBR   = 11880
N_SLICE1    = 495
N_SLICE2    = 24
N_URFtoDLF = 20160
N_URtoDF   = 20160
N_URtoUL   = 1320
N_UBtoDF   = 1320

# ── Facelet index helpers ─────────────────────────────────────────
def _U(x): return x - 1
def _R(x): return _U(9) + x
def _F(x): return _R(9) + x
def _D(x): return _F(9) + x
def _L(x): return _D(9) + x
def _B(x): return _L(9) + x

CENTER_FACELET = [4, 13, 22, 31, 40, 49]

CORNER_FACELET = [
    [_U(9), _R(1), _F(3)], [_U(7), _F(1), _L(3)], [_U(1), _L(1), _B(3)], [_U(3), _B(1), _R(3)],
    [_D(3), _F(9), _R(7)], [_D(1), _L(9), _F(7)], [_D(7), _B(9), _L(7)], [_D(9), _R(9), _B(7)],
]

EDGE_FACELET = [
    [_U(6), _R(2)], [_U(8), _F(2)], [_U(4), _L(2)], [_U(2), _B(2)],
    [_D(6), _R(8)], [_D(2), _F(8)], [_D(4), _L(8)], [_D(8), _B(8)],
    [_F(6), _R(4)], [_F(4), _L(6)], [_B(6), _L(4)], [_B(4), _R(6)],
]

CENTER_COLOR = ['U', 'R', 'F', 'D', 'L', 'B']

CORNER_COLOR = [
    ['U','R','F'], ['U','F','L'], ['U','L','B'], ['U','B','R'],
    ['D','F','R'], ['D','L','F'], ['D','B','L'], ['D','R','B'],
]

EDGE_COLOR = [
    ['U','R'], ['U','F'], ['U','L'], ['U','B'],
    ['D','R'], ['D','F'], ['D','L'], ['D','B'],
    ['F','R'], ['F','L'], ['B','L'], ['B','R'],
]

FACE_NAMES = {0: 'U', 1: 'R', 2: 'F', 3: 'D', 4: 'L', 5: 'B'}

FACE_NUMS = {
    'U': 0, 'R': 1, 'F': 2, 'D': 3, 'L': 4, 'B': 5,
    'E': 6, 'M': 7, 'S': 8,
    'x': 9, 'y': 10, 'z': 11,
    'u': 12, 'r': 13, 'f': 14, 'd': 15, 'l': 16, 'b': 17,
}

# ── Base move definitions ─────────────────────────────────────────
BASE_MOVE_DATA = [
    # U
    CubeState(center=[0,1,2,3,4,5], cp=[3,0,1,2,4,5,6,7], co=[0,0,0,0,0,0,0,0],
              ep=[3,0,1,2,4,5,6,7,8,9,10,11], eo=[0,0,0,0,0,0,0,0,0,0,0,0]),
    # R
    CubeState(center=[0,1,2,3,4,5], cp=[4,1,2,0,7,5,6,3], co=[2,0,0,1,1,0,0,2],
              ep=[8,1,2,3,11,5,6,7,4,9,10,0], eo=[0,0,0,0,0,0,0,0,0,0,0,0]),
    # F
    CubeState(center=[0,1,2,3,4,5], cp=[1,5,2,3,0,4,6,7], co=[1,2,0,0,2,1,0,0],
              ep=[0,9,2,3,4,8,6,7,1,5,10,11], eo=[0,1,0,0,0,1,0,0,1,1,0,0]),
    # D
    CubeState(center=[0,1,2,3,4,5], cp=[0,1,2,3,5,6,7,4], co=[0,0,0,0,0,0,0,0],
              ep=[0,1,2,3,5,6,7,4,8,9,10,11], eo=[0,0,0,0,0,0,0,0,0,0,0,0]),
    # L
    CubeState(center=[0,1,2,3,4,5], cp=[0,2,6,3,4,1,5,7], co=[0,1,2,0,0,2,1,0],
              ep=[0,1,10,3,4,5,9,7,8,2,6,11], eo=[0,0,0,0,0,0,0,0,0,0,0,0]),
    # B
    CubeState(center=[0,1,2,3,4,5], cp=[0,1,3,7,4,5,2,6], co=[0,0,1,2,0,0,2,1],
              ep=[0,1,2,11,4,5,6,10,8,9,3,7], eo=[0,0,0,1,0,0,0,1,0,0,1,1]),
    # E
    CubeState(center=[Center.U,Center.F,Center.L,Center.D,Center.B,Center.R],
              cp=[0,1,2,3,4,5,6,7], co=[0,0,0,0,0,0,0,0],
              ep=[0,1,2,3,4,5,6,7,Edge.FL,Edge.BL,Edge.BR,Edge.FR],
              eo=[0,0,0,0,0,0,0,0,1,1,1,1]),
    # M
    CubeState(center=[Center.B,Center.R,Center.U,Center.F,Center.L,Center.D],
              cp=[0,1,2,3,4,5,6,7], co=[0,0,0,0,0,0,0,0],
              ep=[0,Edge.UB,2,Edge.DB,4,Edge.UF,6,Edge.DF,8,9,10,11],
              eo=[0,1,0,1,0,1,0,1,0,0,0,0]),
    # S
    CubeState(center=[Center.L,Center.U,Center.F,Center.R,Center.D,Center.B],
              cp=[0,1,2,3,4,5,6,7], co=[0,0,0,0,0,0,0,0],
              ep=[Edge.UL,1,Edge.DL,3,Edge.UR,5,Edge.DR,7,8,9,10,11],
              eo=[1,0,1,0,1,0,1,0,0,0,0,0]),
]

# Compound rotation/wide-move recipes (index 9..17 → x y z u r f d l b)
COMPOUND_MOVES = [
    "R M' L'",  # x  (9)
    "U E' D'",  # y  (10)
    "F S B'",   # z  (11)
    "U E'",     # u  (12)
    "R M'",     # r  (13)
    "F S",      # f  (14)
    "D E",      # d  (15)
    "L M",      # l  (16)
    "B S'",     # b  (17)
]

PARITY_TABLE = [
    [1,0,1,1,0,1,1,0,1,1,0,1,1,0,1,1,0,1],
    [0,1,0,0,1,0,0,1,0,0,1,0,0,1,0,0,1,0],
]
