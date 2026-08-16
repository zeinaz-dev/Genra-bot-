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


# =========================
# BOT CLASS
# =========================

class GenraBot(commands.Bot):

    async def setup_hook(self):

        print("================================")
        print("SETUP HOOK STARTED")
        print("================================")

        # =========================
        # DATABASE
        # =========================

        try:
            await create_tables()
            print("DATABASE: OK")

        except Exception as error:
            print("DATABASE ERROR:")
            print(type(error).__name__)
            print(repr(error))

        # =========================
        # LOAD COGS
        # =========================

        cogs = [
            "cogs.packs",
            "cogs.scheduler"
        ]

        for cog in cogs:

            print("--------------------------------")
            print(f"LOADING COG: {cog}")

            try:

                await self.load_extension(cog)

                print(f"COG LOADED SUCCESSFULLY: {cog}")

            except Exception as error:

                print(f"COG FAILED: {cog}")
                print(f"ERROR TYPE: {type(error).__name__}")
                print(f"ERROR: {repr(error)}")

        # =========================
        # SYNC COMMANDS
        # =========================

        print("--------------------------------")
        print("STARTING COMMAND SYNC")

        try:

            synced = await self.tree.sync()

            print(
                f"COMMANDS SYNCED: {len(synced)}"
            )

            for command in synced:

                print(
                    f"COMMAND: /{command.name}"
                )

        except Exception as error:

            print("COMMAND SYNC FAILED")
            print(
                f"ERROR TYPE: {type(error).__name__}"
            )
            print(
                f"ERROR: {repr(error)}"
            )

        print("================================")
        print("SETUP HOOK FINISHED")
        print("================================")


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

    print("================================")
    print("GENRA BOT ONLINE")
    print("================================")
    print(f"Logged in as: {bot.user}")
    print(f"Bot ID: {bot.user.id}")
    print("================================")


# =========================
# PING
# =========================
