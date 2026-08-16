import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise ValueError("DISCORD_TOKEN is missing from .env")

STAFF_ROLE_IDS = [
    int(x.strip())
    for x in os.getenv("STAFF_ROLE_IDS", "").split(",")
    if x.strip()
]

CLASH_ROLE_ID = int(os.getenv("CLASH_ROLE_ID", "0"))
EMPIRE_ROLE_ID = int(os.getenv("EMPIRE_ROLE_ID", "0"))
TRAINING_ROLE_ID = int(os.getenv("TRAINING_ROLE_ID", "0"))
