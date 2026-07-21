"""Ajoute quelques commandes de test pour le client CLI-MEHDI (test SMS réel).

N'affecte aucune autre table : réutilise les produits déjà en base et
insère uniquement des commandes/items/shipments pour ce client précis.

Usage:
    uv run python scripts/seed_mehdi_orders.py
"""
import logging
from datetime import datetime, timedelta

from velmo.business.generate import tracking_number
import random

logger = logging.getLogger(__name__)

CUSTOMER_REF = "CLI-MEHDI"

ORDERS_SPEC = [
    # (statut commande, jours écoulés depuis placed_at, statut shipment)
    ("livrée", 200, "livré"),
    ("livrée", 120, "livré"),
    ("livrée", 60, "livré"),
    ("livrée", 30, "livré"),
    ("expédiée", 8, "en_transit"),
    ("expédiée", 6, "en_transit"),
    ("payée", 2, "en_préparation"),
    ("préparation", 2, "en_préparation"),
    ("en_attente", 0, None),
    ("annulée", 10, None),
]


def seed_orders_for_mehdi(db=None) -> int:
    from velmo.memory.database import get_db

    db = db or get_db()
    conn = db.connect()
    rng = random.Random(7)

    with conn.cursor() as cur:
        cur.execute(
            "SELECT customer_id FROM customers WHERE customer_ref = %s", (CUSTOMER_REF,)
        )
        row = cur.fetchone()
        if not row:
            raise SystemExit(
                f"Client {CUSTOMER_REF} introuvable. Ajoutez-le d'abord dans customers."
            )
        customer_id = row["customer_id"] if isinstance(row, dict) else row[0]

        cur.execute("SELECT product_id, price_eur FROM products LIMIT 20")
        products = cur.fetchall()
        if not products:
            raise SystemExit("Aucun produit en base. Lancez d'abord scripts/seed_business_db.py.")

        cur.execute(
            "SELECT COUNT(*) FROM orders WHERE customer_id = %s", (customer_id,)
        )
        existing_count = cur.fetchone()
        existing_count = existing_count["count"] if isinstance(existing_count, dict) else existing_count[0]

        now = datetime.now()
        created = 0

        for i, (status, days_ago, shipment_status) in enumerate(ORDERS_SPEC, start=1):
            order_number = f"CMD-MEHDI-{existing_count + i:03d}"
            placed_at = now - timedelta(days=days_ago)

            chosen = rng.sample(products, k=min(2, len(products)))
            total = 0.0
            items = []
            for prod in chosen:
                price = prod["price_eur"] if isinstance(prod, dict) else prod[1]
                product_id = prod["product_id"] if isinstance(prod, dict) else prod[0]
                qty = rng.randint(1, 2)
                total += float(price) * qty
                items.append((product_id, qty, price))

            cur.execute(
                "INSERT INTO orders (order_number, customer_id, status, total_eur, placed_at) "
                "VALUES (%s, %s, %s, %s, %s) RETURNING order_id",
                (order_number, customer_id, status, round(total, 2), placed_at),
            )
            order_id = cur.fetchone()
            order_id = order_id["order_id"] if isinstance(order_id, dict) else order_id[0]

            for product_id, qty, price in items:
                cur.execute(
                    "INSERT INTO order_items (order_id, product_id, quantity, unit_price_eur) "
                    "VALUES (%s, %s, %s, %s)",
                    (order_id, product_id, qty, price),
                )

            if shipment_status is not None:
                shipped_at = placed_at + timedelta(days=1)
                delivered_at = shipped_at + timedelta(days=2) if shipment_status == "livré" else None
                estimated_delivery = delivered_at or (shipped_at + timedelta(days=3))
                cur.execute(
                    "INSERT INTO shipments (order_id, carrier, tracking_number, status, "
                    "shipped_at, estimated_delivery, delivered_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (
                        order_id,
                        "Colissimo",
                        tracking_number(rng),
                        shipment_status,
                        shipped_at,
                        estimated_delivery,
                        delivered_at,
                    ),
                )

            created += 1

    conn.commit()
    logger.info("%d commandes créées pour %s.", created, CUSTOMER_REF)
    return created


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    n = seed_orders_for_mehdi()
    print(f"{n} commandes de test créées pour {CUSTOMER_REF}.")
