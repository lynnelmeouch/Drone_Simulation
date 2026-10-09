"""
Outils 3D communs pour le mode Panda3D.

Le projet n'utilise pas d'assets externes obligatoires : le terrain, le drone,
les arbres, les rochers et les panneaux sont générés avec des géométries simples.
Cela évite de bloquer le lancement si aucun fichier .glb/.obj n'est fourni.
"""

from __future__ import annotations

import math
import random
from typing import Iterable, Sequence, Tuple

try:
    from panda3d.core import (
        Geom,
        GeomNode,
        GeomTriangles,
        GeomVertexData,
        GeomVertexFormat,
        GeomVertexWriter,
        LineSegs,
        NodePath,
        TransparencyAttrib,
        Vec3,
    )
except ModuleNotFoundError as exc:  # pragma: no cover - dépendance optionnelle
    raise ModuleNotFoundError(
        "Panda3D n'est pas installé. Lance : python -m pip install -r requirements.txt"
    ) from exc

Color = Tuple[float, float, float, float]
Vec2 = Tuple[float, float]
Vec3Tuple = Tuple[float, float, float]

TILE_SIZE = 2.0
DRONE_FLIGHT_Z = 1.35
DRONE_DOCKED_Z = 0.42


def rgba(r: int, g: int, b: int, a: float = 1.0) -> Color:
    """Convertit une couleur 0..255 en tuple Panda3D 0..1."""
    return (r / 255.0, g / 255.0, b / 255.0, a)


GRASS_COLORS = {
    1: rgba(92, 184, 92),
    2: rgba(191, 168, 76),
    3: rgba(57, 145, 96),
    4: rgba(174, 121, 68),
}
VISITED_OVERLAY = rgba(60, 255, 140, 0.18)
DANGER_COLOR = rgba(150, 42, 42)
DANGER_OVERLAY = rgba(255, 45, 45, 0.35)
BASE_COLOR = rgba(72, 85, 99)
# Eau hors-grille : on garde un rendu joli, mais les arbres ne sont plus posés dessus.
OUTSIDE_COLOR = rgba(70, 150, 210, 0.96)
WATER_DEEP_COLOR = rgba(37, 99, 162, 0.98)
WATER_HIGHLIGHT = rgba(191, 232, 255, 0.28)
BACKGROUND_GROUND_COLOR = rgba(46, 121, 190, 0.98)
SHORE_COLOR = rgba(126, 172, 93, 1.0)
BORDER_COLOR = rgba(18, 24, 38)
WHITE = rgba(245, 245, 245)
BLACK = rgba(15, 23, 42)
YELLOW = rgba(250, 204, 21)
GREEN = rgba(34, 197, 94)
RED = rgba(239, 68, 68)
BLUE = rgba(56, 189, 248)
WOOD = rgba(112, 74, 42)
LEAF = rgba(42, 139, 72)
ROCK = rgba(107, 114, 128)
FLOWER_COLORS = [rgba(244, 114, 182), rgba(250, 204, 21), rgba(147, 197, 253), rgba(255, 255, 255)]


def deterministic_rng(x: int, y: int, salt: int = 0) -> random.Random:
    """Random stable par case : la même case génère toujours les mêmes décors."""
    seed = (x + 1009) * 73856093 ^ (y + 9176) * 19349663 ^ salt * 83492791
    return random.Random(seed & 0xFFFFFFFF)


def node_from_geom(name: str, vertices: Sequence[Vec3Tuple], triangles: Iterable[Tuple[int, int, int]], color: Color) -> NodePath:
    """Construit un NodePath coloré à partir de sommets et triangles."""
    fmt = GeomVertexFormat.getV3c4()
    vdata = GeomVertexData(name, fmt, Geom.UHStatic)
    vertex = GeomVertexWriter(vdata, "vertex")
    colors = GeomVertexWriter(vdata, "color")

    for vx, vy, vz in vertices:
        vertex.addData3f(vx, vy, vz)
        colors.addData4f(*color)

    prim = GeomTriangles(Geom.UHStatic)
    for a, b, c in triangles:
        prim.addVertices(a, b, c)
    prim.closePrimitive()

    geom = Geom(vdata)
    geom.addPrimitive(prim)
    geom_node = GeomNode(name)
    geom_node.addGeom(geom)
    np = NodePath(geom_node)
    if color[3] < 1.0:
        np.setTransparency(TransparencyAttrib.MAlpha)
    return np


