"""Terrain 3D stylisé : ViewPort 5x5, herbe, arbres, base et dangers."""

from __future__ import annotations

from direct.interval.IntervalGlobal import LerpPosInterval
from panda3d.core import NodePath

try:  # exécution en module : python -m view3d.scene3d
    from .common3d import (
        BACKGROUND_GROUND_COLOR,
        BASE_COLOR,
        BLACK,
        BLUE,
        BORDER_COLOR,
        DANGER_COLOR,
        DANGER_OVERLAY,
        FLOWER_COLORS,
        GRASS_COLORS,
        GREEN,
        LEAF,
        OUTSIDE_COLOR,
        RED,
        ROCK,
        TILE_SIZE,
        VISITED_OVERLAY,
        WATER_DEEP_COLOR,
        WATER_HIGHLIGHT,
        SHORE_COLOR,
        WHITE,
        WOOD,
        YELLOW,
        deterministic_rng,
        make_arrow,
        make_box,
        make_disc,
        make_line,
        make_plane,
        make_tile_border,
        rgba,
    )
    from .viewport3d import Viewport3D, VisibleCell
except ImportError:  # exécution directe depuis view3d/
    from common3d import (  # type: ignore
        BACKGROUND_GROUND_COLOR,
        BASE_COLOR,
        BLACK,
        BLUE,
        BORDER_COLOR,
        DANGER_COLOR,
        DANGER_OVERLAY,
        FLOWER_COLORS,
        GRASS_COLORS,
        GREEN,
        LEAF,
        OUTSIDE_COLOR,
        RED,
        ROCK,
        TILE_SIZE,
        VISITED_OVERLAY,
        WATER_DEEP_COLOR,
        WATER_HIGHLIGHT,
        SHORE_COLOR,
        WHITE,
        WOOD,
        YELLOW,
        deterministic_rng,
        make_arrow,
        make_box,
        make_disc,
        make_line,
        make_plane,
        make_tile_border,
        rgba,
    )
    from viewport3d import Viewport3D, VisibleCell  # type: ignore


