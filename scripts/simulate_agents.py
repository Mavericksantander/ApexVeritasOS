import os
import random
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sdk.avos_agent import AVOSAgent

BASE_URL = "http://127.0.0.1:8000"


def _send_heartbeat(agent: AVOSAgent, status: str = "active") -> None:
    if not agent.access_token:
        return
    try:
        agent.send_heartbeat(status=status)
    except Exception as exc:
        print("Heartbeat failed", exc)


def _attempt_dangerous_action(agent: AVOSAgent, command: str) -> None:
    result = agent.authorize_action("execute_shell_command", {"command": command})
    print(f"{agent.agent_name} authorization response for '{command}':", result)


def _simulate_tasks(agent: AVOSAgent, iterations: int = 3) -> None:
    for idx in range(iterations):
        status = random.choice(["success", "failure"])
        duration = round(random.uniform(0.5, 4.0), 2)
        data = agent.log_task(f"simulated task {idx+1}", result_status=status, execution_time=duration)
        print(f"{agent.agent_name} task {idx+1} -> {status}, reputation now {data['reputation_score']}")
        time.sleep(0.3)


def main() -> None:
    agents = []
    capabilities = ["analysis", "web_scraping", "external_comm"]
    for name in ["oracle", "atlas", "kepler"]:
        agent = AVOSAgent(name, owner_id="simulator", capabilities=capabilities, base_url=BASE_URL)
        agent.register_agent()
        agents.append(agent)
        print(f"Registered agent {agent.agent_name} (id={agent.agent_id})")

    for agent in agents:
        _send_heartbeat(agent)
        _simulate_tasks(agent)
        _attempt_dangerous_action(agent, "rm -rf /tmp/avas_sim")
        _attempt_dangerous_action(agent, "sudo systemctl restart sshd")
        _send_heartbeat(agent, status="idle")

    print("Simulation complete")


if __name__ == "__main__":
    main()
