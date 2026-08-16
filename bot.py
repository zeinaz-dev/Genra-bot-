import os
import asyncio
import threading

from flask import Flask
from dotenv import load_dotenv

import discord
from discord.ext import commands

from database.schema import create_tables


# =========================
# CONFIG
# =========================

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise ValueError(
        "DISCORD_TOKEN is missing from environment variables."
    )


# =========================
# FLASK SERVER
# =========================

app = Flask(__name__)


@app.route("/")
def home():
    return "Genra Bot is online!", 200


@app.route("/health")
def health():
    return "OK", 200


def run_web_server():
    port = int(
        os.getenv("PORT", "10000")
    )

    app.run(
        host="0.0.0.0",
        port=port,
        use_reloader=False
    )


# =========================
# DISCORD BOT
# =========================

intents = discord.Intents.default()

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# =========================
# BOT READY
# =========================

@bot.event
async def on_ready():

    print("--------------------------------")
    print(f"✅ Logged in as: {bot.user}")
    print(f"✅ Bot ID: {bot.user.id}")
    print(f"✅ Servers: {len(bot.guilds)}")

    try:

        synced = await bot.tree.sync()

        print(
            f"✅ Slash commands synced: {len(synced)}"
        )

        for command in synced:
            print(
                f"   /{command.name}"
            )

    except Exception as error:

        print(
            "❌ Slash command sync failed:"
        )

        print(
            repr(error)
        )

    print("--------------------------------")


# =========================
# LOAD COGS
# =========================

async def load_cogs():

    try:

        await bot.load_extension(
            "cogs.registration_scheduler"
        )

        print(
            "✅ Loaded: registration_scheduler"
        )

    except Exception as error:

        print(
            "❌ Failed to load registration_scheduler:"
        )

        print(
            repr(error)
        )


# =========================
# START DISCORD
# =========================

async def start_discord():

    # Database
    try:

        create_tables()

        print(
            "✅ Database initialized"
        )

    except Exception as error:

        print(
            "❌ Database initialization failed:"
        )

        print(
            repr(error)
        )

    # Load cogs
    await load_cogs()

    print(
        "🔵 Connecting to Discord..."
    )

    try:

        await bot.start(TOKEN)

    except discord.LoginFailure:

        print(
            "❌ Discord login failed."
        )

        print(
            "Check your DISCORD_TOKEN."
        )

    except Exception as error:

        print(
            "❌ Discord connection error:"
        )

        print(
            repr(error)
        )


# =========================
# MAIN
# =========================

def main():

    # Start Flask in background
    web_thread = threading.Thread(
        target=run_web_server,
        daemon=True
    )

    web_thread.start()

    print(
        "🌐 Flask web server started."
    )

    # Start Discord
    try:

        asyncio.run(
            start_discord()
        )

    except KeyboardInterrupt:

        print(
            "Bot stopped."
        )

    except Exception as error:

        print(
            "❌ Fatal error:"
        )

        print(
            repr(error)
        )


if __name__ == "__main__":
    main()
