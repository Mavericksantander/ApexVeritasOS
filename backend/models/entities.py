from datetime import datetime
import secrets

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy import event, inspect
from sqlalchemy.types import JSON
from .base import Base


class Agent(Base):
    __tablename__ = "agents"

    agent_id = Column(String, primary_key=True, index=True)
    avid = Column(String, unique=True, index=True, nullable=True)
    name = Column(String, nullable=False)
    owner_id = Column(String, nullable=False)
    capabilities = Column(JSON, default=list)
    public_key = Column(String, unique=True, nullable=False, index=True)
    reputation_score = Column(Float, default=0.0)
    total_tasks_executed = Column(Integer, default=0)
    tasks_success = Column(Integer, default=0)
    tasks_failure = Column(Integer, default=0)
    invalid_signature_count = Column(Integer, default=0)
    blocked_action_count = Column(Integer, default=0)
    last_task_at = Column(DateTime, nullable=True)
    registered_at = Column(DateTime, default=datetime.utcnow)
    last_heartbeat_at = Column(DateTime, nullable=True)

    @staticmethod
    def generate_public_key() -> str:
        return secrets.token_urlsafe(32)


@event.listens_for(Agent, "before_update", propagate=True)
def _prevent_avid_mutation(mapper, connection, target) -> None:
    state = inspect(target)
    hist = state.attrs.avid.history
    if hist.has_changes():
        # Allow a one-time backfill (None -> value). Block any subsequent mutation.
        previous_values = [v for v in hist.deleted if v not in (None, "")]
        if previous_values:
            raise ValueError("AVID is immutable and cannot be changed once set")


class AgentKey(Base):
    __tablename__ = "agent_keys"

    agent_id = Column(String, ForeignKey("agents.agent_id"), primary_key=True)
    public_key = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class AgentTask(Base):
    __tablename__ = "agent_tasks"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(String, ForeignKey("agents.agent_id"), nullable=False)
    task_description = Column(Text, nullable=False)
    result_status = Column(String, nullable=False)
    execution_time = Column(Float)
    logged_at = Column(DateTime, default=datetime.utcnow)


class AgentReputation(Base):
    __tablename__ = "agent_reputation"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(String, ForeignKey("agents.agent_id"), nullable=False)
    delta = Column(Float, nullable=False)
    reason = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class AuthorizationLog(Base):
    __tablename__ = "authorization_logs"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(String, ForeignKey("agents.agent_id"), nullable=False)
    action_type = Column(String, nullable=False)
    payload = Column(Text)
    decision = Column(String, nullable=False)
    reason = Column(Text)
    blocked_reason = Column(Text, nullable=True)
    severity = Column(String, nullable=False, server_default="low")
    prev_hash = Column(String, nullable=True)
    entry_hash = Column(String, nullable=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)


class Policy(Base):
    __tablename__ = "policies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True, index=True)
    pattern = Column(Text, nullable=False)
    action = Column(String, nullable=False)  # deny | allow | require_approval
    severity = Column(Integer, nullable=False, default=5)
    created_at = Column(DateTime, default=datetime.utcnow)


class AgentHeartbeat(Base):
    __tablename__ = "agent_heartbeats"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(String, ForeignKey("agents.agent_id"), nullable=False)
    model = Column(String, nullable=True)
    version = Column(String, nullable=True)
    status = Column(String, nullable=False, default="active")
    reported_at = Column(DateTime, default=datetime.utcnow)


class AgentSigningKey(Base):
    __tablename__ = "agent_signing_keys"

    agent_id = Column(String, ForeignKey("agents.agent_id"), primary_key=True)
    public_key_pem = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class A2AMessage(Base):
    __tablename__ = "a2a_messages"

    id = Column(Integer, primary_key=True, index=True)
    from_agent_id = Column(String, ForeignKey("agents.agent_id"), nullable=False, index=True)
    to_agent_id = Column(String, ForeignKey("agents.agent_id"), nullable=False, index=True)
    from_avid = Column(String, nullable=False, index=True)
    to_avid = Column(String, nullable=False, index=True)
    message_id = Column(String, nullable=False, index=True)
    message_type = Column(String, nullable=False)
    sent_at = Column(DateTime, nullable=False)
    payload = Column(Text, nullable=False)
    payload_sha256 = Column(String, nullable=False, index=True)
    signature = Column(Text, nullable=False)
    verified = Column(Boolean, nullable=False, server_default="1")
    rejected_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    delivered_at = Column(DateTime, nullable=True)
    prev_hash = Column(String, nullable=True)
    entry_hash = Column(String, nullable=True, index=True)


class A2ASession(Base):
    __tablename__ = "a2a_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, nullable=False, unique=True, index=True)
    initiator_agent_id = Column(String, ForeignKey("agents.agent_id"), nullable=False, index=True)
    responder_agent_id = Column(String, ForeignKey("agents.agent_id"), nullable=False, index=True)
    initiator_avid = Column(String, nullable=False, index=True)
    responder_avid = Column(String, nullable=False, index=True)
    initiator_nonce = Column(String, nullable=False)
    responder_nonce = Column(String, nullable=False)
    constraints = Column(JSON, default=dict)
    status = Column(String, nullable=False, server_default="pending")  # pending | active | expired | revoked
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    confirmed_at = Column(DateTime, nullable=True)
