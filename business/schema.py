import logging

logger = logging.getLogger(__name__)

BUSINESS_DDL = [
    """
    CREATE TABLE IF NOT EXISTS customers (
        customer_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        customer_ref   VARCHAR(20) UNIQUE NOT NULL,
        full_name      VARCHAR(120) NOT NULL,
        email          VARCHAR(160) UNIQUE NOT NULL,
        phone          VARCHAR(30),
        address_line   VARCHAR(200),
        city           VARCHAR(80),
        zip            VARCHAR(10),
        country        VARCHAR(60) DEFAULT 'France',
        velmo_user_id  VARCHAR(100),
        created_at     TIMESTAMP DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email);",
    "CREATE INDEX IF NOT EXISTS idx_customers_velmo_user ON customers(velmo_user_id);",
    """
    CREATE TABLE IF NOT EXISTS products (
        product_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        sku            VARCHAR(20) UNIQUE NOT NULL,
        name           VARCHAR(160) NOT NULL,
        description    TEXT,
        category       VARCHAR(80),
        price_eur      NUMERIC(10,2) NOT NULL,
        stock          INT DEFAULT 0,
        created_at     TIMESTAMP DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);",
    """
    CREATE TABLE IF NOT EXISTS orders (
        order_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        order_number   VARCHAR(20) UNIQUE NOT NULL,
        customer_id    UUID NOT NULL REFERENCES customers(customer_id),
        status         VARCHAR(20) NOT NULL,
        total_eur      NUMERIC(10,2) NOT NULL DEFAULT 0,
        placed_at      TIMESTAMP NOT NULL,
        updated_at     TIMESTAMP DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);",
    "CREATE INDEX IF NOT EXISTS idx_orders_number ON orders(order_number);",
    """
    CREATE TABLE IF NOT EXISTS order_items (
        item_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        order_id       UUID NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
        product_id     UUID NOT NULL REFERENCES products(product_id),
        quantity       INT NOT NULL CHECK (quantity > 0),
        unit_price_eur NUMERIC(10,2) NOT NULL
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);",
    """
    CREATE TABLE IF NOT EXISTS shipments (
        shipment_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        order_id           UUID NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
        carrier            VARCHAR(40),
        tracking_number    VARCHAR(20),
        status             VARCHAR(20) NOT NULL,
        shipped_at         TIMESTAMP,
        estimated_delivery TIMESTAMP,
        delivered_at       TIMESTAMP
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_shipments_order ON shipments(order_id);",
]


def init_business_tables(db=None) -> None:
    """Créer les 5 tables métier si absentes. Idempotent."""
    from memory.database import get_db

    db = db or get_db()
    conn = db.connect()
    with conn.cursor() as cur:
        for stmt in BUSINESS_DDL:
            cur.execute(stmt)
    conn.commit()
    logger.info("Business tables initialized.")
