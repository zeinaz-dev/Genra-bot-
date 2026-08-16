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


KSA = ZoneInfo("Asia/Riyadh")


def is_admin(member: discord.Member) -> bool:
    return member.guild_permissions.administrator


def format_ksa(dt: datetime) -> str:
    return dt.astimezone(KSA).strftime("%d/%m/%Y %H:%M KSA")


class ScheduleView(discord.ui.View):

    def __init__(self, cog):
        super().__init__(timeout=300)
        self.cog = cog
        self.channels = []
        self.role = None

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        channel_types=[discord.ChannelType.text],
        placeholder="Select registration channels",
        min_values=1,
        max_values=25
    )
    async def channel_select(
        self,
        interaction: discord.Interaction,
        select: discord.ui.ChannelSelect
    ):
        self.channels = list(select.values)

        await interaction.response.send_message(
            f"✅ Selected {len(self.channels)} channel(s).",
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
            f"✅ Selected role: {self.role.mention}",
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
                "❌ Select at least one channel.",
                ephemeral=True
            )
            return

        if self.role is None:
            await interaction.response.send_message(
                "❌ Select a role to mention.",
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

    registration_name = discord.ui.TextInput(
        label="Registration name",
        placeholder="Example: CLASH REGISTRATION",
        required=True,
        max_length=100
    )

    opening_date = discord.ui.TextInput(
        label="Opening date",
        placeholder="DD/MM/YYYY",
        required=True,
        max_length=10
    )

    opening_time = discord.ui.TextInput(
        label="Opening time - KSA",
        placeholder="20:00",
        required=True,
        max_length=5
    )

    closing_time = discord.ui.TextInput(
        label="Closing time - KSA",
        placeholder="23:00",
        required=True,
        max_length=5
    )

    opening_message = discord.ui.TextInput(
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
            date_value = datetime.strptime(
                self.opening_date.value.strip(),
                "%d/%m/%Y"
            )

            open_time_value = datetime.strptime(
                self.opening_time.value.strip(),
                "%H:%M"
            )

            close_time_value = datetime.strptime(
                self.closing_time.value.strip(),
                "%H:%M"
            )

        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid date or time.\n\n"
                "Date: `DD/MM/YYYY`\n"
                "Time: `HH:MM`",
                ephemeral=True
            )
            return

        open_datetime = datetime(
            date_value.year,
            date_value.month,
            date_value.day,
            open_time_value.hour,
            open_time_value.minute,
            tzinfo=KSA
        )

        close_datetime = datetime(
            date_value.year,
            date_value.month,
            date_value.day,
            close_time_value.hour,
            close_time_value.minute,
            tzinfo=KSA
        )

        now = datetime.now(KSA)

        if open_datetime <= now:
            await interaction.response.send_message(
                "❌ The opening date/time must be in the future.",
                ephemeral=True
            )
            return

        if close_datetime <= open_datetime:
            await interaction.response.send_message(
                "❌ Closing time must be after opening time.",
                ephemeral=True
            )
            return

        schedule_id = create_schedule(
            name=self.registration_name.value.strip(),
            channel_ids=[
                channel.id
                for channel in self.channels
            ],
            role_id=self.role.id,
            open_datetime=open_datetime.isoformat(),
            close_datetime=close_datetime.isoformat(),
            message=self.opening_message.value.strip()
        )

        channels_text = "\n".join(
            channel.mention
            for channel in self.channels
        )

        embed = discord.Embed(
            title="✅ Registration Scheduled",
            color=discord.Color.green()
        )

        embed.add_field(
            name="Registration",
            value=self.registration_name.value,
            inline=False
        )

        embed.add_field(
            name="Opening",
            value=format_ksa(open_datetime),
            inline=True
        )

        embed.add_field(
            name="Closing",
            value=format_ksa(close_datetime),
            inline=True
        )

        embed.add_field(
            name="Mention Role",
            value=self.role.mention,
            inline=False
        )

        embed.add_field(
            name="Channels",
            value=channels_text,
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

            try:
                open_datetime = datetime.fromisoformat(
                    schedule["open_datetime"]
                )

                close_datetime = None

                if schedule["close_datetime"]:
                    close_datetime = datetime.fromisoformat(
                        schedule["close_datetime"]
                    )

                if (
                    schedule["status"] == "scheduled"
                    and now >= open_datetime
                ):
                    await self.open_registration(schedule)

                elif (
                    schedule["status"] == "open"
                    and close_datetime is not None
                    and now >= close_datetime
                ):
                    await self.close_registration(schedule)

            except Exception as error:
                print(
                    f"Scheduler error for "
                    f"{schedule['id']}: {error}"
                )

    @scheduler_loop.before_loop
    async def before_scheduler(self):
        await self.bot.wait_until_ready()

    async def get_channels(self, schedule):

        channels = []

        for channel_id in schedule["channel_ids"].split(","):

            channel = self.bot.get_channel(
                int(channel_id)
            )

            if channel is not None:
                channels.append(channel)

        return channels

    async def open_registration(self, schedule):

        channels = await self.get_channels(schedule)

        if not channels:
            print(
                f"No channels found for schedule "
                f"{schedule['id']}"
            )
            return

        guild = channels[0].guild

        role = guild.get_role(
            int(schedule["role_id"])
        )

        if role is None:
            print(
                f"Role not found for schedule "
                f"{schedule['id']}"
            )
            return

        for channel in channels:

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

                message = message.replace(
                    "{channels}",
                    " ".join(
                        channel.mention
                        for channel in channels
                    )
                )

                await channel.send(
                    content=f"{role.mention}\n{message}",
                    allowed_mentions=discord.AllowedMentions(
                        roles=[role]
                    )
                )

            except Exception as error:
                print(
                    f"Error opening channel "
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

        channels = await self.get_channels(schedule)

        if not channels:
            return

        guild = channels[0].guild

        role = guild.get_role(
            int(schedule["role_id"])
        )

        for channel in channels:

            try:

                if role is not None:
                    await channel.set_permissions(
                        role,
                        send_messages=False
                    )

                await channel.send(
                    "🔒 **Registration is now CLOSED.**"
                )

            except Exception as error:
                print(
                    f"Error closing channel "
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
        description="Schedule a registration."
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

        if not is_admin(interaction.user):
            await interaction.response.send_message(
                "❌ Only members with **Administrator** permission "
                "can use this command.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="📅 Registration Scheduler",
            description=(
                "Create a new registration schedule.\n\n"
                "**Step 1:** Select one or more channels.\n"
                "**Step 2:** Select the role to mention.\n"
                "**Step 3:** Press Continue.\n"
                "**Step 4:** Enter the date, KSA times and message."
            ),
            color=discord.Color.blurple()
        )

        await interaction.response.send_message(
            embed=embed,
            view=ScheduleView(self),
            ephemeral=True
        )

    @app_commands.command(
        name="schedules",
        description="View registration schedules."
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

        if not is_admin(interaction.user):
            await interaction.response.send_message(
                "❌ Only members with **Administrator** permission "
                "can use this command.",
                ephemeral=True
            )
            return

        schedules = get_active_schedules()

        if not schedules:
            await interaction.response.send_message(
                "📭 No scheduled registrations.",
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

            close_datetime = datetime.fromisoformat(
                schedule["close_datetime"]
            )

            value = (
                f"**Status:** {schedule['status'].upper()
