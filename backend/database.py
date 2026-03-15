import logging
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy import inspect
from sqlalchemy.orm import sessionmaker

from .core.config import settings
from .models import Base, Policy

DATABASE_URL = settings.DATABASE_URL

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(engine, future=True, expire_on_commit=False)


def init_db():
    # Prefer Alembic migrations when available so schema changes (new columns/tables) are applied safely.
    try:
        from alembic import command
        from alembic.config import Config

        alembic_ini = Path(__file__).resolve().parents[1] / "alembic.ini"
        if alembic_ini.exists():
            cfg = Config(str(alembic_ini))
            command.upgrade(cfg, "head")
        else:
            Base.metadata.create_all(bind=engine)
    except Exception as exc:
        logging.warning("init_db: alembic upgrade failed; falling back to create_all: %s", exc)
        Base.metadata.create_all(bind=engine)

    # Guardrail: if a local SQLite file already existed and migrations didn't apply (or were skipped),
    # ensure the schema matches the current models for dev/test ergonomics.
    try:
        if DATABASE_URL.startswith("sqlite"):
            insp = inspect(engine)
            if insp.has_table("agents"):
                cols = {c["name"] for c in insp.get_columns("agents")}
                required = {
                    "agent_id",
                    "name",
                    "owner_id",
                    "capabilities",
                    "public_key",
                    "reputation_score",
                    "total_tasks_executed",
                    "registered_at",
                    "last_heartbeat_at",
                    "avid",
                    "tasks_success",
                    "tasks_failure",
                    "invalid_signature_count",
                    "blocked_action_count",
                    "last_task_at",
                }
                if not required.issubset(cols):
                    logging.warning("init_db: sqlite schema mismatch; recreating tables (dev/test).")
                    Base.metadata.drop_all(bind=engine)
                    Base.metadata.create_all(bind=engine)
            if insp.has_table("authorization_logs"):
                cols = {c["name"] for c in insp.get_columns("authorization_logs")}
                required = {"id", "agent_id", "action_type", "decision", "timestamp", "entry_hash"}
                if not required.issubset(cols):
                    logging.warning("init_db: sqlite auth_logs mismatch; recreating tables (dev/test).")
                    Base.metadata.drop_all(bind=engine)
                    Base.metadata.create_all(bind=engine)
            if insp.has_table("agent_attestations"):
                # ok, no additional checks
                pass
    except Exception as exc:
        logging.warning("init_db: schema check failed: %s", exc)

    with SessionLocal() as db:
        existing = db.query(Policy).limit(1).first()
        if not existing:
            defaults = [
                Policy(name="deny_rm_rf", pattern="rm -rf", action="deny", severity=10),
                Policy(name="deny_sudo", pattern="sudo", action="deny", severity=9),
                Policy(name="deny_sensitive_paths", pattern="/etc", action="deny", severity=9),
                Policy(name="deny_root_paths", pattern="/root", action="deny", severity=9),
                Policy(name="approve_privileged_fs", pattern="chmod", action="require_approval", severity=7),
                Policy(name="approve_privileged_owner", pattern="chown", action="require_approval", severity=7),
                Policy(name="approve_disk_tools", pattern="mkfs", action="require_approval", severity=8),
                Policy(name="approve_raw_copy", pattern="dd ", action="require_approval", severity=8),
            ]
            db.add_all(defaults)
            db.commit()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
