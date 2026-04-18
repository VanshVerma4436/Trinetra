from django.apps import AppConfig
import threading
import time

def keep_ai_awake():
    # Ping every 12 hours (43200 seconds) to ensure the 48-hour sleep limit is never hit
    time.sleep(43200)
    from django.core.management import call_command
    while True:
        try:
            call_command('ping_ai')
        except Exception as e:
            print("Keep-alive ping failed:", e)
        time.sleep(43200)

class OfficerPortalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'officer_portal'

    def ready(self):
        # Start background ping thread as a daemon (stops when server stops)
        daemon_thread = threading.Thread(target=keep_ai_awake, daemon=True)
        daemon_thread.start()