def make_plane(name: str, width: float, depth: float, color: Color, parent: NodePath | None = None, pos: Vec3Tuple = (0, 0, 0)) -> NodePath:
    """Plan horizontal dans le repère Panda3D : X/Y au sol, Z vertical."""
    hw, hd = width / 2.0, depth / 2.0
    vertices = [(-hw, -hd, 0), (hw, -hd, 0), (hw, hd, 0), (-hw, hd, 0)]
    triangles = [(0, 1, 2), (0, 2, 3)]
    np = node_from_geom(name, vertices, triangles, color)
    np.setPos(*pos)
    if parent is not None:
        np.reparentTo(parent)
    return np


def make_box(name: str, sx: float, sy: float, sz: float, color: Color, parent: NodePath | None = None, pos: Vec3Tuple = (0, 0, 0)) -> NodePath:
    """Cuboid centré sur son origine locale."""
    hx, hy, hz = sx / 2.0, sy / 2.0, sz / 2.0
    v = [
        (-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz),
        (-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz),
    ]
    t = [
        (0, 2, 1), (0, 3, 2),  # bottom
        (4, 5, 6), (4, 6, 7),  # top
        (0, 1, 5), (0, 5, 4),  # front
        (1, 2, 6), (1, 6, 5),  # right
        (2, 3, 7), (2, 7, 6),  # back
        (3, 0, 4), (3, 4, 7),  # left
    ]
    np = node_from_geom(name, v, t, color)
    np.setPos(*pos)
    if parent is not None:
        np.reparentTo(parent)
    return np


def make_disc(name: str, radius: float, color: Color, sides: int = 24, parent: NodePath | None = None, pos: Vec3Tuple = (0, 0, 0.02)) -> NodePath:
    """Disque plat horizontal, utile pour l'héliport."""
    vertices = [(0, 0, 0)]
    for i in range(sides):
        a = 2.0 * math.pi * i / sides
        vertices.append((math.cos(a) * radius, math.sin(a) * radius, 0))
    triangles = []
    for i in range(1, sides + 1):
        triangles.append((0, i, 1 if i == sides else i + 1))
    np = node_from_geom(name, vertices, triangles, color)
    np.setPos(*pos)
    if parent is not None:
        np.reparentTo(parent)
    return np


def make_line(name: str, points: Sequence[Vec3Tuple], color: Color, thickness: float = 2.0, parent: NodePath | None = None) -> NodePath:
    segs = LineSegs(name)
    segs.setColor(*color)
    segs.setThickness(thickness)
    if not points:
        np = NodePath(name)
    else:
        first = points[0]
        segs.moveTo(*first)
        for point in points[1:]:
            segs.drawTo(*point)
        np = NodePath(segs.create())
    if parent is not None:
        np.reparentTo(parent)
    return np


def make_tile_border(name: str, size: float, color: Color, parent: NodePath | None = None, z: float = 0.035) -> NodePath:
    h = size / 2.0
    return make_line(
        name,
        [(-h, -h, z), (h, -h, z), (h, h, z), (-h, h, z), (-h, -h, z)],
        color,
        thickness=1.0,
        parent=parent,
    )


def make_arrow(name: str, direction: Vec2, color: Color, parent: NodePath | None = None, length: float = 0.75) -> NodePath:
    """Flèche plate depuis le centre vers une direction de grille."""
    dx, dy = direction
    norm = math.hypot(dx, dy)
    root = NodePath(name)
    if norm <= 1e-6:
        if parent is not None:
            root.reparentTo(parent)
        return root

    dx, dy = dx / norm, dy / norm
    start = (0.0, 0.0, 0.13)
    end = (dx * length, dy * length, 0.13)
    make_line(f"{name}_shaft", [start, end], color, thickness=5.0, parent=root)

    # Deux ailettes de flèche.
    left = (-dy, dx)
    back = (-dx, -dy)
    wing_len = 0.22
    p1 = (end[0] + back[0] * wing_len + left[0] * wing_len * 0.65,
          end[1] + back[1] * wing_len + left[1] * wing_len * 0.65,
          0.13)
    p2 = (end[0] + back[0] * wing_len - left[0] * wing_len * 0.65,
          end[1] + back[1] * wing_len - left[1] * wing_len * 0.65,
          0.13)
    make_line(f"{name}_left", [end, p1], color, thickness=5.0, parent=root)
    make_line(f"{name}_right", [end, p2], color, thickness=5.0, parent=root)

    if parent is not None:
        root.reparentTo(parent)
    return root
