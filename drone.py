from grille import grille_env
from etats import DroneState
from constants import *

class DroneEnvironment:
    def __init__(self, maxX=MAX_X, maxY=MAX_Y, baseX=BASE_X, baseY=BASE_Y, danger=DANGER):
        self.grille = grille_env(maxX, maxY, baseX, baseY, danger)
        self.state = None
        self.reset()
    
    def reset(self):
        self.state = DroneState(
            self.grille.baseX,
            self.grille.baseY,
            self.grille.baseX,
            self.grille.baseY
        )
        # Zone de la base est visitée dès l'initialisation
        self.state.visZones.add(self.grille.zoneOf(self.state.posX, self.state.posY))
        return self.state

    def _check_invariant(self):
        if not self.state.check_invariant(
            self.grille.maxX,
            self.grille.maxY,
            ZONE_COUNT
        ):
            raise ValueError("Invariant d'état violé")
    
    def get_available_actions(self):
        actions = []
        
        if self._can_takeoff():
            actions.append('takeoff_cmd')
        if self._can_move():
            actions.append('move_step')
        if self._can_avoid():
            actions.append('avoid_maneuver')
        if self._can_return_home():
            actions.append('return_home')
        if self._can_dock():
            actions.append('dock_cmd')
        if self._can_undock():
            actions.append('undock_cmd')
        if self._can_charge():
            actions.append('charge_step')
        # emergency_stop est toujours disponible (pas de précondition)
        actions.append('emergency_stop')
        
        return actions
    
    # ========== PRÉCONDITIONS ==========
    
    def _can_takeoff(self):
        """Précondition pour takeoff_cmd"""
        return (self.state.crashed == 0 and # pas crashé
                self.state.airborne == 0 and #pas deja en vol
                self.state.docked == 0 and #pas docke
                self.state.battery > 0) # batterie > 0
    
    def _can_move(self):
        """Précondition pour move_step"""
        return (self.state.crashed == 0 and 
                self.state.airborne == 1 and 
                self.state.docked == 0 and 
                self.state.battery > 0)
    
    def _can_avoid(self):
        """Précondition pour avoid_maneuver"""
        return (self.state.crashed == 0 and 
                self.state.airborne == 1 and 
                self.state.docked == 0 and 
                self.state.battery > 1)
    
    def _can_return_home(self):
        """Précondition pour return_home"""
        return (self.state.crashed == 0 and 
                self.state.airborne == 1 and 
                self.state.docked == 0 and 
                self.state.battery > 0)
    
    def _can_dock(self):
        """Précondition pour dock_cmd"""
        return (self.state.crashed == 0 and # pas crashé
                self.state.airborne == 1 and # en vol
                self.state.docked == 0 and # pas déjà docké
                self.grille.isInBase(self.state.posX, self.state.posY)) # à la base
    
    def _can_undock(self):
        """Précondition pour undock_cmd"""
        return (self.state.crashed == 0 and 
                self.state.docked == 1 and 
                self.state.battery > 0)
    
    def _can_charge(self):
        """Précondition pour charge_step"""
        return (self.state.crashed == 0 and 
                self.state.docked == 1)
    
    # ========== OPÉRATIONS ==========
    
    def takeoff_cmd(self):
        if not self._can_takeoff():
            return False
        
        self.state.airborne = 1
        
        # Mise à jour de obstacle_distance
        if self.grille.indangerZone(self.state.posX, self.state.posY):
            self.state.obstacle_distance = 0 # Danger immediat
        else:
            self.state.obstacle_distance = 2 # pas de danger immediat
        
        return True
    
    def move_step(self):
        if not self._can_move():
            return []
        
        successors = []
        voisins = self.grille.voisins(self.state.posX, self.state.posY)
        
        for nextX, nextY in voisins:
            new_state = self.state.copy()
            new_state.posX = nextX
            new_state.posY = nextY
            new_state.battery -= COST_MOVE # enleve 1 de la batterie
            new_state.visZones.add(self.grille.zoneOf(nextX, nextY)) # ajoute la zone visitée
            
            # Mise à jour obstacle_distance
            if self.grille.indangerZone(nextX, nextY):
                new_state.obstacle_distance = 0
            else:
                new_state.obstacle_distance = 2
            
            successors.append(new_state)
        
        return successors
    
    def avoid_maneuver(self):
        if not self._can_avoid():
            return []
        
        successors = []
        voisins = self.grille.voisins(self.state.posX, self.state.posY)
        
        # Chercher les voisins sûrs
        safe_neighbors = [(x, y) for x, y in voisins 
                         if not self.grille.indangerZone(x, y)]
        
        if len(safe_neighbors) > 0:
            # Cas favorable : voisin sûr disponible
            for nextX, nextY in safe_neighbors:
                new_state = self.state.copy()
                new_state.posX = nextX
                new_state.posY = nextY
                new_state.battery -= COST_AVOID # enleve 2 de la batterie
                new_state.visZones.add(self.grille.zoneOf(nextX, nextY))
                new_state.obstacle_distance = 2  # Toujours 2 car cellule sûre
                successors.append(new_state)
        else:
            # Cas défavorable : aucun voisin sûr
            for nextX, nextY in voisins:
                new_state = self.state.copy()
                new_state.posX = nextX
                new_state.posY = nextY
                new_state.battery -= COST_AVOID # enleve 2 de la batterie
                new_state.visZones.add(self.grille.zoneOf(nextX, nextY))
                
                # Mise à jour obstacle_distance
                if self.grille.indangerZone(nextX, nextY):
                    new_state.obstacle_distance = 0
                else:
                    new_state.obstacle_distance = 2
                
                successors.append(new_state)
        
        return successors
    
    def return_home(self):
        if not self._can_return_home():
            return None
        
        new_state = self.state.copy()
        
        # Calcul de la position suivante
        if self.state.posX < self.state.baseX:
            new_state.posX = self.state.posX + 1
        elif self.state.posX > self.state.baseX:
            new_state.posX = self.state.posX - 1
        else:
            new_state.posX = self.state.posX
        
        if self.state.posY < self.state.baseY:
            new_state.posY = self.state.posY + 1
        elif self.state.posY > self.state.baseY:
            new_state.posY = self.state.posY - 1
        else:
            new_state.posY = self.state.posY
        
        new_state.battery -= COST_MOVE
        new_state.visZones.add(self.grille.zoneOf(new_state.posX, new_state.posY))
        
        # Mise à jour obstacle_distance
        if self.grille.indangerZone(new_state.posX, new_state.posY):
            new_state.obstacle_distance = 0
        else:
            new_state.obstacle_distance = 2
        
        return new_state
    
    def dock_cmd(self):
        if not self._can_dock():
            return False
        
        self.state.docked = 1
        self.state.airborne = 0
        
        return True
    
    def undock_cmd(self):
        if not self._can_undock():
            return False
        
        self.state.docked = 0
        self.state.airborne = 1
        self.state.visZones.add(self.grille.zoneOf(self.state.posX, self.state.posY))
        
        return True
    
    def charge_step(self):
        if not self._can_charge():
            return False
        
        if self.state.battery <= 95:
            self.state.battery += BATTERY_CHARGE_STEP
        else:
            self.state.battery = BATTERY_MAX
        
        return True
    
    def emergency_stop(self):
        self.state.crashed = 1
        self.state.airborne = 0
        self.state.docked = 0
        self.state.obstacle_distance = 0
        
        return True
    
    def execute_action(self, action_name):
        import random
        success = False
        if action_name == 'takeoff_cmd':
            success = self.takeoff_cmd()
        elif action_name == 'dock_cmd':
            success = self.dock_cmd()
        elif action_name == 'undock_cmd':
            success = self.undock_cmd()
        elif action_name == 'charge_step':
            success = self.charge_step()
        elif action_name == 'emergency_stop':
            success = self.emergency_stop()
        elif action_name == 'move_step':
            successors = self.move_step()
            if successors:
                self.state = random.choice(successors)
                success = True
        elif action_name == 'avoid_maneuver':
            successors = self.avoid_maneuver()
            if successors:
                self.state = random.choice(successors)
                success = True
        elif action_name == 'return_home':
            new_state = self.return_home()
            if new_state:
                self.state = new_state
                success = True
        else:
            return False
        if success:
            self._check_invariant()
        return success
    
    def is_terminal(self):
        return self.state.crashed == 1 or self.state.battery == 0
    