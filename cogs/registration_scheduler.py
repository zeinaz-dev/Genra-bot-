import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands, tasks

from database.schema import (
    create_schedule,
    get_schedule,
    get_active_schedules,
    update_status,
    delete_schedule
)


KSA = ZoneInfo("Asia/Riyadh")

INDEPENDENT_CLOSE_FILE = "data/independent_closes.json"


DEFAULT_CLOSING_MESSAGE = (
    "🔒 **REGISTRATION IS NOW CLOSED!**\n\n"
    "Please check the **WhatsApp group** for the **Group ID** 📱\n\n"
    "⚠️ If you have any problem or need assistance, "
    "please contact the **room organizer**.\n\n"
    "Thank you for your cooperation & good luck! 🏆❤️‍🔥\n\n"
    "━━━━━━━━━━━━━━\n\n"
    "🔒 **التسجيل مغلق الآن!**\n\n"
    "يرجى التوجه إلى **مجموعة الواتساب** للاطلاع على "
    "**رقم المجموعة (Group ID)** 📱\n\n"
    "⚠️ في حال وجود أي مشكلة أو استفسار، يرجى التواصل "
    "مع **منظم الروم**.\n\n"
    "شكرًا لتعاونكم وبالتوفيق للجميع! 🏆❤️‍🔥"
)


def is_admin(member: discord.Member) -> bool:
    return member.guild_permissions.administrator


def format_ksa(dt: datetime) -> str:
    return dt.astimezone(KSA).strftime(
        "%d/%m/%Y %H:%M KSA"
    )


def load_independent_closes():
    os.makedirs(
        "data",
        exist_ok=True
    )

    if not os.path.exists(
        INDEPENDENT_CLOSE_FILE
    ):
        return []

    try:
        with open(
            INDEPENDENT_CLOSE_FILE,
            "r",
            encoding="utf-8"
        ) as file:
            return json.load(file)

    except Exception as error:
        print(
            f"Could not load independent closes: {error}"
        )
        return []


def save_independent_closes(closes):
    os.makedirs(
        "data",
        exist_ok=True
    )

    with open(
        INDEPENDENT_CLOSE_FILE,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            closes,
            file,
            ensure_ascii=False,
            indent=4
        )


def replace_placeholders(
    message,
    role=None,
    name=None,
    channels=None
):
    if role is not None:
        message = message.replace(
            "{role}",
            role.mention
        )

    if name is not None:
        message = message.replace(
            "{name}",
            name
        )

    if channels:
        message = message.replace(
            "{channels}",
            " ".join(
                channel.mention
                for channel in channels
            )
        )

    return message


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

        await interaction.response.send_modal(
            ScheduleModal(
                self.cog,
                self.channels,
                self.role
            )
        )


class ScheduleModal(discord.ui.Modal):

    def __init__(
        self,
        cog,
        channels,
        role
    ):
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

    closing_date = discord.ui.TextInput(
        label="Closing date",
        placeholder="DD/MM/YYYY",
        required=True,
        max_length=10
    )

    closing_time = discord.ui.TextInput(
        label="Closing time - KSA",
        placeholder="23:00",
        required=True,
        max_length=5
    )

    opening_message = discord.ui.TextInput(
        label="Opening message",
        placeholder="Write your opening message here",
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
                self.opening_date.value.strip(),
                "%d/%m/%Y"
            )

            open_time = datetime.strptime(
                self.opening_time.value.strip(),
                "%H:%M"
            )

            close_date = datetime.strptime(
                self.closing_date.value.strip(),
                "%d/%m/%Y"
            )

            close_time = datetime.strptime(
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
            open_date.year,
            open_date.month,
            open_date.day,
            open_time.hour,
            open_time.minute,
            tzinfo=KSA
        )

        close_datetime = datetime(
            close_date.year,
            close_date.month,
            close_date.day,
            close_time.hour,
            close_time.minute,
            tzinfo=KSA
        )

        now = datetime.now(KSA)

        if open_datetime <= now:
            await interaction.response.send_message(
                "❌ Opening time must be in the future.",
                ephemeral=True
            )
            return

        if close_datetime <= open_datetime:
            await interaction.response.send_message(
                "❌ Closing time must be after opening time.",
                ephemeral=True
            )
            return

        try:
            schedule_id = create_schedule(
                name=self.registration_name.value.strip(),
                channel_ids=",".join(
                    str(channel.id)
                    for channel in self.channels
                ),
                role_id=self.role.id,
                open_datetime=open_datetime.isoformat(),
                close_datetime=close_datetime.isoformat(),
                message=self.opening_message.value.strip()
            )

        except Exception as error:
            print(
                f"Create schedule error: {error}"
            )

            await interaction.response.send_message(
                "❌ Could not create the schedule.",
                ephemeral=True
            )
            return

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
            name="Role",
            value=self.role.mention,
            inline=False
        )

        embed.add_field(
            name="Channels",
            value=channels_text,
            inline=False
        )

        embed.add_field(
            name="Opening Message",
            value=self.opening_message.value[:1024],
            inline=False
        )

        embed.add_field(
            name="Closing Message",
            value="Default closing message",
            inline=False
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )


