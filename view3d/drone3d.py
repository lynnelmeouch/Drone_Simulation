"""Drone 3D stylisé avec hélices animées."""

from __future__ import annotations

import math

from direct.interval.IntervalGlobal import Func, LerpHprInterval, LerpPosInterval, Parallel, Sequence
from panda3d.core import NodePath

try:
    from .common3d import BLUE, DRONE_DOCKED_Z, DRONE_FLIGHT_Z, GREEN, RED, TILE_SIZE, WHITE, YELLOW, make_box, make_disc, rgba
except ImportError:
    from common3d import BLUE, DRONE_DOCKED_Z, DRONE_FLIGHT_Z, GREEN, RED, TILE_SIZE, WHITE, YELLOW, make_box, make_disc, rgba  # type: ignore


class Drone3D:
    def __init__(self, parent: NodePath):
        self.parent = parent
        self.root = parent.attachNewNode("drone3d")
        self.propellers = []
        self.current_interval = None
        self.marker_root = None
        self.marker_glow = None
        self.marker_ring = None
        self.marker_beam = None
        self._build_model()
        self.root.setPos(0, 0, DRONE_DOCKED_Z)

    def _build_model(self):
        # Corps central.
        make_box("body", 0.55, 0.42, 0.20, rgba(226, 232, 240), self.root, (0, 0, 0))
        make_box("camera", 0.20, 0.14, 0.12, rgba(15, 23, 42), self.root, (0, -0.31, -0.03))
        make_box("top_light", 0.14, 0.14, 0.06, GREEN, self.root, (0, 0, 0.15))

        # Bras.
        make_box("arm_x", 1.35, 0.08, 0.08, rgba(148, 163, 184), self.root, (0, 0, 0))
        make_box("arm_y", 0.08, 1.35, 0.08, rgba(148, 163, 184), self.root, (0, 0, 0))

        # Hélices.
        for i, (x, y) in enumerate([(0.72, 0.72), (-0.72, 0.72), (0.72, -0.72), (-0.72, -0.72)]):
            motor = self.root.attachNewNode(f"motor_{i}")
            motor.setPos(x, y, 0.03)
            make_box("motor_body", 0.18, 0.18, 0.10, rgba(30, 41, 59), motor, (0, 0, 0))
            prop = motor.attachNewNode(f"propeller_{i}")
            make_box("blade_a", 0.62, 0.06, 0.025, WHITE, prop, (0, 0, 0.08))
            make_box("blade_b", 0.06, 0.62, 0.025, WHITE, prop, (0, 0, 0.08))
            make_box("cap", 0.12, 0.12, 0.05, BLUE if i % 2 == 0 else YELLOW, prop, (0, 0, 0.10))
            self.propellers.append(prop)

        # Repère visuel élégant pour montrer la case actuelle du drone.
        self.marker_root = self.root.attachNewNode("drone_marker")
        self.marker_glow = make_disc("marker_glow", 0.78, rgba(56, 189, 248, 0.18), sides=30, parent=self.marker_root, pos=(0, 0, 0.0))
        self.marker_ring = make_disc("marker_ring", 0.54, rgba(147, 197, 253, 0.55), sides=26, parent=self.marker_root, pos=(0, 0, 0.015))
        self.marker_beam = make_box("marker_beam", 0.14, 0.14, 1.0, rgba(125, 211, 252, 0.12), self.marker_root, (0, 0, 0.50))
        self._update_marker_height(DRONE_DOCKED_Z)

    def update_visual_state(self, state):
        if state.crashed:
            target_z = 0.23
            self.root.setZ(target_z)
            self.root.setHpr(20, 0, 28)
        elif state.airborne:
            target_z = DRONE_FLIGHT_Z
            self.root.setZ(target_z)
        elif state.docked:
            target_z = DRONE_DOCKED_Z
            self.root.setZ(target_z)
        else:
            target_z = DRONE_DOCKED_Z
            self.root.setZ(target_z)
        self._update_marker_height(target_z)

    def spin_task(self, task):
        speed = 30.0 if self.root.getZ() > 0.6 else 6.0
        for prop in self.propellers:
            prop.setH(prop.getH() + speed)

        # Petit pulse lumineux sous le drone : plus lisible et plus "beau".
        pulse = 1.0 + 0.10 * math.sin(task.time * 4.8)
        if self.marker_glow is not None:
            self.marker_glow.setScale(pulse, pulse, 1.0)
            self.marker_glow.setColorScale(1, 1, 1, 0.75 + 0.20 * math.sin(task.time * 3.2))
        if self.marker_ring is not None:
            ring_scale = 0.92 + 0.08 * math.sin(task.time * 5.6 + 0.8)
            self.marker_ring.setScale(ring_scale, ring_scale, 1.0)
            self.marker_ring.setColorScale(1, 1, 1, 0.80)
        if self.marker_beam is not None:
            self.marker_beam.setColorScale(1, 1, 1, 0.38 + 0.08 * math.sin(task.time * 2.8))
        return task.cont

    def animate_transition(self, old_state, new_state, duration: float = 0.42, on_done=None, centered: bool = False):
        """
        Animation classique : le drone glisse depuis l'ancienne case vers le centre.

        Si centered=True, la carte est déjà en train de glisser sous le drone, donc
        le drone reste au centre et on anime seulement sa hauteur + son inclinaison.
        """
        if self.current_interval is not None:
            self.current_interval.finish()
            self.current_interval = None

        target_z = DRONE_FLIGHT_Z if new_state.airborne else DRONE_DOCKED_Z
        if new_state.crashed:
            target_z = 0.23
        self._update_marker_height(target_z)

        if centered:
            start_x = 0
            start_y = 0
            self.root.setX(0)
            self.root.setY(0)
        else:
            start_x = (old_state.posX - new_state.posX) * TILE_SIZE
            start_y = (old_state.posY - new_state.posY) * TILE_SIZE
            self.root.setX(start_x)
            self.root.setY(start_y)

        dx = new_state.posX - old_state.posX
        dy = new_state.posY - old_state.posY
        tilt_hpr = self._tilt_for_direction(dx, dy, new_state)
        final_hpr = (20, 0, 28) if new_state.crashed else (0, 0, 0)

        move = LerpPosInterval(
            self.root,
            duration,
            (0, 0, target_z),
            startPos=(start_x, start_y, self.root.getZ()),
            blendType="easeInOut",
        )
        tilt = LerpHprInterval(self.root, duration * 0.50, tilt_hpr, blendType="easeOut")
        untilt = LerpHprInterval(self.root, duration * 0.50, final_hpr, blendType="easeIn")
        self.current_interval = Sequence(
            Parallel(move, Sequence(tilt, untilt)),
            Func(self._finish_interval, on_done),
        )
        self.current_interval.start()

    def animate_centered_transition(self, old_state, new_state, duration: float = 0.42, on_done=None):
        """Animation utilisée quand Terrain3D.animate_scroll() fait bouger la map."""
        self.animate_transition(old_state, new_state, duration=duration, on_done=on_done, centered=True)

    def _update_marker_height(self, drone_z: float):
        if self.marker_root is None:
            return
        ground_z = -drone_z + 0.03
        self.marker_root.setZ(ground_z)
        if self.marker_beam is not None:
            self.marker_beam.setSz(max(0.12, drone_z - 0.03))
            self.marker_beam.setZ((drone_z - 0.03) / 2.0)

    def _finish_interval(self, on_done):
        self.current_interval = None
        if on_done is not None:
            on_done()

    def _tilt_for_direction(self, dx: int, dy: int, state):
        if state.crashed:
            return (20, 0, 28)
        # Panda HPR : petit roulis/tangage visuel, pas de vraie physique.
        if dx > 0:
            return (0, 0, -10)
        if dx < 0:
            return (0, 0, 10)
        if dy > 0:
            return (0, -10, 0)
        if dy < 0:
            return (0, 10, 0)
        if state.airborne:
            return (0, 0, 0)
        return (0, 0, 0)
