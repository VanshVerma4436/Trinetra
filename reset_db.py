import os
import django
from dotenv import load_dotenv

def reset_db_and_create_admin():
    print("Loading environment variables from .env...")
    load_dotenv()
    print("Setting up Django environment...")
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()
    
    # Import models
    from officer_portal.models import Case, ChatMessage, Evidence, LegalDraft, AIUsageLog
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    print("Deleting all existing application data (row-level to prevent lock hangs)...")
    Evidence.objects.all().delete()
    ChatMessage.objects.all().delete()
    LegalDraft.objects.all().delete()
    AIUsageLog.objects.all().delete()
    Case.objects.all().delete()
    print("Application data deleted.")
    
    print("Deleting all non-admin users...")
    User.objects.exclude(username='admin').delete()
    print("Other users deleted.")
    
    print("Creating or updating admin user...")
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
        print("Admin user created successfully (username: admin, password: admin123).")
    else:
        print("User 'admin' already exists. Updating password...")
        admin = User.objects.get(username='admin')
        admin.set_password('admin123')
        admin.is_superuser = True
        admin.is_staff = True
        admin.save()
        print("Admin user password reset to 'admin123'.")
        
    print("Database reset complete.")

if __name__ == '__main__':
    reset_db_and_create_admin()
