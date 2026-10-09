# Drone de patrouille — Environnement RL + Mode 3D

Projet Python de simulation d'un drone autonome de patrouille. Le projet contient :

- un environnement logique `DroneEnvironment` ;
- une grille 2D avec zones de patrouille et cellules dangereuses ;
- les modes console : interactif, automatique, exhaustif ;
- une interface graphique Tkinter ;
- un agent RL basé sur **Value Iteration** ;
- un mode **3D Panda3D** avec champ stylisé, drone animé et ViewPort local 5x5.

Le mode 3D est une **visualisation** : il ne remplace pas la logique du projet. Les états, actions, préconditions, transitions, récompenses et états terminaux restent dans l'environnement Python existant.

---

## 1. Prérequis

Version conseillée :

```bash
python3 --version
```

Utiliser Python 3.10 ou plus récent.

Sous Linux, pour l'interface Tkinter :

```bash
sudo apt update
sudo apt install python3-tk python3-venv
```

---

## 2. Installation

Depuis le dossier du projet :

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

Sous Windows PowerShell :

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

`requirements.txt` installe surtout Panda3D pour le mode 3D. Les modes console utilisent principalement la bibliothèque standard de Python.

---

## 3. Lancer le projet

### Menu principal console

```bash
python3 main.py
```

Modes disponibles :

```text
1. Mode interactif
2. Mode automatique
3. Mode exhaustif
4. Mode agent RL
5. Mode 3D RL
0. Quitter
```

### Interface graphique Tkinter

```bash
python3 gui.py
```

L'interface propose les modes principaux, dont le mode agent RL. Le bouton **Mode 3D RL** lance une fenêtre Panda3D séparée.

### Mode 3D directement

```bash
python3 run_3d.py
```

ou :

```bash
python3 -m view3d.scene3d
```

Raccourcis dans la fenêtre 3D :

```text
Espace : pas suivant de la politique RL
P      : play / pause
R      : reset mission
T      : entraîner l'agent
Échap  : quitter
```

---

## 4. Mode 3D Panda3D

Le mode 3D affiche seulement un **ViewPort local 5x5** autour du drone. La carte logique complète existe toujours dans `DroneEnvironment`, mais la scène 3D n'affiche que les cases proches de la position courante.

Éléments visuels :

- terrain stylisé avec herbe ;
- variations de couleur selon les zones ;
- fleurs, buissons, arbres et décor de fond ;
- base sous forme d'héliport ;
- dangers avec sol rouge, rochers et panneau ;
- drone 3D stylisé avec 4 hélices animées ;
- flèche jaune indiquant la prochaine décision de l'agent ;
- HUD avec batterie, position, action RL, zones visitées et récompense.

Important : une zone est considérée visitée dès que le drone entre dans **une cellule** de cette zone. Il ne faut pas visiter toutes les cases d'une zone.

---

## 5. Structure des fichiers

```text
.
├── actions.csv
├── agent_rl.py
├── constants.py
├── drone.py
├── etats.py
├── grille.py
├── gui.py
├── main.py
├── README.md
├── requirements.txt
├── run_3d.py
├── tests/
│   ├── test_agent_rl.py
│   └── test_viewport3d.py
└── view3d/
    ├── __init__.py
    ├── camera3d.py
    ├── common3d.py
    ├── drone3d.py
    ├── hud3d.py
    ├── scene3d.py
    ├── terrain3d.py
    └── viewport3d.py
```

---

## 6. Rôle des modules principaux

### `drone.py`

Contient `DroneEnvironment`, c'est le cœur de la simulation :

- préconditions des actions ;
- transitions déterministes et non déterministes ;
- exécution des actions ;
- validation des invariants ;
- états terminaux.

### `etats.py`

Contient `DroneState`, l'état complet du drone :

- position ;
- base ;
- batterie ;
- statut `airborne`, `docked`, `crashed` ;
- zones visitées ;
- invariants.

### `grille.py`

Contient la grille logique :

- bornes de la carte ;
- calcul de zone `zoneOf(x, y)` ;
- danger ;
- voisins valides ;
- affichage console.

### `agent_rl.py`

Contient `ValueIterationAgent`.

Il construit l'espace d'états, calcule les transitions, applique Value Iteration et déduit une politique.

L'agent utilise des actions directionnelles côté politique :

```text
move_up, move_down, move_left, move_right
avoid_up, avoid_down, avoid_left, avoid_right
```

Cela évite que l'agent dise simplement `move_step` puis laisse l'environnement choisir une direction au hasard.

### `view3d/`

Contient uniquement la visualisation Panda3D.

La 3D ne décide pas si une action est valide. Elle lit seulement l'état courant de l'environnement.

---

## 7. Lancer les tests

Installer pytest si nécessaire :

```bash
python3 -m pip install pytest
```

Puis lancer :

```bash
python3 -m pytest -q
```

Les tests fournis vérifient notamment :

- que l'agent RL construit une politique ;
- que l'agent atteint les 4 zones sans crash ;
- que le ViewPort 3D calcule correctement les cases visibles ;
- que les dangers et la base sont correctement reconnus dans le ViewPort.

---

## 8. Problèmes fréquents

### `ModuleNotFoundError: No module named 'panda3d'`

Installer les dépendances :

```bash
python3 -m pip install -r requirements.txt
```

### L'interface graphique Tkinter ne s'ouvre pas sous Linux

Installer Tkinter :

```bash
sudo apt install python3-tk
```

### Le mode 3D ne s'ouvre pas sur une machine distante ou en SSH

Panda3D a besoin d'un affichage graphique. Sur un serveur sans écran, il peut échouer. Lance le projet sur une machine avec environnement graphique.

### L'entraînement RL prend quelques secondes

C'est normal : l'agent construit l'espace d'états et applique Value Iteration. Pour une démo, il suffit d'attendre que le HUD affiche que la politique est prête.

---

## 9. Commandes rapides

```bash
# créer l'environnement virtuel
python3 -m venv .venv
source .venv/bin/activate

# installer
python3 -m pip install -r requirements.txt

# lancer menu console
python3 main.py

# lancer interface Tkinter
python3 gui.py

# lancer 3D directement
python3 run_3d.py

# lancer tests
python3 -m pytest -q
```
