import os
from threading import Thread

from flask import Flask

import discord
from discord.ext import commands

from config import TOKEN
from database.schema import create_tables


# =========================
# CONFIG
# =========================

GUILD_ID = 1142434590980571217


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


# =========================
# BOT
# =========================

class GenraBot(commands.Bot):

    async def setup_hook(self):

        print("")
        print("================================")
        print("GENRA BOT SETUP START")
        print("================================")

        # =========================
        # DATABASE
        # =========================

        print("[1/3] Initializing database...")

        try:
            await create_tables()
            print("[OK] Database ready.")

        except Exception as error:
            print("[ERROR] Database initialization failed:")
            print(repr(error))

        # =========================
        # LOAD COGS
        # =========================

        print("")
        print("[2/3] Loading Cogs...")

        cogs = [
            "cogs.packs",
            "cogs.scheduler"
        ]

        for cog in cogs:

            try:
                await self.load_extension(cog)

                print(f"[OK] Loaded: {cog}")

            except Exception as error:

                print(f"[ERROR] Failed to load: {cog}")
                print(f"[ERROR] {type(error).__name__}: {error}")

        # =========================
        # COMMAND LIST
        # =========================

        print("")
        print("Commands currently registered:")

        for command in self.tree.get_commands():

            print(f" - /{command.name}")

        # =========================
        # GUILD SYNC
        # =========================

        print("")
        print("[3/3] Synchronizing commands...")

        try:

            guild = discord.Object(
                id=GUILD_ID
            )

            synced = await self.tree.sync(
                guild=guild
            )

            print(
                f"[OK] Synced {len(synced)} commands "
                f"to guild {GUILD_ID}"
            )

            for command in synced:

                print(
                    f"[OK] Discord command: /{command.name}"
                )

        except Exception as error:

            print("[ERROR] Command synchronization failed:")
            print(f"[ERROR] {type(error).__name__}: {error}")

        print("")
        print("================================")
        print("GENRA BOT SETUP FINISHED")
        print("================================")
        print("")


# =========================
# CREATE BOT
# =========================

bot = GenraBot(
    command_prefix="!",
    intents=intents
)


# =========================
# BOT READY
# =========================

@bot.event
async def on_ready():

    print("")
    print("================================")
    print("GENRA BOT ONLINE")
    print("================================")

    print(f"Bot: {bot.user}")
    print(f"Bot ID: {bot.user.id}")

    guild = bot.get_guild(GUILD_ID)

    if guild:

        print(f"Guild: {guild.name}")
        print(f"Guild ID: {guild.id}")

    else:

        print(
            f"[WARNING] Guild {GUILD_ID} was not found."
        )

    print("")
    print("Available slash commands:")

    for command in bot.tree.get_commands():

        print(f" - /{command.name}")

    print("")
    print("GENRA BOT IS READY")
    print("================================")
    print("")


# =========================
# PING
# =========================

@bot.tree.command(
    name="ping",
    description="Check bot latency",
    guild=discord.Object(id=GUILD_ID)
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
# START
# =========================

if __name__ == "__main__":

    print("STARTING GENRA BOT")

    web_thread = Thread(
        target=run_web,
        daemon=True
    )

    web_thread.start()

    bot.run(TOKEN)
