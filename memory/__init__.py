"""Velmo 2.0 Memory Package.

Implements the three-layer memory architecture:
1. Short-Term Memory: Sliding window memory of the last 30 messages.
2. Judge Agent: Extraction of facts from conversation every 5 tours using Kimi 2.6.
3. Long-Term Memory: PostgreSQL JSONB + pgvector persistent database.
"""

from .config import Settings, load_settings
from .database import Database, get_db
from .short_term import SlidingWindowMemory
from .long_term import LongTermMemory
from .judge import JudgeAgent
from .manager import VelmoMemoryManager

# Alias used by the VelmoAgent orchestrator
MemoryManager = VelmoMemoryManager

__all__ = [
    "Settings",
    "load_settings",
    "Database",
    "get_db",
    "SlidingWindowMemory",
    "LongTermMemory",
    "JudgeAgent",
    "VelmoMemoryManager",
    "MemoryManager",
]
