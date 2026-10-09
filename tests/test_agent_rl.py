from agent_rl import ValueIterationAgent
from drone import DroneEnvironment
from constants import ZONE_COUNT


def test_agent_rl_trains_and_visits_all_zones_quickly():
    env = DroneEnvironment()
    agent = ValueIterationAgent(env, gamma=0.95, theta=0.01, max_iterations=5)
    stats = agent.train()

    assert stats["states"] > 0
    assert stats["transitions"] > 0
    assert len(agent.policy) > 0

    trajectory, final_state = agent.run_episode(DroneEnvironment(), max_steps=60)
    assert len(trajectory) > 0
    assert final_state.crashed == 0
    assert len(final_state.visZones) == ZONE_COUNT


def test_agent_uses_directional_actions_after_takeoff():
    agent = ValueIterationAgent(DroneEnvironment(), max_iterations=2)
    agent.train()
    trajectory, _ = agent.run_episode(DroneEnvironment(), max_steps=5)
    actions = [step["action"] for step in trajectory]

    assert "takeoff_cmd" in actions
    assert any(action.startswith("move_") or action.startswith("avoid_") for action in actions)
