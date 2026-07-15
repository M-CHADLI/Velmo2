"""LangSmith tracing & metrics for Velmo 2.0 (Chantier 3 - Observabilité).

Design principles:
- **Non-invasive**: LangChain auto-traces every `ChatOpenAI` call once the
  env vars are set. We only add run names, tags, metadata and custom scores.
- **Fail-safe**: if tracing is disabled, LangSmith is unreachable, or no API
  key is configured, every helper degrades to a silent no-op. Observability
  must NEVER break the agent.
- **User context**: `user_id` / `conversation_id` are propagated via
  contextvars so guardrail/judge calls (which don't receive the user_id in
  their signature) can still tag their traces.
"""
import logging
import os
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator, Optional

logger = logging.getLogger(__name__)

# --- User context (propagated across guardrail/judge calls) ------------------
_current_user_id: ContextVar[Optional[str]] = ContextVar("velmo_user_id", default=None)
_current_conversation_id: ContextVar[Optional[str]] = ContextVar(
    "velmo_conversation_id", default=None
)

_ENABLED = False
_CONFIGURED = False
_client = None  # lazily-created langsmith.Client


def _ensure_configured() -> None:
    """Run configuration once, lazily (avoids import-time cycles)."""
    global _CONFIGURED
    if not _CONFIGURED:
        _CONFIGURED = True
        _configure()


def _configure() -> None:
    """Set LangChain tracing env vars from settings (idempotent)."""
    global _ENABLED, _client
    from velmo.config import load_settings

    settings = load_settings()

    if not settings.langsmith_tracing or not settings.langsmith_api_key:
        _ENABLED = False
        logger.info("LangSmith tracing disabled (no LANGSMITH_TRACING/API key).")
        return

    # LangChain reads LANGCHAIN_* ; newer langsmith also reads LANGSMITH_*.
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
    os.environ["LANGCHAIN_ENDPOINT"] = settings.langsmith_endpoint
    os.environ.setdefault("LANGSMITH_API_KEY", settings.langsmith_api_key)
    os.environ.setdefault("LANGSMITH_PROJECT", settings.langsmith_project)

    try:
        from langsmith import Client

        _client = Client(
            api_key=settings.langsmith_api_key, api_url=settings.langsmith_endpoint
        )
        _ENABLED = True
        logger.info(
            "LangSmith tracing enabled (project=%s).", settings.langsmith_project
        )
    except Exception as e:  # noqa: BLE001
        _ENABLED = False
        logger.error("LangSmith init failed, tracing disabled: %s", e)


def set_user_context(user_id: str, conversation_id: str | None = None) -> None:
    """Attach the current user to subsequent traces (call at request start)."""
    _current_user_id.set(user_id)
    _current_conversation_id.set(conversation_id)


def is_enabled() -> bool:
    _ensure_configured()
    return _ENABLED


class RunHandle:
    """Handle returned by :func:`trace_run`.

    Carries the LangChain `config` to pass to `.invoke(config=handle.config)`,
    captures the resulting run id, and lets callers attach numeric scores that
    are flushed to LangSmith as feedback when the context exits.
    """

    def __init__(self, name: str, metadata: dict[str, Any]):
        self.name = name
        self._config: dict[str, Any] = {}
        self._collector = None
        self._run_id = None
        self._pending_scores: list[tuple[str, float, Optional[str]]] = []

    @property
    def config(self) -> dict[str, Any]:
        """Pass this to `chain.invoke(..., config=handle.config)`."""
        return self._config

    def log_score(self, key: str, score: float, comment: str | None = None) -> None:
        """Queue a numeric feedback score; flushed on context exit."""
        self._pending_scores.append((key, float(score), comment))

    def _flush(self) -> None:
        if not _ENABLED or _client is None:
            return
        if self._collector is not None and self._collector.traced_runs:
            self._run_id = self._collector.traced_runs[0].id
        if self._run_id is None:
            return
        for key, score, comment in self._pending_scores:
            try:
                _client.create_feedback(
                    run_id=self._run_id, key=key, score=score, comment=comment
                )
            except Exception as e:  # noqa: BLE001
                logger.debug("LangSmith feedback '%s' failed: %s", key, e)


@contextmanager
def trace_run(name: str, **metadata: Any) -> Iterator[RunHandle]:
    """Context manager tagging an LLM call and capturing its run for scoring.

    Usage::

        with trace_run("guardrail_classifier", category=None) as run:
            result = chain.invoke(payload, config=run.config)
            run.log_score("blocked", 1.0 if blocked else 0.0)
    """
    handle = RunHandle(name, metadata)
    _ensure_configured()
    if not _ENABLED:
        yield handle
        return

    try:
        from langchain_core.tracers.run_collector import RunCollectorCallbackHandler

        collector = RunCollectorCallbackHandler()
        handle._collector = collector

        tags = [f"component:{name}"]
        uid = _current_user_id.get()
        if uid:
            tags.append(f"user:{uid}")

        run_metadata = {k: v for k, v in metadata.items() if v is not None}
        if uid:
            run_metadata["user_id"] = uid
        conv = _current_conversation_id.get()
        if conv:
            run_metadata["conversation_id"] = conv

        handle._config = {
            "run_name": name,
            "tags": tags,
            "metadata": run_metadata,
            "callbacks": [collector],
        }
    except Exception as e:  # noqa: BLE001
        logger.debug("trace_run setup failed (%s), running untraced.", e)

    try:
        yield handle
    finally:
        try:
            handle._flush()
        except Exception as e:  # noqa: BLE001
            logger.debug("trace_run flush failed: %s", e)
