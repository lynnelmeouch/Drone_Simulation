import sys
import csv
from drone import DroneEnvironment
from agent_rl import ValueIterationAgent
from constants import *

def mode_interactif():
    """
    Mode 1 : Pilotage manuel du drone.
    L'utilisateur choisit les actions à chaque étape.
    """
    print("=" * 60)
    print("MODE INTERACTIF - Pilotage manuel du drone")
    print("=" * 60)
    
    env = DroneEnvironment()
    print("\n État initial:")
    print(env.state)
    env.grille.display()
    step = 0
    while not env.is_terminal():
        print(f"\n--- Étape {step} ---")
        available_actions = env.get_available_actions()
        
        if not available_actions:
            print("Aucune action disponible. Fin de la simulation.")
            break
        
        print("\nActions disponibles:")
        for i, action in enumerate(available_actions):
            print(f"  {i+1}. {action}")
        print(f"  0. Quitter")
        
        try:
            choice = input("\nChoisissez une action (numéro): ")
            choice = int(choice)
            
            if choice == 0:
                print("Simulation arrêtée par l'utilisateur.")
                break
            
            if 1 <= choice <= len(available_actions):
                action = available_actions[choice - 1]
                print(f"\nExécution de: {action}")
                
                success = env.execute_action(action)
                
                if success:
                    print("\nAction exécutée avec succès")
                    print(env.state)
                    env.grille.display(env.state.posX, env.state.posY) 
                    step += 1
                else:
                    print("\nÉchec de l'exécution de l'action")
            else:
                print("Choix invalide.")
        
        except (ValueError, IndexError):
            print("Entrée invalide.")
    
    print("\n" + "=" * 60)
    print("FIN DE LA SIMULATION")
    print(f"Nombre d'étapes: {step}")
    print(f"Zones visitées: {len(env.state.visZones)}/{ZONE_COUNT}")
    print(f"État final: {'CRASH' if env.state.crashed else 'OK'}")
    print("=" * 60)


def mode_automatique(fichier_actions):
    """
    Mode 2 : Exécution automatique d'une séquence d'actions.
    
    Args:
        fichier_actions: chemin vers le fichier CSV contenant les actions
    """
    print("=" * 60)
    print("MODE AUTOMATIQUE - Exécution de séquence")
    print("=" * 60)
    
    # Charger la séquence d'actions
    try:
        with open(fichier_actions, 'r') as f:
            reader = csv.reader(f)
            actions = [row[0].strip() for row in reader if row]
    except FileNotFoundError:
        print(f"Erreur: fichier '{fichier_actions}' introuvable.")
        return
    except Exception as e:
        print(f"Erreur lors de la lecture du fichier: {e}")
        return
    
    print(f"\nSéquence chargée: {len(actions)} actions")
    print(f"Actions: {', '.join(actions)}\n")
    
    env = DroneEnvironment()
    print("État initial:")
    print(env.state)
    executed = 0
    for step, action in enumerate(actions):
        print(f"\n--- Étape {step + 1}/{len(actions)} ---")
        print(f"Action: {action}")
        
        # Vérifier si l'état est terminal
        if env.is_terminal():
            print("\n⚠ État terminal atteint. Arrêt de la séquence.")
            break
        
        # Vérifier si l'action est disponible
        available = env.get_available_actions()
        if action not in available:
            print(f"\nAction '{action}' non exécutable dans l'état actuel.")
            print(f"Actions disponibles: {', '.join(available)}")
            print("Arrêt de la séquence.")
            break
        
        # Exécuter l'action
        success = env.execute_action(action)
        
        if success:
            executed += 1
            print("Action exécutée avec succès")
            print(env.state)
        else:
            print("Échec de l'exécution")
            break
    
    print("\n" + "=" * 60)
    print("FIN DE LA SIMULATION AUTOMATIQUE")
    print(f"Actions exécutées: {executed}/{len(actions)}")
    print(f"Zones visitées: {len(env.state.visZones)}/{ZONE_COUNT}")
    print(f"État final: {'CRASH' if env.state.crashed else 'OK'}")
    print("=" * 60)


