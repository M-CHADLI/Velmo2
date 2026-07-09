"""Database viewer component for live table inspection."""

import streamlit as st
import pandas as pd
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class DatabaseViewer:
    """Display database tables in Streamlit tabs."""

    def __init__(self, db, user_id: str):
        self.db = db
        self.user_id = user_id

    def render(self):
        """Render database viewer with 4 tabs."""
        st.divider()
        st.subheader("📊 Database Live View")

        tab1, tab2, tab3, tab4 = st.tabs([
            "🧠 Facts",
            "🛡️ Guardrails",
            "📝 Audit Log",
            "📈 Extraction"
        ])

        with tab1:
            self._render_facts()
        with tab2:
            self._render_guardrails()
        with tab3:
            self._render_audit_log()
        with tab4:
            self._render_extraction_metadata()

    def _render_facts(self):
        """Display facts table for current user."""
        try:
            conn = self.db.connect()
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        fact_id,
                        (data->>'key') as key,
                        (data->>'value') as value,
                        (data->>'type') as type,
                        (data->>'confidence')::float as confidence,
                        created_at,
                        status
                    FROM facts
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT 10
                """, (self.user_id,))

                rows = cur.fetchall()

            if not rows:
                st.info("Aucun fact stocké encore")
                return

            df = pd.DataFrame(rows, columns=[
                'Fact ID', 'Key', 'Value', 'Type', 'Confidence', 'Created', 'Status'
            ])

            # Format confidence as percentage
            df['Confidence'] = df['Confidence'].apply(lambda x: f"{x*100:.0f}%" if x else "N/A")

            # Format datetime
            if 'Created' in df.columns:
                df['Created'] = pd.to_datetime(df['Created']).dt.strftime('%H:%M:%S')

            st.dataframe(df, use_container_width=True, hide_index=True)

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Facts", len(df))
            with col2:
                st.metric("Types", df['Type'].nunique())
            with col3:
                active = (df['Status'] == 'active').sum()
                st.metric("Active", active)

        except Exception as e:
            st.error(f"Erreur: {e}")
            logger.error(f"Facts query error: {e}")

    def _render_guardrails(self):
        """Display guardrail decisions for current user."""
        try:
            conn = self.db.connect()
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        id,
                        where_,
                        category,
                        allowed,
                        reason,
                        latency_ms,
                        created_at
                    FROM guardrail_log
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT 10
                """, (self.user_id,))

                rows = cur.fetchall()

            if not rows:
                st.info("Aucune décision garde-fou encore")
                return

            df = pd.DataFrame(rows, columns=[
                'ID', 'Where', 'Category', 'Allowed', 'Reason', 'Latency (ms)', 'Created'
            ])

            # Format datetime
            if 'Created' in df.columns:
                df['Created'] = pd.to_datetime(df['Created']).dt.strftime('%H:%M:%S')

            # Color code allowed/blocked
            def highlight_allowed(val):
                if val == True:
                    return '🟢 Allowed'
                else:
                    return '🔴 Blocked'

            df['Allowed'] = df['Allowed'].apply(highlight_allowed)

            st.dataframe(df, use_container_width=True, hide_index=True)

            col1, col2, col3 = st.columns(3)
            with col1:
                total = len(df)
                st.metric("Total Checks", total)
            with col2:
                blocked = (df['Allowed'] == '🔴 Blocked').sum()
                pct = (blocked / total * 100) if total > 0 else 0
                st.metric("Blocked", f"{blocked} ({pct:.0f}%)")
            with col3:
                avg_latency = pd.to_numeric(df['Latency (ms)'], errors='coerce').mean()
                st.metric("Avg Latency", f"{avg_latency:.0f}ms" if not pd.isna(avg_latency) else "N/A")

        except Exception as e:
            st.error(f"Erreur: {e}")
            logger.error(f"Guardrails query error: {e}")

    def _render_audit_log(self):
        """Display audit log for current user."""
        try:
            conn = self.db.connect()
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        log_id,
                        action,
                        fact_id,
                        reason,
                        created_at
                    FROM audit_log
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT 10
                """, (self.user_id,))

                rows = cur.fetchall()

            if not rows:
                st.info("Aucune entrée audit encore")
                return

            df = pd.DataFrame(rows, columns=[
                'Log ID', 'Action', 'Fact ID', 'Reason', 'Created'
            ])

            # Format datetime
            if 'Created' in df.columns:
                df['Created'] = pd.to_datetime(df['Created']).dt.strftime('%H:%M:%S')

            st.dataframe(df, use_container_width=True, hide_index=True)

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Logs", len(df))
            with col2:
                actions = df['Action'].nunique()
                st.metric("Action Types", actions)

        except Exception as e:
            st.error(f"Erreur: {e}")
            logger.error(f"Audit log query error: {e}")

    def _render_extraction_metadata(self):
        """Display extraction metadata."""
        try:
            conn = self.db.connect()
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        extraction_id,
                        round_number,
                        messages_count,
                        judge_confidence,
                        facts_extracted,
                        facts_valid,
                        judge_latency_ms,
                        created_at
                    FROM extraction_metadata
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT 10
                """, (self.user_id,))

                rows = cur.fetchall()

            if not rows:
                st.info("Aucune extraction effectuée encore")
                return

            df = pd.DataFrame(rows, columns=[
                'Extraction ID', 'Round', 'Messages', 'Judge Confidence',
                'Facts Extracted', 'Facts Valid', 'Latency (ms)', 'Created'
            ])

            # Format confidence as percentage
            if 'Judge Confidence' in df.columns:
                df['Judge Confidence'] = df['Judge Confidence'].apply(
                    lambda x: f"{x*100:.0f}%" if x else "N/A"
                )

            # Format datetime
            if 'Created' in df.columns:
                df['Created'] = pd.to_datetime(df['Created']).dt.strftime('%H:%M:%S')

            st.dataframe(df, use_container_width=True, hide_index=True)

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Extractions", len(df))
            with col2:
                total_facts = pd.to_numeric(df['Facts Extracted'], errors='coerce').sum()
                st.metric("Total Facts", int(total_facts) if not pd.isna(total_facts) else 0)
            with col3:
                avg_latency = pd.to_numeric(df['Latency (ms)'], errors='coerce').mean()
                st.metric("Avg Latency", f"{avg_latency:.0f}ms" if not pd.isna(avg_latency) else "N/A")

        except Exception as e:
            st.error(f"Erreur: {e}")
            logger.error(f"Extraction metadata query error: {e}")
