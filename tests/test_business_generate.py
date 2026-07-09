from business.models import Pools
from business.generate import (
    assemble_dataset, customer_ref, order_number, DEFAULT_POOLS,
)

FORCED_DEMO_STATUSES = {"préparation", "expédiée", "livrée"}


def test_id_formatters():
    assert customer_ref(123) == "CLI-000123"
    assert order_number(4490) == "CMD-4490"


def test_assemble_counts_and_uniqueness():
    ds = assemble_dataset(DEFAULT_POOLS, n_customers=20, seed=1)
    assert len(ds.customers) == 20
    assert len(ds.products) == 40           # ratio 2:1
    assert len(ds.orders) == 53             # round(20 * 2.667)
    # unicité des identifiants métier
    assert len({c["customer_ref"] for c in ds.customers}) == 20
    assert len({c["email"] for c in ds.customers}) == 20
    assert len({p["sku"] for p in ds.products}) == 40
    assert len({o["order_number"] for o in ds.orders}) == len(ds.orders)


def test_demo_user_prelinked_with_status_coverage():
    ds = assemble_dataset(DEFAULT_POOLS, n_customers=20, seed=1)
    demo = [c for c in ds.customers if c["velmo_user_id"] == "demo_user"]
    assert len(demo) == 1
    demo_id = demo[0]["customer_id"]
    demo_orders = [o for o in ds.orders if o["customer_id"] == demo_id]
    statuses = {o["status"] for o in demo_orders}
    assert FORCED_DEMO_STATUSES.issubset(statuses)


def test_order_totals_match_items():
    ds = assemble_dataset(DEFAULT_POOLS, n_customers=15, seed=2)
    items_by_order = {}
    for it in ds.order_items:
        items_by_order.setdefault(it["order_id"], []).append(it)
    for o in ds.orders:
        items = items_by_order[o["order_id"]]
        assert items, "chaque commande a au moins un article"
        expected = round(sum(i["quantity"] * i["unit_price_eur"] for i in items), 2)
        assert o["total_eur"] == expected


def test_shipment_coherence_with_status():
    ds = assemble_dataset(DEFAULT_POOLS, n_customers=25, seed=3)
    ship_by_order = {s["order_id"]: s for s in ds.shipments}
    for o in ds.orders:
        if o["status"] == "annulée":
            assert o["order_id"] not in ship_by_order
        elif o["status"] == "expédiée":
            s = ship_by_order[o["order_id"]]
            assert s["status"] == "en_transit" and s["shipped_at"] is not None
        elif o["status"] == "livrée":
            s = ship_by_order[o["order_id"]]
            assert s["status"] == "livré" and s["delivered_at"] is not None


def test_order_items_reference_existing_products():
    ds = assemble_dataset(DEFAULT_POOLS, n_customers=15, seed=4)
    product_ids = {p["product_id"] for p in ds.products}
    for it in ds.order_items:
        assert it["product_id"] in product_ids
