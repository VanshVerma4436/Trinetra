from gradio_client import Client, handle_file
import os
import logging
import json

logger = logging.getLogger(__name__)

# CONFIGURATION
HF_TOKEN = os.getenv("HF_API_TOKEN")
# [CRITICAL] Your specific Space URL
SPACE_URL = os.getenv("TRINETRA_AI_NODE", "https://vverma4436-legal-log-engine.hf.space/")

def get_ai_client():
    if not HF_TOKEN:
         logger.error("HF_API_TOKEN is missing in .env")
         raise ValueError("HF_API_TOKEN not configured.")
    try:
        # max_workers=1 avoids spawning extra threads; timeout prevents blocking Gunicorn indefinitely
        return Client(SPACE_URL, token=HF_TOKEN, max_workers=1)
    except Exception as e:
        logger.error(f"Failed to connect to AI Client: {e}")
        raise e

# --- ENDPOINT 1: ANALYZE LOGS ---
def analyze_logs(case_id, question, log_file_path=None):
    try:
        client = get_ai_client()
        
        file_input = None
        if log_file_path:
            file_input = handle_file(log_file_path)
        
        # Matches the inputs in your HF Space app.py
        result = client.predict(
            case_no=case_id,
            file_obj=file_input,
            user_q=question,
            api_name="/analyze_logs"
        )
        return result
    except Exception as e:
        logger.error(f"AI Analysis Error: {e}")
        return f"Error connecting to AI Node: {str(e)}"

# --- ENDPOINT 2: LEGAL DRAFTER ---
def generate_legal_doc(case_id, facts):
    try:
        client = get_ai_client()
        
        # Matches the inputs in your HF Space app.py
        json_str = client.predict(
            case_no=case_id,
            user_instruction=facts, 
            api_name="/draft_legal_json"
        )
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
