import os
import asyncio
import threading

from flask import Flask
from dotenv import load_dotenv

import discord
from discord.ext import commands

from database.schema import create_tables


load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise ValueError("DISCORD_TOKEN is missing")


# =========================
# FLASK
# =========================

app = Flask(__name__)


@app.route("/")
def home():
    return "Genra Bot is online!", 200


@app.route("/health")
def health():
    return "OK", 200


def run_web():
    port = int(os.getenv("PORT", "10000"))

    app.run(
        host="0.0.0.0",
        port=port,
        use_reloader=False,
    )


# =========================
# DISCORD INTENTS
# =========================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True


# =========================
# BOT
# =========================

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
)


# =========================
# PREFIX PING
# =========================

@bot.command(name="ping")
async def ping(ctx):

    latency = round(
        bot.latency * 1000
    )

    await ctx.send(
        f"🏓 Pong! `{latency}ms`"
    )


# =========================
# SLASH PING
# =========================

@bot.tree.command(
    name="ping",
    description="Check if the bot is online.",
)
async def slash_ping(
    interaction: discord.Interaction,
):

    latency = round(
        bot.latency * 1000
    )

    await interaction.response.send_message(
        f"🏓 Pong! `{latency}ms`",
        ephemeral=True,
    )


# =========================
# READY
# =========================

@bot.event
async def on_ready():

    print("--------------------------------")
    print(f"✅ Logged in as: {bot.user}")
    print(f"🆔 ID: {bot.user.id}")
    print(f"🌐 Servers: {len(bot.guilds)}")

    print("🔄 Syncing slash commands...")

    try:

        synced = await bot.tree.sync()

        print(
            f"✅ Synced {len(synced)} slash commands"
        )

        for command in synced:
            print(
                f"   /{command.name}"
            )

    except Exception as error:

        print(
            f"❌ Slash sync error: {error!r}"
        )

    print("--------------------------------")


# =========================
# LOAD COGS
# =========================

async def load_extensions():

    try:

        await bot.load_extension(
            "cogs.registration_scheduler"
        )

        print(
            "✅ registration_scheduler loaded"
        )

    except Exception as error:

        print(
            "❌ registration_scheduler ERROR:"
        )

        print(
            repr(error)
        )


# =========================
# START BOT
# =========================

async def start_bot():

    print("🗄️ Initializing database...")

    try:

        create_tables()

        print(
            "✅ Database initialized"
        )

    except Exception as error:

        print(
            f"❌ Database error: {error!r}"
        )

    print("📦 Loading extensions...")

    await load_extensions()

    print(
        "🔵 Connecting to Discord..."
    )

    await bot.start(TOKEN)


# =========================
# MAIN
# =========================

def main():

    web_thread = threading.Thread(
        target=run_web,
        daemon=True,
    )

    web_thread.start()

    print(
        "🌐 Flask server started"
    )

    try:

        asyncio.run(
            start_bot()
        )

    except KeyboardInterrupt:

        print(
            "🛑 Bot stopped."
        )

    except Exception as error:

        print(
            f"❌ Fatal error: {error!r}"
        )


if __name__ == "__main__":
    main()
