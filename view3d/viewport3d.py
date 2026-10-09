"""Calcul du ViewPort local 3D autour du drone."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Set


@dataclass(frozen=True)
class VisibleCell:
    x: int
    y: int
    local_x: int
    local_y: int
    in_bounds: bool
    zone: int | None
    is_base: bool
    is_danger: bool
    is_visited_zone: bool


class Viewport3D:
    """
    Le ViewPort contrôle uniquement l'affichage.
    Il ne change jamais les règles de l'environnement.
    """

    def __init__(self, grille, radius: int = 2):
        self.grille = grille
        self.radius = radius

    def visible_cells(
        self,
        center_x: int,
        center_y: int,
        visited_zones: Iterable[int] | None = None,
        radius: int | None = None,
    ) -> List[VisibleCell]:
        """
        Retourne les cellules visibles autour d'un centre logique.

        `radius` peut être temporairement augmenté pendant une animation de scroll.
        Cela permet d'avoir une colonne/ligne en plus déjà construite, donc pas de vide
        quand la carte glisse avec le drone.
        """
        current_radius = self.radius if radius is None else radius
        visited: Set[int] = set(visited_zones or [])
        cells: List[VisibleCell] = []

        for gy in range(center_y + current_radius, center_y - current_radius - 1, -1):
            for gx in range(center_x - current_radius, center_x + current_radius + 1):
                in_bounds = self.grille.insideGrid(gx, gy)
                zone = self.grille.zoneOf(gx, gy) if in_bounds else None
                cells.append(
                    VisibleCell(
                        x=gx,
                        y=gy,
                        local_x=gx - center_x,
                        local_y=gy - center_y,
                        in_bounds=in_bounds,
                        zone=zone,
                        is_base=in_bounds and self.grille.isInBase(gx, gy),
                        is_danger=in_bounds and self.grille.indangerZone(gx, gy),
                        is_visited_zone=zone in visited if zone is not None else False,
                    )
                )
        return cells
