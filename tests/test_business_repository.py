from unittest.mock import MagicMock
from velmo.business import repository as repo


def _db_with(fetchone_seq, fetchall_seq):
    """Mock db dont le curseur renvoie les valeurs fournies dans l'ordre."""
    cur = MagicMock()
    cur.fetchone.side_effect = list(fetchone_seq)
    cur.fetchall.side_effect = list(fetchall_seq)
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    db = MagicMock()
    db.connect.return_value = conn
    return db, cur


def test_get_order_by_number_found_with_items_and_shipment():
    order_row = {"order_id": "o1", "order_number": "CMD-4490",
                 "status": "expédiée", "total_eur": 59.8, "placed_at": "2026-07-01"}
    items = [{"name": "T-shirt coton Noir", "sku": "PRD-A1B2",
              "quantity": 2, "unit_price_eur": 19.9}]
    shipment = {"carrier": "Colissimo", "tracking_number": "FR123456789",
                "status": "en_transit", "shipped_at": "2026-07-02",
                "estimated_delivery": "2026-07-05", "delivered_at": None}
    db, cur = _db_with([order_row, shipment], [items])
    out = repo.get_order_by_number("CMD-4490", db=db)
    assert out["order_number"] == "CMD-4490"
    assert out["items"][0]["sku"] == "PRD-A1B2"
    assert out["shipment"]["tracking_number"] == "FR123456789"


def test_get_order_by_number_not_found_returns_none():
    db, cur = _db_with([None], [])
    assert repo.get_order_by_number("CMD-0000", db=db) is None


def test_get_customer_by_velmo_user():
    db, cur = _db_with([{"customer_id": "c1", "full_name": "Karim Martin",
                         "email": "karim.martin@example.fr"}], [])
    out = repo.get_customer_by_velmo_user("demo_user", db=db)
    assert out["customer_id"] == "c1"


def test_get_customer_by_phone():
    db, cur = _db_with([{"customer_id": "c1", "full_name": "Alice Dupont",
                         "email": "alice.dupont@example.fr", "phone": "+33612345678"}], [])
    out = repo.get_customer_by_phone("+33612345678", db=db)
    assert out["customer_id"] == "c1"
    assert out["phone"] == "+33612345678"


def test_get_customer_by_phone_not_found_returns_none():
    db, cur = _db_with([None], [])
    assert repo.get_customer_by_phone("+33699999999", db=db) is None


def test_get_orders_for_customer_lists_orders():
    orders = [{"order_number": "CMD-0001", "status": "livrée",
               "total_eur": 19.9, "placed_at": "2026-01-01"}]
    db, cur = _db_with([], [orders])
    out = repo.get_orders_for_customer("c1", db=db)
    assert out[0]["order_number"] == "CMD-0001"
