import sqlite3

import discord
from discord import app_commands
from discord.ext import commands

from database.schema import DATABASE
from utils.permissions import (
    STAFF_ROLE_IDS,
    PACKAGE_ROLES
)


class Subscribers(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="subscribers",
        description="Show Genra subscribers"
    )
    async def subscribers(
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

        embed = discord.Embed(
            title="GENRA SUBSCRIBERS",
            color=discord.Color.blue()
        )

        for package, role_id in PACKAGE_ROLES.items():

            role = interaction.guild.get_role(
                role_id
            )

            if role is None:
                continue

            members = role.members

            lines = []

            for member in members:
                lines.append(
                    member.mention
                )

                cursor.execute(
                    """
                    INSERT OR IGNORE INTO role_history
                    (
                        discord_id,
                        role_id,
                        package
                    )
                    VALUES (?, ?, ?)
                    """,
                    (
                        member.id,
                        role_id,
                        package
                    )
                )

            if not lines:
                lines.append(
                    "No subscribers."
                )

            embed.add_field(
                name=f"{package} — {len(members)}",
                value="\n".join(lines),
                inline=False
            )

        connection.commit()
        connection.close()

        await interaction.response.send_message(
            embed=embed
        )


async def setup(bot):
    await bot.add_cog(Subscribers(bot))
