import discord
from discord.ext import commands
import sqlite3

from database.schema import DATABASE


STAFF_ROLE_IDS = {
    1392127614285643816,
    1392127615300538468,
    1392127618815627466,
    1392127620166193192,
    1392127621420027956,
    1392127622430986392
}


def is_staff(interaction: discord.Interaction):

    if not interaction.guild:
        return False

    member = interaction.guild.get_member(
        interaction.user.id
    )

    if member is None:
        return False

    return any(
        role.id in STAFF_ROLE_IDS
        for role in member.roles
    )


class Subscribers(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(
        name="subscribe",
        description="Register yourself as a Genra subscriber"
    )
    @discord.app_commands.describe(
        pack="Choose your package"
    )
    async def subscribe(
        self,
        interaction: discord.Interaction,
        pack: str
    ):

        if not is_staff(interaction):
            await interaction.response.send_message(
                "❌ Staff only.",
                ephemeral=True
            )
            return

        pack = pack.upper()

        connection = sqlite3.connect(
            DATABASE
        )

        cursor = connection.cursor()

        cursor.execute(
            "SELECT name FROM packs WHERE name = ?",
            (pack,)
        )

        result = cursor.fetchone()

        if not result:

            connection.close()

            await interaction.response.send_message(
                "Invalid package. Use CLASH, EMPIRE or TRAINING.",
                ephemeral=True
            )

            return

        cursor.execute(
            """
            SELECT id
            FROM subscribers
            WHERE discord_id = ?
            AND pack = ?
            """,
            (
                interaction.user.id,
                pack
            )
        )

        if cursor.fetchone():

            connection.close()

            await interaction.response.send_message(
                "You are already subscribed to this package.",
                ephemeral=True
            )

            return

        cursor.execute(
            """
            INSERT INTO subscribers (
                discord_id,
                username,
                pack
            )
            VALUES (?, ?, ?)
            """,
            (
                interaction.user.id,
                str(interaction.user),
                pack
            )
        )

        connection.commit()
        connection.close()

        await interaction.response.send_message(
            f"Subscription confirmed for **{pack}**.",
            ephemeral=True
        )

    @discord.app_commands.command(
        name="subscribers",
        description="Show subscriber count"
    )
    async def subscribers(
        self,
        interaction: discord.Interaction
    ):

        if not is_staff(interaction):
            await interaction.response.send_message(
                "❌ Staff only.",
                ephemeral=True
            )
            return

        connection = sqlite3.connect(
            DATABASE
        )

        cursor = connection.cursor()

        cursor.execute(
            "SELECT COUNT(*) FROM subscribers"
        )

        count = cursor.fetchone()[0]

        connection.close()

        await interaction.response.send_message(
            f"Total subscribers: **{count}**"
        )


async def setup(bot):
    await bot.add_cog(
        Subscribers(bot)
    )
