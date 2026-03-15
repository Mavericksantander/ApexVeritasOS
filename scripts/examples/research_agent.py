from __future__ import annotations

from avos_sdk import AVOSAgent
from avos_sdk.adapters.core import governed_tool


def main() -> None:
    agent = AVOSAgent(
        agent_name="research_agent",
        owner_id="local",
        capabilities=["web_research"],
        base_url="http://127.0.0.1:8000",
    )
    agent.register_agent()
    agent.fetch_token()

    # Example: ask permission before calling an external API.
    executed, result, decision = governed_tool(
        agent=agent,
        task_description="Fetch market headlines",
        action_type="call_external_api",
        action_payload={"url": "https://example.com/api/headlines", "method": "GET"},
        fn=lambda: {"headlines": ["demo headline 1", "demo headline 2"]},
    )
    print({"executed": executed, "decision": decision, "result": result})


if __name__ == "__main__":
    main()

