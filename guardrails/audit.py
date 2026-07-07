import logging
from memory.database import get_db
from .schema import GuardDecision

logger = logging.getLogger(__name__)


def init_guardrail_table(db=None) -> None:
    """Crée la table guardrail_log si elle n'existe pas."""
    db = db or get_db()
    conn = db.connect()
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS guardrail_log (
                id          SERIAL PRIMARY KEY,
                user_id     VARCHAR(100) NOT NULL,
                where_      VARCHAR(10) NOT NULL,
                category    VARCHAR(50) NOT NULL,
                allowed     BOOLEAN NOT NULL,
                reason      TEXT,
                latency_ms  INTEGER,
                created_at  TIMESTAMPTZ DEFAULT now()
            );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_guardrail_log_user_id ON guardrail_log(user_id);")
    conn.commit()


def write_log(user_id: str, decision: GuardDecision, db=None) -> None:
    """Journalise une décision. Ne lève jamais : une panne DB ne bloque pas l'agent."""
    try:
        db = db or get_db()
        conn = db.connect()
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO guardrail_log (user_id, where_, category, allowed, reason, latency_ms)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (user_id, decision.where, decision.category,
                 decision.allowed, decision.reason, decision.latency_ms),
            )
        conn.commit()
    except Exception as e:  # noqa: BLE001
        logger.error(f"Échec écriture guardrail_log (décision conservée): {e}")
