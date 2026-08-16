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


class Teams(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(
        name="team",
        description="Register a team"
    )
    @discord.app_commands.describe(
        team_name="Name of the team",
        pack="Choose the package"
    )
    async def team(
        self,
        interaction: discord.Interaction,
        team_name: str,
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

        if not cursor.fetchone():

            connection.close()

            await interaction.response.send_message(
                "Invalid package. Use CLASH, EMPIRE or TRAINING.",
                ephemeral=True
            )

            return

        cursor.execute(
            """
            SELECT id
            FROM teams
            WHERE team_name = ?
            AND pack = ?
            """,
            (
                team_name,
                pack
            )
        )

        if cursor.fetchone():

            connection.close()

            await interaction.response.send_message(
                "This team is already registered for this package.",
                ephemeral=True
            )

            return

        cursor.execute(
            """
            INSERT INTO teams (
                team_name,
                discord_id,
                pack
            )
            VALUES (?, ?, ?)
            """,
            (
                team_name,
                interaction.user.id,
                pack
            )
        )

        connection.commit()
        connection.close()

        await interaction.response.send_message(
            f"Team **{team_name}** registered successfully for **{pack}**."
        )

    @discord.app_commands.command(
        name="teams",
        description="Show registered teams"
    )
    @discord.app_commands.describe(
        pack="Choose a package"
    )
    async def teams(
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
            """
            SELECT team_name
            FROM teams
            WHERE pack = ?
            ORDER BY id
            """,
            (pack,)
        )

        teams = cursor.fetchall()

        connection.close()

        if not teams:

            await interaction.response.send_message(
                f"No teams registered for **{pack}**.",
                ephemeral=True
            )

            return

        team_list = "\n".join(
            f"{index}. {team[0]}"
            for index, team in enumerate(
                teams,
                start=1
            )
        )

        embed = discord.Embed(
            title=f"{pack} TEAMS",
            description=team_list,
            color=discord.Color.green()
        )

        await interaction.response.send_message(
            embed=embed
        )


async def setup(bot):
    await bot.add_cog(
        Teams(bot)
    )
