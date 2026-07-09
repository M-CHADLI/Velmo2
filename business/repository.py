"""Requêtes lecture seule sur la base métier (thread principal, connexion partagée)."""


def _conn(db):
    from memory.database import get_db
    db = db or get_db()
    return db.connect()


def get_order_by_number(order_number: str, db=None) -> dict | None:
    conn = _conn(db)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT order_id, order_number, status, total_eur, placed_at "
            "FROM orders WHERE order_number = %s",
            (order_number,),
        )
        order = cur.fetchone()
        if not order:
            return None
        cur.execute(
            "SELECT p.name AS name, p.sku AS sku, oi.quantity AS quantity, "
            "oi.unit_price_eur AS unit_price_eur "
            "FROM order_items oi JOIN products p ON p.product_id = oi.product_id "
            "WHERE oi.order_id = %s",
            (order["order_id"],),
        )
        items = cur.fetchall()
        cur.execute(
            "SELECT carrier, tracking_number, status, shipped_at, "
            "estimated_delivery, delivered_at FROM shipments WHERE order_id = %s",
            (order["order_id"],),
        )
        shipment = cur.fetchone()
    return {
        "order_number": order["order_number"],
        "status": order["status"],
        "total_eur": float(order["total_eur"]),
        "placed_at": order["placed_at"],
        "items": [dict(it) for it in items],
        "shipment": dict(shipment) if shipment else None,
    }


def get_customer_by_email(email: str, db=None) -> dict | None:
    conn = _conn(db)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT customer_id, full_name, email FROM customers WHERE email = %s",
            (email,),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def get_customer_by_velmo_user(user_id: str, db=None) -> dict | None:
    if not user_id:
        return None
    conn = _conn(db)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT customer_id, full_name, email FROM customers "
            "WHERE velmo_user_id = %s LIMIT 1",
            (user_id,),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def get_orders_for_customer(customer_id: str, db=None, limit: int = 10) -> list[dict]:
    conn = _conn(db)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT order_number, status, total_eur, placed_at FROM orders "
            "WHERE customer_id = %s ORDER BY placed_at DESC LIMIT %s",
            (customer_id, limit),
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]
