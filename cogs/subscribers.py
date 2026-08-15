import discord
from discord.ext import commands
import sqlite3
from database.schema import DATABASE


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
        pack = pack.upper()

        connection = sqlite3.connect(DATABASE)
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
            WHERE discord_id = ? AND pack = ?
            """,
            (interaction.user.id, pack)
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
        connection = sqlite3.connect(DATABASE)
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
    await bot.add_cog(Subscribers(bot))
