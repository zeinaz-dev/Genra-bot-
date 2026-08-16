
import discord
from discord import app_commands
from discord.ext import commands, tasks

from datetime import datetime
from zoneinfo import ZoneInfo

from database.schema import (
    create_schedule,
    get_schedule,
    get_active_schedules,
    update_status,
    delete_schedule
)

from config import STAFF_ROLE_IDS


KSA = ZoneInfo("Asia/Riyadh")


def is_staff(member: discord.Member):

    if member.guild_permissions.administrator:
        return True

    if not STAFF_ROLE_IDS:
        return False

    return any(
        role.id in STAFF_ROLE_IDS
        for role in member.roles
    )


def format_datetime(dt):

    return dt.strftime("%d/%m/%Y %H:%M KSA")


class ScheduleSetupView(discord.ui.View):

    def __init__(self, cog):

        super().__init__(timeout=300)

        self.cog = cog

        self.channels = []
        self.role = None

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        placeholder="Select registration channels",
        min_values=1,
        max_values=25,
        channel_types=[
            discord.ChannelType.text
        ]
    )
    async def channel_select(
        self,
        interaction: discord.Interaction,
        select: discord.ui.ChannelSelect
    ):

        self.channels = select.values

        await interaction.response.send_message(
            f"Selected {len(self.channels)} channel(s).",
            ephemeral=True
        )

    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="Select the role to mention",
        min_values=1,
        max_values=1
    )
    async def role_select(
        self,
        interaction: discord.Interaction,
        select: discord.ui.RoleSelect
    ):

        self.role = select.values[0]

        await interaction.response.send_message(
            f"Selected role: {self.role.mention}",
            ephemeral=True
        )

    @discord.ui.button(
        label="Continue",
        style=discord.ButtonStyle.green
    )
    async def continue_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not self.channels:

            await interaction.response.send_message(
                "❌ Please select at least one registration channel.",
                ephemeral=True
            )

            return

        if not self.role:

            await interaction.response.send_message(
                "❌ Please select a role.",
                ephemeral=True
            )

            return

        modal = ScheduleModal(
            self.cog,
            self.channels,
            self.role
        )

        await interaction.response.send_modal(modal)


class ScheduleModal(discord.ui.Modal):

    def __init__(self, cog, channels, role):

        super().__init__(
            title="Create Registration Schedule"
        )

        self.cog = cog
        self.channels = channels
        self.role = role

    name = discord.ui.TextInput(
        label="Registration name",
        placeholder="Example: CLASH REGISTRATION",
        required=True,
        max_length=100
    )

    date = discord.ui.TextInput(
        label="Opening date",
        placeholder="DD/MM/YYYY",
        required=True,
        max_length=10
    )

    time = discord.ui.TextInput(
        label="Opening time - KSA",
        placeholder="20:00",
        required=True,
        max_length=5
    )

    close_time = discord.ui.TextInput(
        label="Closing time - KSA (optional)",
        placeholder="23:00",
        required=False,
        max_length=5
    )

    message = discord.ui.TextInput(
        label="Opening message",
        placeholder="Registration is now OPEN!",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1800
    )

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        try:

            open_date = datetime.strptime(
                self.date.value.strip(),
                "%d/%m/%Y"
            )

            open_time = datetime.strptime(
                self.time.value.strip(),
                "%H:%M"
            )

            open_datetime = datetime(
                open_date.year,
                open_date.month,
                open_date.day,
                open_time.hour,
                open_time.minute,
                tzinfo=KSA
            )

        except ValueError:

            await interaction.response.send_message(
                "❌ Invalid date/time.\n\n"
                "Use:\n"
                "`DD/MM/YYYY`\n"
                "`HH:MM`",
                ephemeral=True
            )

            return

        close_datetime = None

        if self.close_time.value.strip():

            try:

                close_time = datetime.strptime(
                    self.close_time.value.strip(),
                    "%H:%M"
                )

                close_datetime = datetime(
                    open_date.year,
                    open_date.month,
                    open_date.day,
                    close_time.hour,
                    close_time.minute,
                    tzinfo=KSA
                )

                if close_datetime <= open_datetime:

                    await interaction.response.send_message(
                        "❌ Closing time must be after opening time.",
                        ephemeral=True
                    )

                    return

            except ValueError:

                await interaction.response.send_message(
                    "❌ Invalid closing time. Use `HH:MM`.",
                    ephemeral=True
                )

                return

        now = datetime.now(KSA)

        if open_datetime <= now:

            await interaction.response.send_message(
                "❌ The opening date/time must be in the future.",
                ephemeral=True
            )

            return

        schedule_id = create_schedule(
            name=self.name.value.strip(),
            channel_ids=[channel.id for channel in self.channels],
            role_id=self.role.id,
            open_datetime=open_datetime.isoformat(),
            close_datetime=(
                close_datetime.isoformat()
                if close_datetime
                else None
            ),
            message=self.message.value.strip()
        )

        channel_text = "\n".join(
            f"• {channel.mention}"
            for channel in self.channels
        )

        close_text = (
            format_datetime(close_datetime)
            if close_datetime
            else "Not scheduled"
        )

        embed = discord.Embed(
            title="✅ Registration Scheduled",
            color=discord.Color.green()
        )

        embed.add_field(
            name="Registration",
            value=self.name.value,
            inline=False
        )

        embed.add_field(
            name="Opening",
            value=format_datetime(open_datetime),
            inline=True
        )

        embed.add_field(
            name="Closing",
            value=close_text,
            inline=True
        )

        embed.add_field(
            name="Mention",
            value=self.role.mention,
            inline=False
        )

        embed.add_field(
            name="Channels",
            value=channel_text,
            inline=False
        )

        embed.set_footer(
            text=f"Schedule ID: {schedule_id}"
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )


class RegistrationScheduler(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.scheduler_loop.start()

    def cog_unload(self):

        self.scheduler_loop.cancel()

    @tasks.loop(seconds=30)
    async def scheduler_loop(self):

        if not self.bot.is_ready():
            return

        schedules = get_active_schedules()

        now = datetime.now(KSA)

        for schedule in schedules:

            schedule_id = schedule["id"]

            try:

                open_datetime = datetime.fromisoformat(
                    schedule["open_datetime"]
                )

                if open_datetime.tzinfo is None:
                    open_datetime = open_datetime.replace(
                        tzinfo=KSA
                    )

                close_datetime = None

                if schedule["close_datetime"]:

                    close_datetime = datetime.fromisoformat(
                        schedule["close_datetime"]
                    )

                    if close_datetime.tzinfo is None:
                        close_datetime = close_datetime.replace(
                            tzinfo=KSA
                        )

                if (
                    schedule["status"] == "scheduled"
                    and now >= open_datetime
                ):

                    await self.open_registration(schedule)

                elif (
                    schedule["status"] == "open"
                    and close_datetime
                    and now >= close_datetime
                ):

                    await self.close_registration(schedule)

            except Exception as error:

                print(
                    f"Scheduler error for schedule "
                    f"{schedule_id}: {error}"
                )

    @scheduler_loop.before_loop
    async def before_scheduler(self):

        await self.bot.wait_until_ready()

    async def open_registration(self, schedule):

        guild_channels = []

        for channel_id in schedule["channel_ids"].split(","):

            channel = self.bot.get_channel(
                int(channel_id)
            )

            if channel:

                guild_channels.append(channel)

        if not guild_channels:

            print(
                f"No channels found for schedule "
                f"{schedule['id']}"
            )

            return

        role = None

        guild = guild_channels[0].guild

        role = guild.get_role(
            int(schedule["role_id"])
        )

        if not role:

            print(
                f"Role not found for schedule "
                f"{schedule['id']}"
            )

            return

        for channel in guild_channels:

            try:

                await channel.set_permissions(
                    guild.default_role,
                    send_messages=False
                )

                await channel.set_permissions(
                    role,
                    view_channel=True,
                    send_messages=True
                )

                message = schedule["message"]

                message = message.replace(
                    "{role}",
                    role.mention
                )

                message = message.replace(
                    "{name}",
                    schedule["name"]
                )

                channel_mentions = " ".join(
                    channel.mention
                    for channel in guild_channels
                )

                message = message.replace(
                    "{channels}",
                    channel_mentions
                )

                await channel.send(
                    content=f"{role.mention}\n{message}",
                    allowed_mentions=discord.AllowedMentions(
                        roles=[role]
                    )
                )

            except Exception as error:

                print(
                    f"Could not open channel "
                    f"{channel.id}: {error}"
                )

        update_status(
            schedule["id"],
            "open"
        )

        print(
            f"Registration {schedule['id']} opened."
        )

    async def close_registration(self, schedule):

        guild_channels = []

        for channel_id in schedule["channel_ids"].split(","):

            channel = self.bot.get_channel(
                int(channel_id)
            )

            if channel:

                guild_channels.append(channel)

        if not guild_channels:

            return

        guild = guild_channels[0].guild

        role = guild.get_role(
            int(schedule["role_id"])
        )

        for channel in guild_channels:

            try:

                if role:

                    await channel.set_permissions(
                        role,
                        send_messages=False
                    )

                await channel.send(
                    "🔒 **Registration is now CLOSED.**"
                )

            except Exception as error:

                print(
                    f"Could not close channel "
                    f"{channel.id}: {error}"
                )

        update_status(
            schedule["id"],
            "closed"
        )

        print(
            f"Registration {schedule['id']} closed."
        )

    @app_commands.command(
        name="schedule",
        description="Schedule a registration opening."
    )
    async def schedule(
        self,
        interaction: discord.Interaction
    ):

        if not isinstance(
            interaction.user,
            discord.Member
        ):

            return

        if not is_staff(interaction.user):

            await interaction.response.send_message(
                "❌ You do not have permission to use this command.",
                ephemeral=True
            )

            return

        view = ScheduleSetupView(self)

        embed = discord.Embed(
            title="📅 Registration Scheduler",
            description=(
                "Configure the registration below.\n\n"
                "1️⃣ Select one or more channels\n"
                "2️⃣ Select the role to mention\n"
                "3️⃣ Press **Continue**\n"
                "4️⃣ Enter the date, KSA time and message"
            ),
            color=discord.Color.blurple()
        )

        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True
        )

    @app_commands.command(
        name="schedules",
        description="View scheduled registrations."
    )
    async def schedules(
        self,
        interaction: discord.Interaction
    ):

        if not isinstance(
            interaction.user,
            discord.Member
        ):

            return

        if not is_staff(interaction.user):

            await interaction.response.send_message(
                "❌ You do not have permission to use this command.",
                ephemeral=True
            )

            return

        schedules = get_active_schedules()

        if not schedules:

            await interaction.response.send_message(
                "📭 There are no active or scheduled registrations.",
                ephemeral=True
            )

            return

        embed = discord.Embed(
            title="📅 Registration Schedules",
            color=discord.Color.blurple()
        )

        for schedule in schedules:

            open_datetime = datetime.fromisoformat(
                schedule["open_datetime"]
            )

            close_datetime = None

            if schedule["close_datetime"]:

                close_datetime = datetime.fromisoformat(
                    schedule["close_datetime"]
                )

            status = schedule["status"].upper()

            value = (
                f"**Status:** {status}\n"
                f"**Open:** {format_datetime(open_datetime)}\n"
            )

            if close_datetime:

                value += (
                    f"**Close:** "
                    f"{format_datetime(close_datetime)}\n"
                )

            value += (
                f"**Schedule ID:** `{schedule['id']}`"
            )

            embed.add_field(
                name=schedule["name"],
                value=value,
                inline=False
            )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

    @app_commands.command(
        name="cancel_schedule",
        description="Cancel a scheduled registration."
    )
    @app_commands.describe(
        schedule_id="The schedule ID"
    )
    async def cancel_schedule(
        self,
        interaction: discord.Interaction,
        schedule_id: int
    ):

        if not isinstance(
            interaction.user,
            discord.Member
        ):

            return

        if not is_staff(interaction.user):

            await interaction.response.send_message(
                "❌ You do not have permission to use this command.",
                ephemeral=True
            )

            return

        schedule = get_schedule(schedule_id)

        if not schedule:

            await interaction.response.send_message(
                "❌ Schedule not found.",
                ephemeral=True
            )

            return

        if schedule["status"] == "closed":

            await interaction.response.send_message(
                "❌ This registration is already closed.",
                ephemeral=True
            )

            return

        delete_schedule(schedule_id)

        await interaction.response.send_message(
            f"✅ Schedule `{schedule_id}` has been cancelled.",
            ephemeral=True
        )

    @app_commands.command(
        name="open_now",
        description="Open a scheduled registration immediately."
    )
    @app_commands.describe(
        schedule_id="The schedule ID"
    )
    async def open_now(
        self,
        interaction: discord.Interaction,
        schedule_id: int
    ):

        if not isinstance(
            interaction.user,
            discord.Member
        ):

            return

        if not is_staff(interaction.user):

            await interaction.response.send_message(
                "❌ You do not have permission to use this command.",
                ephemeral=True
            )

            return

        schedule = get_schedule(schedule_id)

        if not schedule:

            await interaction.response.send_message(
                "❌ Schedule not found.",
                ephemeral=True
            )

            return

        if schedule["status"] == "open":

            await interaction.response.send_message(
                "⚠️ This registration is already open.",
                ephemeral=True
            )

            return

        await self.open_registration(schedule)

        await interaction.response.send_message(
            f"✅ Registration `{schedule_id}` opened.",
            ephemeral=True
        )

    @app_commands.command(
        name="close_now",
        description="Close a registration immediately."
    )
    @app_commands.describe(
        schedule_id="The schedule ID"
    )
    async def close_now(
        self,
        interaction: discord.Interaction,
        schedule_id: int
    ):

        if not isinstance(
            interaction.user,
            discord.Member
        ):

            return

        if not is_staff(interaction.user):

            await interaction.response.send_message(
                "❌ You do not have permission to use this command.",
                ephemeral=True
            )

            return

        schedule = get_schedule(schedule_id)

        if not schedule:

            await interaction.response.send_message(
                "❌ Schedule not found.",
                ephemeral=True
            )

            return

        if schedule["status"] != "open":

            await interaction.response.send_message(
                "⚠️ This registration is not currently open.",
                ephemeral=True
            )

            return

        await self.close_registration(schedule)

        await interaction.response.send_message(
            f"🔒 Registration `{schedule_id}` closed.",
            ephemeral=True
        )


async def setup(bot):

    await bot.add_cog(
        RegistrationScheduler(bot)
    )
