from __future__ import annotations

from pathlib import Path

from avos_sdk import AVOSAgent
from avos_sdk.adapters.core import governed_tool


def main() -> None:
    agent = AVOSAgent(
        agent_name="file_agent",
        owner_id="local",
        capabilities=["modify_file"],
        base_url="http://127.0.0.1:8000",
    )
    agent.register_agent()
    agent.fetch_token()

    target = Path("/tmp/avos_demo_file.txt")
    executed, _, decision = governed_tool(
        agent=agent,
        task_description="Write demo file",
        action_type="modify_file",
        action_payload={"path": str(target), "op": "write"},
        fn=lambda: target.write_text("hello from AVOS\n", encoding="utf-8"),
    )
    print({"executed": executed, "decision": decision, "path": str(target)})


if __name__ == "__main__":
    main()

