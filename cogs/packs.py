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


class Packs(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(
        name="packs",
        description="Show Genra packages"
    )
    async def packs(
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
            "SELECT name, price FROM packs"
        )

        packs = cursor.fetchall()

        connection.close()

        if not packs:
            await interaction.response.send_message(
                "No packs found.",
                ephemeral=True
            )
            return

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
    await bot.add_cog(
        Packs(bot)
    )
