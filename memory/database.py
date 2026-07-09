import logging
import psycopg
from psycopg.rows import dict_row
from .config import load_settings

logger = logging.getLogger(__name__)

class Database:
    """PostgreSQL database connector and initializer for Velmo 2.0 Memory."""

    def __init__(self, connection_url: str | None = None) -> None:
        settings = load_settings()
        self.connection_url = connection_url or settings.database_url
        self._conn = None

    def connect(self) -> psycopg.Connection:
        """Establish or return connection to the database."""
        if self._conn is None or self._conn.closed:
            try:
                self._conn = psycopg.connect(self.connection_url, row_factory=dict_row)
            except Exception as e:
                logger.error(f"Failed to connect to PostgreSQL at {self.connection_url}: {e}")
                raise e
        return self._conn

    def close(self) -> None:
        """Close the database connection."""
        if self._conn and not self._conn.closed:
            self._conn.close()
            self._conn = None

    def init_db(self) -> None:
        """Initialize database schema, tables, and extensions."""
        from guardrails.audit import init_guardrail_table
        conn = self.connect()
        try:
            with conn.cursor() as cur:
                # 1. Create pgvector extension
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                conn.commit()

                # 2. Create facts table (using VARCHAR/TEXT for ids to support test strings)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS facts (
                        fact_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        user_id VARCHAR(100) NOT NULL,
                        conversation_id VARCHAR(100) NOT NULL,
                        data JSONB NOT NULL,
                        embedding vector(384),
                        extracted_at_message INT,
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW(),
                        last_accessed_at TIMESTAMP,
                        status VARCHAR(20) DEFAULT 'active',
                        deletion_reason VARCHAR(255),
                        version INT DEFAULT 1,
                        version_history JSONB DEFAULT '[]'::jsonb
                    );
                """)

                # Create indices for facts
                cur.execute("CREATE INDEX IF NOT EXISTS idx_facts_user_id ON facts(user_id);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_facts_conversation_id ON facts(conversation_id);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_facts_status ON facts(status);")
                # HNSW index for fast vector search (using cosine distance)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_facts_embedding ON facts USING hnsw (embedding vector_cosine_ops)
                    WITH (m = 16, ef_construction = 64);
                """)
                cur.execute("CREATE INDEX IF NOT EXISTS idx_facts_data ON facts USING GIN (data);")

                # 3. Create extraction_metadata table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS extraction_metadata (
                        extraction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        user_id VARCHAR(100) NOT NULL,
                        conversation_id VARCHAR(100) NOT NULL,
                        round_number INT,
                        messages_count INT,
                        judge_confidence FLOAT,
                        judge_latency_ms INT,
                        facts_extracted INT,
                        facts_valid INT,
                        embedding_latency_ms INT,
                        embedding_model VARCHAR(100),
                        embedding_dimensions INT,
                        db_latency_ms INT,
                        created_at TIMESTAMP DEFAULT NOW()
                    );
                """)
                cur.execute("CREATE INDEX IF NOT EXISTS idx_extraction_metadata_user_id ON extraction_metadata(user_id);")

                # 4. Create audit_log table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS audit_log (
                        log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        user_id VARCHAR(100) NOT NULL,
                        action VARCHAR(100) NOT NULL,
                        fact_id UUID,
                        old_value JSONB,
                        new_value JSONB,
                        reason VARCHAR(255),
                        ip_address INET,
                        created_at TIMESTAMP DEFAULT NOW()
                    );
                """)
                cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_user_id ON audit_log(user_id);")

                conn.commit()
                logger.info("Database tables initialized successfully.")

                # 5. Create guardrail_log table (for tracking all guardrail decisions)
                init_guardrail_table(self)
        except Exception as e:
            conn.rollback()
            logger.error(f"Error initializing database: {e}")
            raise e

_db_instance = None

def get_db(connection_url: str | None = None) -> Database:
    """Singleton getter for the Database instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database(connection_url)
    return _db_instance
