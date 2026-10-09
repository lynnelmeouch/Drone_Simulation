from drone import DroneEnvironment
from view3d.viewport3d import Viewport3D


def test_viewport_center_and_bounds():
    env = DroneEnvironment()
    viewport = Viewport3D(env.grille, radius=2)
    cells = viewport.visible_cells(0, 0, visited_zones={1})

    assert len(cells) == 25
    center = next(cell for cell in cells if cell.local_x == 0 and cell.local_y == 0)
    assert center.x == 0
    assert center.y == 0
    assert center.in_bounds
    assert center.is_base
    assert center.is_visited_zone
    assert any(not cell.in_bounds for cell in cells)


def test_viewport_marks_danger_cells():
    env = DroneEnvironment()
    viewport = Viewport3D(env.grille, radius=2)
    cells = viewport.visible_cells(2, 2, visited_zones={1})
    danger = next(cell for cell in cells if (cell.x, cell.y) == (2, 2))
    assert danger.in_bounds
    assert danger.is_danger
