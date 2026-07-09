from unittest.mock import MagicMock
import scripts.seed_business_db as s
from business.generate import DEFAULT_POOLS


def test_generate_pools_falls_back_on_llm_error(monkeypatch):
    class BoomLLM:
        def invoke(self, *a, **k):
            raise RuntimeError("no llm")
    monkeypatch.setattr(s, "_build_llm", lambda settings: BoomLLM())
    pools = s.generate_pools(settings=object())
    assert pools.base_products  # fallback non vide


def test_insert_dataset_truncates_then_inserts():
    cur = MagicMock()
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    db = MagicMock()
    db.connect.return_value = conn
    from business.generate import assemble_dataset
    ds = assemble_dataset(DEFAULT_POOLS, n_customers=5, seed=7)
    s.insert_dataset(ds, db=db)
    executed = " ".join(str(c.args[0]) for c in cur.execute.call_args_list
                        if c.args) + " ".join(
        str(c.args[0]) for c in cur.executemany.call_args_list if c.args)
    assert "TRUNCATE" in executed
    assert cur.executemany.call_count == 5   # 5 tables
    conn.commit.assert_called()


def test_seed_assembles_expected_quotas(monkeypatch):
    monkeypatch.setattr(s, "generate_pools", lambda settings=None: DEFAULT_POOLS)
    monkeypatch.setattr(s, "insert_dataset", lambda ds, db=None: None)
    ds = s.seed(n_customers=5, db=MagicMock(), settings=object())
    assert len(ds.customers) == 5
    assert len(ds.products) == 10
    assert any(c["velmo_user_id"] == "demo_user" for c in ds.customers)