def mode_exhaustif(max_depth=-1, max_breadth=-1, afficher_transitions=False):
    """
    Mode 3 : Exploration exhaustive de l'espace d'états.

    Args:
        max_depth: profondeur maximale (-1 pour illimité)
        max_breadth: largeur maximale (-1 pour illimitée)
        afficher_transitions: affiche ou non les transitions détaillées
    """
    print("=" * 60)
    print("MODE EXHAUSTIF - Exploration de l'espace d'états")
    print("=" * 60)
    print(f"Profondeur max: {max_depth if max_depth != -1 else 'illimitée'}")
    print(f"Largeur max: {max_breadth if max_breadth != -1 else 'illimitée'}")

    env = DroneEnvironment()
    initial_state = env.state.copy()

    visited_states = set()
    transitions = {}

    def short_state(state):
        return (
            f"pos=({state.posX},{state.posY}), "
            f"bat={state.battery}, "
            f"obs={state.obstacle_distance}, "
            f"air={state.airborne}, "
            f"dock={state.docked}, "
            f"crash={state.crashed}, "
            f"zones={sorted(state.visZones)}"
        )

    def explore(state, depth):
        if state in visited_states:
            return

        visited_states.add(state.copy())

        # Si état terminal, on l'enregistre mais on ne l'explore pas plus
        if env.is_terminal_state(state):
            transitions[state] = []
            return

        if max_depth != -1 and depth <= 0:
            transitions[state] = []
            return

        saved_state = env.state
        env.state = state.copy()

        available_actions = env.get_available_actions()
        if max_breadth != -1:
            available_actions = available_actions[:max_breadth]

        transitions[state.copy()] = []

        for action in available_actions:
            env.state = state.copy()

            if action == "move_step":
                successors = env.move_step()
                for successor in successors:
                    successor_copy = successor.copy()
                    transitions[state.copy()].append((action, successor_copy))
                    new_depth = depth - 1 if max_depth != -1 else -1
                    explore(successor_copy, new_depth)

            elif action == "avoid_maneuver":
                successors = env.avoid_maneuver()
                for successor in successors:
                    successor_copy = successor.copy()
                    transitions[state.copy()].append((action, successor_copy))
                    new_depth = depth - 1 if max_depth != -1 else -1
                    explore(successor_copy, new_depth)

            elif action == "return_home":
                successor = env.return_home()
                if successor is not None:
                    successor_copy = successor.copy()
                    transitions[state.copy()].append((action, successor_copy))
                    new_depth = depth - 1 if max_depth != -1 else -1
                    explore(successor_copy, new_depth)

            else:
                success = env.execute_action(action)
                if success:
                    successor_copy = env.state.copy()
                    transitions[state.copy()].append((action, successor_copy))
                    new_depth = depth - 1 if max_depth != -1 else -1
                    explore(successor_copy, new_depth)

        env.state = saved_state

    # petite fonction utilitaire locale
    def is_terminal_state(state):
        return state.crashed == 1 or state.battery == 0

    # rattacher à env pour réutiliser facilement
    env.is_terminal_state = is_terminal_state

    print("\nDébut de l'exploration...\n")
    explore(initial_state, max_depth)

    if afficher_transitions:
        print("\n" + "=" * 60)
        print("TRANSITIONS EXPLORÉES")
        print("=" * 60)

        for src_state, trans_list in transitions.items():
            if not trans_list:
                continue
            for action, dst_state in trans_list:
                print(short_state(src_state))
                print(f"  --{action}--> ")
                print(short_state(dst_state))
                print()

    print("=" * 60)
    print("RÉSULTATS DE L'EXPLORATION")
    print("=" * 60)

    print(f"Nombre d'états visités: {len(visited_states)}")

    total_transitions = sum(len(trans_list) for trans_list in transitions.values())
    print(f"Nombre de transitions: {total_transitions}")

    terminal_states = sum(
        1 for state in visited_states
        if state.crashed == 1 or state.battery == 0
    )
    print(f"États terminaux: {terminal_states}")

    crashed_states = sum(1 for state in visited_states if state.crashed == 1)
    print(f"États crashés: {crashed_states}")

    docked_states = sum(1 for state in visited_states if state.docked == 1)
    print(f"États dockés: {docked_states}")

    airborne_states = sum(1 for state in visited_states if state.airborne == 1)
    print(f"États airborne: {airborne_states}")

    max_zones = max((len(state.visZones) for state in visited_states), default=0)
    print(f"Nombre maximum de zones visitées: {max_zones}")



