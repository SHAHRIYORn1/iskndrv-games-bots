import os
from dotenv import load_dotenv

load_dotenv()

# Bot Tokenlari
ADMIN_BOT_TOKEN = "9167217199:AAELhmBOOz92LN3esmYBsSsH8lke7x6NlTQ"
USER_BOT_TOKEN = "9018347209:AAFn36Yy8CkpA2GpsD0MfvRD8e5RkPSLq38"

# Baza fayli
DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")

# Dastlabki admin paroli (Admin botga birinchi kirganda adminga aylanishingiz uchun)
# Shuningdek birinchi kirgan odam avtomatik yoki /setadmin komandasi orqali admin bo'ladi
ADMIN_SECRET_KEY = "admin777"