class IndependentCloseView(discord.ui.View):

    def __init__(self, cog):
        super().__init__(timeout=300)

        self.cog = cog
        self.channel = None
        self.role = None

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        channel_types=[discord.ChannelType.text],
        placeholder="Select ONE channel",
        min_values=1,
        max_values=1
    )
    async def channel_select(
        self,
        interaction: discord.Interaction,
        select: discord.ui.ChannelSelect
    ):
        self.channel = select.values[0]

        await interaction.response.send_message(
            f"✅ Selected: {self.channel.mention}",
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
        style=discord.ButtonStyle.red
    )
    async def continue_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if self.channel is None:
            await interaction.response.send_message(
                "❌ Select one channel.",
                ephemeral=True
            )
            return

        if self.role is None:
            await interaction.response.send_message(
                "❌ Select a role.",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(
            IndependentCloseModal(
                self.cog,
                self.channel,
                self.role
            )
        )


class IndependentCloseModal(discord.ui.Modal):

    def __init__(
        self,
        cog,
        channel,
        role
    ):
        super().__init__(
            title="Schedule Registration Close"
        )

        self.cog = cog
        self.channel = channel
        self.role = role

    closing_date = discord.ui.TextInput(
        label="Closing date",
        placeholder="DD/MM/YYYY",
        required=True,
        max_length=10
    )

    closing_time = discord.ui.TextInput(
        label="Closing time - KSA",
        placeholder="23:00",
        required=True,
        max_length=5
    )

    closing_message = discord.ui.TextInput(
        label="Closing message",
        placeholder="Write your closing message here",
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
                self.closing_date.value.strip(),
                "%d/%m/%Y"
            )

            time_value = datetime.strptime(
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

        close_datetime = datetime(
            date_value.year,
            date_value.month,
            date_value.day,
            time_value.hour,
            time_value.minute,
            tzinfo=KSA
        )

        if close_datetime <= datetime.now(KSA):
            await interaction.response.send_message(
                "❌ Closing time must be in the future.",
                ephemeral=True
            )
            return

        closes = load_independent_closes()

        next_id = 1

        if closes:
            next_id = max(
                item["id"]
                for item in closes
            ) + 1

        closes.append(
            {
                "id": next_id,
                "channel_id": self.channel.id,
                "role_id": self.role.id,
                "guild_id": self.channel.guild.id,
                "close_datetime": close_datetime.isoformat(),
                "message": self.closing_message.value.strip(),
                "status": "scheduled"
            }
        )

        save_independent_closes(closes)

        embed = discord.Embed(
            title="🔒 Registration Close Scheduled",
            color=discord.Color.red()
        )

        embed.add_field(
            name="Channel",
            value=self.channel.mention,
            inline=False
        )

        embed.add_field(
            name="Role",
            value=self.role.mention,
            inline=False
        )

        embed.add_field(
            name="Closing",
            value=format_ksa(close_datetime),
            inline=False
        )

        embed.add_field(
            name="Message",
            value=self.closing_message.value[:1024],
            inline=False
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

        await self.process_regular_schedules()
        await self.process_independent_closes()

    @scheduler_loop.before_loop
    async def before_scheduler(self):
        await self.bot.wait_until_ready()

    async def process_regular_schedules(self):

        try:
            schedules = get_active_schedules()
        except Exception as error:
            print(
                f"Could not load schedules: {error}"
            )
            return

        now = datetime.now(KSA)

        for schedule in schedules:

            try:
                open_datetime = datetime.fromisoformat(
                    schedule["open_datetime"]
                )

                close_datetime = datetime.fromisoformat(
                    schedule["close_datetime"]
                )

                if (
                    schedule["status"] == "scheduled"
                    and now >= open_datetime
                ):
                    await self.open_registration(
                        schedule
                    )

                elif (
                    schedule["status"] == "open"
                    and now >= close_datetime
                ):
                    await self.close_registration(
                        schedule
                    )

            except Exception as error:
                print(
                    f"Schedule {schedule['id']} error: "
                    f"{error}"
                )

    async def process_independent_closes(self):

        closes = load_independent_closes()

        if not closes:
            return

        now = datetime.now(KSA)
        changed = False

        for close_data in closes:

            if close_data["status"] != "scheduled":
                continue

            try:
                close_datetime = datetime.fromisoformat(
                    close_data["close_datetime"]
                )

                if now < close_datetime:
                    continue

                channel = self.bot.get_channel(
                    int(close_data["channel_id"])
                )

                if channel is None:
                    close_data["status"] = "error"
                    changed = True
                    continue

                role = channel.guild.get_role(
                    int(close_data["role_id"])
                )

                if role is None:
                    close_data["status"] = "error"
                    changed = True
                    continue

                await self.close_single_channel(
                    channel,
                    role,
                    close_data["message"]
                )

                close_data["status"] = "closed"
                changed = True

            except Exception as error:
                print(
                    f"Independent close error: {error}"
                )

        if changed:
            save_independent_closes(closes)

    async def get_channels(self, schedule):

        channels = []

        channel_ids = schedule["channel_ids"]

        if isinstance(channel_ids, str):
            channel_ids = channel_ids.split(",")

        for channel_id in channel_ids:

            try:
                channel = self.bot.get_channel(
                    int(channel_id)
                )

                if channel:
                    channels.append(channel)

            except Exception:
                continue

        return channels

    async def open_registration(
        self,
        schedule
    ):

        channels = await self.get_channels(
            schedule
        )

        if not channels:
            return

        guild = channels[0].guild

        role = guild.get_role(
            int(schedule["role_id"])
        )

        if role is None:
            return

        for channel in channels:

            try:
                # Everyone cannot see registration channel.
                await channel.set_permissions(
                    guild.default_role,
                    view_channel=False
                )

                # Selected registration role:
                # CAN SEE + CAN WRITE.
                await channel.set_permissions(
                    role,
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                )

                message = replace_placeholders(
                    schedule["message"],
                    role=role,
                    name=schedule["name"],
                    channels=channels
                )

                await channel.send(
                    content=(
                        f"{role.mention}\n"
                        f"{message}"
                    ),
                    allowed_mentions=discord.AllowedMentions(
                        roles=[role]
                    )
                )

            except Exception as error:
                print(
                    f"Opening channel error: {error}"
                )

        update_status(
            schedule["id"],
            "open"
        )

        print(
            f"Registration {schedule['id']} opened."
        )

    async def close_registration(
        self,
        schedule
    ):

        channels = await self.get_channels(
            schedule
        )

        if not channels:
            return

        guild = channels[0].guild

        role = guild.get_role(
            int(schedule["role_id"])
        )

        if role is None:
            return

        for channel in channels:

            try:
                # IMPORTANT:
                # Role STILL sees the channel.
                # Role CANNOT write.
                await channel.set_permissions(
                    role,
                    view_channel=True,
                    send_messages=False,
                    read_message_history=True
                )

                await channel.send(
                    content=(
                        f"{role.mention}\n"
                        f"{DEFAULT_CLOSING_MESSAGE}"
                    ),
                    allowed_mentions=discord.AllowedMentions(
                        roles=[role]
                    )
                )

            except Exception as error:
                print(
                    f"Closing channel error: {error}"
                )

        update_status(
            schedule["id"],
            "closed"
        )

        print(
            f"Registration {schedule['id']} closed."
        )

    async def close_single_channel(
        self,
        channel,
        role,
        message
    ):

        # IMPORTANT:
        # Keep VIEW permission.
        # Remove WRITE permission.
        await channel.set_permissions(
            role,
            view_channel=True,
            send_messages=False,
            read_message_history=True
        )

        message = replace_placeholders(
            message,
            role=role,
            channels=[channel]
        )

        await channel.send(
            content=(
                f"{role.mention}\n"
                f"{message}"
            ),
            allowed_mentions=discord.AllowedMentions(
                roles=[role]
            )
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

        if not is_admin(
            interaction.user
        ):
            await interaction.response.send_message(
                "❌ Only members with "
                "**Administrator** permission "
                "can use this command.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="📅 Registration Scheduler",
            description=(
                "Select the registration channels "
                "and role."
            ),
            color=discord.Color.blurple()
        )

        await interaction.response.send_message(
            embed=embed,
            view=ScheduleView(self),
            ephemeral=True
        )

    @app_commands.command(
        name="close_registration",
        description="Schedule an independent registration close."
    )
    async def close_registration_command(
        self,
        interaction: discord.Interaction
    ):

        if not isinstance(
            interaction.user,
            discord.Member
        ):
            return

        if not is_admin(
            interaction.user
        ):
            await interaction.response.send_message(
                "❌ Only members with "
                "**Administrator** permission "
                "can use this command.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="🔒 Schedule Registration Close",
            description=(
                "Select ONE registration channel, "
                "the role, closing time and message."
            ),
            color=discord.Color.red()
        )

        await interaction.response.send_message(
            embed=embed,
            view=IndependentCloseView(self),
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

        if not is_admin(
            interaction.user
        ):
            await interaction.response.send_message(
                "❌ Administrator only.",
                ephemeral=True
            )
            return

        schedules = get_active_schedules()

        if not schedules:
            await interaction.response.send_message(
                "📭 No schedules found.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="📅 Registration Schedules",
            color=discord.Color.blurple()
        )

        for schedule in schedules:

            opening = datetime.fromisoformat(
                schedule["open_datetime"]
            )

            closing = datetime.fromisoformat(
                schedule["close_datetime"]
            )

            embed.add_field(
                name=schedule["name"],
                value=(
                    f"Status: `{schedule['status']}`\n"
                    f"Open: `{format_ksa(opening)}`\n"
                    f"Close: `{format_ksa(closing)}`\n"
                    f"ID: `{schedule['id']}`"
                ),
                inline=False
            )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

    @app_commands.command(
        name="cancel_schedule",
        description="Cancel a registration schedule."
    )
    @app_commands.describe(
        schedule_id="Schedule ID"
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

        if not is_admin(
            interaction.user
        ):
            await interaction.response.send_message(
                "❌ Administrator only.",
                ephemeral=True
            )
            return

        schedule = get_schedule(
            schedule_id
        )

        if schedule is None:
            await interaction.response.send_message(
                "❌ Schedule not found.",
                ephemeral=True
            )
            return

        delete_schedule(
            schedule_id
        )

        await interaction.response.send_message(
            f"✅ Schedule `{schedule_id}` cancelled.",
            ephemeral=True
        )

    @app_commands.command(
        name="open_now",
        description="Open a registration immediately."
    )
    @app_commands.describe(
        schedule_id="Schedule ID"
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

        if not is_admin(
            interaction.user
        ):
            await interaction.response.send_message(
                "❌ Administrator only.",
                ephemeral=True
            )
            return

        schedule = get_schedule(
            schedule_id
        )

        if schedule is None:
            await interaction.response.send_message(
                "❌ Schedule not found.",
                ephemeral=True
            )
            return

        await self.open_registration(
            schedule
        )

        await interaction.response.send_message(
            f"✅ Registration `{schedule_id}` opened.",
            ephemeral=True
        )

    @app_commands.command(
        name="close_now",
        description="Close a registration immediately."
    )
    @app_commands.describe(
        schedule_id="Schedule ID"
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

        if not is_admin(
            interaction.user
        ):
            await interaction.response.send_message(
                "❌ Administrator only.",
                ephemeral=True
            )
            return

        schedule = get_schedule(
            schedule_id
        )

        if schedule is None:
            await interaction.response.send_message(
                "❌ Schedule not found.",
                ephemeral=True
            )
            return

        await self.close_registration(
            schedule
        )

        await interaction.response.send_message(
            f"🔒 Registration `{schedule_id}` closed.",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(
        RegistrationScheduler(bot)
    )
