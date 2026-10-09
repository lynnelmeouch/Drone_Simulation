#Dimensions de la grille
MAX_X = 5
MAX_Y = 5
 
#Position de la base
BASE_X = 0
BASE_Y = 0
 
#Zones dangereuses (ensemble de tuples (x, y))
DANGER = {
    (2, 2),
    (3, 2),
    (4, 3),
    (1, 4)
}
 
#Nombre de zones de patrouille
ZONE_COUNT = 4
 
#Parametres de la batterie
BATTERY_MAX = 100
BATTERY_CHARGE_STEP = 5
 
#Couts energetiques
COST_MOVE = 1
COST_AVOID = 2
 
#Actions disponibles
ACTIONS = [
    'takeoff_cmd',
    'move_step',
    'avoid_maneuver',
    'return_home',
    'dock_cmd',
    'undock_cmd',
    'charge_step',
    'emergency_stop'
]