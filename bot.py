import discord
from discord.ext import commands

from config import TOKEN
from database.schema import create_tables
from cogs.registration_scheduler import RegistrationScheduler


class GenraBot(commands.Bot):

    def __init__(self):
        intents = discord.Intents.default()

        super().__init__(
            command_prefix="!",
            intents=intents
        )

    async def setup_hook(self):
        create_tables()

        await self.add_cog(
            RegistrationScheduler(self)
        )

        synced = await self.tree.sync()

        print(f"Synced {len(synced)} slash commands")


bot = GenraBot()


@bot.event
async def on_ready():
    print("--------------------------------")
    print(f"Bot logged in as {bot.user}")
    print(f"Bot ID: {bot.user.id}")
    print("--------------------------------")


bot.run(TOKEN)
