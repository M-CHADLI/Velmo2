import json
import logging
import time
import uuid
import numpy as np
from datetime import datetime
from typing import Any, Optional
from langchain_openai import AzureOpenAIEmbeddings
from .config import load_settings
from .database import get_db
from .schema import Fact, FactData, AuditLog, ExtractionMetadata

logger = logging.getLogger(__name__)

class LongTermMemory:
    """Long-term memory module using PostgreSQL + pgvector for fact storage, retrieval, and updates."""

    def __init__(self, settings=None, db=None) -> None:
        self.settings = settings or load_settings()
        self.db = db or get_db()

        # Initialize LangChain Azure OpenAI embeddings (text-embedding-3-small via Azure)
        try:
            self.embeddings = AzureOpenAIEmbeddings(
                model=self.settings.embedding_model,
                api_key=self.settings.azure_openai_api_key,
                azure_endpoint=self.settings.azure_openai_endpoint,
                api_version=self.settings.azure_openai_api_version,
                dimensions=self.settings.embedding_dimensions
            )
        except Exception as e:
            logger.warning(f"Could not initialize AzureOpenAIEmbeddings: {e}. Fallback to mock embeddings will be active.")
            self.embeddings = None

    def _get_embedding(self, text: str) -> list[float]:
        """Generate vector embedding for the given text. Falls back to mock vector if API fails."""
        if self.embeddings:
            try:
                # Call OpenAI API to generate embedding
                return self.embeddings.embed_query(text)
            except Exception as e:
                logger.warning(f"OpenAI embedding API failed: {e}. Generating mock embedding.")
        
        # Fallback deterministic mock embedding (generates a normalized vector of 384 dimensions)
        dim = self.settings.embedding_dimensions
        # Create a deterministic mock vector by hashing the text
        seed = sum(ord(c) for c in text) % 10000
        rng = np.random.default_rng(seed)
        vec = rng.standard_normal(dim)
        vec /= np.linalg.norm(vec)  # Normalize
        return vec.tolist()

    def store_fact(
        self,
        user_id: str,
        conversation_id: str,
        fact_data: FactData,
        extracted_at_msg: Optional[int] = None
    ) -> str:
        """Insert or update a fact in the database with user isolation and version tracking.

        If a fact with the same 'key' already exists for this user, it updates it, increments the version,
        and saves the old value in the version history.
        """
        # Embed the value to capture semantic similarity
        embedding = self._get_embedding(fact_data.value)
        conn = self.db.connect()

        try:
            with conn.cursor() as cur:
                # Check if an active fact with the same key already exists for this user
                cur.execute("""
                    SELECT fact_id, data, version, version_history 
                    FROM facts 
                    WHERE user_id = %s AND (data->>'key') = %s AND status = 'active'
                """, (user_id, fact_data.key))
                
                existing = cur.fetchone()

                if existing:
                    # Update scenario
                    fact_id = existing["fact_id"]
                    old_data = existing["data"]
                    old_version = existing["version"]
                    old_history = existing["version_history"] or []
                    
                    # If value hasn't changed, just return the ID
                    if old_data.get("value") == fact_data.value:
                        return str(fact_id)

                    # Build version history item
                    history_entry = {
                        "version": old_version,
                        "value": old_data.get("value"),
                        "timestamp": datetime.now().isoformat(),
                        "reason": "updated_by_judge"
                    }
                    new_history = list(old_history)
                    new_history.append(history_entry)
                    new_history = new_history[-3:]  # Keep last 3 versions as per design

                    # Update fact
                    new_data = fact_data.model_dump()
                    cur.execute("""
                        UPDATE facts
                        SET data = %s,
                            embedding = %s::vector,
                            version = %s,
                            version_history = %s,
                            updated_at = NOW()
                        WHERE fact_id = %s
                    """, (
                        json.dumps(new_data),
                        embedding,
                        old_version + 1,
                        json.dumps(new_history),
                        fact_id
                    ))

                    # Audit log for update
                    cur.execute("""
                        INSERT INTO audit_log (user_id, action, fact_id, old_value, new_value, reason)
                        VALUES (%s, 'fact_updated', %s, %s, %s, %s)
                    """, (
                        user_id,
                        fact_id,
                        json.dumps(old_data),
                        json.dumps(new_data),
                        "Fact updated automatically by Judge Agent"
                    ))
                else:
                    # Insert scenario
                    fact_id = uuid.uuid4()
                    new_data = fact_data.model_dump()
                    cur.execute("""
                        INSERT INTO facts (
                            fact_id, user_id, conversation_id, data, embedding,
                            extracted_at_message, status, version
                        ) VALUES (%s, %s, %s, %s, %s::vector, %s, 'active', 1)
                    """, (
                        fact_id,
                        user_id,
                        conversation_id,
                        json.dumps(new_data),
                        embedding,
                        extracted_at_msg
                    ))

                    # Audit log for insert
                    cur.execute("""
                        INSERT INTO audit_log (user_id, action, fact_id, new_value, reason)
                        VALUES (%s, 'fact_extracted', %s, %s, %s)
                    """, (
                        user_id,
                        fact_id,
                        json.dumps(new_data),
                        "Fact extracted by Judge Agent"
                    ))

                conn.commit()
                return str(fact_id)
        except Exception as e:
            conn.rollback()
            logger.error(f"Error storing fact in DB: {e}")
            raise e

    def retrieve_context(self, user_id: str, query: str, k: int = 5) -> list[dict[str, Any]]:
        """Retrieve top-k similar facts using vector cosine similarity, enforced with strict user isolation."""
        query_embedding = self._get_embedding(query)
        conn = self.db.connect()

        try:
            with conn.cursor() as cur:
                # Query similar active facts for this user
                # Operators: <=> represents Cosine Distance
                # Similarity is 1 - Cosine Distance
                cur.execute("""
                    SELECT 
                        fact_id,
                        data,
                        version,
                        1 - (embedding <=> %s::vector) AS similarity
                    FROM facts
                    WHERE user_id = %s
                      AND status = 'active'
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                """, (query_embedding, user_id, query_embedding, k))

                results = cur.fetchall()
                
                # Format response and audit access
                facts = []
                for row in results:
                    fact_id = row["fact_id"]
                    data = row["data"]
                    
                    # Log audit check for accessing fact
                    cur.execute("""
                        INSERT INTO audit_log (user_id, action, fact_id, reason)
                        VALUES (%s, 'fact_accessed', %s, 'context_retrieval')
                    """, (user_id, fact_id))

                    fact = {
                        "fact_id": str(fact_id),
                        "key": data.get("key"),
                        "value": data.get("value"),
                        "type": data.get("type"),
                        "confidence": data.get("confidence"),
                        "similarity": float(row["similarity"] or 0.0),
                        "version": row["version"]
                    }
                    facts.append(fact)

                # Keep last_accessed_at updated
                if facts:
                    fact_ids = [row["fact_id"] for row in results]
                    cur.execute("""
                        UPDATE facts
                        SET last_accessed_at = NOW()
                        WHERE fact_id = ANY(%s)
                    """, (fact_ids,))

                conn.commit()
                return facts

        except Exception as e:
            conn.rollback()
            logger.error(f"Error retrieving context facts: {e}")
            raise e

    def delete_fact_gdpr(self, fact_id: str, user_id: str, reason: str) -> bool:
        """Soft-delete a fact to comply with GDPR Droit à l'oubli (R5)."""
        conn = self.db.connect()
        try:
            with conn.cursor() as cur:
                # Fetch target fact first to log old value
                cur.execute("""
                    SELECT data FROM facts 
                    WHERE fact_id = %s AND user_id = %s AND status = 'active'
                """, (fact_id, user_id))
                row = cur.fetchone()
                
                if not row:
                    logger.warning(f"GDPR soft-delete failed: active fact {fact_id} for user {user_id} not found.")
                    return False
                
                old_value = row["data"]

                # Soft delete update
                cur.execute("""
                    UPDATE facts
                    SET status = 'soft_deleted',
                        deletion_reason = %s,
                        updated_at = NOW()
                    WHERE fact_id = %s AND user_id = %s
                """, (reason, fact_id, user_id))

                # Log deletion to audit log
                cur.execute("""
                    INSERT INTO audit_log (user_id, action, fact_id, old_value, reason)
                    VALUES (%s, 'fact_soft_delete', %s, %s, %s)
                """, (user_id, fact_id, json.dumps(old_value), reason))

                conn.commit()
                logger.info(f"GDPR soft-delete successful for fact {fact_id} of user {user_id}")
                return True
        except Exception as e:
            conn.rollback()
            logger.error(f"Error executing GDPR soft-delete in DB: {e}")
            raise e

    def get_audit_trail(self, user_id: str) -> list[dict[str, Any]]:
        """Return the audit log trace for a specific user (R6)."""
        conn = self.db.connect()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT log_id, action, fact_id, old_value, new_value, reason, created_at
                    FROM audit_log
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                """, (user_id,))
                rows = cur.fetchall()
                
                for row in rows:
                    row["log_id"] = str(row["log_id"])
                    if row["fact_id"]:
                        row["fact_id"] = str(row["fact_id"])
                    if row["created_at"]:
                        row["created_at"] = row["created_at"].isoformat()
                return rows
        except Exception as e:
            logger.error(f"Error fetching audit trail for user {user_id}: {e}")
            raise e

    def inspect_memory(self, user_id: str) -> list[dict[str, Any]]:
        """Retrieve all active facts stored for a user (R6)."""
        conn = self.db.connect()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT fact_id, data, version, created_at, last_accessed_at
                    FROM facts
                    WHERE user_id = %s AND status = 'active'
                    ORDER BY created_at DESC
                """, (user_id,))
                rows = cur.fetchall()
                
                facts = []
                for row in rows:
                    fact = {
                        "fact_id": str(row["fact_id"]),
                        "key": row["data"].get("key"),
                        "value": row["data"].get("value"),
                        "type": row["data"].get("type"),
                        "confidence": row["data"].get("confidence"),
                        "version": row["version"],
                        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                        "last_accessed_at": row["last_accessed_at"].isoformat() if row["last_accessed_at"] else None
                    }
                    facts.append(fact)
                return facts
        except Exception as e:
            logger.error(f"Error inspecting memory for user {user_id}: {e}")
            raise e

    def record_extraction_metadata(self, meta: ExtractionMetadata) -> str:
        """Log metadata regarding a Judge fact extraction operation."""
        conn = self.db.connect()
        ext_id = uuid.uuid4()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO extraction_metadata (
                        extraction_id, user_id, conversation_id, round_number, messages_count,
                        judge_confidence, judge_latency_ms, facts_extracted, facts_valid,
                        embedding_latency_ms, embedding_model, embedding_dimensions, db_latency_ms
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    ext_id,
                    meta.user_id,
                    meta.conversation_id,
                    meta.round_number,
                    meta.messages_count,
                    meta.judge_confidence,
                    meta.judge_latency_ms,
                    meta.facts_extracted,
                    meta.facts_valid,
                    meta.embedding_latency_ms,
                    meta.embedding_model,
                    meta.embedding_dimensions,
                    meta.db_latency_ms
                ))
                conn.commit()
                return str(ext_id)
        except Exception as e:
            conn.rollback()
            logger.error(f"Error logging extraction metadata: {e}")
            raise e
