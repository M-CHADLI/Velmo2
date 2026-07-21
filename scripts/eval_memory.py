import json
import logging
import time
import sys
import unicodedata
from typing import Any
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from velmo.memory import get_db, VelmoMemoryManager
from velmo.config import load_settings

def normalize_text(text: str) -> str:
    """Normalize unicode to strip accents and convert to lowercase for robust matching."""
    if not text:
        return ""
    # Normalize to decompose diacritics
    nfd_form = unicodedata.normalize('NFD', text)
    # Remove combining marks
    without_accents = "".join(c for c in nfd_form if unicodedata.category(c) != 'Mn')
    # Replace special French characters like ç
    return without_accents.replace('ç', 'c').replace('Ç', 'C').lower().strip()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def reset_database() -> None:
    """Clear database tables to ensure clean evaluation state."""
    db = get_db()
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE facts, audit_log, extraction_metadata RESTART IDENTITY CASCADE;")
            conn.commit()
            logger.info("Database truncated for fresh evaluation.")
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to reset database: {e}")
        raise e

def run_llm_query(manager: VelmoMemoryManager, user_id: str, question: str) -> str:
    """Query Kimi 2.6 using short-term history and retrieved long-term facts."""
    settings = load_settings()

    # Même client que VelmoAgent : endpoint OpenAI-compatible via base_url.
    # (AzureChatOpenAI + azure_endpoint produisait une URL malformée -> 404.)
    llm = ChatOpenAI(
        model=settings.azure_openai_deployment_name,
        api_key=settings.azure_openai_api_key,
        base_url=settings.azure_openai_endpoint,
        temperature=0.0,
    )

    # 1. Retrieve long-term context
    lt_context = manager.get_conversation_context(user_id, question, k=3)

    # 2. Retrieve short-term history (fenêtre glissante propre à cet utilisateur)
    st_history_str = manager._get_user_short_term(user_id).format_history_string()

    # System prompt combining context and short-term
    system_prompt = f"""You are Velmo Support Assistant. Answer the client's question accurately.
Use the following known facts about the client if relevant:
{lt_context}
"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "Conversation history:\n{history}\n\nClient question: {question}")
    ])

    chain = prompt | llm
    try:
        response = chain.invoke({
            "history": st_history_str,
            "question": question
        })
        return response.content.strip()
    except Exception as e:
        logger.error(f"Error querying Kimi 2.6 during evaluation: {e}")
        return ""

def evaluate_cases(cases_file: str) -> dict[str, Any]:
    """Execute evaluation cases and return scores."""
    settings = load_settings()
    db = get_db()

    # Ensure database is initialized
    try:
        db.init_db()
    except Exception as e:
        print(f"Error: Could not connect to or initialize database: {e}")
        print("Please make sure your Docker container is running by executing: docker compose up -d")
        sys.exit(1)

    reset_database()

    # Load cases
    cases = []
    with open(cases_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                cases.append(json.loads(line))

    results = []
    passed_count = 0
    total_latency_ms = 0

    print("\n" + "="*80)
    print(f"RUNNING MEMORY EVALUATION HARNESS: {len(cases)} cases")
    print("="*80)

    for case in cases:
        case_id = case["id"]
        tag = case["tag"]
        user_id = case["user_id"]
        turns = case["turns"]
        eval_info = case["evaluation"]

        print(f"\n[Test Case] {case_id} (Tag: {tag}) - User: {user_id}")

        # 1. Initialize Memory Manager
        manager = VelmoMemoryManager(settings)
        conv_id = f"conv-{case_id}"

        # 2. Feed dialogue turns
        start_time = time.perf_counter()
        for turn in turns:
            role = turn["role"]
            content = turn["content"]
            if role == "user":
                manager.record_user_message(user_id, conv_id, content)
            else:
                manager.record_assistant_message(user_id, conv_id, content)

        # Force a fact extraction at the end of the conversation to simulate final session sync
        manager.trigger_fact_extraction(user_id, conv_id)

        # 3. Simulate session logic depending on requirement tag
        if eval_info["type"] == "persistence":
            # For multi-session persistence, clear short-term memory to force loading from database
            print("  -> Simulating new session: clearing short-term memory")
            manager._get_user_short_term(user_id).clear()

        # 4. Run retrieval and LLM completion
        question = eval_info["question"]
        llm_response = run_llm_query(manager, user_id, question)
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        total_latency_ms += latency_ms

        print(f"  Question: {question}")
        print(f"  Assistant Response: {llm_response}")

        # 5. Assertions
        passed = False
        if eval_info["type"] in ("recall", "persistence"):
            expected = eval_info["expected_substring"]
            if normalize_text(expected) in normalize_text(llm_response):
                passed = True
                print(f"  Result: \033[92mPASS\033[0m (Found expected substring: '{expected}')")
            else:
                print(f"  Result: \033[91mFAIL\033[0m (Expected substring '{expected}' not found)")

        elif eval_info["type"] == "forget":
            forbidden = eval_info["forbidden_substring"]
            # Check context retrieval directly to verify it was soft-deleted
            context = manager.get_conversation_context(user_id, question)

            if normalize_text(forbidden) not in normalize_text(context) and normalize_text(forbidden) not in normalize_text(llm_response):
                passed = True
                print(f"  Result: \033[92mPASS\033[0m (Verified forgotten information '{forbidden}' is absent)")
            else:
                print(f"  Result: \033[91mFAIL\033[0m (Forgotten information '{forbidden}' is still present in memory/response)")

        if passed:
            passed_count += 1

        results.append({
            "id": case_id,
            "tag": tag,
            "passed": passed,
            "latency_ms": latency_ms
        })

    # Summary
    success_rate = (passed_count / len(cases)) * 100 if cases else 0
    avg_latency = (total_latency_ms / len(cases)) if cases else 0

    print("\n" + "="*80)
    print("EVALUATION SUMMARY")
    print("="*80)
    print(f"Total Cases:  {len(cases)}")
    print(f"Passed:       {passed_count}")
    print(f"Failed:       {len(cases) - passed_count}")
    print(f"Success Rate: {success_rate:.2f}%")
    print(f"Avg Latency:  {avg_latency:.2f} ms")
    print("="*80)

    # Return summary dictionary
    return {
        "total": len(cases),
        "passed": passed_count,
        "success_rate": success_rate,
        "avg_latency_ms": avg_latency
    }

if __name__ == "__main__":
    cases_file = "eval/memory_cases.jsonl"
    if len(sys.argv) > 1:
        cases_file = sys.argv[1]

    evaluate_cases(cases_file)
