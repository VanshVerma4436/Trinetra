from django.core.management.base import BaseCommand
from gradio_client import Client
import os
import time

class Command(BaseCommand):
    help = 'Pings the AI Node to keep it awake'

    def handle(self, *args, **kwargs):
        SPACE_URL = os.getenv("TRINETRA_AI_NODE", "https://vverma4436-legal-log-engine.hf.space/")
        HF_TOKEN = os.getenv("HF_API_TOKEN")

        self.stdout.write(f"Pinging AI Node at {SPACE_URL}...")
        
        try:
            # Initialize Client
            client = Client(SPACE_URL, hf_token=HF_TOKEN)
            
            # Send a dummy request (using the fetch_or_create_case endpoint as it's lightweight)
            client.predict(
                case_no="KEEP-ALIVE-PING",
                justification="Routine maintenance ping",
                api_name="/fetch_or_create_case"
            )
            self.stdout.write(self.style.SUCCESS('Successfully pinged AI Node.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to ping AI Node: {e}'))
