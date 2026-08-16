import sqlite3

import discord
from discord import app_commands
from discord.ext import commands

from database.schema import DATABASE
from utils.permissions import STAFF_ROLE_IDS


class Packs(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="packs",
        description="Show Genra packages"
    )
    async def packs(
        self,
        interaction: discord.Interaction
    ):

        if not any(
            role.id in STAFF_ROLE_IDS
            for role in interaction.user.roles
        ):
            await interaction.response.send_message(
                "❌ Staff only.",
                ephemeral=True
            )
            return

        connection = sqlite3.connect(DATABASE)
        cursor = connection.cursor()

        cursor.execute(
            "SELECT name, price FROM packs"
        )

        packs = cursor.fetchall()

        connection.close()

        embed = discord.Embed(
            title="GENRA AGENCY PACKAGES",
            color=discord.Color.blue()
        )

        for name, price in packs:
            embed.add_field(
                name=name,
                value=f"Price: ${price:.2f}",
                inline=False
            )

        await interaction.response.send_message(
            embed=embed
        )


async def setup(bot):
    await bot.add_cog(Packs(bot))
