import csv
import subprocess
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from drone import DroneEnvironment
from agent_rl import ValueIterationAgent
from constants import ZONE_COUNT


BG = "#0f172a"
PANEL = "#111827"
CARD = "#1e293b"
CARD_2 = "#0b1220"
TEXT = "#e5e7eb"
MUTED = "#94a3b8"
ACCENT = "#22c55e"
ACCENT_2 = "#38bdf8"
WARNING = "#f59e0b"
DANGER = "#ef4444"
BORDER = "#334155"
LIGHT = "#f8fafc"
SUCCESS = "#16a34a"
RL_PURPLE = "#8b5cf6"
RL_YELLOW = "#facc15"

ZONE_COLORS = {
    1: "#1d4ed8",
    2: "#7c3aed",
    3: "#059669",
    4: "#d97706",
}

CELL = 58
PAD = 14
ANIM_MS = 260
ANIM_STEPS = 14

ALL_ACTIONS = [
    "takeoff_cmd",
    "move_step",
    "avoid_maneuver",
    "return_home",
    "dock_cmd",
    "undock_cmd",
    "charge_step",
    "emergency_stop",
]

ACTION_LABELS = {
    "takeoff_cmd": "Décollage",
    "move_step": "Déplacement",
    "avoid_maneuver": "Évitement",
    "return_home": "Retour base",
    "dock_cmd": "Arrimer",
    "undock_cmd": "Désarrimer",
    "charge_step": "Recharger",
    "emergency_stop": "Stop urgence",
}

ACTION_HINTS = {
    "takeoff_cmd": "Le drone décolle depuis le sol.",
    "move_step": "Déplacement standard vers un voisin.",
    "avoid_maneuver": "Déplacement priorisant les voisins sûrs.",
    "return_home": "Rapprochement automatique vers la base.",
    "dock_cmd": "Arrimage à la base.",
    "undock_cmd": "Quitte la base et repasse en vol.",
    "charge_step": "Recharge de la batterie à la base.",
    "emergency_stop": "Met fin immédiatement à la mission.",
}


def state_status(state):
    parts = []
    if state.crashed:
        parts.append("CRASHED")
    if state.airborne:
        parts.append("AIRBORNE")
    if state.docked:
        parts.append("DOCKED")
    if not parts:
        parts.append("GROUNDED")
    return ", ".join(parts)


class StatCard(ttk.Frame):
    def __init__(self, parent, title, value=""):
        super().__init__(parent, style="Card.TFrame", padding=(12, 10))
        ttk.Label(self, text=title, style="Mini.TLabel").pack(anchor="w")
        self.value = ttk.Label(self, text=value, style="Value.TLabel")
        self.value.pack(anchor="w", pady=(4, 0))
        

    def set(self, value):
        self.value.config(text=value)


class DroneApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Drone Patrol Simulator")
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        win_w = min(1180, max(980, screen_w - 80))
        win_h = min(760, max(700, screen_h - 80))
        self.geometry(f"{win_w}x{win_h}")
        self.minsize(960, 680)
        self.configure(bg=BG)

        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass
        self._setup_style()

        self.env = DroneEnvironment()
        self.mode = None
        self.step_count = 0
        self.history = []
        self.auto_queue = []
        self.auto_job = None
        self.auto_running = False
        self.animating = False
        self.exhaustive_running = False
        self.last_transitions_text = ""

        self.rl_agent = None
        self.rl_stats = None
        self.rl_training = False
        self.rl_playing = False
        self.rl_job = None
        self.rl_path_cells = set()
        self.rl_total_reward = 0.0
        self.rl_mission_steps = 0
        self.rl_last_action = "—"
        self.rl_last_reward = "—"

        self.csv_path_var = tk.StringVar(value="actions.csv")
        self.depth_var = tk.StringVar(value="5")
        self.breadth_var = tk.StringVar(value="4")
        self.auto_delay_var = tk.IntVar(value=650)
        self.rl_gamma_var = tk.StringVar(value="0.95")
        self.rl_theta_var = tk.StringVar(value="0.001")
        self.rl_iterations_var = tk.StringVar(value="30")
        self.rl_max_steps_var = tk.StringVar(value="80")
        self.rl_seed_var = tk.StringVar(value="0")
        self.status_var = tk.StringVar(value="Bienvenue")

        self.root_frame = ttk.Frame(self, style="Main.TFrame")
        self.root_frame.pack(fill="both", expand=True)

        self.show_home()

    # ---------- style ----------
    def _setup_style(self):
        self.style.configure("Main.TFrame", background=BG)
        self.style.configure("Panel.TFrame", background=PANEL)
        self.style.configure("Card.TFrame", background=CARD)
        self.style.configure("TLabelframe", background=PANEL, foreground=TEXT)
        self.style.configure("TLabelframe.Label", background=PANEL, foreground=TEXT, font=("Segoe UI", 11, "bold"))
        self.style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        self.style.configure("Title.TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 24, "bold"))
        self.style.configure("Sub.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 11))
        self.style.configure("CardTitle.TLabel", background=CARD, foreground=TEXT, font=("Segoe UI", 12, "bold"))
        self.style.configure("Mini.TLabel", background=CARD, foreground=MUTED, font=("Segoe UI", 10, "bold"))
        self.style.configure("Value.TLabel", background=CARD, foreground=TEXT, font=("Segoe UI", 17, "bold"))
        self.style.configure("Treeview", background=CARD_2, fieldbackground=CARD_2, foreground=TEXT, rowheight=28)
        self.style.configure("Treeview.Heading", background="#172554", foreground=TEXT, font=("Segoe UI", 10, "bold"))
        self.style.map("Treeview", background=[("selected", "#1d4ed8")])

    # ---------- generic ----------
    def clear_root(self):
        self.stop_auto(set_status=False)
        self.stop_rl(set_status=False)
        for child in self.root_frame.winfo_children():
            child.destroy()

    def show_home(self):
        self.clear_root()
        self.mode = None

        wrap = ttk.Frame(self.root_frame, style="Main.TFrame")
        wrap.pack(fill="both", expand=True, padx=30, pady=26)

        ttk.Label(wrap, text="Drone Patrol Simulator", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            wrap,
            text="Chaque mode a maintenant sa propre interface : uniquement les bons boutons, les bonnes infos, et la grille au centre.",
            style="Sub.TLabel",
        ).pack(anchor="w", pady=(8, 24))

        cards = ttk.Frame(wrap, style="Main.TFrame")
        cards.pack(fill="both", expand=True)
        for i in range(2):
            cards.columnconfigure(i, weight=1)
        for i in range(3):
            cards.rowconfigure(i, weight=1)

        self._home_card(cards, 0, 0, "Mode interactif", "Pilotage manuel, animation du drone, actions visibles uniquement quand elles sont autorisées.", "interactif")
        self._home_card(cards, 0, 1, "Mode automatique", "Lecture d'un CSV, boutons play / pause / pas suivant, suivi de la progression et animation sur la grille.", "automatique")
        self._home_card(cards, 1, 0, "Mode exhaustif", "Exploration des états avec paramètres depth/breadth et affichage des résultats utiles.", "exhaustif")
        self._home_card(cards, 1, 1, "Mode agent RL", "Value Iteration, politique optimale, score, récompenses et mission animée directement sur la grille.", "agent_rl")
        self._home_card(cards, 2, 0, "Mode 3D RL", "Visualisation Panda3D : champ stylisé, drone animé, ViewPort 5x5, HUD et politique RL.", "mode_3d")

    def _home_card(self, parent, row, col, title, desc, mode):
        card = ttk.Frame(parent, style="Card.TFrame", padding=18)
        card.grid(row=row, column=col, sticky="nsew", padx=12, pady=12)
        ttk.Label(card, text=title, style="CardTitle.TLabel").pack(anchor="w")
        tk.Label(card, text=desc, bg=CARD, fg=MUTED, justify="left", wraplength=320, font=("Segoe UI", 11)).pack(anchor="w", pady=(10, 18))
        tk.Button(
            card,
            text="Ouvrir",
            command=lambda m=mode: self.open_mode(m),
            bg="#2563eb",
            fg="white",
            activebackground="#1d4ed8",
            activeforeground="white",
            relief="flat",
            font=("Segoe UI", 11, "bold"),
            padx=16,
            pady=10,
            cursor="hand2",
        ).pack(anchor="w")

    def open_mode(self, mode):
        if mode == "mode_3d":
            self.launch_3d_mode()
            return
        self.clear_root()
        self.mode = mode
        self.env.reset()
        self.step_count = 0
        self.history = []
        self.auto_queue = []
        if mode == "agent_rl":
            self.reset_rl_mission_state()
        self.status_var.set(f"Mode {mode} prêt")

        self._build_shell(mode)
        self.refresh_view(full=True)

    def launch_3d_mode(self):
        """Lance le mode Panda3D dans un second processus pour ne pas bloquer Tkinter."""
        project_dir = Path(__file__).resolve().parent
        script = project_dir / "run_3d.py"
        if not script.exists():
            messagebox.showerror("Mode 3D", "run_3d.py est introuvable.")
            return
        try:
            subprocess.Popen([sys.executable, str(script)], cwd=str(project_dir))
            self.status_var.set("Mode 3D lancé dans une nouvelle fenêtre.")
            messagebox.showinfo("Mode 3D", "La fenêtre Panda3D va s'ouvrir. Si rien ne s'ouvre, installe Panda3D avec : python -m pip install -r requirements.txt")
        except Exception as exc:
            messagebox.showerror("Mode 3D", f"Impossible de lancer le mode 3D : {exc}")

    def _build_shell(self, mode):
        frame = ttk.Frame(self.root_frame, style="Main.TFrame")
        frame.pack(fill="both", expand=True, padx=18, pady=14)

        header = ttk.Frame(frame, style="Main.TFrame")
        header.pack(fill="x", pady=(0, 12))
        ttk.Label(header, text="Drone Patrol Simulator", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text=f"{mode.capitalize()}", style="Sub.TLabel").pack(side="left", padx=(14, 0), pady=(10, 0))
        tk.Button(
            header,
            text="← Retour menu",
            command=self.show_home,
            bg="#334155",
            fg="white",
            activebackground="#475569",
            activeforeground="white",
            relief="flat",
            padx=14,
            pady=8,
            font=("Segoe UI", 10, "bold"),
            cursor="hand2",
        ).pack(side="right")

        body = ttk.Frame(frame, style="Main.TFrame")
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=0, minsize=250)
        body.columnconfigure(1, weight=1, minsize=430)
        body.columnconfigure(2, weight=0, minsize=300)
        body.rowconfigure(0, weight=1)

        self.left_panel = ttk.Frame(body, style="Panel.TFrame", width=250)
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.left_panel.grid_propagate(False)
        self.center_panel = ttk.Frame(body, style="Panel.TFrame")
        self.center_panel.grid(row=0, column=1, sticky="nsew")
        self.right_panel = ttk.Frame(body, style="Panel.TFrame", width=300)
        self.right_panel.grid(row=0, column=2, sticky="nsew", padx=(8, 0))
        self.right_panel.grid_propagate(False)

        self._build_center_panel()
        if mode == "interactif":
            self._build_interactive_ui()
        elif mode == "automatique":
            self._build_automatic_ui()
        elif mode == "agent_rl":
            self._build_agent_rl_ui()
        else:
            self._build_exhaustive_ui()

    # ---------- center / canvas ----------
    def _build_center_panel(self):
        top = ttk.Frame(self.center_panel, style="Panel.TFrame")
        top.pack(fill="x", padx=12, pady=12)
        self.status_badge = tk.Label(top, textvariable=self.status_var, bg="#052e16", fg="#dcfce7", padx=12, pady=8, font=("Segoe UI", 10, "bold"))
        self.status_badge.pack(side="left")

        self.hint_label = tk.Label(top, text="", bg="#172554", fg="#dbeafe", padx=12, pady=8, font=("Segoe UI", 10, "bold"))
        self.hint_label.pack(side="left", padx=8)

        card = ttk.Frame(self.center_panel, style="Card.TFrame")
        card.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        ttk.Label(card, text="Grille et déplacement du drone", style="CardTitle.TLabel").pack(anchor="w", padx=12, pady=(12, 0))

        self.canvas = tk.Canvas(card, width=520, height=560, bg="#020617", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=12, pady=12)
        self.drone_center = None

    # ---------- mode: interactif ----------
    def _build_interactive_ui(self):
        controls = ttk.LabelFrame(self.left_panel, text="Actions manuelles")
        controls.pack(fill="x", padx=12, pady=12)

        ttk.Button(controls, text="Réinitialiser", command=self.reset_env).pack(fill="x", padx=10, pady=(10, 8))
        ttk.Label(controls, text="Clique sur une action disponible.").pack(anchor="w", padx=10, pady=(0, 8))

        self.action_buttons_frame = ttk.Frame(controls, style="Panel.TFrame")
        self.action_buttons_frame.pack(fill="x", padx=8, pady=(0, 10))

        mission = ttk.LabelFrame(self.left_panel, text="Mission")
        mission.pack(fill="x", padx=12, pady=(0, 12))
        self.manual_help = tk.Label(mission, text="Les infos utiles s'affichent ici selon l'action sélectionnée.", bg=PANEL, fg=MUTED, justify="left", wraplength=220, font=("Segoe UI", 10))
        self.manual_help.pack(anchor="w", padx=10, pady=10)

        self._build_side_monitor(show_tree=False)

    # ---------- mode: automatique ----------
    def _build_automatic_ui(self):
        csv_box = ttk.LabelFrame(self.left_panel, text="Lecture CSV")
        csv_box.pack(fill="x", padx=12, pady=12)

        row = ttk.Frame(csv_box)
        row.pack(fill="x", padx=10, pady=(10, 8))
        self.csv_entry = tk.Entry(row, textvariable=self.csv_path_var, bg=CARD_2, fg=TEXT, insertbackground=TEXT, relief="flat")
        self.csv_entry.pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Ouvrir", command=self.choose_csv).pack(side="left", padx=(8, 0))

        ttk.Button(csv_box, text="Charger la séquence", command=self.load_csv_queue).pack(fill="x", padx=10, pady=4)

        player = ttk.Frame(csv_box)
        player.pack(fill="x", padx=10, pady=(8, 10))
        ttk.Button(player, text="Pas suivant", command=self.next_auto_step).pack(side="left", fill="x", expand=True)
        ttk.Button(player, text="Play", command=self.start_auto).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(player, text="Pause", command=self.stop_auto).pack(side="left", fill="x", expand=True)

        speed = ttk.LabelFrame(self.left_panel, text="Vitesse")
        speed.pack(fill="x", padx=12, pady=(0, 12))
        tk.Scale(
            speed,
            from_=150,
            to=1500,
            resolution=50,
            orient="horizontal",
            variable=self.auto_delay_var,
            bg=PANEL,
            fg=TEXT,
            troughcolor=CARD,
            highlightthickness=0,
            activebackground=ACCENT_2,
            label="Délai entre deux actions (ms)",
        ).pack(fill="x", padx=10, pady=10)

        self.queue_label = tk.Label(self.left_panel, text="Aucune séquence chargée", bg=PANEL, fg=MUTED, justify="left", wraplength=220, font=("Segoe UI", 10))
        self.queue_label.pack(anchor="w", padx=16, pady=(0, 8))

        self._build_side_monitor(show_tree=False)

    # ---------- mode: exhaustif ----------
    def _build_exhaustive_ui(self):
        params = ttk.LabelFrame(self.left_panel, text="Paramètres d'exploration")
        params.pack(fill="x", padx=12, pady=12)

        grid = ttk.Frame(params)
        grid.pack(fill="x", padx=10, pady=(10, 8))
        ttk.Label(grid, text="Depth").grid(row=0, column=0, sticky="w")
        tk.Entry(grid, textvariable=self.depth_var, bg=CARD_2, fg=TEXT, insertbackground=TEXT, relief="flat", width=8).grid(row=0, column=1, padx=(8, 14))
        ttk.Label(grid, text="Breadth").grid(row=0, column=2, sticky="w")
        tk.Entry(grid, textvariable=self.breadth_var, bg=CARD_2, fg=TEXT, insertbackground=TEXT, relief="flat", width=8).grid(row=0, column=3, padx=(8, 0))

        ttk.Button(params, text="Lancer l'exploration", command=self.run_exhaustive).pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(params, text="Voir les transitions", command=self.open_transitions_window).pack(fill="x", padx=10, pady=(0, 10))
        note = ttk.LabelFrame(self.left_panel, text="Ce qu'on affiche")
        note.pack(fill="x", padx=12, pady=(0, 12))
        tk.Label(
            note,
            text=(
                "Ici on évite l'écran surchargé.\n\n"
                "• paramètres depth / breadth\n"
                "• résultats principaux\n"
                "• résumé lisible\n\n"
                "Le pilotage manuel n'apparaît pas dans ce mode."
            ),
            bg=PANEL,
            fg=MUTED,
            justify="left",
            wraplength=220,
            font=("Segoe UI", 10),
        ).pack(anchor="w", padx=10, pady=10)

        self._build_side_monitor(show_tree=True)


    # ---------- mode: agent RL ----------
    def _build_agent_rl_ui(self):
        learning = ttk.LabelFrame(self.left_panel, text="Apprentissage RL")
        learning.pack(fill="x", padx=12, pady=12)

        form = ttk.Frame(learning)
        form.pack(fill="x", padx=10, pady=(10, 8))
        ttk.Label(form, text="Gamma").grid(row=0, column=0, sticky="w", pady=3)
        tk.Entry(form, textvariable=self.rl_gamma_var, bg=CARD_2, fg=TEXT, insertbackground=TEXT, relief="flat", width=8).grid(row=0, column=1, padx=(8, 12), pady=3)
        ttk.Label(form, text="Theta").grid(row=0, column=2, sticky="w", pady=3)
        tk.Entry(form, textvariable=self.rl_theta_var, bg=CARD_2, fg=TEXT, insertbackground=TEXT, relief="flat", width=8).grid(row=0, column=3, padx=(8, 0), pady=3)

        ttk.Label(form, text="Itérations").grid(row=1, column=0, sticky="w", pady=3)
        tk.Entry(form, textvariable=self.rl_iterations_var, bg=CARD_2, fg=TEXT, insertbackground=TEXT, relief="flat", width=8).grid(row=1, column=1, padx=(8, 12), pady=3)
        ttk.Label(form, text="Seed").grid(row=1, column=2, sticky="w", pady=3)
        tk.Entry(form, textvariable=self.rl_seed_var, bg=CARD_2, fg=TEXT, insertbackground=TEXT, relief="flat", width=8).grid(row=1, column=3, padx=(8, 0), pady=3)

        ttk.Button(learning, text="Entraîner l'agent", command=self.train_rl_agent).pack(fill="x", padx=10, pady=(0, 6))
        ttk.Button(learning, text="Voir politique complète", command=self.open_transitions_window).pack(fill="x", padx=10, pady=(0, 10))

        mission = ttk.LabelFrame(self.left_panel, text="Mission avec la politique")
        mission.pack(fill="x", padx=12, pady=(0, 12))

        max_row = ttk.Frame(mission)
        max_row.pack(fill="x", padx=10, pady=(10, 8))
        ttk.Label(max_row, text="Max steps").pack(side="left")
        tk.Entry(max_row, textvariable=self.rl_max_steps_var, bg=CARD_2, fg=TEXT, insertbackground=TEXT, relief="flat", width=8).pack(side="left", padx=(8, 0))

        ttk.Button(mission, text="Réinitialiser mission", command=self.reset_env).pack(fill="x", padx=10, pady=(0, 6))

        player = ttk.Frame(mission)
        player.pack(fill="x", padx=10, pady=(4, 10))
        ttk.Button(player, text="Pas politique", command=self.rl_step_policy).pack(side="left", fill="x", expand=True)
        ttk.Button(player, text="Play", command=self.start_rl_policy).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(player, text="Pause", command=self.stop_rl).pack(side="left", fill="x", expand=True)

        speed = ttk.LabelFrame(self.left_panel, text="Vitesse animation")
        speed.pack(fill="x", padx=12, pady=(0, 12))
        tk.Scale(
            speed,
            from_=150,
            to=1500,
            resolution=50,
            orient="horizontal",
            variable=self.auto_delay_var,
            bg=PANEL,
            fg=TEXT,
            troughcolor=CARD,
            highlightthickness=0,
            activebackground=RL_PURPLE,
            label="Délai entre deux actions (ms)",
        ).pack(fill="x", padx=10, pady=10)

        note = ttk.LabelFrame(self.left_panel, text="Objectif de l'agent")
        note.pack(fill="x", padx=12, pady=(0, 12))
        tk.Label(
            note,
            text=(
                "Value Iteration calcule une politique π*.\n\n"
                "Le score récompense :\n"
                "• nouvelles zones visitées\n"
                "• progression vers zones non visitées\n"
                "• retour à la base seulement quand utile\n"
                "• mission complète = toutes les zones visitées\n\n"
                "Il pénalise : danger, batterie vide, crash et boucles inutiles."
            ),
            bg=PANEL,
            fg=MUTED,
            justify="left",
            wraplength=220,
            font=("Segoe UI", 10),
        ).pack(anchor="w", padx=10, pady=10)

        self._build_side_monitor(show_tree=True)
        self.result_title.config(text="Stats RL")
        self.transitions_title.config(text="Politique / trajectoire")
        self.log_title.config(text="Journal RL")

    def _build_side_monitor(self, show_tree):
        metrics = ttk.Frame(self.right_panel, style="Main.TFrame")
        metrics.pack(fill="x", padx=10, pady=10)

        top_row = ttk.Frame(metrics, style="Main.TFrame")
        top_row.pack(fill="x")
        self.stat_position = StatCard(top_row, "Position")
        self.stat_position.pack(side="left", fill="x", expand=True, pady=(0, 8))
        self.stat_battery = StatCard(top_row, "Batterie")
        self.stat_battery.pack(side="left", fill="x", expand=True, padx=(8, 0), pady=(0, 8))

        self.stat_status = StatCard(metrics, "Statut")
        self.stat_status.pack(fill="x", pady=(0, 8))
        self.stat_zones = StatCard(metrics, "Zones")
        self.stat_zones.pack(fill="x", pady=(0, 8))

        tel = ttk.Frame(self.right_panel, style="Card.TFrame", padding=10)
        tel.pack(fill="x", padx=10, pady=(0, 10))
        title = "Résumé d'exploration" if show_tree else "Infos utiles"
        ttk.Label(tel, text=title, style="CardTitle.TLabel").pack(anchor="w")

        self.side_info = tk.Label(
            tel,
            text="",
            bg=CARD,
            fg=TEXT,
            justify="left",
            anchor="w",
            font=("Consolas", 9),
            wraplength=260
        )
        self.side_info.pack(fill="x", pady=(8, 0))

        self.log_card = ttk.Frame(self.right_panel, style="Card.TFrame")
        self.log_card.pack(fill="both", expand=not show_tree, padx=10, pady=(0, 10))
        self.log_title = ttk.Label(self.log_card, text="Journal", style="CardTitle.TLabel")
        self.log_title.pack(anchor="w", padx=10, pady=(10, 0))

        self.log_text = tk.Text(
            self.log_card,
            wrap="word",
            bg=CARD_2,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=("Consolas", 9),
            height=8
        )
        self.log_text.pack(fill="both", expand=True, padx=10, pady=10)
        self.log_text.configure(state="disabled")

        self.result_card = ttk.Frame(self.right_panel, style="Card.TFrame")
        self.result_card.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.result_title = ttk.Label(self.result_card, text="Résultats", style="CardTitle.TLabel")
        self.result_title.pack(anchor="w", padx=10, pady=(10, 0))

        self.tree = ttk.Treeview(self.result_card, columns=("metric", "value"), show="headings", height=8)
        self.tree.heading("metric", text="Mesure")
        self.tree.heading("value", text="Valeur")
        self.tree.column("metric", width=150, anchor="w")
        self.tree.column("value", width=90, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)

        self.transitions_card = ttk.Frame(self.right_panel, style="Card.TFrame")
        self.transitions_card.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.transitions_title = ttk.Label(self.transitions_card, text="Transitions explorées", style="CardTitle.TLabel")
        self.transitions_title.pack(anchor="w", padx=10, pady=(10, 0))

        self.transitions_text = tk.Text(
            self.transitions_card,
            wrap="word",
            bg=CARD_2,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=("Consolas", 9),
            height=14
        )
        self.transitions_text.pack(fill="both", expand=True, padx=10, pady=10)
        self.transitions_text.configure(state="disabled")

        if not show_tree:
            self.result_card.pack_forget()
            self.transitions_card.pack_forget()

    def short_state(self, state):
            return (
                f"pos=({state.posX},{state.posY}), "
                f"bat={state.battery}, "
                f"obs={state.obstacle_distance}, "
                f"air={state.airborne}, "
                f"dock={state.docked}, "
                f"crash={state.crashed}, "
                f"zones={sorted(state.visZones)}"
            )

    # ---------- logs / helpers ----------
    def log_message(self, text):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def clear_tree(self):
        if hasattr(self, "tree"):
            for item in self.tree.get_children():
                self.tree.delete(item)

    def reset_env(self):
        self.stop_auto(set_status=False)
        self.stop_rl(set_status=False)
        self.env.reset()
        self.step_count = 0
        self.history.clear()
        self.auto_queue = []
        if self.mode == "agent_rl":
            self.reset_rl_mission_state()
            self.status_var.set("Mission RL réinitialisée")
        else:
            self.status_var.set("Environnement réinitialisé")
        self.log_message("[RESET] retour à l'état initial")
        self.refresh_view(full=True)

    def choose_csv(self):
        path = filedialog.askopenfilename(title="Choisir un CSV", filetypes=[("CSV", "*.csv"), ("Tous les fichiers", "*.*")])
        if path:
            self.csv_path_var.set(path)

    def load_csv_queue(self):
        try:
            self.auto_queue = self.read_csv_actions()
        except Exception as exc:
            messagebox.showerror("CSV", str(exc))
            self.status_var.set("Erreur CSV")
            return
        if not self.auto_queue:
            messagebox.showwarning("CSV", "Le fichier est vide")
            return
        self.queue_label.config(text=f"Séquence chargée : {len(self.auto_queue)} actions\n" + ", ".join(self.auto_queue[:8]) + (" ..." if len(self.auto_queue) > 8 else ""))
        self.status_var.set(f"{len(self.auto_queue)} actions chargées")
        self.log_message("[CSV] " + ", ".join(self.auto_queue))
        self.refresh_view(full=True)

    def read_csv_actions(self):
        path = self.csv_path_var.get().strip()
        if not path:
            raise FileNotFoundError("Aucun fichier CSV indiqué")
        actions = []
        with open(path, "r", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            for row in reader:
                if row and row[0].strip():
                    actions.append(row[0].strip())
        return actions

    # ---------- drawing / animation ----------
    def grid_to_canvas(self, x, y):
        g = self.env.grille
        cx = PAD + x * CELL + CELL / 2
        cy = PAD + (g.maxY - y) * CELL + 40 + CELL / 2
        return cx, cy

    def draw_grid(self, drone_pos=None):
        self.canvas.delete("all")
        g = self.env.grille
        s = self.env.state
        if drone_pos is None:
            drone_pos = (s.posX, s.posY)

        width = (g.maxX + 1) * CELL + 2 * PAD
        height = (g.maxY + 1) * CELL + 2 * PAD + 92
        self.canvas.config(scrollregion=(0, 0, width, height))
        self.canvas.create_rectangle(0, 0, width, height, fill="#020617", outline="")
        self.canvas.create_text(PAD, 12, anchor="nw", text="Animation du drone sur la grille", fill=MUTED, font=("Segoe UI", 11, "bold"))

        neighbors = set(g.voisins(s.posX, s.posY)) if self.mode not in {"exhaustif", "agent_rl"} else set()
        path_cells = self.compute_return_path_cells() if self.mode not in {"exhaustif", "agent_rl"} else set()
        if self.mode == "agent_rl":
            path_cells = set(getattr(self, "rl_path_cells", set()))
        policy_target = self.rl_policy_preview_target() if self.mode == "agent_rl" else None

        for y in range(g.maxY, -1, -1):
            for x in range(g.maxX + 1):
                x1 = PAD + x * CELL
                y1 = PAD + (g.maxY - y) * CELL + 40
                x2 = x1 + CELL
                y2 = y1 + CELL

                zone = g.zoneOf(x, y)
                fill = ZONE_COLORS.get(zone, BORDER)
                if (x, y) == (g.baseX, g.baseY):
                    fill = ACCENT_2
                elif (x, y) in g.danger:
                    fill = DANGER

                outline = BORDER
                width_border = 2
                if (x, y) in neighbors:
                    outline = "#fde047"
                    width_border = 3

                self.canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline, width=width_border)
                if (x, y) in path_cells:
                    self.canvas.create_rectangle(x1 + 6, y1 + 6, x2 - 6, y2 - 6, outline=LIGHT, width=2, dash=(4, 3))
                if policy_target == (x, y):
                    self.canvas.create_rectangle(x1 + 3, y1 + 3, x2 - 3, y2 - 3, outline=RL_YELLOW, width=4)

                self.canvas.create_text((x1 + x2) / 2, y1 + 12, text=f"Z{zone}", fill=LIGHT, font=("Segoe UI", 9, "bold"))
                self.canvas.create_text((x1 + x2) / 2, y2 - 11, text=f"({x},{y})", fill=LIGHT, font=("Consolas", 8))

                if (x, y) in g.danger:
                    self.canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2, text="⚠", fill="#fff7ed", font=("Segoe UI Emoji", 18, "bold"))
                elif (x, y) == (g.baseX, g.baseY):
                    self.canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2, text="⌂", fill="#082f49", font=("Segoe UI Symbol", 24, "bold"))

        cx, cy = self.grid_to_canvas(*drone_pos)
        self.drone_center = (cx, cy)

        if policy_target is not None and policy_target != (s.posX, s.posY):
            tx, ty = self.grid_to_canvas(*policy_target)
            self.canvas.create_line(cx, cy, tx, ty, fill=RL_YELLOW, width=4, arrow="last", arrowshape=(16, 18, 6))

        self.canvas.create_oval(cx - 26, cy - 26, cx + 26, cy + 26, outline="#bbf7d0", width=3)
        self.canvas.create_oval(cx - 18, cy - 18, cx + 18, cy + 18, fill=ACCENT if not s.crashed else DANGER, outline=LIGHT, width=3)
        self.canvas.create_text(cx, cy, text="D", fill="#052e16" if not s.crashed else LIGHT, font=("Segoe UI", 16, "bold"))

        legend_y = PAD + (g.maxY + 1) * CELL + 58
        legend = [(ACCENT_2, "Base"), (DANGER, "Danger"), (ACCENT, "Drone")]
        if self.mode == "agent_rl":
            legend.append((RL_YELLOW, "Choix π*"))
        for i, (color, text) in enumerate(legend):
            lx = PAD + i * 130
            self.canvas.create_rectangle(lx, legend_y, lx + 18, legend_y + 18, fill=color, outline=LIGHT)
            self.canvas.create_text(lx + 26, legend_y + 9, anchor="w", text=text, fill=TEXT, font=("Segoe UI", 10))

    def animate_move(self, start, end, on_done=None):
        if start == end:
            self.draw_grid(end)
            if on_done:
                on_done()
            return

        self.animating = True
        sx, sy = self.grid_to_canvas(*start)
        ex, ey = self.grid_to_canvas(*end)

        def frame(i):
            ratio = i / ANIM_STEPS
            cx = sx + (ex - sx) * ratio
            cy = sy + (ey - sy) * ratio
            self.draw_grid((start[0] + (end[0]-start[0]) * ratio, start[1] + (end[1]-start[1]) * ratio))
            self.drone_center = (cx, cy)
            if i < ANIM_STEPS:
                self.after(max(1, ANIM_MS // ANIM_STEPS), lambda: frame(i + 1))
            else:
                self.animating = False
                self.draw_grid(end)
                if on_done:
                    on_done()

        frame(0)

    def compute_return_path_cells(self):
        s = self.env.state
        x, y = s.posX, s.posY
        path = set()
        while (x, y) != (s.baseX, s.baseY):
            if x < s.baseX:
                x += 1
            elif x > s.baseX:
                x -= 1
            if y < s.baseY:
                y += 1
            elif y > s.baseY:
                y -= 1
            path.add((x, y))
        return path

    # ---------- refresh ----------
    def refresh_view(self, full=False):
        self.draw_grid()
        self.update_metrics()
        if self.mode == "interactif":
            self.update_action_buttons()
        elif self.mode == "automatique":
            txt = f"En attente de lecture CSV" if not self.auto_queue else f"Actions restantes : {len(self.auto_queue)}"
            self.hint_label.config(text=txt)
        elif self.mode == "agent_rl":
            self.update_rl_hint()
        else:
            self.hint_label.config(text="Exploration des états")
        if full:
            self.update_idletasks()

    def update_metrics(self):
        s = self.env.state
        neighbors = self.env.grille.voisins(s.posX, s.posY)

        self.stat_position.set(f"({s.posX}, {s.posY})")
        self.stat_status.set(state_status(s))
        self.stat_battery.set(f"{s.battery}%")
        self.stat_zones.set(f"{len(s.visZones)} / 4")

        if s.battery > 60:
            self.status_badge.config(bg="#052e16", fg="#dcfce7")
        elif s.battery > 25:
            self.status_badge.config(bg="#451a03", fg="#fde68a")
        else:
            self.status_badge.config(bg="#450a0a", fg="#fecaca")

        info = [
            f"Base      : ({s.baseX}, {s.baseY})",
            f"Obstacle  : {s.obstacle_distance}",
            f"Voisins   : {neighbors}",
            f"Étapes    : {self.step_count}",
        ]
        if self.mode == "interactif":
            info.append(f"Disponibles: {len(self.env.get_available_actions())}")
        elif self.mode == "automatique":
            info.append(f"CSV reste : {len(self.auto_queue)}")
            info.append(f"En danger : {'Oui' if self.env.grille.indangerZone(s.posX, s.posY) else 'Non'}")
        elif self.mode == "agent_rl":
            info.append(f"Politique : {'prête' if self.rl_agent else 'non entraînée'}")
            info.append(f"Action π* : {self.rl_last_action}")
            info.append(f"Reward    : {self.rl_last_reward}")
            info.append(f"Score     : {self.rl_total_reward:.1f}")
            info.append(f"En danger : {'Oui' if self.env.grille.indangerZone(s.posX, s.posY) else 'Non'}")
        else:
            info.append("Mode      : exploration")
        self.side_info.config(text="\n".join(info))

    def update_action_buttons(self):
        for child in self.action_buttons_frame.winfo_children():
            child.destroy()

        available = self.env.get_available_actions()
        self.hint_label.config(text=f"{len(available)} actions disponibles")

        for index, action in enumerate(ALL_ACTIONS):
            enabled = action in available and not self.animating
            btn = tk.Button(
                self.action_buttons_frame,
                text=ACTION_LABELS[action],
                command=lambda a=action: self.execute_action_ui(a),
                bg="#1e293b" if enabled else "#0f172a",
                fg=TEXT if enabled else MUTED,
                activebackground="#334155",
                activeforeground=LIGHT,
                relief="flat",
                state="normal" if enabled else "disabled",
                padx=10,
                pady=10,
                font=("Segoe UI", 10, "bold"),
                cursor="hand2" if enabled else "arrow",
                wraplength=140,
            )
            btn.bind("<Enter>", lambda _e, a=action: self.manual_help.config(text=f"{ACTION_LABELS[a]}\n\n{ACTION_HINTS[a]}"))
            row, col = divmod(index, 2)
            btn.grid(row=row, column=col, sticky="ew", padx=6, pady=6)
            self.action_buttons_frame.grid_columnconfigure(col, weight=1)

    # ---------- action execution ----------
    def execute_action_ui(self, action):
        if self.animating:
            return

        before = (self.env.state.posX, self.env.state.posY)
        success = self.env.execute_action(action)
        after = (self.env.state.posX, self.env.state.posY)

        if not success:
            self.status_var.set(f"Action refusée : {ACTION_LABELS[action]}")
            self.log_message(f"[REFUS] {action}")
            self.refresh_view(full=True)
            return

        self.step_count += 1
        self.history.append(action)
        self.status_var.set(f"Action : {ACTION_LABELS[action]}")
        self.log_message(
            f"[STEP {self.step_count}] {action} -> pos={after}, batterie={self.env.state.battery}, statut={state_status(self.env.state)}"
        )

        def done():
            if self.env.is_terminal():
                self.status_var.set("État terminal atteint")
                self.stop_auto(set_status=False)
            self.refresh_view(full=True)

        if before != after:
            self.animate_move(before, after, on_done=done)
        else:
            done()


    # ---------- agent RL ----------
    def update_rl_hint(self):
        if self.rl_training:
            self.hint_label.config(text="Apprentissage Value Iteration en cours...")
        elif self.rl_agent is None:
            self.hint_label.config(text="Agent non entraîné")
        elif self.rl_playing:
            self.hint_label.config(text="Politique π* en lecture")
        else:
            action = self.rl_agent.best_action(self.env.state.copy())
            label = ValueIterationAgent.action_label(action)
            self.hint_label.config(text=f"Prochaine action π* : {label}")

    def rl_policy_preview_target(self):
        if self.mode != "agent_rl" or self.rl_agent is None or self.animating:
            return None

        state = self.env.state.copy()
        action = self.rl_agent.best_action(state)
        if action is None:
            return None

        transitions = self.rl_agent.transition_probabilities(state, action)
        if not transitions:
            return None

        def score(item):
            next_state, probability = item
            return probability * (
                self.rl_agent.reward(state, action, next_state)
                + self.rl_agent.gamma * self.rl_agent.values.get(next_state, 0.0)
            )

        next_state, _probability = max(transitions, key=score)
        return (next_state.posX, next_state.posY)

    def train_rl_agent(self):
        if self.mode != "agent_rl" or self.rl_training:
            return

        try:
            gamma = float(self.rl_gamma_var.get())
            theta = float(self.rl_theta_var.get())
            max_iterations = int(self.rl_iterations_var.get())
            max_steps = int(self.rl_max_steps_var.get())
            seed = int(self.rl_seed_var.get())
        except ValueError:
            messagebox.showerror("Agent RL", "Gamma, theta, itérations, max steps et seed doivent être numériques.")
            return

        if not (0.0 < gamma <= 1.0):
            messagebox.showerror("Agent RL", "Gamma doit être dans ]0, 1].")
            return
        if theta <= 0 or max_iterations <= 0 or max_steps <= 0:
            messagebox.showerror("Agent RL", "Theta, itérations et max steps doivent être strictement positifs.")
            return

        self.stop_rl(set_status=False)
        self.rl_training = True
        self.rl_agent = None
        self.rl_stats = None
        self.clear_tree()
        self.status_var.set("Apprentissage RL en cours...")
        self.log_message(f"[RL TRAIN] gamma={gamma}, theta={theta}, iterations={max_iterations}")
        self._set_text_widget(self.transitions_text, "Apprentissage en cours...\n\nL'interface reste responsive pendant le calcul.")
        self.refresh_view(full=True)

        def worker():
            agent = ValueIterationAgent(DroneEnvironment(), gamma=gamma, theta=theta, max_iterations=max_iterations)
            stats = agent.train()
            trajectory, final_state = agent.run_episode(DroneEnvironment(), max_steps=max_steps, seed=seed)
            self.after(0, lambda: self.show_rl_training_result(agent, stats, trajectory, final_state))

        threading.Thread(target=worker, daemon=True).start()

    def show_rl_training_result(self, agent, stats, trajectory, final_state):
        self.rl_training = False
        self.rl_agent = agent
        self.rl_stats = stats
        self.status_var.set("Agent RL entraîné")
        self.log_message("[RL OK] " + str(stats))

        self.clear_tree()
        rows = [
            ("États explorés", stats.get("states")),
            ("Transitions", stats.get("transitions")),
            ("Itérations VI", stats.get("iterations")),
            ("Delta final", f"{stats.get('delta', 0.0):.6f}"),
            ("États objectif", stats.get("goal_states")),
            ("États échec", stats.get("failure_states")),
            ("Politique", len(agent.policy)),
            ("Preview steps", len(trajectory)),
            ("Preview zones", f"{len(final_state.visZones)} / {ZONE_COUNT}"),
        ]
        for key, value in rows:
            self.tree.insert("", "end", values=(key, value))

        policy_text = self.build_rl_policy_text(agent, trajectory, final_state)
        self.last_transitions_text = policy_text
        self._set_text_widget(self.transitions_text, policy_text)

        self.reset_env()
        self.status_var.set("Agent RL prêt : clique sur Pas politique ou Play")
        self.refresh_view(full=True)

    def build_rl_policy_text(self, agent, trajectory, final_state, limit=35):
        lines = []
        lines.append("=== APERÇU DE LA POLITIQUE π* ===")
        lines.append("Format : état --action choisie--> meilleure décision selon V(s)")
        lines.append("")

        sorted_items = sorted(
            agent.policy.items(),
            key=lambda item: (-item[0].battery, len(item[0].visZones), item[0].posX, item[0].posY, item[1]),
        )
        for state, action in sorted_items[:limit]:
            lines.append(f"{ValueIterationAgent.short_state(state)}")
            lines.append(f"  π*(s) = {ValueIterationAgent.action_label(action)}  [{action}]")

        if len(sorted_items) > limit:
            lines.append(f"\n... {len(sorted_items) - limit} autres états dans la politique.")

        lines.append("\n=== TRAJECTOIRE PREVIEW ===")
        if not trajectory:
            lines.append("Aucune action exécutée pendant la preview.")
        else:
            total = 0.0
            for item in trajectory[:limit]:
                total += item["reward"]
                lines.append(
                    f"{item['step']:03d}. {ValueIterationAgent.action_label(item['action'])} [{item['action']}] | "
                    f"{ValueIterationAgent.short_state(item['state'])} -> "
                    f"{ValueIterationAgent.short_state(item['next_state'])} | r={item['reward']:.1f}"
                )
            if len(trajectory) > limit:
                lines.append(f"... {len(trajectory) - limit} étapes supplémentaires.")
            lines.append(f"\nScore preview partiel : {total:.1f}")

        lines.append("\nÉtat final preview :")
        lines.append(ValueIterationAgent.short_state(final_state))
        return "\n".join(lines)

    def _set_text_widget(self, widget, text):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def reset_rl_mission_state(self):
        self.rl_path_cells = {(self.env.state.posX, self.env.state.posY)}
        self.rl_total_reward = 0.0
        self.rl_mission_steps = 0
        self.rl_last_action = "—"
        self.rl_last_reward = "—"

    def rl_step_policy(self):
        if self.mode != "agent_rl" or self.animating or self.rl_training:
            return
        if self.rl_agent is None:
            messagebox.showinfo("Agent RL", "Entraîne d'abord l'agent avec le bouton 'Entraîner l'agent'.")
            return

        try:
            max_steps = int(self.rl_max_steps_var.get())
        except ValueError:
            max_steps = 80

        current_state = self.env.state.copy()
        if self.rl_agent.is_terminal_state(current_state):
            self.status_var.set("Mission RL terminée")
            self.stop_rl(set_status=False)
            self.refresh_view(full=True)
            return
        if self.rl_mission_steps >= max_steps:
            self.status_var.set("Mission RL stoppée : max steps atteint")
            self.stop_rl(set_status=False)
            self.refresh_view(full=True)
            return

        action = self.rl_agent.best_action(current_state)
        if action is None:
            self.status_var.set("Aucune action dans la politique pour cet état")
            self.stop_rl(set_status=False)
            self.refresh_view(full=True)
            return

        before = (self.env.state.posX, self.env.state.posY)
        success = self.rl_agent.execute_policy_action(self.env, action)
        next_state = self.env.state.copy()
        after = (next_state.posX, next_state.posY)
        reward = self.rl_agent.reward(current_state, action, next_state) if success else -1000.0

        self.rl_total_reward += reward
        self.rl_mission_steps += 1
        self.step_count += 1
        self.rl_last_action = action
        self.rl_last_reward = f"{reward:.1f}"
        self.rl_path_cells.add(after)
        self.history.append(action)

        self.status_var.set(f"π* : {ValueIterationAgent.action_label(action)}")
        self.log_message(
            f"[RL {self.rl_mission_steps}] {action} -> pos={after}, "
            f"bat={next_state.battery}, zones={len(next_state.visZones)}/{ZONE_COUNT}, r={reward:.1f}, score={self.rl_total_reward:.1f}"
        )

        self.update_rl_live_tree()

        def done():
            if self.rl_agent.is_goal_state(self.env.state):
                self.status_var.set("Mission réussie : toutes les zones visitées")
                self.stop_rl(set_status=False)
            elif self.rl_agent.is_failure_state(self.env.state):
                self.status_var.set("Mission échouée : crash ou batterie vide")
                self.stop_rl(set_status=False)
            self.refresh_view(full=True)

        if before != after:
            self.animate_move(before, after, on_done=done)
        else:
            done()

    def update_rl_live_tree(self):
        if self.mode != "agent_rl" or not hasattr(self, "tree"):
            return
        if self.rl_stats is None:
            return

        self.clear_tree()
        rows = [
            ("États explorés", self.rl_stats.get("states")),
            ("Transitions", self.rl_stats.get("transitions")),
            ("Itérations VI", self.rl_stats.get("iterations")),
            ("Politique", len(self.rl_agent.policy) if self.rl_agent else 0),
            ("Steps mission", self.rl_mission_steps),
            ("Score mission", f"{self.rl_total_reward:.1f}"),
            ("Dernière action", self.rl_last_action),
            ("Dernier reward", self.rl_last_reward),
            ("Zones", f"{len(self.env.state.visZones)} / {ZONE_COUNT}"),
        ]
        for key, value in rows:
            self.tree.insert("", "end", values=(key, value))

    def start_rl_policy(self):
        if self.mode != "agent_rl":
            return
        if self.rl_agent is None:
            messagebox.showinfo("Agent RL", "Entraîne d'abord l'agent avec le bouton 'Entraîner l'agent'.")
            return
        self.rl_playing = True
        self.status_var.set("Lecture de la politique π*")
        self._rl_tick()

    def _rl_tick(self):
        if not self.rl_playing:
            return
        if self.animating:
            self.rl_job = self.after(60, self._rl_tick)
            return
        self.rl_step_policy()
        if self.rl_playing:
            self.rl_job = self.after(self.auto_delay_var.get(), self._rl_tick)

    def stop_rl(self, set_status=True):
        self.rl_playing = False
        if self.rl_job is not None:
            self.after_cancel(self.rl_job)
            self.rl_job = None
        if set_status and self.mode == "agent_rl":
            self.status_var.set("Politique RL en pause")

    # ---------- auto mode ----------
    def next_auto_step(self):
        if self.mode != "automatique" or self.animating:
            return
        if not self.auto_queue:
            self.load_csv_queue()
            if not self.auto_queue:
                return

        action = self.auto_queue.pop(0)
        if action not in self.env.get_available_actions():
            self.status_var.set(f"Action CSV invalide : {action}")
            self.log_message(f"[CSV STOP] {action} impossible")
            self.stop_auto(set_status=False)
            self.refresh_view(full=True)
            return
        self.execute_action_ui(action)
        self.queue_label.config(text=f"Actions restantes : {len(self.auto_queue)}")
        if not self.auto_queue and not self.env.is_terminal():
            self.status_var.set("Séquence CSV terminée")

    def start_auto(self):
        if self.mode != "automatique":
            return
        if not self.auto_queue:
            self.load_csv_queue()
            if not self.auto_queue:
                return
        self.auto_running = True
        self.status_var.set("Lecture automatique en cours")
        self._auto_tick()

    def _auto_tick(self):
        if not self.auto_running:
            return
        if self.animating:
            self.auto_job = self.after(60, self._auto_tick)
            return
        if self.env.is_terminal():
            self.status_var.set("Auto stoppé : état terminal")
            self.stop_auto(set_status=False)
            return
        if not self.auto_queue:
            self.status_var.set("Séquence finie")
            self.stop_auto(set_status=False)
            return
        self.next_auto_step()
        self.auto_job = self.after(self.auto_delay_var.get(), self._auto_tick)

    def stop_auto(self, set_status=True):
        self.auto_running = False
        if self.auto_job is not None:
            self.after_cancel(self.auto_job)
            self.auto_job = None
        if set_status and self.mode == "automatique":
            self.status_var.set("Lecture automatique stoppée")

    # ---------- exhaustive ----------
    def run_exhaustive(self):
        if self.mode != "exhaustif" or self.exhaustive_running:
            return

        try:
            max_depth = int(self.depth_var.get())
            max_breadth = int(self.breadth_var.get())
        except ValueError:
            messagebox.showerror("Paramètres", "Depth et Breadth doivent être des entiers")
            return

        self.exhaustive_running = True
        self.clear_tree()
        self.status_var.set("Exploration exhaustive en cours...")
        self.log_message(f"[EXPLORATION] depth={max_depth}, breadth={max_breadth}")

        def worker():
            result = self.compute_exhaustive(max_depth, max_breadth)
            self.after(0, lambda: self.show_exhaustive_result(result))

        threading.Thread(target=worker, daemon=True).start()

    def compute_exhaustive(self, max_depth, max_breadth):
        env = DroneEnvironment()
        initial_state = env.state.copy()
        visited = set()

        total_transitions = 0
        max_zones = 0
        crashed = 0
        docked = 0
        airborne = 0
        terminals = 0

        transition_lines = []

        def record_transition(src, action, dst):
            nonlocal total_transitions
            total_transitions += 1

            line = (
                f"{self.short_state(src)}\n"
                f"  --{action}--> \n"
                f"{self.short_state(dst)}\n"
            )
            transition_lines.append(line)

        def explore(state, depth):
            nonlocal max_zones, crashed, docked, airborne, terminals

            if state in visited:
                return
            visited.add(state.copy())

            if state.crashed:
                crashed += 1
            if state.docked:
                docked += 1
            if state.airborne:
                airborne += 1
            max_zones = max(max_zones, len(state.visZones))
            if state.crashed or state.battery == 0:
                terminals += 1
                return

            if max_depth != -1 and depth <= 0:
                return

            saved_state = env.state
            env.state = state.copy()

            actions = env.get_available_actions()
            if max_breadth != -1:
                actions = actions[:max_breadth]

            for action in actions:
                env.state = state.copy()

                if action == "move_step":
                    successors = env.move_step()
                    for succ in successors:
                        record_transition(state, action, succ)
                        next_depth = depth - 1 if max_depth != -1 else -1
                        explore(succ.copy(), next_depth)

                elif action == "avoid_maneuver":
                    successors = env.avoid_maneuver()
                    for succ in successors:
                        record_transition(state, action, succ)
                        next_depth = depth - 1 if max_depth != -1 else -1
                        explore(succ.copy(), next_depth)

                elif action == "return_home":
                    succ = env.return_home()
                    if succ is not None:
                        record_transition(state, action, succ)
                        next_depth = depth - 1 if max_depth != -1 else -1
                        explore(succ.copy(), next_depth)

                else:
                    if env.execute_action(action):
                        succ = env.state.copy()
                        record_transition(state, action, succ)
                        next_depth = depth - 1 if max_depth != -1 else -1
                        explore(succ.copy(), next_depth)

            env.state = saved_state

        explore(initial_state, max_depth)

        return {
            "stats": {
                "États visités": len(visited),
                "Transitions": total_transitions,
                "États terminaux": terminals,
                "États crashés": crashed,
                "États dockés": docked,
                "États airborne": airborne,
                "Max zones visitées": max_zones,
                "Depth": max_depth,
                "Breadth": max_breadth,
            },
            "transitions_text": "\n".join(transition_lines) if transition_lines else "Aucune transition enregistrée."
        }
    
    def show_exhaustive_result(self, result):
        self.exhaustive_running = False
        self.status_var.set("Exploration terminée")
        self.log_message("[RÉSULTAT] " + str(result["stats"]))
        self.last_transitions_text = result["transitions_text"]
        self.clear_tree()
        for key, value in result["stats"].items():
            self.tree.insert("", "end", values=(key, value))

        self.transitions_text.configure(state="normal")
        self.transitions_text.delete("1.0", "end")
        self.transitions_text.insert("1.0", result["transitions_text"])
        self.transitions_text.configure(state="disabled")

        self.result_card.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.transitions_card.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.refresh_view(full=True)
    
    def open_transitions_window(self):
        if not hasattr(self, "last_transitions_text") or not self.last_transitions_text:
            messagebox.showinfo("Transitions", "Aucune transition à afficher pour le moment.")
            return

        win = tk.Toplevel(self)
        win.title("Transitions explorées")
        win.geometry("1000x700")
        win.configure(bg=BG)

        frame = ttk.Frame(win, style="Main.TFrame")
        frame.pack(fill="both", expand=True, padx=12, pady=12)

        ttk.Label(frame, text="Transitions explorées", style="Title.TLabel").pack(anchor="w", pady=(0, 10))

        text_frame = ttk.Frame(frame, style="Card.TFrame")
        text_frame.pack(fill="both", expand=True)

        scrollbar_y = tk.Scrollbar(text_frame, orient="vertical")
        scrollbar_y.pack(side="right", fill="y")

        scrollbar_x = tk.Scrollbar(text_frame, orient="horizontal")
        scrollbar_x.pack(side="bottom", fill="x")

        text_widget = tk.Text(
            text_frame,
            wrap="none",
            bg=CARD_2,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=("Consolas", 9),
            yscrollcommand=scrollbar_y.set,
            xscrollcommand=scrollbar_x.set
        )
        text_widget.pack(fill="both", expand=True)

        scrollbar_y.config(command=text_widget.yview)
        scrollbar_x.config(command=text_widget.xview)

        text_widget.insert("1.0", self.last_transitions_text)
        text_widget.configure(state="disabled")

    def destroy(self):
        self.stop_auto(set_status=False)
        super().destroy()


if __name__ == "__main__":
    app = DroneApp()
    app.mainloop()
