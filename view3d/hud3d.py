"""HUD Panda3D : panneau latéral compact pour ne pas cacher le drone."""

from __future__ import annotations

from direct.gui.DirectGui import DirectButton, DirectFrame, DirectLabel

try:
    from .common3d import rgba
except ImportError:
    from common3d import rgba  # type: ignore


class Hud3D:
    """
    HUD du mode 3D.

    Il est volontairement placé sur le côté droit de l'écran pour laisser
    la scène 3D et le drone visibles au centre.
    """

    def __init__(self, base, on_train, on_play_pause, on_step, on_reset, on_quit):
        self.base = base
        self.lines = {}
        self.status_label = None
        self.play_button = None
        self._build(on_train, on_play_pause, on_step, on_reset, on_quit)

    def _build(self, on_train, on_play_pause, on_step, on_reset, on_quit):
        # Panneau latéral droit : ne passe plus au milieu de l'écran.
        self.panel = DirectFrame(
            frameColor=(0.02, 0.05, 0.10, 0.72),
            frameSize=(-0.55, 0.55, -0.88, 0.88),
            pos=(1.14, 0, 0.0),
        )

        DirectLabel(
            parent=self.panel,
            text="DRONE RL 3D",
            scale=0.052,
            pos=(-0.48, 0, 0.78),
            text_align=0,
            frameColor=(0, 0, 0, 0),
            text_fg=(0.72, 0.88, 1.0, 1),
        )

        self.status_label = DirectLabel(
            parent=self.panel,
            text="Mode 3D prêt",
            scale=0.032,
            pos=(-0.48, 0, 0.68),
            text_align=0,
            frameColor=(0, 0, 0, 0),
            text_fg=(0.92, 0.95, 1.0, 1),
        )

        # Boutons en grille 2 colonnes, plus petits et dans le panneau.
        self._button("Train", -0.30, 0.54, on_train)
        self.play_button = self._button("Play", 0.20, 0.54, on_play_pause)
        self._button("Step", -0.30, 0.42, on_step)
        self._button("Reset", 0.20, 0.42, on_reset)
        self._button("Quit", -0.05, 0.30, on_quit, color=(0.50, 0.09, 0.09, 0.88), width=0.82)

        keys = ["pos", "battery", "zones", "action", "reward", "total", "state", "stats"]
        start_y = 0.14
        for i, key in enumerate(keys):
            self.lines[key] = DirectLabel(
                parent=self.panel,
                text="",
                scale=0.031,
                pos=(-0.48, 0, start_y - i * 0.105),
                text_align=0,
                frameColor=(0, 0, 0, 0),
                text_fg=(0.88, 0.92, 0.98, 1),
            )

        # Aide discrète en bas du panneau.
        DirectLabel(
            parent=self.panel,
            text="Raccourcis : Espace=Step | P=Play | R=Reset",
            scale=0.023,
            pos=(-0.48, 0, -0.80),
            text_align=0,
            frameColor=(0, 0, 0, 0),
            text_fg=(0.65, 0.72, 0.82, 1),
        )

    def _button(self, text, x, z, command, color=(0.08, 0.22, 0.43, 0.88), width=0.42):
        return DirectButton(
            parent=self.panel,
            text=text,
            scale=0.036,
            pos=(x, 0, z),
            command=command,
            frameColor=color,
            text_fg=(1, 1, 1, 1),
            relief=1,
            pad=(width, 0.075),
            frameSize=(-0.5, 0.5, -0.22, 0.22),
        )

    def set_status(self, message: str):
        if self.status_label is not None:
            self.status_label["text"] = self._shorten(message, 54)

    def set_playing(self, playing: bool):
        if self.play_button is not None:
            self.play_button["text"] = "Pause" if playing else "Play"

    def update(self, *, state, action="—", step_reward="—", total_reward=0.0, steps=0, stats=None):
        status = []
        if state.crashed:
            status.append("CRASHED")
        if state.airborne:
            status.append("AIRBORNE")
        if state.docked:
            status.append("DOCKED")
        if not status:
            status.append("GROUNDED")

        stats_text = "agent non entraîné"
        if stats:
            stats_text = f"S={stats.get('states', '?')} | T={stats.get('transitions', '?')} | it={stats.get('iterations', '?')}"

        values = {
            "pos": f"Position : ({state.posX}, {state.posY})",
            "battery": f"Batterie : {state.battery}%",
            "zones": f"Zones : {len(state.visZones)} / 4  {sorted(state.visZones)}",
            "action": f"Action : {self._shorten(str(action), 24)}",
            "reward": f"Reward étape : {step_reward}",
            "total": f"Reward total : {total_reward:.1f} | steps {steps}",
            "state": f"État : {', '.join(status)}",
            "stats": f"VI : {stats_text}",
        }
        for key, text in values.items():
            self.lines[key]["text"] = text

    @staticmethod
    def _shorten(text: str, max_len: int) -> str:
        return text if len(text) <= max_len else text[: max_len - 1] + "…"
