from gradio_client import Client, handle_file
import os
import logging
import json
import concurrent.futures

logger = logging.getLogger(__name__)

# CONFIGURATION
HF_TOKEN = os.getenv("HF_API_TOKEN")
# [CRITICAL] Your specific Space URL
SPACE_URL = os.getenv("TRINETRA_AI_NODE", "https://vverma4436-legal-log-engine.hf.space/")

# Azure's load-balancer kills any HTTP connection after 230 seconds.
# We set our own timeout LOWER so Django can send a friendly error before Azure hard-kills the socket.
AI_TIMEOUT_SECONDS = 180

def get_ai_client():
    if not HF_TOKEN:
         logger.error("HF_API_TOKEN is missing in .env")
         raise ValueError("HF_API_TOKEN not configured.")
    try:
        return Client(SPACE_URL, token=HF_TOKEN, max_workers=1)
    except Exception as e:
        logger.error(f"Failed to connect to AI Client: {e}")
        raise e

def _do_analyze(case_id, question, file_input):
    """Inner function that does the actual HF call, run inside a timed thread."""
    client = get_ai_client()
    return client.predict(
        case_no=case_id,
        file_obj=file_input,
        user_q=question,
        api_name="/analyze_logs"
    )

# --- ENDPOINT 1: ANALYZE LOGS ---
def analyze_logs(case_id, question, log_file_path=None):
    try:
        file_input = None
        if log_file_path:
            file_input = handle_file(log_file_path)

        # Wrap in a thread with a hard timeout so we never exceed Azure's 230s proxy limit
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_do_analyze, case_id, question, file_input)
            try:
                result = future.result(timeout=AI_TIMEOUT_SECONDS)
                return result
            except concurrent.futures.TimeoutError:
                logger.warning(f"AI timeout after {AI_TIMEOUT_SECONDS}s - HF Space may be waking up.")
                return (
                    "⏳ **Trinetra AI is waking up from sleep.** "
                    "Please wait 60 seconds and send your message again. "
                    "The model needs time to initialize on first contact."
                )
    except Exception as e:
        logger.error(f"AI Analysis Error: {e}")
        return f"Error connecting to AI Node: {str(e)}"

def _do_legal(case_id, facts):
    """Inner function for legal drafting, run inside a timed thread."""
    client = get_ai_client()
    return client.predict(
        case_no=case_id,
        user_instruction=facts,
        api_name="/draft_legal_json"
    )

# --- ENDPOINT 2: LEGAL DRAFTER ---
def generate_legal_doc(case_id, facts):
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_do_legal, case_id, facts)
            try:
                json_str = future.result(timeout=AI_TIMEOUT_SECONDS)
            except concurrent.futures.TimeoutError:
                logger.warning("Legal doc AI timeout.")
                return {
                    "title": f"Timeout - Case {case_id}",
                    "facts": "AI is initializing. Please retry in 60 seconds.",
                    "legal_analysis": "The Hugging Face model is waking from sleep.",
                    "conclusion": "Retry required."
                }
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            logger.warning("AI returned malformed JSON. Falling back to raw text.")
            return {
                "title": f"Raw Draft - Case {case_id}",
                "facts": "AI output could not be formatted correctly. Raw text below:",
                "legal_analysis": json_str,
                "conclusion": "Manual review required."
            }
    except Exception as e:
        logger.error(f"AI Legal Doc Error: {e}")
        return {"error": str(e)}
