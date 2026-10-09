from constants import BATTERY_MAX
 
class DroneState:
    
    def __init__(self, posX, posY, baseX, baseY):
        # Position du drone
        self.posX = posX
        self.posY = posY
        
        # Position de la base
        self.baseX = baseX
        self.baseY = baseY
        
        # Niveau de batterie (0-100)
        self.battery = BATTERY_MAX
        
        # Distance à l'obstacle (information de danger)
        self.obstacle_distance = 2
        
        # États booléens (0 ou 1)
        self.docked = 0      # Arrimé à la base
        self.airborne = 0    # En vol
        self.crashed = 0     # Crashé
        
        # Ensemble des zones visitées
        self.visZones = set()
    
    def copy(self):
        new_state = DroneState(self.posX, self.posY, self.baseX, self.baseY)
        new_state.battery = self.battery
        new_state.obstacle_distance = self.obstacle_distance
        new_state.docked = self.docked
        new_state.airborne = self.airborne
        new_state.crashed = self.crashed
        new_state.visZones = self.visZones.copy()
        return new_state
    
    def __str__(self):
        status = []
        if self.crashed:
            status.append("CRASHED")
        if self.airborne:
            status.append("AIRBORNE")
        if self.docked:
            status.append("DOCKED")
        
        status_str = ", ".join(status) if status else "GROUNDED"
        
        return f"""
État du drone:
  Position: ({self.posX}, {self.posY})
  Base: ({self.baseX}, {self.baseY})
  Batterie: {self.battery}%
  Distance obstacle: {self.obstacle_distance}
  Statut: {status_str}
  Zones visitées: {sorted(self.visZones)}
  Nombre de zones: {len(self.visZones)}
"""
    
    def __hash__(self):
        return hash((
            self.posX, self.posY,
            self.battery,
            self.obstacle_distance,
            self.docked, self.airborne, self.crashed,
            frozenset(self.visZones)
        ))
    
    def __eq__(self, other):
        if not isinstance(other, DroneState):
            return False
        return (
            self.posX == other.posX and
            self.posY == other.posY and
            self.battery == other.battery and
            self.obstacle_distance == other.obstacle_distance and
            self.docked == other.docked and
            self.airborne == other.airborne and
            self.crashed == other.crashed and
            self.visZones == other.visZones
        )
    
    def check_invariant(self, maxX, maxY,  zoneCount):
        # Vérifications des bornes
        if not (0 <= self.posX <= maxX and 0 <= self.posY <= maxY):
            return False
        if not (0 <= self.baseX <= maxX and 0 <= self.baseY <= maxY):
            return False
        if not (0 <= self.battery <= 100):
            return False
        if self.obstacle_distance < 0:
            return False
        
        # Vérifications des états booléens
        if self.docked not in [0, 1]:
            return False
        if self.airborne not in [0, 1]:
            return False
        if self.crashed not in [0, 1]:
            return False
        
        # Vérification de visZones inclus dans 1..zoneCount
        if not all(isinstance(z, int) and 1 <= z <= zoneCount for z in self.visZones):
            return False
        
        # Contraintes logiques
        if self.crashed == 1 and self.airborne == 1:
            return False
        if self.docked == 1 and self.airborne == 1:
            return False
        if self.docked == 1 and (self.posX != self.baseX or self.posY != self.baseY):
            return False
        
        return True
 