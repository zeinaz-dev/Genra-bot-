import os
from threading import Thread

from flask import Flask

import discord
from discord.ext import commands

from config import TOKEN
from database.schema import create_tables


# =========================
# RENDER WEB SERVER
# =========================

app = Flask(__name__)


@app.route("/")
def home():
    return "Genra Bot is Online!"


def run_web():
    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
    )


# =========================
# DISCORD INTENTS
# =========================

intents = discord.Intents.default()

intents.guilds = True
intents.members = True
intents.message_content = True


bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# =========================
# LOAD COGS
# =========================

async def load_cogs():

    cogs = [
        "cogs.packs",
        "cogs.subscribers",
        "cogs.teams"
    ]

    for cog in cogs:

        try:
            await bot.load_extension(cog)
            print(f"Loaded: {cog}")

        except Exception as error:
            print(f"FAILED: {cog}")
            print(error)


# =========================
# BOT SETUP
# =========================

@bot.event
async def setup_hook():

    try:
        await create_tables()
        print("Database ready.")

    except Exception as error:
        print(f"Database error: {error}")

    await load_cogs()

    try:

        synced = await bot.tree.sync()

        print(
            f"Synced {len(synced)} slash commands."
        )

        for command in synced:
            print(
                f"Command loaded: /{command.name}"
            )

    except Exception as error:

        print(
            f"SYNC ERROR: {error}"
        )


# =========================
# BOT READY
# =========================

@bot.event
async def on_ready():

    print("==============================")
    print("GENRA BOT ONLINE")
    print("==============================")
    print(f"Logged in as: {bot.user}")
    print(f"Bot ID: {bot.user.id}")
    print("Genra Bot is ready!")
    print("==============================")


# =========================
# PING
# =========================

@bot.tree.command(
    name="ping",
    description="Check bot latency"
)
async def ping(
    interaction: discord.Interaction
):

    latency = round(
        bot.latency * 1000
    )

    await interaction.response.send_message(
        f"🏓 Pong! {latency}ms"
    )


# =========================
# START BOT
# =========================

if __name__ == "__main__":

    web_thread = Thread(
        target=run_web,
        daemon=True
    )

    web_thread.start()

    bot.run(TOKEN)
