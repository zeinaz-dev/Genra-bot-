import os
import sqlite3
from threading import Thread

from flask import Flask
import discord
from discord.ext import commands

from config import TOKEN
from database.schema import DATABASE, create_tables
from utils.permissions import (
    STAFF_ROLE_IDS,
    PACKAGE_ROLES,
    REGISTRATION_CHANNELS
)


# =========================
# WEB SERVER FOR RENDER
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

intents.message_content = True
intents.guilds = True
intents.members = True


bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# =========================
# STAFF CHECK
# =========================

def is_staff_member(member):

    role_ids = {
        role.id
        for role in member.roles
    }

    return bool(
        role_ids.intersection(
            STAFF_ROLE_IDS
        )
    )


# =========================
# REGISTRATION CHANNEL
# =========================

def get_registration_info(channel_id):

    for package, groups in REGISTRATION_CHANNELS.items():

        for group_name, registered_channel_id in groups.items():

            if channel_id == registered_channel_id:
                return package, group_name

    return None, None


# =========================
# PACKAGE ROLE CHECK
# =========================

def has_package_role(member, package):

    required_role_id = PACKAGE_ROLES[package]

    return any(
        role.id == required_role_id
        for role in member.roles
    )


# =========================
# LOAD COGS
# =========================

async def load_cogs():

    await bot.load_extension(
        "cogs.packs"
    )

    await bot.load_extension(
        "cogs.subscribers"
    )

    await bot.load_extension(
        "cogs.teams"
    )


# =========================
# BOT SETUP
# =========================

@bot.event
async def setup_hook():

    await create_tables()

    await load_cogs()

    try:

        synced = await bot.tree.sync()

        print(
            f"Synced {len(synced)} slash commands"
        )

    except Exception as error:

        print(
            f"Sync Error: {error}"
        )


# =========================
# BOT READY
# =========================

@bot.event
async def on_ready():

    print(
        f"Logged in as: {bot.user}"
    )

    print(
        f"Bot ID: {bot.user.id}"
    )

    print(
        "Genra Bot is Online!"
    )


# =========================
# AUTOMATIC REGISTRATION
# =========================

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    if not message.guild:
        return

    package, group_name = get_registration_info(
        message.channel.id
    )

    if package is None:
        return

    # Staff messages are ignored.
    if is_staff_member(
        message.author
    ):
        return

    # User needs the correct package role.
    if not has_package_role(
        message.author,
        package
    ):
        return

    team_name = message.content.strip()

    if not team_name:
        return

    # Team name maximum length.
    if len(team_name) > 50:

        await message.add_reaction(
            "❌"
        )

        return

    connection = sqlite3.connect(
        DATABASE
    )

    cursor = connection.cursor()

    # Check duplicate team in
    # the same package and group.
    cursor.execute(
        """
        SELECT id
        FROM teams
        WHERE LOWER(team_name) = LOWER(?)
        AND pack = ?
        AND group_name = ?
        """,
        (
            team_name,
            package,
            group_name
        )
    )

    existing_team = cursor.fetchone()

    if existing_team:

        connection.close()

        await message.add_reaction(
            "❌"
        )

        return

    # Count registered teams.
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM teams
        WHERE pack = ?
        AND group_name = ?
        """,
        (
            package,
            group_name
        )
    )

    team_count = cursor.fetchone()[0]

    # Maximum 20 teams.
    # Slots are displayed from 3 to 22.
    if team_count >= 20:

        connection.close()

        await message.add_reaction(
            "❌"
        )

        return

    # Save registration.
    cursor.execute(
        """
        INSERT INTO teams (
            team_name,
            discord_id,
            pack,
            group_name,
            message_id,
            channel_id,
            username
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            team_name,
            message.author.id,
            package,
            group_name,
            message.id,
            message.channel.id,
            str(message.author)
        )
    )

    connection.commit()

    connection.close()

    # Successful registration.
    await message.add_reaction(
        "✅"
    )


# =========================
# DELETE
