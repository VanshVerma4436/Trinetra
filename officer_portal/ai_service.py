from gradio_client import Client, handle_file
import os
import logging
import json

logger = logging.getLogger(__name__)

# CONFIGURATION
HF_TOKEN = os.getenv("HF_API_TOKEN")
# Make sure this URL matches your space exactly
SPACE_URL = os.getenv("TRINETRA_AI_NODE", "https://vverma4436-legal-log-engine.hf.space/")

def get_ai_client():
    if not HF_TOKEN:
         logger.error("HF_API_TOKEN is missing in .env")
         raise ValueError("HF_API_TOKEN not configured.")
    
    try:
        # [FIX] Authenticate securely with hf_token
        return Client(SPACE_URL, hf_token=HF_TOKEN)
    except Exception as e:
        logger.error(f"Failed to connect to AI Client: {e}")
        raise e

def fetch_or_create_case(case_id):
    """
    Syncs the case ID with the Remote AI Node.
    """
    try:
        client = get_ai_client()
        # [FIX] Explicit keyword argument 'case_no' to match Space
        return client.predict(
            case_no=case_id,
            api_name="/fetch_or_create_case"
        )
    except Exception as e:
        logger.error(f"Case Sync Error: {e}")
        return "AI Node offline."

def analyze_logs(case_id, question, log_file_path=None):
    """
    Sends logs/questions to the Remote AI.
    """
    try:
        client = get_ai_client()
        
        file_input = None
        if log_file_path:
            file_input = handle_file(log_file_path)
        
        # [FIX] Explicit keyword arguments matching Remote App inputs
        result = client.predict(
            case_no=case_id,
            file_obj=file_input,
            user_q=question,
            api_name="/analyze_logs"
        )
        return result
    except Exception as e:
        logger.error(f"Analysis Error: {e}")
        return f"AI Connection Error: {str(e)}"

def generate_legal_doc(case_id, facts):
    """
    Generates JSON for legal documents.
    """
    try:
        client = get_ai_client()
        
        # [FIX] Key Update: Space expects 'user_instruction', not 'justification'
        json_str = client.predict(
            case_no=case_id,
            user_instruction=facts, 
            api_name="/draft_legal_json"
        )
        
        # Parse the returned string into a Dict
        return json.loads(json_str)
    except Exception as e:
        logger.error(f"Legal Doc Error: {e}")
        return {"error": str(e)}
