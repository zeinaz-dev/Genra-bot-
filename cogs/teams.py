import sqlite3

import discord
from discord import app_commands
from discord.ext import commands

from database.schema import DATABASE
from utils.permissions import STAFF_ROLE_IDS


def is_staff(member):
    return any(
        role.id in STAFF_ROLE_IDS
        for role in member.roles
    )


class Teams(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def show_list(
        self,
        interaction,
        package,
        group
    ):

        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Staff only.",
                ephemeral=True
            )
            return

        connection = sqlite3.connect(DATABASE)
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT team_name
            FROM teams
            WHERE pack = ?
            AND group_name = ?
            ORDER BY id ASC
            LIMIT 20
            """,
            (
                package,
                group
            )
        )

        teams = cursor.fetchall()

        connection.close()

        if package == "CLASH":
            title = "GENRA CLASH SERIES"

        elif package == "EMPIRE":
            title = "EMPIRE SERIES"

        else:
            title = "TRAINING SERIES"

        lines = []

        for number, team in enumerate(
            teams,
            start=3
        ):
            lines.append(
                f"{number} - {team[0]}"
            )

        if not lines:
            lines.append(
                "No teams registered."
            )

        embed = discord.Embed(
            title=title,
            description="\n".join(lines),
            color=discord.Color.green()
        )

        embed.add_field(
            name="INFO",
            value=(
                "Date: Today\n"
                "3 Matches\n"
                "3 Same Tag or 0 Pts"
            ),
            inline=False
        )

        await interaction.response.send_message(
            embed=embed
        )

    @app_commands.command(
        name="teams_clash_a",
        description="Show Clash Group A"
    )
    async def clash_a(self, interaction):
        await self.show_list(
            interaction,
            "CLASH",
            "A"
        )

    @app_commands.command(
        name="teams_clash_b",
        description="Show Clash Group B"
    )
    async def clash_b(self, interaction):
        await self.show_list(
            interaction,
            "CLASH",
            "B"
        )

    @app_commands.command(
        name="teams_empire_a",
        description="Show Empire Group A"
    )
    async def empire_a(self, interaction):
        await self.show_list(
            interaction,
            "EMPIRE",
            "A"
        )

    @app_commands.command(
        name="teams_empire_b",
        description="Show Empire Group B"
    )
    async def empire_b(self, interaction):
        await self.show_list(
            interaction,
            "EMPIRE",
            "B"
        )

    @app_commands.command(
        name="teams_training_a",
        description="Show Training Group A"
    )
    async def training_a(self, interaction):
        await self.show_list(
            interaction,
            "TRAINING",
            "A"
        )

    @app_commands.command(
        name="teams_training_b",
        description="Show Training Group B"
    )
    async def training_b(self, interaction):
        await self.show_list(
            interaction,
            "TRAINING",
            "B"
        )


async def setup(bot):
    await bot.add_cog(Teams(bot))
