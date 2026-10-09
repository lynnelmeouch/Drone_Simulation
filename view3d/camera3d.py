"""Caméra isométrique du mode 3D."""

from __future__ import annotations


class IsoCamera3D:
    def __init__(self, base, radius: int = 2):
        self.base = base
        self.radius = radius

    def setup(self):
        self.base.disableMouse()
        # Vue isométrique : lisible pour un ViewPort 5x5.
        dist = 8.5 + self.radius * 0.8
        self.base.camera.setPos(0, -dist, 7.2)
        self.base.camera.lookAt(0, 0, 0)
        try:
            self.base.camLens.setFov(48)
            self.base.camLens.setNearFar(0.1, 200)
        except Exception:
            pass
