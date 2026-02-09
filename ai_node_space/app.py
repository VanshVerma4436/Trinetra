import gradio as gr
import json
import time
import os

# --- LOGIC 1: UNIVERSAL FILE ANALYZER ---
def process_file(file_obj, user_question):
    """
    Smart Analyzer: Detects file type and acts accordingly.
    """
    content_preview = ""
    ai_answer = ""
    
    if file_obj is None:
        return "Error: No file received.", {"error": "No file"}

    try:
        # 1. DETECT FILE TYPE
        filename = file_obj.name.lower()
        file_ext = os.path.splitext(filename)[1]
        
        # 2. READ CONTENT (Text-based)
        # Note: For PDFs/Images, you would need specific libraries (PyPDF2, PIL)
        with open(file_obj.name, 'r', errors='ignore') as f:
            file_content = f.read()
            content_preview = file_content[:500] # Preview for debug
            
        # 3. SELECT THE "PERSONA" (Dynamic Prompting)
        if file_ext in ['.log', '.csv', '.out']:
            system_role = "Security Analyst"
            task = "Scan these logs for IP anomalies, errors, and security breaches."
            context = f"File Type: SERVER LOGS\nUser Question: {user_question}"
            
        elif file_ext in ['.py', '.js', '.java', '.html']:
            system_role = "Senior Code Reviewer"
            task = "Analyze this code for bugs, security vulnerabilities, and logic errors."
            context = f"File Type: SOURCE CODE\nUser Question: {user_question}"
            
        else:
            system_role = "Intelligence Officer"
            task = "Summarize this document and extract key entities."
            context = f"File Type: GENERAL DOCUMENT\nUser Question: {user_question}"

        # 4. AI GENERATION (Mocked for Demo - Replace with real LLM call)
        # In a real scenario, you would pass 'system_role', 'task', and 'file_content' to your LLM.
        
        # --- MOCK RESPONSE GENERATOR ---
        if "error" in user_question.lower() or "crash" in user_question.lower():
            ai_answer = f"[{system_role}] CRITICAL ALERT: Pattern matching indicates a severe failure. Immediate attention required."
        elif system_role == "Senior Code Reviewer":
            ai_answer = f"[{system_role}] Code Analysis: The syntax appears valid, but I recommend adding error handling around the file operations."
        else:
            ai_answer = f"[{system_role}] Analysis Complete. No immediate threats detected in the provided data. \n(Context: {user_question})"
        # -------------------------------

    except Exception as e:
        ai_answer = f"System Error processing file: {str(e)}"
        content_preview = "N/A"

    # 5. PREPARE DB DATA
    db_data = {
        "analysis_type": system_role,
        "timestamp": time.time(),
        "summary": ai_answer[:200],
        "file_preview": content_preview[:100]
    }
    
    return ai_answer, db_data

# --- LOGIC 2: LEGAL DRAFTING (Unchanged) ---
def draft_legal_doc(case_id, justification):
    # 1. AI GENERATION (Mocked)
    legal_text = f"The justification provided regarding '{justification}' has been reviewed. Authorized under Section 4 of the Trinetra Protocols."
    
    # 2. STRUCTURED RESPONSE
    # This matches the 'pdf_utils.py' expectations
    doc_structure = {
        "case_id": case_id,
        "title": "OFFICIAL LEGAL JUSTIFICATION",
        "facts": f"Justification provided: {justification}",
        "analysis": legal_text,
        "conclusion": "APPROVED PENDING SIGNATURE",
        "date": time.strftime("%d-%b-%Y")
    }
    return doc_structure

# --- THE INTERFACE ---
with gr.Blocks() as demo:
    
    with gr.Tab("Universal_Analyzer"):
        in_file = gr.File(label="Upload Log, Code, or Text")
        in_text = gr.Textbox(label="Your Question")
        out_text = gr.Textbox(label="AI Analysis")
        out_json = gr.JSON(label="Database Metadata")
        
        btn_logs = gr.Button("Analyze File")
        # API NAME must match what you call in Django
        btn_logs.click(process_file, inputs=[in_file, in_text], outputs=[out_text, out_json], api_name="analyze_logs")

    with gr.Tab("Legal_Drafter"):
        in_case = gr.Textbox()
        in_just = gr.Textbox()
        out_doc = gr.JSON()
        
        btn_legal = gr.Button("Draft")
        btn_legal.click(draft_legal_doc, inputs=[in_case, in_just], outputs=out_doc, api_name="draft_legal_json")

demo.queue(default_concurrency_limit=1)
demo.launch(server_name="0.0.0.0", server_port=7860)
