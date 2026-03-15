from __future__ import annotations

import json
from pathlib import Path

from apex_runtime.core import authorize_action
from apex_runtime.audit import HashChainAuditLog


def test_block_rm_rf(tmp_path: Path):
    policy = tmp_path / "policies.yaml"
    policy.write_text(
        "\n".join(
            [
                "rules:",
                '  - action_type: "execute_shell"',
                '    deny_if: "rm -rf"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    audit_file = tmp_path / "audit.log"
    agent_ctx = {"public_key": "pk-test", "created_at": "2026-03-15T00:00:00Z"}
    result = authorize_action(
        agent_ctx,
        "execute_shell",
        "rm -rf /",
        policy_file=policy,
        audit_log_path=audit_file,
    )
    assert result["decision"] == "DENY"
    assert "rm -rf" in result["reason"]
    assert result["avid"].startswith("AVID-")


def test_require_approval_external_api(tmp_path: Path):
    policy = tmp_path / "policies.yaml"
    policy.write_text(
        "\n".join(
            [
                "rules:",
                '  - action_type: "call_external_api"',
                "    require_approval: true",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    audit_file = tmp_path / "audit.log"
    agent_ctx = {"public_key": "pk-test", "created_at": "2026-03-15T00:00:00Z"}
    result = authorize_action(
        agent_ctx,
        "call_external_api",
        {"url": "https://example.com"},
        policy_file=policy,
        audit_log_path=audit_file,
    )
    assert result["decision"] == "REQUIRE_APPROVAL"


def test_safe_paths_modify_file(tmp_path: Path):
    policy = tmp_path / "policies.yaml"
    policy.write_text(
        "\n".join(
            [
                "rules:",
                '  - action_type: "modify_file"',
                '    allow_if: "safe_paths"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    audit_file = tmp_path / "audit.log"
    agent_ctx = {
        "public_key": "pk-test",
        "created_at": "2026-03-15T00:00:00Z",
        "safe_paths": [str(tmp_path)],
    }
    ok = authorize_action(
        agent_ctx,
        "modify_file",
        {"path": str(tmp_path / "file.txt")},
        policy_file=policy,
        audit_log_path=audit_file,
    )
    assert ok["decision"] == "ALLOW"

    bad = authorize_action(
        agent_ctx,
        "modify_file",
        {"path": "/etc/passwd"},
        policy_file=policy,
        audit_log_path=audit_file,
    )
    assert bad["decision"] == "DENY"


def test_audit_hash_chain_integrity(tmp_path: Path):
    audit_file = tmp_path / "audit.log"
    log = HashChainAuditLog(audit_file)
    log.append(avid="AVID-1", action_type="t1", decision="ALLOW", reason="ok", timestamp="2026-03-15T00:00:00Z")
    log.append(avid="AVID-1", action_type="t2", decision="DENY", reason="no", timestamp="2026-03-15T00:00:01Z")
    assert log.verify_integrity() is True

    # Tamper with the second entry.
    lines = audit_file.read_text(encoding="utf-8").splitlines()
    obj = json.loads(lines[1])
    obj["reason"] = "tampered"
    lines[1] = json.dumps(obj, ensure_ascii=False)
    audit_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert HashChainAuditLog(audit_file).verify_integrity() is False

