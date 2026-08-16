import os
import threading

from flask import Flask

import discord
from discord.ext import commands

from dotenv import load_dotenv

from database.schema import create_tables


# =========================
# ENVIRONMENT
# =========================

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise ValueError("DISCORD_TOKEN is missing from environment variables")


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
    port = int(os.getenv("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
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

    print(
        f"Logged in as {bot.user} "
        f"(ID: {bot.user.id})"
    )

    print(
        f"Connected to {len(bot.guilds)} server(s)"
    )

    try:
        synced = await bot.tree.sync()

        print(
            f"Synced {len(synced)} slash command(s)"
        )

    except Exception as error:
        print(
            f"Slash command sync error: {error}"
        )


# =========================
# LOAD COGS
# =========================

async def load_cogs():

    try:
        await bot.load_extension(
            "cogs.registration_scheduler"
        )

        print(
            "Loaded: registration_scheduler"
        )

    except Exception as error:

        print(
            f"Failed to load registration_scheduler: "
            f"{error}"
        )


# =========================
# STARTUP
# =========================

async def main():

    create_tables()

    await load_cogs()

    await bot.start(TOKEN)


if __name__ == "__main__":

    # Start Flask in a separate thread
    web_thread = threading.Thread(
        target=run_web_server,
        daemon=True
    )

    web_thread.start()

    # Start Discord bot
    import asyncio

    asyncio.run(main())
