from collections import deque

from constants import ZONE_COUNT
from drone import DroneEnvironment


class ValueIterationAgent:
    """
    Agent RL basé sur Value Iteration.

    Important : l'environnement expose move_step et avoid_maneuver comme actions
    non déterministes. Pour obtenir un agent réellement intelligent en GUI, on
    transforme ces successeurs en décisions directionnelles déterministes côté
    agent : move_up, move_down, move_left, move_right, etc.

    Ainsi l'agent ne dit plus seulement "déplacement" en laissant l'environnement
    choisir un voisin au hasard : il choisit la case voisine qui maximise V(s).
    """

    DIRECTIONS = {
        "up": (0, 1),
        "down": (0, -1),
        "right": (1, 0),
        "left": (-1, 0),
    }

    DIRECTION_LABELS = {
        "up": "↑",
        "down": "↓",
        "right": "→",
        "left": "←",
    }

    def __init__(self, env=None, gamma=0.95, theta=1e-3, max_iterations=40):
        self.env = env if env is not None else DroneEnvironment()
        self.gamma = gamma
        self.theta = theta
        self.max_iterations = max_iterations

        self.states = set()
        self.transitions = {}
        self.values = {}
        self.policy = {}
        self._distance_unvisited_cache = {}
        self._reward_cache = {}

    # ===================== États terminaux côté agent =====================

    def is_failure_state(self, state):
        """Échec : drone crashé ou batterie vide."""
        return state.crashed == 1 or state.battery == 0

    def is_goal_state(self, state):
        """
        Mission réussie : toutes les zones de patrouille sont visitées.
        On ne force pas le retour à la base, car sinon l'agent peut donner
        l'impression de rentrer trop souvent. Le retour reste disponible
        uniquement si la batterie devient faible.
        """
        return (
            len(state.visZones) == ZONE_COUNT
            and state.crashed == 0
            and not self.env.grille.indangerZone(state.posX, state.posY)
        )

    def is_terminal_state(self, state):
        return self.is_failure_state(state) or self.is_goal_state(state)

    # ===================== Aides état / distance =====================

    def distance_to_base(self, state):
        return abs(state.posX - state.baseX) + abs(state.posY - state.baseY)

    def unvisited_zones(self, state):
        return set(range(1, ZONE_COUNT + 1)) - set(state.visZones)

    def distance_to_nearest_unvisited_zone(self, state):
        """Distance Manhattan minimale vers une cellule appartenant à une zone non visitée."""
        key = (state.posX, state.posY, frozenset(state.visZones))
        if key in self._distance_unvisited_cache:
            return self._distance_unvisited_cache[key]

        targets = self.unvisited_zones(state)
        if not targets:
            self._distance_unvisited_cache[key] = 0
            return 0

        best = None
        for x in range(self.env.grille.maxX + 1):
            for y in range(self.env.grille.maxY + 1):
                if self.env.grille.zoneOf(x, y) in targets:
                    distance = abs(state.posX - x) + abs(state.posY - y)
                    if best is None or distance < best:
                        best = distance
        best = best if best is not None else 0
        self._distance_unvisited_cache[key] = best
        return best

    def battery_is_low(self, state):
        """
        Batterie faible = il faut penser au retour. On garde une marge au-dessus
        de la distance à la base pour éviter les crashs.
        """
        return state.battery <= max(18, self.distance_to_base(state) + 8)

    def return_home_is_useful(self, state):
        return self.battery_is_low(state)

    # ===================== Actions directionnelles côté agent =====================

    @classmethod
    def is_directional_action(cls, action):
        return action.startswith("move_") or action.startswith("avoid_")

    @classmethod
    def action_direction(cls, action):
        for prefix in ("move_", "avoid_"):
            if action.startswith(prefix):
                direction = action[len(prefix):]
                if direction in cls.DIRECTIONS:
                    return direction
        return None

    @classmethod
    def base_environment_action(cls, action):
        if action.startswith("move_"):
            return "move_step"
        if action.startswith("avoid_"):
            return "avoid_maneuver"
        return action

    @classmethod
    def action_label(cls, action):
        if action is None:
            return "mission terminée"
        direction = cls.action_direction(action)
        if action.startswith("move_") and direction:
            return f"Déplacement {cls.DIRECTION_LABELS[direction]}"
        if action.startswith("avoid_") and direction:
            return f"Évitement {cls.DIRECTION_LABELS[direction]}"
        labels = {
            "takeoff_cmd": "Décollage",
            "return_home": "Retour base",
            "dock_cmd": "Arrimer",
            "undock_cmd": "Désarrimer",
            "charge_step": "Recharger",
            "emergency_stop": "Stop urgence",
        }
        return labels.get(action, action)

    def direction_from_to(self, state, next_state):
        dx = next_state.posX - state.posX
        dy = next_state.posY - state.posY
        for name, vector in self.DIRECTIONS.items():
            if vector == (dx, dy):
                return name
        return None

    # ===================== Interface avec l'environnement =====================

    def _environment_actions(self, state):
        saved_state = self.env.state
        self.env.state = state.copy()
        actions = self.env.get_available_actions()
        self.env.state = saved_state
        return actions

    def available_actions(self, state):
        """
        Retourne les actions choisissables par l'agent.

        On filtre les actions inutiles :
        - pas de return_home tant que toutes les zones ne sont pas visitées,
          sauf si la batterie devient faible ;
        - pas de dock/charge inutiles au début ;
        - emergency_stop seulement en dernier recours.
        """
        if self.is_terminal_state(state):
            return []

        env_actions = self._environment_actions(state)
        agent_actions = []

        if "takeoff_cmd" in env_actions:
            agent_actions.append("takeoff_cmd")

        if "move_step" in env_actions:
            for successor in self.raw_successors(state, "move_step"):
                direction = self.direction_from_to(state, successor)
                if direction is not None:
                    agent_actions.append(f"move_{direction}")

        if "avoid_maneuver" in env_actions:
            for successor in self.raw_successors(state, "avoid_maneuver"):
                direction = self.direction_from_to(state, successor)
                if direction is not None:
                    action = f"avoid_{direction}"
                    if action not in agent_actions:
                        agent_actions.append(action)

        if "return_home" in env_actions and self.return_home_is_useful(state):
            agent_actions.append("return_home")

        if "dock_cmd" in env_actions and self.battery_is_low(state):
            agent_actions.append("dock_cmd")

        if "charge_step" in env_actions and state.battery < 100 and self.battery_is_low(state):
            agent_actions.append("charge_step")

        if "undock_cmd" in env_actions and len(state.visZones) < ZONE_COUNT and state.battery >= 60:
            agent_actions.append("undock_cmd")

        # Stop urgence uniquement si l'agent n'a vraiment rien d'autre.
        if not agent_actions and "emergency_stop" in env_actions:
            agent_actions.append("emergency_stop")

        return agent_actions

    def raw_successors(self, state, action):
        """
        Retourne les successeurs possibles de (state, action), sans probabilité.
        Les actions directionnelles de l'agent retournent un seul successeur.
        """
        base_action = self.base_environment_action(action)
        saved_state = self.env.state
        self.env.state = state.copy()

        if base_action == "move_step":
            successors = self.env.move_step()
        elif base_action == "avoid_maneuver":
            successors = self.env.avoid_maneuver()
        elif base_action == "return_home":
            successor = self.env.return_home()
            successors = [] if successor is None else [successor]
        elif base_action in {
            "takeoff_cmd",
            "dock_cmd",
            "undock_cmd",
            "charge_step",
            "emergency_stop",
        }:
            success = getattr(self.env, base_action)()
            successors = [self.env.state.copy()] if success else []
        else:
            successors = []

        self.env.state = saved_state
        successors = [s.copy() for s in successors]

        direction = self.action_direction(action)
        if direction is not None:
            dx, dy = self.DIRECTIONS[direction]
            target = (state.posX + dx, state.posY + dy)
            successors = [s for s in successors if (s.posX, s.posY) == target]

        return successors

    def transition_probabilities(self, state, action):
        """
        Retourne [(successeur, probabilité), ...].
        Les anciennes actions non déterministes restent équiprobables, mais les
        actions directionnelles utilisées par la politique ont une probabilité 1.
        """
        successors = self.raw_successors(state, action)
        if not successors:
            return []

        # On regroupe manuellement les doublons possibles.
        grouped = {}
        for successor in successors:
            grouped[successor] = grouped.get(successor, 0) + 1

        total = len(successors)
        return [(succ.copy(), count / total) for succ, count in grouped.items()]

    def execute_policy_action(self, env, action):
        """
        Exécute une action de la politique dans un vrai DroneEnvironment.
        Nécessaire pour les actions directionnelles move_up/move_right/etc.
        """
        if action is None:
            return False

        if self.action_direction(action) is None:
            return env.execute_action(action)

        state = env.state.copy()
        successors = self.raw_successors(state, action)
        if not successors:
            return False

        env.state = successors[0].copy()
        env._check_invariant()
        return True

    # ===================== Exploration exhaustive =====================

    def build_state_space(self):
        """Construit S et les transitions accessibles depuis l'état initial."""
        initial_state = self.env.reset().copy()

        self.states = {initial_state}
        self.transitions = {}
        queue = deque([initial_state])

        while queue:
            state = queue.popleft().copy()

            if self.is_terminal_state(state):
                self.transitions[state] = {}
                continue

            action_map = {}
            for action in self.available_actions(state):
                trans = self.transition_probabilities(state, action)
                if not trans:
                    continue

                action_map[action] = trans
                for next_state, _probability in trans:
                    if next_state not in self.states:
                        self.states.add(next_state.copy())
                        queue.append(next_state.copy())

            self.transitions[state] = action_map

        self.values = {state: 0.0 for state in self.states}
        self.policy = {}
        return self.states, self.transitions

    # ===================== Récompense =====================

    def reward(self, state, action, next_state):
        cached = self._reward_cache.get((state, action, next_state))
        if cached is not None:
            return cached

        """
        Récompense plus guidée pour éviter les boucles :
        - gros bonus pour nouvelle zone ;
        - bonus de progression vers la prochaine zone non visitée ;
        - retour base utile seulement après couverture complète ou batterie basse ;
        - mission finale quand toutes les zones sont visitées et drone docké.
        """
        base_action = self.base_environment_action(action)

        key = (state, action, next_state)
        if base_action == "emergency_stop" or next_state.crashed == 1:
            self._reward_cache[key] = -1000.0
            return -1000.0
        if next_state.battery == 0:
            self._reward_cache[key] = -1000.0
            return -1000.0
        if self.is_goal_state(next_state):
            self._reward_cache[key] = 800.0
            return 800.0

        reward = 0.0

        # Coût de base, pour que chaque action inutile fasse mal.
        if base_action == "move_step":
            reward -= 2.0
        elif base_action == "avoid_maneuver":
            reward -= 3.0
        elif base_action == "return_home":
            reward -= 1.5
        elif base_action in {"dock_cmd", "undock_cmd", "charge_step"}:
            reward -= 0.5
        else:
            reward -= 0.2

        old_zone_count = len(state.visZones)
        new_zone_count = len(next_state.visZones)
        new_zones = next_state.visZones - state.visZones

        # Le but principal : visiter de nouvelles zones.
        if new_zones:
            reward += 180.0 * len(new_zones)
        elif base_action in {"move_step", "avoid_maneuver"} and new_zone_count < ZONE_COUNT:
            # Déplacement qui ne sert pas directement : pénalité supplémentaire.
            reward -= 4.0

        # Shaping : tant que tout n'est pas visité, on favorise la direction qui
        # rapproche d'une zone non visitée.
        if old_zone_count < ZONE_COUNT and base_action in {"move_step", "avoid_maneuver"}:
            old_dist = self.distance_to_nearest_unvisited_zone(state)
            new_dist = self.distance_to_nearest_unvisited_zone(next_state)
            if new_dist < old_dist:
                reward += 8.0
            elif new_dist > old_dist:
                reward -= 4.0

        # Danger.
        if self.env.grille.indangerZone(next_state.posX, next_state.posY):
            reward -= 420.0
        elif self.env.grille.indangerZone(state.posX, state.posY):
            reward += 20.0

        # Retour à la base : interdit/fortement pénalisé avant que ce soit utile.
        if base_action == "return_home":
            old_distance = self.distance_to_base(state)
            new_distance = self.distance_to_base(next_state)
            if len(state.visZones) == ZONE_COUNT:
                if new_distance < old_distance:
                    reward += 35.0
            elif self.battery_is_low(state):
                if new_distance < old_distance:
                    reward += 15.0
            else:
                reward -= 100.0

        # Une fois toutes les zones visitées, on pousse vers base + dock.
        if len(state.visZones) == ZONE_COUNT and base_action in {"move_step", "avoid_maneuver"}:
            old_distance = self.distance_to_base(state)
            new_distance = self.distance_to_base(next_state)
            if new_distance < old_distance:
                reward += 12.0
            elif new_distance > old_distance:
                reward -= 8.0

        if base_action == "dock_cmd":
            if len(state.visZones) == ZONE_COUNT:
                reward += 300.0
            elif self.battery_is_low(state):
                reward += 20.0
            else:
                reward -= 80.0

        if base_action == "charge_step":
            if state.battery <= 30 and next_state.battery > state.battery:
                reward += 25.0
            elif state.battery >= 95:
                reward -= 50.0
            else:
                reward += 2.0

        self._reward_cache[key] = reward
        return reward

    # ===================== Value Iteration =====================

    def q_value(self, state, action):
        total = 0.0
        for next_state, probability in self.transitions.get(state, {}).get(action, []):
            total += probability * (
                self.reward(state, action, next_state)
                + self.gamma * self.values.get(next_state, 0.0)
            )
        return total

    def train(self):
        """Calcule V* puis la politique optimale pi*."""
        if not self.states or not self.transitions:
            self.build_state_space()

        iteration_count = 0
        last_delta = 0.0

        ordered_states = sorted(
            self.states,
            key=lambda state: (
                len(state.visZones),
                state.docked,
                state.airborne,
                -state.battery,
                state.posX,
                state.posY,
            ),
            reverse=True,
        )

        for iteration in range(1, self.max_iterations + 1):
            iteration_count = iteration
            last_delta = 0.0

            new_values = dict(self.values)
            for state in ordered_states:
                actions = self.transitions.get(state, {})

                if self.is_terminal_state(state) or not actions:
                    new_values[state] = 0.0
                    continue

                old_value = self.values[state]
                best_value = max(self.q_value(state, action) for action in actions)
                new_values[state] = best_value
                last_delta = max(last_delta, abs(best_value - old_value))

            self.values = new_values
            if last_delta < self.theta:
                break

        self.extract_policy()

        return {
            "states": len(self.states),
            "transitions": sum(
                len(successors)
                for action_map in self.transitions.values()
                for successors in action_map.values()
            ),
            "iterations": iteration_count,
            "delta": last_delta,
            "goal_states": sum(1 for state in self.states if self.is_goal_state(state)),
            "failure_states": sum(1 for state in self.states if self.is_failure_state(state)),
        }

    def extract_policy(self):
        self.policy = {}

        for state in self.states:
            actions = self.transitions.get(state, {})
            if self.is_terminal_state(state) or not actions:
                continue

            best_action = max(actions, key=lambda action: self.q_value(state, action))
            self.policy[state] = best_action

        return self.policy

    def best_action(self, state):
        return self.policy.get(state)

    # ===================== Simulation avec la politique =====================

    def run_episode(self, env=None, max_steps=200, seed=None):
        """Exécute la politique calculée dans un environnement concret."""
        run_env = env if env is not None else DroneEnvironment()
        run_env.reset()

        trajectory = []

        for step in range(max_steps):
            state = run_env.state.copy()

            if self.is_terminal_state(state):
                break

            action = self.best_action(state)
            if action is None:
                break

            success = self.execute_policy_action(run_env, action)
            next_state = run_env.state.copy()
            step_reward = self.reward(state, action, next_state) if success else -1000.0

            trajectory.append({
                "step": step,
                "state": state,
                "action": action,
                "next_state": next_state,
                "reward": step_reward,
                "success": success,
            })

            if not success:
                break

        return trajectory, run_env.state.copy()

    @staticmethod
    def short_state(state):
        return (
            f"pos=({state.posX},{state.posY}), "
            f"bat={state.battery}, "
            f"air={state.airborne}, "
            f"dock={state.docked}, "
            f"crash={state.crashed}, "
            f"zones={sorted(state.visZones)}"
        )
