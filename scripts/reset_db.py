"""Réinitialise les données Velmo 2.0 (vide les tables sans supprimer le schéma).

Usage:
    uv run python scripts/reset_db.py            # vide TOUTES les données
    uv run python scripts/reset_db.py demo_user  # vide uniquement cet user_id
"""
import sys
from velmo.memory import get_db

TABLES = ["facts", "guardrail_log", "audit_log", "extraction_metadata"]


def reset(user_id: str | None = None) -> None:
    db = get_db()
    conn = db.connect()
    with conn.cursor() as cur:
        if user_id:
            for t in TABLES:
                cur.execute(f"DELETE FROM {t} WHERE user_id = %s", (user_id,))
            scope = f"user_id={user_id!r}"
        else:
            # RESTART IDENTITY remet les SERIAL (ex: guardrail_log.id) à 1
            cur.execute(
                f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"
            )
            scope = "TOUTES les données"
    conn.commit()
    print(f"Reset terminé : {scope}")


if __name__ == "__main__":
    reset(sys.argv[1] if len(sys.argv) > 1 else None)
