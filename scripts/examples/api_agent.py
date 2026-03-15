from __future__ import annotations

import requests

from avos_sdk import AVOSAgent
from avos_sdk.adapters.core import governed_tool


def main() -> None:
    agent = AVOSAgent(
        agent_name="api_agent",
        owner_id="local",
        capabilities=["call_external_api"],
        base_url="http://127.0.0.1:8000",
    )
    agent.register_agent()
    agent.fetch_token()

    url = "https://httpbin.org/get"
    executed, result, decision = governed_tool(
        agent=agent,
        task_description="Call httpbin",
        action_type="call_external_api",
        action_payload={"url": url, "method": "GET"},
        fn=lambda: requests.get(url, timeout=10).json(),
    )
    print({"executed": executed, "decision": decision, "result_keys": list((result or {}).keys())})


if __name__ == "__main__":
    main()

