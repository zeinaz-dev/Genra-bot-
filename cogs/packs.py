import discord
from discord.ext import commands
import sqlite3
from database.schema import DATABASE


class Packs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @discord.app_commands.command(
        name="packs",
        description="Show Genra packages"
    )
    async def packs(self, interaction: discord.Interaction):
        connection = sqlite3.connect(DATABASE)
        cursor = connection.cursor()

        cursor.execute("SELECT name, price FROM packs")
        packs = cursor.fetchall()

        connection.close()

        if not packs:
            await interaction.response.send_message(
                "No packs found."
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

        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Packs(bot))
