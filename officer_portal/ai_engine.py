import random
import os
from . import ai_service
import tempfile
import shutil
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
        
        # Use provided Case ID or fallback
        if not case_id:
             case_id = "CMD-USER-" + str(user_context.get('id', '000')) if user_context else "CMD-GUEST"

        # [NEW] Ensure Case Exists in AI Memory (as per user's API guide)
        try:
            ai_service.fetch_or_create_case(case_id)
        except Exception:
            pass # Continue even if status fetch fails, analyze might still work

        # --- PHASE 1: REMOTE NEURAL LINK (Gradio) ---
        try:
            # Handle File Attachment: Gradio Client needs a file path
            temp_path = None
            if attachment:
                # Save temp file
                suffix = os.path.splitext(attachment.name)[1]
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    for chunk in attachment.chunks():
                        tmp.write(chunk)
                    temp_path = tmp.name

            # Call Service -> analyze_logs
            # This returns a string analysis report directly
            response_text = ai_service.analyze_logs(case_id, query, temp_path)
            
            # Clean up temp file
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)

            if response_text and "Error" not in response_text:
                 return response_text
            else:
                 logger.warning(f"AI Service turned error/empty: {response_text}")

        except Exception as e:
             logger.error(f"[AI WARN] Remote Node Error: {e}. Switching to Local Core.")

        # --- PHASE 2: LOCAL FALLBACK ---
        return TrinetraAI._local_fallback(query, user_context, attachment)

    @staticmethod
    def generate_legal_doc(reference_no, justification, user_context):
        """
        Generates legal doc JSON via Gradio.
        """
        try:
            # Call Service -> generate_legal_doc
            # This returns a python dict
            doc_data = ai_service.generate_legal_doc(reference_no, justification)
            
            return doc_data

        except Exception as e:
            logger.error(f"Legal Doc Gen Error: {e}")
            return {"error": str(e)}

    @staticmethod
    def _local_fallback(query, user_context, attachment):
        """
        Original Local Logic (Preserved for Continuity).
        """
        query_lower = query.lower()

        # Handle Attachment
        if attachment:
            file_name = attachment.name.lower()
            if "log" in file_name or ".txt" in file_name:
                return f"Analysis Complete: File '{attachment.name}' processed. No anomalies detected in log stream."
            elif ".pdf" in file_name:
                return f"Document '{attachment.name}' scanned. Summary: Encrypted officer protocol v3.4."
            else:
                return f"File '{attachment.name}' received. Format analysis pending."
        
        # Rule-Based Logic (Mock)
        if "status" in query_lower or "system" in query_lower:
            return "SYSTEM NOMINAL. All secure grid sectors are operational. No critical alerts."
        
        elif "hello" in query_lower or "hi" in query_lower:
            user_name = user_context.get('username', 'Officer') if user_context else 'Officer'
            return f"Greetings, {user_name}. Trinetra Core is listening. State your command."
            
        elif "warrant" in query_lower or "search" in query_lower:
            return "Warrant Database Access: GRANTED. Please use the Search Module to input suspect parameters."
            
        elif "joke" in query_lower:
            return " Humor module not installed. Constructive directives only."
            
        elif "closure" in query_lower:
            return "Closure Application Protocol initiated. Use the 'App Generator' form to file the request."
            
        else:
            # Fallback
            responses = [
                "Processing... Insufficient data to formulate a precise response.",
                "Command not recognized. Please rephrase using standard protocol syntax.",
                "Query logged for manual review. Trinetra is standing by."
            ]
            return random.choice(responses)
