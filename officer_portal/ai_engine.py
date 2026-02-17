import random
import os
from . import ai_service
import tempfile
import logging

logger = logging.getLogger(__name__)

class TrinetraAI:
    """
    Hybrid AI Engine:
    Connects to Hugging Face Gradio Space via 'ai_service.py'.
    Falls back to simple local logic if connection fails.
    """
    
    @staticmethod
    def process_query(query, user_context=None, attachment=None, case_id=None):
        """
        Process the user's natural language query.
        """
        response_text = ""
        
        # 1. Determine Case ID
        if not case_id:
             case_id = "CMD-USER-" + str(user_context.get('id', '000')) if user_context else "CMD-GUEST"

        # 2. [SYNC] Ensure Case Exists in AI Memory (NeonDB)
        try:
            # We call this to create the table/row if missing
            ai_service.fetch_or_create_case(case_id)
        except Exception:
            # If sync fails (e.g. timeout), we proceed anyway. 
            # The analyze_logs endpoint creates the case automatically too.
            pass 

        # 3. [REMOTE] Analyze via Hugging Face
        try:
            temp_path = None
            if attachment:
                suffix = os.path.splitext(attachment.name)[1]
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    for chunk in attachment.chunks():
                        tmp.write(chunk)
                    temp_path = tmp.name

            # Call Service
            response_text = ai_service.analyze_logs(case_id, query, temp_path)
            
            # Cleanup
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)

            if response_text and "Error" not in response_text:
                 return response_text
            else:
                 logger.warning(f"AI Service error: {response_text}")

        except Exception as e:
             logger.error(f"[AI WARN] Remote Node Error: {e}. Switching to Local Core.")

        # 4. [FALLBACK] Local Logic
        return TrinetraAI._local_fallback(query, user_context, attachment)

    @staticmethod
    def _local_fallback(query, user_context, attachment):
    # Just a placeholder for the actual local fallback logic
    # In a real scenario, this would probably look up keywords or return canned responses
        return f"Local Fallback: I received '{query}' but cannot connect to the Neural Cloud."
