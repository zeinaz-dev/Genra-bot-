import os
from threading import Thread

from flask import Flask

import discord
from discord.ext import commands

from config import TOKEN


# =========================
# WEB SERVER
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
# STAFF ROLE IDS
# =========================

STAFF_ROLE_IDS = {
    1392127614285643816,
    1392127615300538468,
    1392127618815627466,
    1392127620166193192,
    1392127621420027956,
    1392127622430986392
}


# =========================
# DISCORD
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
# STAFF CHECK
# =========================

def is_staff(member):

    for role in member.roles:

        if role.id in STAFF_ROLE_IDS:
            return True

    return False


# =========================
# READY
# =========================

@bot.event
async def on_ready():

    print("================================")
    print("GENRA BOT STARTING")
    print("================================")

    print(f"Logged in as: {bot.user}")
    print(f"Bot ID: {bot.user.id}")

    print("Staff roles:")

    for role_id in STAFF_ROLE_IDS:
        print(role_id)

    try:

        synced = await bot.tree.sync()

        print(
            f"Synced {len(synced)} slash commands"
        )

    except Exception as error:

        print(
            f"Slash command sync error: {error}"
        )

    print("Genra Bot is Online!")
    print("================================")


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

    if not is_staff(
        interaction.user
    ):

        await interaction.response.send_message(
            "❌ Staff only.",
            ephemeral=True
        )

        return

    latency = round(
        bot.latency * 1000
    )

    await interaction.response.send_message(
        f"🏓 Pong! {latency}ms"
    )


# =========================
# MY ROLES
# =========================

@bot.tree.command(
    name="myroles",
    description="Check your roles"
)
async def myroles(
    interaction: discord.Interaction
):

    role_ids = [
        role.id
        for role in interaction.user.roles
    ]

    staff = is_staff(
        interaction.user
    )

    text = (
        "**Your role IDs:**\n"
        + "\n".join(
            str(role_id)
            for role_id in role_ids
        )
        + "\n\n"
        f"**Staff detected:** {staff}"
    )

    await interaction.response.send_message(
        text,
        ephemeral=True
    )


# =========================
# START
# =========================

if __name__ == "__main__":

    web_thread = Thread(
        target=run_web,
        daemon=True
    )

    web_thread.start()

    bot.run(TOKEN)
