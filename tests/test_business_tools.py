import business.tools as t


def test_lookup_order_found(monkeypatch):
    monkeypatch.setattr(t.repo, "get_order_by_number", lambda n, db=None: {
        "order_number": "CMD-4490", "status": "expédiée", "total_eur": 59.8,
        "placed_at": "2026-07-01",
        "items": [{"name": "T-shirt coton Noir", "sku": "PRD-A1B2",
                   "quantity": 2, "unit_price_eur": 19.9}],
        "shipment": {"carrier": "Colissimo", "tracking_number": "FR123456789",
                     "status": "en_transit", "shipped_at": "2026-07-02",
                     "estimated_delivery": "2026-07-05", "delivered_at": None},
    })
    out = t.lookup_order.invoke({"order_number": "CMD-4490"})
    assert "CMD-4490" in out and "expédiée" in out and "FR123456789" in out


def test_lookup_order_not_found(monkeypatch):
    monkeypatch.setattr(t.repo, "get_order_by_number", lambda n, db=None: None)
    out = t.lookup_order.invoke({"order_number": "CMD-0000"})
    assert "CMD-0000" in out and "aucune" in out.lower()


def test_lookup_order_never_raises(monkeypatch):
    def boom(n, db=None):
        raise RuntimeError("db down")
    monkeypatch.setattr(t.repo, "get_order_by_number", boom)
    out = t.lookup_order.invoke({"order_number": "CMD-4490"})
    assert isinstance(out, str) and len(out) > 0


def test_get_customer_orders_by_prelinked_identity(monkeypatch):
    monkeypatch.setattr(t.repo, "get_customer_by_velmo_user",
                        lambda uid, db=None: {"customer_id": "c1", "full_name": "Karim",
                                              "email": "k@example.fr"})
    monkeypatch.setattr(t.repo, "get_orders_for_customer",
                        lambda cid, db=None: [{"order_number": "CMD-0001",
                                               "status": "livrée", "total_eur": 19.9,
                                               "placed_at": "2026-01-01"}])
    t.set_business_identity("demo_user")
    out = t.get_customer_orders.invoke({})
    assert "CMD-0001" in out and "livrée" in out


def test_get_customer_orders_by_email_records_identity(monkeypatch):
    monkeypatch.setattr(t.repo, "get_customer_by_email",
                        lambda e, db=None: {"customer_id": "c2", "full_name": "Julie",
                                            "email": e})
    monkeypatch.setattr(t.repo, "get_orders_for_customer",
                        lambda cid, db=None: [])
    t.set_business_identity("demo_user")
    out = t.get_customer_orders.invoke({"email": "julie@example.fr"})
    assert t.get_discovered_email() == "julie@example.fr"
    assert "aucune commande" in out.lower()
