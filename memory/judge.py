import json
import logging
import time
from typing import Any
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from .config import load_settings
from .schema import FactData

logger = logging.getLogger(__name__)

JUDGE_SYSTEM_PROMPT = """You are the Fact Extraction Judge for Velmo 2.0.
Your task is to analyze the recent conversation history between the User (Client) and the Assistant, and extract durable facts, preferences, or identifiers about the user.

Categories of facts to extract:
1. 'identifier': Fixed business identifiers (e.g. contract number 'CT-7788', order ID '4490', SIRET).
2. 'preference': User preferences (e.g. 'tutoyez-moi', contact by email, prefers French).
3. 'user_fact': General stable info about the user (e.g. 'je suis client pro', 'habite à Lyon, code postal 69003').

Guidelines:
- Extract ONLY facts that are explicitly stated by the user and have long-term value.
- Do NOT extract temporary details (e.g. 'I am happy today', greeting remarks, general questions).
- For each fact, assign a confidence score between 0.0 and 1.0. If you are very sure, assign >= 0.9.
- If the user explicitly asks to modify a fact or changes their preference, output the new value.
- The output MUST be a valid JSON object matching the schema below. Do not output any conversational filler or extra text.

JSON Output Schema:
{{
  "facts": [
    {{
      "key": "contract_id | contact_method | language | relation_type | address_zip | SIRET | name | account_type",
      "value": "the extracted value (string)",
      "type": "identifier | preference | user_fact",
      "confidence": 0.95
    }}
  ]
}}

If no facts are extracted, output:
{{
  "facts": []
}}
"""

class JudgeAgent:
    """Judge Agent using Kimi 2.6 (via AzureChatOpenAI) to extract structured facts from conversation."""

    def __init__(self, settings=None) -> None:
        self.settings = settings or load_settings()
        self.llm = ChatOpenAI(
            model=self.settings.azure_openai_deployment_name,
            api_key=self.settings.azure_openai_api_key,
            base_url=self.settings.azure_openai_endpoint,
            temperature=0.0,  # Deterministic fact extraction
        )

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", JUDGE_SYSTEM_PROMPT),
            ("user", "Conversation history:\n{conversation}")
        ])

    def extract_facts(self, messages: list[dict[str, str]]) -> tuple[list[FactData], float, int]:
        """Extract facts from the given message list.

        Args:
            messages: List of message dicts (role, content)

        Returns:
            - List of FactData objects
            - Judge average confidence score
            - Latency in milliseconds
        """
        # Format conversation for the prompt
        formatted_conv = []
        for msg in messages:
            role_label = "Client" if msg["role"] == "user" else "Assistant"
            formatted_conv.append(f"{role_label}: {msg['content']}")
        conversation_str = "\n".join(formatted_conv)

        # Trigger LLM and measure latency
        start_time = time.perf_counter()
        try:
            chain = self.prompt | self.llm
            response = chain.invoke({"conversation": conversation_str})
            content = response.content.strip()
            logger.debug(f"Judge Agent raw response: {content}")
        except Exception as e:
            logger.error(f"Error calling Judge LLM: {e}")
            return [], 0.0, int((time.perf_counter() - start_time) * 1000)

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        # Parse response
        # Clean potential markdown JSON fences
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        try:
            data = json.loads(content)
            facts_list = data.get("facts", [])
            extracted_facts = []
            confidences = []

            for f in facts_list:
                # Validate using Pydantic schema
                fact_obj = FactData(
                    key=f.get("key"),
                    value=str(f.get("value")),
                    type=f.get("type", "user_fact"),
                    confidence=float(f.get("confidence", 1.0)),
                    source="user_statement",
                    context=messages[-1]["content"] if messages else None
                )
                extracted_facts.append(fact_obj)
                confidences.append(fact_obj.confidence)

            avg_confidence = sum(confidences) / len(confidences) if confidences else 1.0
            return extracted_facts, avg_confidence, latency_ms

        except Exception as e:
            logger.error(f"Error parsing Judge Agent JSON response: {e}. Raw content: {content}")
            return [], 0.0, latency_ms