class Terrain3D:
    """
    Affiche le ViewPort local autour du drone.

    Correction importante : pendant un déplacement, on ne construit plus un
    ViewPort 7x7. On reconstruit le ViewPort exact 5x5 centré sur la destination,
    puis on place `scroll_root` avec un décalage correspondant à l'ancienne case.
    Le terrain glisse ensuite vers (0, 0), comme un vrai scrolling de map.
    """

    def __init__(self, parent: NodePath, grille, radius: int = 2):
        self.parent = parent
        self.grille = grille
        self.viewport = Viewport3D(grille, radius=radius)
        self.radius = radius
        self.active_radius = radius
        self.current_interval = None
        self.target_local = None

        # Tous les éléments du terrain sont sous ce nœud pour pouvoir faire
        # glisser la carte entière de manière fluide.
        self.scroll_root = parent.attachNewNode("terrain3d_scroll_root")
        self.root = self.scroll_root.attachNewNode("terrain3d_root")
        self.arrow_root = self.scroll_root.attachNewNode("next_action_arrow")

    def clear(self):
        if self.current_interval is not None:
            self.current_interval.finish()
            self.current_interval = None
        self.scroll_root.setPos(0, 0, 0)
        self.root.removeNode()
        self.arrow_root.removeNode()
        self.root = self.scroll_root.attachNewNode("terrain3d_root")
        self.arrow_root = self.scroll_root.attachNewNode("next_action_arrow")

    def update(self, state, next_action: str | None = None, extra_radius: int = 0):
        """
        Reconstruit le ViewPort exact autour de `state`.

        `extra_radius` est conservé pour compatibilité avec les anciennes versions
        de scene3d.py, mais il est volontairement ignoré : sinon Panda3D affiche
        pendant le déplacement des cases que le drone n'est pas censé voir.
        """
        self.clear()
        self.target_local = action_to_direction(next_action)
        self.active_radius = self.radius
        cells = self.viewport.visible_cells(state.posX, state.posY, state.visZones, radius=self.active_radius)
        for cell in cells:
            self._build_cell(cell)
        self._build_background_forest()
        self._build_next_action_arrow(next_action)

    def animate_scroll(self, old_state, new_state, duration: float = 0.42):
        """
        Fait glisser la carte comme un vrai scrolling.

        IMPORTANT : avant d'appeler cette méthode, le terrain doit déjà être
        reconstruit autour de `new_state` avec update(new_state, ...).
        On démarre avec un décalage qui fait apparaître l'ancienne case au centre,
        puis on anime vers (0, 0), où la nouvelle case est au centre.
        """
        if self.current_interval is not None:
            self.current_interval.finish()
            self.current_interval = None

        dx = new_state.posX - old_state.posX
        dy = new_state.posY - old_state.posY
        if dx == 0 and dy == 0:
            self.scroll_root.setPos(0, 0, 0)
            return

        start = (dx * TILE_SIZE, dy * TILE_SIZE, 0)
        self.scroll_root.setPos(*start)
        self.current_interval = LerpPosInterval(self.scroll_root, duration, (0, 0, 0), blendType="easeInOut")
        self.current_interval.start()

    def _cell_world_pos(self, cell: VisibleCell):
        return (cell.local_x * TILE_SIZE, cell.local_y * TILE_SIZE, 0.0)

    def _build_cell(self, cell: VisibleCell):
        x, y, _ = self._cell_world_pos(cell)
        cell_root = self.root.attachNewNode(f"cell_{cell.x}_{cell.y}")
        cell_root.setPos(x, y, 0)

        if not cell.in_bounds:
            # Hors-grille : jolie eau. Aucun arbre ni décor terrestre n'est placé
            # ici, donc on garde l'effet eau sans l'ancien bug des arbres dedans.
            self._build_water(cell_root, cell)
            return

        base_color = self._cell_color(cell)
        make_plane("ground", TILE_SIZE * 0.98, TILE_SIZE * 0.98, base_color, cell_root, (0, 0, 0))
        make_tile_border("border", TILE_SIZE * 0.98, BORDER_COLOR, cell_root)

        if cell.is_visited_zone:
            overlay = make_plane("visited_overlay", TILE_SIZE * 0.78, TILE_SIZE * 0.78, VISITED_OVERLAY, cell_root, (0, 0, 0.035))
            overlay.setBin("transparent", 20)

        if cell.is_base:
            self._build_base(cell_root)
        elif cell.is_danger:
            self._build_danger(cell_root, cell)
        else:
            self._build_grass_decorations(cell_root, cell)
            self._maybe_build_tree(cell_root, cell)

        if cell.in_bounds and self.target_local is not None and (cell.local_x, cell.local_y) == self.target_local:
            self._build_target_highlight(cell_root)

    def _cell_color(self, cell: VisibleCell):
        if cell.is_base:
            return BASE_COLOR
        if cell.is_danger:
            return DANGER_COLOR
        return GRASS_COLORS.get(cell.zone, GRASS_COLORS[1])

    def _build_water(self, root: NodePath, cell: VisibleCell):
        """Tuile hors-grille : eau stylisée avec petites vagues, sans arbres."""
        rng = deterministic_rng(cell.x, cell.y, salt=88)
        make_plane("water_deep", TILE_SIZE * 0.98, TILE_SIZE * 0.98, WATER_DEEP_COLOR, root, (0, 0, -0.018))
        water = make_plane("water_surface", TILE_SIZE * 0.92, TILE_SIZE * 0.92, OUTSIDE_COLOR, root, (0, 0, -0.006))
        water.setBin("transparent", 10)

        # Petites lignes de vague, déterministes par case pour éviter le clignotement.
        for i in range(3):
            wy = rng.uniform(-0.55, 0.55)
            wx = rng.uniform(-0.25, 0.25)
            length = rng.uniform(0.45, 0.85)
            wave = make_line(
                f"wave_{i}",
                [(-length / 2 + wx, wy, 0.018), (length / 2 + wx, wy + rng.uniform(-0.04, 0.04), 0.018)],
                WATER_HIGHLIGHT,
                thickness=1.4,
                parent=root,
            )
            wave.setBin("transparent", 20)

    def _build_base(self, root: NodePath):
        make_disc("heliport_disc", 0.82, rgba(31, 41, 55), sides=28, parent=root, pos=(0, 0, 0.055))
        make_disc("heliport_light", 0.95, rgba(56, 189, 248, 0.16), sides=32, parent=root, pos=(0, 0, 0.045))
        make_box("h_left", 0.12, 0.7, 0.045, WHITE, root, (-0.22, 0, 0.09))
        make_box("h_right", 0.12, 0.7, 0.045, WHITE, root, (0.22, 0, 0.09))
        make_box("h_mid", 0.52, 0.12, 0.045, WHITE, root, (0, 0, 0.09))
        make_box("charger", 0.18, 0.18, 0.34, BLUE, root, (0.65, -0.55, 0.18))

    def _build_danger(self, root: NodePath, cell: VisibleCell):
        overlay = make_plane("danger_overlay", TILE_SIZE * 0.82, TILE_SIZE * 0.82, DANGER_OVERLAY, root, (0, 0, 0.04))
        overlay.setBin("transparent", 25)
        rng = deterministic_rng(cell.x, cell.y, salt=20)
        for i in range(4):
            rx = rng.uniform(-0.55, 0.55)
            ry = rng.uniform(-0.55, 0.55)
            size = rng.uniform(0.16, 0.32)
            rock = make_box(f"rock_{i}", size * 1.4, size, size * 0.7, ROCK, root, (rx, ry, 0.08 + size * 0.2))
            rock.setH(rng.uniform(0, 180))
        make_box("danger_pole", 0.06, 0.06, 0.55, BLACK, root, (-0.65, 0.62, 0.28))
        make_box("danger_panel", 0.38, 0.05, 0.28, YELLOW, root, (-0.65, 0.62, 0.62))
        make_box("red_light", 0.18, 0.18, 0.07, RED, root, (0.58, -0.62, 0.10))

    def _build_grass_decorations(self, root: NodePath, cell: VisibleCell):
        rng = deterministic_rng(cell.x, cell.y, salt=7)
        # Brins d'herbe fins et bas : assez visibles, mais pas lourds.
        for i in range(rng.randint(4, 8)):
            gx = rng.uniform(-0.75, 0.75)
            gy = rng.uniform(-0.75, 0.75)
            blade = make_box(f"grass_{i}", 0.025, 0.025, rng.uniform(0.10, 0.20), GREEN, root, (gx, gy, 0.06))
            blade.setH(rng.uniform(0, 360))
        # Quelques fleurs.
        if rng.random() < 0.55:
            for i in range(rng.randint(1, 3)):
                fx = rng.uniform(-0.65, 0.65)
                fy = rng.uniform(-0.65, 0.65)
                make_box(f"flower_stem_{i}", 0.025, 0.025, 0.11, GREEN, root, (fx, fy, 0.06))
                make_box(f"flower_{i}", 0.09, 0.09, 0.035, rng.choice(FLOWER_COLORS), root, (fx, fy, 0.14))

    def _maybe_build_tree(self, root: NodePath, cell: VisibleCell):
        # Sécurité : aucun arbre sur hors-grille, base ou danger.
        if not cell.in_bounds or cell.is_base or cell.is_danger or cell.zone is None:
            return

        rng = deterministic_rng(cell.x, cell.y, salt=40)
        on_viewport_edge = abs(cell.local_x) == self.active_radius or abs(cell.local_y) == self.active_radius
        if not on_viewport_edge or rng.random() > 0.32:
            return
        tx = rng.choice([-0.72, 0.72]) if abs(cell.local_x) == self.active_radius else rng.uniform(-0.65, 0.65)
        ty = rng.choice([-0.72, 0.72]) if abs(cell.local_y) == self.active_radius else rng.uniform(-0.65, 0.65)
        self._build_tree(root, tx, ty, rng)

    def _build_tree(self, root: NodePath, x: float, y: float, rng):
        height = rng.uniform(0.55, 0.85)
        make_box("tree_trunk", 0.13, 0.13, height, WOOD, root, (x, y, height / 2.0))
        leaf_size = rng.uniform(0.45, 0.62)
        crown = make_box("tree_crown", leaf_size, leaf_size, leaf_size * 0.7, LEAF, root, (x, y, height + 0.22))
        crown.setH(rng.uniform(0, 45))
        make_box("tree_crown_2", leaf_size * 0.72, leaf_size * 0.72, leaf_size * 0.55, rgba(61, 158, 86), root, (x + 0.08, y - 0.06, height + 0.52))

    def _build_target_highlight(self, root: NodePath):
        # Mise en valeur de la case visée par la prochaine action : halo + coins lumineux.
        halo = make_plane("target_halo", TILE_SIZE * 0.74, TILE_SIZE * 0.74, rgba(250, 204, 21, 0.16), root, (0, 0, 0.05))
        halo.setBin("transparent", 30)
        outer = make_disc("target_ring_outer", 0.72, rgba(250, 204, 21, 0.18), sides=30, parent=root, pos=(0, 0, 0.06))
        outer.setBin("transparent", 31)
        inner = make_disc("target_ring_inner", 0.42, rgba(253, 224, 71, 0.34), sides=24, parent=root, pos=(0, 0, 0.07))
        inner.setBin("transparent", 32)

        corners = [(-0.72, -0.72), (0.72, -0.72), (-0.72, 0.72), (0.72, 0.72)]
        for i, (cx, cy) in enumerate(corners):
            make_box(f"target_corner_h_{i}", 0.30, 0.06, 0.05, YELLOW, root, (cx, cy + (0.12 if cy < 0 else -0.12), 0.10))
            make_box(f"target_corner_v_{i}", 0.06, 0.30, 0.05, YELLOW, root, (cx + (0.12 if cx < 0 else -0.12), cy, 0.10))

        pillar = make_box("target_pillar", 0.09, 0.09, 0.36, rgba(253, 224, 71, 0.18), root, (0, 0, 0.24))
        pillar.setBin("transparent", 33)

    def _build_fence(self, root: NodePath):
        make_box("fence_front", TILE_SIZE * 0.75, 0.05, 0.25, rgba(71, 85, 105), root, (0, -0.55, 0.13))
        make_box("fence_back", TILE_SIZE * 0.75, 0.05, 0.25, rgba(71, 85, 105), root, (0, 0.55, 0.13))

    def _build_background_forest(self):
        """Décor fixe loin du ViewPort : eau + petites îles pour les arbres."""
        border = (self.active_radius + 1.25) * TILE_SIZE

        # Fond aquatique propre autour du ViewPort. L'eau reste jolie, mais les
        # arbres de décor sont posés sur de petites îles, pas directement dans l'eau.
        make_plane("background_water", border * 2.75, border * 2.75, BACKGROUND_GROUND_COLOR, self.root, (0, 0, -0.06))
        make_plane("background_water_glow", border * 2.35, border * 2.35, WATER_HIGHLIGHT, self.root, (0, 0, -0.048))

        positions = [(-border, -border * 0.65), (border, -border * 0.55), (-border * 0.9, border), (border * 0.95, border * 0.8)]
        for i, (x, y) in enumerate(positions):
            island = self.root.attachNewNode(f"background_island_{i}")
            island.setPos(x, y, 0)
            rng = deterministic_rng(i, 99, salt=3)
            make_disc("island_grass", 0.72, SHORE_COLOR, sides=18, parent=island, pos=(0, 0, -0.025))
            make_disc("island_center", 0.54, GRASS_COLORS[1], sides=18, parent=island, pos=(0, 0, -0.015))
            self._build_tree(island, 0, 0, rng)
            island.setScale(1.25)

    def _build_next_action_arrow(self, action: str | None):
        direction = action_to_direction(action)
        if direction is None:
            return
        make_arrow("policy_arrow", direction, YELLOW, self.arrow_root, length=0.72)
        self.arrow_root.setZ(0.05)


def action_to_direction(action: str | None):
    if not action:
        return None
    mapping = {
        "move_up": (0, 1),
        "move_down": (0, -1),
        "move_right": (1, 0),
        "move_left": (-1, 0),
        "avoid_up": (0, 1),
        "avoid_down": (0, -1),
        "avoid_right": (1, 0),
        "avoid_left": (-1, 0),
    }
    return mapping.get(action)
