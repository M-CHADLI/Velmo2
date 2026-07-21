from unittest.mock import MagicMock
from velmo.business.schema import init_business_tables


def _fake_db():
    db = MagicMock()
    cur = MagicMock()
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    db.connect.return_value = conn
    return db, conn, cur


def test_init_business_tables_creates_all_tables():
    db, conn, cur = _fake_db()
    init_business_tables(db=db)
    executed = " ".join(str(c.args[0]) for c in cur.execute.call_args_list)
    for table in ["customers", "products", "orders", "order_items", "shipments"]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in executed
    conn.commit.assert_called_once()


def test_init_business_tables_defines_alnum_identifiers():
    db, conn, cur = _fake_db()
    init_business_tables(db=db)
    executed = " ".join(str(c.args[0]) for c in cur.execute.call_args_list)
    assert "customer_ref" in executed and "order_number" in executed
    assert "tracking_number" in executed and "sku" in executed
