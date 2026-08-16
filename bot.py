import os
from threading import Thread

from flask import Flask

import discord
from discord.ext import commands

from config import TOKEN
from database.schema import create_tables


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

        print("===== SETUP HOOK STARTED =====")

        # =========================
        # DATABASE
        # =========================

        try:
            await create_tables()
            print("Database ready.")

        except Exception as error:
            print("Database error:")
            print(repr(error))

        # =========================
        # LOAD COGS
        # =========================

        cogs = [
            "cogs.packs",
            "cogs.subscribers",
            "cogs.teams",
            "cogs.scheduler"
        ]

        for cog in cogs:

            try:
                await self.load_extension(cog)

                print(
                    f"Loaded: {cog}"
                )

            except Exception as error:

                print(
                    f"FAILED: {cog}"
                )

                print(
                    repr(error)
                )

        # =========================
        # SYNC COMMANDS
        # =========================

        try:

            guild = discord.Object(
                id=GUILD_ID
            )

            synced = await self.tree.sync(
                guild=guild
            )

            print(
                f"Synced {len(synced)} commands "
                f"to server {GUILD_ID}"
            )

            for command in synced:

                print(
                    f"Command loaded: /{command.name}"
                )

        except Exception as error:

            print("GUILD SYNC ERROR:")
            print(repr(error))


# =========================
# CREATE BOT
# =========================

bot = GenraBot(
    command_prefix="!",
    intents=intents
)


# =========================
# READY
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
# START
# =========================

if __name__ == "__main__":

    web_thread = Thread(
        target=run_web,
        daemon
