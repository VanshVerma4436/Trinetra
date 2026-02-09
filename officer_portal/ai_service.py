from gradio_client import Client, handle_file
import os
import logging
import json

logger = logging.getLogger(__name__)

# CONFIGURATION
HF_TOKEN = os.getenv("HF_API_TOKEN")
SPACE_URL = os.getenv("TRINETRA_AI_NODE", "https://vverma4436-legal-log-engine.hf.space/")

def get_ai_client():
    if not HF_TOKEN:
         logger.error("HF_API_TOKEN is missing in .env")
         raise ValueError("HF_API_TOKEN not configured.")
    
    try:
        # Try passing token explicitly (newer versions)
        return Client(SPACE_URL, hf_token=HF_TOKEN)
    except TypeError:
        # Fallback for older versions or different signature
        logger.warning("Client does not accept hf_token, trying with headers or plain connection.")
        return Client(SPACE_URL, headers={"Authorization": f"Bearer {HF_TOKEN}"})
    except Exception as e:
        logger.error(f"Failed to connect to AI Client: {e}")
        raise e

# --- API Endpoint 1: Case Manager ---
def fetch_or_create_case(case_id, justification=None):
    """
    Goal: Initialize a case or retrieve its history.
    """
    try:
        client = get_ai_client()
        logger.info(f"Fetching/Creating case: {case_id}")
        
        # [FIX] Re-added 'justification'. API requires it.
        result = client.predict(
            case_no=case_id,
            justification=justification or "Routine AI initialization",
            api_name="/fetch_or_create_case"
        )
        return result
    except Exception as e:
        logger.error(f"AI Node Error (Case Status): {e}")
        return f"Error connecting to AI Node: {e}"

# --- API Endpoint 2: Security Analyst ---
def analyze_logs(case_id, question, log_file_path=None):
    try:
        client = get_ai_client()
        
        file_input = None
        if log_file_path:
            # handle_file prepares the file for upload
            file_input = handle_file(log_file_path)
        
        logger.info(f"Analyzing logs for case {case_id}. Question: {question}")
        
        result = client.predict(
            case_no=case_id,
            file_obj=file_input,
            user_q=question,
            api_name="/analyze_logs"
        )
        return result
    except Exception as e:
        logger.error(f"AI Node Error (Analyze): {e}")
        return f"Error during analysis: {e}"

# --- API Endpoint 3: Legal Drafter ---
def generate_legal_doc(case_id, facts):
    try:
        client = get_ai_client()
        logger.info(f"Generating legal doc for case {case_id}")
        
        json_str = client.predict(
            case_no=case_id,
            user_instruction=facts,
            api_name="/draft_legal_json"
        )
        # Parse the JSON string returned by the AI
        return json.loads(json_str)
    except Exception as e:
        logger.error(f"AI Node Error (Legal Doc): {e}")
        return {"error": str(e)}
