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


def is_staff_member(member):
    return any(
        role.id in STAFF_ROLE_IDS
        for role in member.roles
    )


def get_registration_info(channel_id):
    for package, groups in REGISTRATION_CHANNELS.items():
        for group_name, channel_id_value in groups.items():
            if channel_id == channel_id_value:
                return package, group_name

    return None, None


def has_package_role(member, package):
    required_role_id = PACKAGE_ROLES[package]

    return any(
        role.id == required_role_id
        for role in member.roles
    )


@bot.event
async def setup_hook():
    await create_tables()
    await load_cogs()

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands")
    except Exception as error:
        print(f"Sync Error: {error}")


@bot.event
async def on_ready():
    print(f"Logged in as: {bot.user}")
    print(f"Bot ID: {bot.user.id}")
    print("Genra Bot is Online!")


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

    # Staff messages are ignored by the registration system.
    if is_staff_member(message.author):
        return

    # The member must have the package role.
    if not has_package_role(
        message.author,
        package
    ):
        return

    team_name = message.content.strip()

    if not team_name:
        return

    # Only the team name should be written.
    if len(team_name) > 50:
        await message.add_reaction("❌")
        return

    connection = sqlite3.connect(DATABASE)
    cursor = connection.cursor()

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

        await message.add_reaction("❌")
        return

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

    # Slots 3 to 22 = maximum 20 teams.
    if team_count >= 20:
        connection.close()

        await message.add_reaction("❌")
        return

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

    await message.add_reaction("✅")


@bot.event
async def on_message_delete(message):

    if message.author.bot:
        return

    connection = sqlite3.connect(DATABASE)
    cursor = connection.cursor()

    cursor.execute(
        """
        DELETE FROM teams
        WHERE message_id = ?
        """,
        (message.id,)
    )

    connection.commit()
    connection.close()


@bot.event
async def on_member_update(before, after):

    connection = sqlite3.connect(DATABASE)
    cursor = connection.cursor()

    for package, role_id in PACKAGE_ROLES.items():

        had_role = any(
            role.id == role_id
            for role in before.roles
        )

        has_role = any(
            role.id == role_id
            for role in after.roles
        )

        if has_role and not had_role:

            cursor.execute(
                """
                INSERT OR IGNORE INTO role_history (
                    discord_id,
                    role_id,
                    package
                )
                VALUES (?, ?, ?)
                """,
                (
                    after.id,
                    role_id,
                    package
                )
            )

    connection.commit()
    connection.close()


@bot.tree.command(
    name="setup",
    description="Genra Bot setup check"
)
async def setup_command(
    interaction: discord.Interaction
):

    if not is_staff_member(interaction.user):
        await interaction.response.send_message(
            "❌ You do not have permission to use this command.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="Genra Bot Setup",
        description="Bot is working correctly.",
        color=discord.Color.green()
    )

    embed.add_field(
        name="Commands",
        value="Staff Commands Enabled",
        inline=False
    )

    embed.add_field(
        name="Database",
        value="SQLite Connected",
        inline=False
    )

    embed.add_field(
        name="Registration",
        value="Automatic registration enabled",
        inline=False
    )

    await interaction.response.send_message(
        embed=embed
    )


@bot.tree.command(
    name="ping",
    description="Check bot latency"
)
async def ping(
    interaction: discord.Interaction
):

    if not is_staff_member(interaction.user):
        await interaction.response.send_message(
            "❌ You do not have permission to use this command.",
            ephemeral=True
        )
        return

    latency = round(
        bot.latency * 1000
    )

    await interaction.response.send_message(
        f"Pong! {latency}ms"
    )


if __name__ == "__main__":

    web_thread = Thread(
        target=run_web,
        daemon=True
    )

    web_thread.start()

    bot.run(TOKEN)
