from gradio_client import Client, handle_file
import os
import logging
import json
import time

logger = logging.getLogger(__name__)

HF_TOKEN = os.getenv("HF_API_TOKEN")
SPACE_URL = os.getenv("TRINETRA_AI_NODE", "VVerma4436/Legal-Log-Engine")

def get_ai_client():
    try:
        # Prefer headers for compatibility
        if HF_TOKEN:
            return Client(SPACE_URL, headers={"Authorization": f"Bearer {HF_TOKEN}"})
        return Client(SPACE_URL)
    except Exception as e:
        logger.error(f"Failed to initialize AI Client: {e}")
        raise e

def predict_with_retry(fn_name, *args, **kwargs):
    """
    Retries AI calls for 120 seconds to handle Cold Boot.
    """
    MAX_RETRIES = 6
    RETRY_DELAY = 20
    
    for attempt in range(MAX_RETRIES):
        try:
            client = get_ai_client()
            return client.predict(*args, **kwargs)
        except Exception as e:
            logger.warning(f"{fn_name} attempt {attempt+1} failed: {e}")
            if attempt == MAX_RETRIES - 1:
                raise e
            time.sleep(RETRY_DELAY)

def fetch_or_create_case(case_id, justification=None):
    try:
        # HF App Signature: fetch_or_create_case(case_no)
        return predict_with_retry(
            "fetch_case",
            case_id,
            api_name="/fetch_or_create_case"
        )
    except Exception:
        return "AI Node offline."

def analyze_logs(case_id, question, log_file_path=None):
    try:
        file_input = handle_file(log_file_path) if log_file_path else None
        
        # HF App Signature: analyze_logs(case_no, file_obj, user_q)
        result = predict_with_retry(
            "analyze_logs",
            case_id,
            file_input,
            question,
            api_name="/analyze_logs"
        )
        # Result is (text, json_data) tuple
        if isinstance(result, (list, tuple)):
            return result[0] 
        return result
    except Exception as e:
        return f"AI Connection Error: {str(e)}"

def generate_legal_doc(case_id, facts):
    try:
        # HF App Signature: draft_legal_json(case_no, user_instruction)
        json_res = predict_with_retry(
            "legal_doc",
            case_id,
            facts,
            api_name="/draft_legal_json"
        )
        return json_res if isinstance(json_res, dict) else json.loads(json_res)
    except Exception as e:
        return {"error": str(e)}