def mode_agent_rl():
    """Mode 4 : apprentissage par Value Iteration puis exécution de la politique."""
    print("=" * 60)
    print("MODE AGENT RL - Value Iteration")
    print("=" * 60)

    env = DroneEnvironment()
    agent = ValueIterationAgent(env, gamma=0.95, theta=1e-3, max_iterations=30)

    print("Construction de l'espace d'états et apprentissage...")
    stats = agent.train()

    print("\nRésultat de l'apprentissage:")
    print(f"  États explorés      : {stats['states']}")
    print(f"  Transitions         : {stats['transitions']}")
    print(f"  Itérations VI       : {stats['iterations']}")
    print(f"  Delta final         : {stats['delta']:.6f}")
    print(f"  États objectif      : {stats['goal_states']}")
    print(f"  États d'échec       : {stats['failure_states']}")

    print("\nSimulation d'une mission avec la politique apprise:")
    trajectory, final_state = agent.run_episode(DroneEnvironment(), max_steps=200, seed=0)

    for item in trajectory:
        state = item["state"]
        next_state = item["next_state"]
        print(
            f"{item['step']:03d}. "
            f"{ValueIterationAgent.short_state(state)} "
            f"--{item['action']}--> "
            f"{ValueIterationAgent.short_state(next_state)} "
            f"r={item['reward']:.1f}"
        )

    print("\nÉtat final:")
    print(final_state)

    if agent.is_goal_state(final_state):
        print("Mission réussie : toutes les zones ont été visitées.")
    elif agent.is_failure_state(final_state):
        print("Mission échouée : état terminal d'échec atteint.")
    else:
        print("Mission arrêtée avant un état terminal agent.")


def mode_3d_rl():
    """Mode 5 : visualisation 3D Panda3D de l'agent RL."""
    print("=" * 60)
    print("MODE 3D RL - Panda3D")
    print("=" * 60)
    print("Ouverture de la fenêtre 3D...")
    print("Raccourcis dans la fenêtre : Espace=pas suivant, P=play/pause, R=reset, T=entraîner, Échap=quitter")
    try:
        from view3d.scene3d import run_scene_3d
    except ModuleNotFoundError as exc:
        if exc.name == "panda3d":
            print("\nPanda3D n'est pas installé.")
            print("Installe les dépendances avec : python3 -m pip install -r requirements.txt")
            return
        raise
    run_scene_3d(auto_train=True)


def afficher_menu():
    """Affiche le menu principal."""
    print("\n" + "=" * 60)
    print("ENVIRONNEMENT DE SIMULATION - DRONE DE PATROUILLE")
    print("=" * 60)
    print("\nModes disponibles:")
    print("  1. Mode interactif (pilotage manuel)")
    print("  2. Mode automatique (exécution de séquence)")
    print("  3. Mode exhaustif (exploration d'états)")
    print("  4. Mode agent RL (Value Iteration)")
    print("  5. Mode 3D RL (Panda3D)")
    print("  0. Quitter")
    print("=" * 60)


def main():
    """Point d'entrée principal."""
    while True:
        afficher_menu()
        
        try:
            choix = input("\nChoisissez un mode: ")
            choix = int(choix)
            
            if choix == 0:
                print("\nAu revoir!")
                break
            
            elif choix == 1:
                mode_interactif()
            
            elif choix == 2:
                fichier = input("\nChemin du fichier CSV (ou Enter pour 'actions.csv'): ")
                if not fichier:
                    fichier = "actions.csv"
                mode_automatique(fichier)
            
            elif choix == 3:
                try:
                    depth = int(input("Profondeur max (-1 pour illimitée): "))
                    breadth = int(input("Largeur max (-1 pour illimitée): "))

                    rep = input("Afficher les transitions détaillées ? (o/n): ").strip().lower()
                    afficher_transitions = rep in ("o", "oui", "y", "yes")

                    mode_exhaustif(depth, breadth, afficher_transitions)

                except ValueError:
                    print("Entrée invalide. Veuillez saisir des entiers pour depth et breadth.")

            elif choix == 4:
                mode_agent_rl()

            elif choix == 5:
                mode_3d_rl()
            
            else:
                print("Choix invalide.")
        
        except ValueError:
            print("Entrée invalide.")
        except KeyboardInterrupt:
            print("\n\nInterruption par l'utilisateur.")
            break


if __name__ == "__main__":
    main()