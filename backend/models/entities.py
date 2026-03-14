from datetime import datetime
import secrets

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.types import JSON
from .base import Base


class Agent(Base):
    __tablename__ = "agents"

    agent_id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    owner_id = Column(String, nullable=False)
    capabilities = Column(JSON, default=list)
    public_key = Column(String, unique=True, nullable=False, index=True)
    reputation_score = Column(Float, default=0.0)
    total_tasks_executed = Column(Integer, default=0)
    registered_at = Column(DateTime, default=datetime.utcnow)
    last_heartbeat_at = Column(DateTime, nullable=True)

    @staticmethod
    def generate_public_key() -> str:
        return secrets.token_urlsafe(32)


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
