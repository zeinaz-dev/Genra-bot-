import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise ValueError("DISCORD_TOKEN is missing from .env or Render Environment Variables")

STAFF_ROLE_IDS = []

staff_roles = os.getenv("STAFF_ROLE_IDS", "")

if staff_roles:
    for role_id in staff_roles.split(","):
        role_id = role_id.strip()

        if role_id.isdigit():
            STAFF_ROLE_IDS.append(int(role_id))
