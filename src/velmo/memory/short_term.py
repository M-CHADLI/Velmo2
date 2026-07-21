from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from ..config import load_settings

class SlidingWindowMemory:
    """In-memory sliding window FIFO buffer for short-term conversation context.

    Keeps the last N messages (e.g. 30 messages, representing 15 tours).
    """

    def __init__(self, max_messages: int | None = None) -> None:
        settings = load_settings()
        self.max_messages = max_messages or settings.short_term_max_messages
        self._messages: list[dict[str, str]] = []

    def record(self, role: str, content: str) -> None:
        """Add a turn (message) to the short-term sliding window.

        Args:
            role: 'user' or 'assistant'
            content: The text content of the message
        """
        # Normalise role to user/assistant
        normalized_role = "user" if role.lower() in ("user", "human") else "assistant"
        self._messages.append({"role": normalized_role, "content": content})

        # Enforce sliding window capacity
        if len(self._messages) > self.max_messages:
            self._messages = self._messages[-self.max_messages:]

    def history(self) -> list[dict[str, str]]:
        """Return the current short-term window of messages as a list of dicts."""
        return self._messages

    def clear(self) -> None:
        """Clear all messages from the sliding window."""
        self._messages.clear()

    def to_langchain_messages(self) -> list[BaseMessage]:
        """Convert stored messages to LangChain BaseMessage objects."""
        messages: list[BaseMessage] = []
        for msg in self._messages:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            else:
                messages.append(AIMessage(content=msg["content"]))
        return messages

    def format_history_string(self) -> str:
        """Format the history as a single string for prompt injection."""
        lines = []
        for msg in self._messages:
            role_label = "Client" if msg["role"] == "user" else "Assistant"
            lines.append(f"{role_label}: {msg['content']}")
        return "\n".join(lines)

    def __len__(self) -> int:
        return len(self._messages)
