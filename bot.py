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
    app.run(host="0.0.0.0", port=port)


# =========================
# DISCORD BOT
# =========================

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


async def load_cogs():
    await bot.load_extension("cogs.packs")
    await bot.load_extension("cogs.subscribers")
    await bot.load_extension("cogs.teams")


@bot.event
async def setup_hook():
    await create_tables()
    await load_cogs()


@bot.event
async def on_ready():
    print(f"Logged in as: {bot.user}")
    print(f"Bot ID: {bot.user.id}")

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"Sync Error: {e}")

    print("Genra Bot is Online!")


# =========================
# PING COMMAND
# =========================

@bot.tree.command(
    name="ping",
    description="Check bot latency"
)
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)

    await interaction.response.send_message(
        f"Pong! {latency}ms"
    )


# =========================
# SETUP COMMAND
# =========================

@bot.tree.command(
    name="setup",
    description="Genra Bot setup check"
)
async def setup(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Genra Bot Setup",
        description="Bot is working correctly.",
        color=discord.Color.green()
    )

    embed.add_field(
        name="Commands",
        value="Slash Commands Enabled",
        inline=False
    )

    embed.add_field(
        name="Database",
        value="SQLite Connected",
        inline=False
    )

    embed.add_field(
        name="Version",
        value="Phase 1",
        inline=False
    )

    await interaction.response.send_message(
        embed=embed
    )


# =========================
# START
# =========================

if __name__ == "__main__":
    web_thread = Thread(target=run_web)
    web_thread.daemon = True
    web_thread.start()

    bot.run(TOKEN)



