"""Mode 3D RL avec Panda3D.

Lancer depuis la racine du projet :
    python run_3d.py
ou :
    python -m view3d.scene3d
"""

from __future__ import annotations

import os
import sys

# Autorise aussi : python view3d/scene3d.py
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from direct.showbase.ShowBase import ShowBase
from panda3d.core import AmbientLight, DirectionalLight, Vec4, WindowProperties

from agent_rl import ValueIterationAgent
from drone import DroneEnvironment

try:
    from .camera3d import IsoCamera3D
    from .drone3d import Drone3D
    from .hud3d import Hud3D
    from .terrain3d import Terrain3D
except ImportError:
    from camera3d import IsoCamera3D  # type: ignore
    from drone3d import Drone3D  # type: ignore
    from hud3d import Hud3D  # type: ignore
    from terrain3d import Terrain3D  # type: ignore


class Scene3D(ShowBase):
    """Fenêtre 3D : visualisation uniquement, logique dans DroneEnvironment."""

    def __init__(self, auto_train: bool = True):
        super().__init__()
        self.env = DroneEnvironment()
        self.agent: ValueIterationAgent | None = None
        self.agent_stats = None
        self.total_reward = 0.0
        self.steps = 0
        self.last_reward = "—"
        self.last_action_label = "—"
        self.playing = False
        self.animating = False
        self.play_delay = 0.55

        self._setup_window()
        self._setup_lighting()

        self.camera_controller = IsoCamera3D(self, radius=2)
        self.camera_controller.setup()

        self.terrain = Terrain3D(self.render, self.env.grille, radius=2)
        self.drone = Drone3D(self.render)
        self.taskMgr.add(self.drone.spin_task, "spin_propellers")

        self.hud = Hud3D(
            self,
            on_train=self.train_agent,
            on_play_pause=self.toggle_play,
            on_step=self.step_policy,
            on_reset=self.reset_mission,
            on_quit=self.userExit,
        )

        self.accept("space", self.step_policy)
        self.accept("p", self.toggle_play)
        self.accept("r", self.reset_mission)
        self.accept("t", self.train_agent)
        self.accept("escape", self.userExit)

        self.refresh_scene()
        if auto_train:
            self.train_agent()

    def _setup_window(self):
        if hasattr(self.win, "requestProperties"):
            props = WindowProperties()
            props.setTitle("Drone de patrouille - Mode 3D RL")
            props.setSize(1280, 720)
            self.win.requestProperties(props)
        self.setBackgroundColor(0.55, 0.73, 0.95, 1)

    def _setup_lighting(self):
        ambient = AmbientLight("ambient_light")
        ambient.setColor(Vec4(0.52, 0.55, 0.62, 1))
        ambient_np = self.render.attachNewNode(ambient)
        self.render.setLight(ambient_np)

        sun = DirectionalLight("sun_light")
        sun.setColor(Vec4(1.0, 0.96, 0.85, 1))
        sun_np = self.render.attachNewNode(sun)
        sun_np.setHpr(45, -58, 0)
        self.render.setLight(sun_np)

    # ---------- RL ----------
    def train_agent(self):
        self.hud.set_status("Entraînement Value Iteration en cours...")
        self.playing = False
        self.hud.set_playing(False)

        # Agent séparé de l'environnement visualisé pour éviter de modifier la scène pendant l'entraînement.
        self.agent = ValueIterationAgent(DroneEnvironment(), gamma=0.95, theta=0.001, max_iterations=30)
        self.agent_stats = self.agent.train()
        self.env.reset()
        self.total_reward = 0.0
        self.steps = 0
        self.last_reward = "—"
        self.last_action_label = "—"
        self.hud.set_status("Agent entraîné : politique prête. Espace = pas suivant, P = play/pause.")
        self.refresh_scene()

    def reset_mission(self):
        self.playing = False
        self.hud.set_playing(False)
        self.env.reset()
        self.total_reward = 0.0
        self.steps = 0
        self.last_reward = "—"
        self.last_action_label = "—"
        self.animating = False
        self.hud.set_status("Mission réinitialisée.")
        self.refresh_scene()

    def toggle_play(self):
        if self.agent is None:
            self.train_agent()
        self.playing = not self.playing
        self.hud.set_playing(self.playing)
        self.hud.set_status("Lecture automatique." if self.playing else "Pause.")
        if self.playing:
            self._schedule_next_step()

    def _schedule_next_step(self):
        self.taskMgr.doMethodLater(self.play_delay, self._play_task, "rl3d_play_task")

    def _play_task(self, task):
        if not self.playing:
            return task.done
        if not self.animating:
            self.step_policy()
        if self.playing:
            self._schedule_next_step()
        return task.done

    def step_policy(self):
        if self.animating:
            return
        if self.agent is None:
            self.train_agent()
            return

        state = self.env.state.copy()
        if self.agent.is_terminal_state(state):
            self.playing = False
            self.hud.set_playing(False)
            self.hud.set_status("Mission terminée : toutes les zones sont visitées ou état terminal atteint.")
            self.refresh_scene()
            return

        action = self.agent.best_action(state)
        if action is None:
            self.playing = False
            self.hud.set_playing(False)
            self.hud.set_status("Aucune action dans la politique pour cet état.")
            return

        success = self.agent.execute_policy_action(self.env, action)
        new_state = self.env.state.copy()
        reward = self.agent.reward(state, action, new_state) if success else -1000.0
        self.total_reward += reward
        self.steps += 1
        self.last_reward = f"{reward:.1f}"
        self.last_action_label = ValueIterationAgent.action_label(action)

        next_action = self.agent.best_action(new_state) if success else None

        # Vrai scrolling : on construit uniquement le ViewPort 5x5 de la destination,
        # puis on décale temporairement la map pour partir de l'ancienne position.
        # Pas de extra_radius : sinon on voit des cases hors champ pendant l'animation.
        self.terrain.update(new_state, next_action=next_action)
        self.terrain.animate_scroll(state, new_state, duration=0.42)

        self.animating = True
        self.drone.animate_centered_transition(state, new_state, duration=0.42, on_done=self._after_animation)
        self.hud.set_status(f"Action exécutée : {self.last_action_label}")
        self._update_hud()

    def _after_animation(self):
        self.animating = False
        state = self.env.state.copy()
        self.drone.update_visual_state(state)
        self.refresh_scene(update_terrain=False)
        if self.agent and self.agent.is_terminal_state(state):
            self.playing = False
            self.hud.set_playing(False)
            if self.agent.is_goal_state(state):
                self.hud.set_status("Mission réussie : les 4 zones ont été visitées.")
            else:
                self.hud.set_status("Mission terminée par échec ou batterie vide.")

    # ---------- affichage ----------
    def refresh_scene(self, update_terrain: bool = True):
        state = self.env.state.copy()
        next_action = self.agent.best_action(state) if self.agent is not None else None
        if update_terrain:
            self.terrain.update(state, next_action=next_action)
        self.drone.update_visual_state(state)
        self._update_hud()

    def _update_hud(self):
        self.hud.update(
            state=self.env.state,
            action=self.last_action_label,
            step_reward=self.last_reward,
            total_reward=self.total_reward,
            steps=self.steps,
            stats=self.agent_stats,
        )


def run_scene_3d(auto_train: bool = True):
    app = Scene3D(auto_train=auto_train)
    app.run()


def main():
    run_scene_3d(auto_train=True)


if __name__ == "__main__":
    main()
