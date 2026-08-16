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
    delete_schedule,
)


KSA = ZoneInfo("Asia/Riyadh")

CLOSE_FILE = "data/independent_closes.json"


DEFAULT_CLOSE_MESSAGE = (
    "🔒 **REGISTRATION IS NOW CLOSED!**\n\n"
    "Please check the **WhatsApp group** for the Group ID 📱\n\n"
    "If you have any problem, please contact the room organiser.\n"
    "Thank you! ❤️‍🔥\n\n"
    "━━━━━━━━━━━━━━\n\n"
    "🔒 **التسجيل مغلق الآن!**\n\n"
    "يرجى التوجه إلى **مجموعة الواتساب** لمعرفة رقم المجموعة 📱\n\n"
    "في حال وجود أي مشكلة، يرجى التواصل مع منظم الروم.\n"
    "شكراً لكم ❤️‍🔥"
)


# =========================================================
# HELPERS
# =========================================================

def is_admin(interaction: discord.Interaction):

    return (
        isinstance(interaction.user, discord.Member)
        and interaction.user.guild_permissions.administrator
    )


def now_ksa():

    return datetime.now(KSA)


def parse_ksa(date_text, time_text):

    date_value = datetime.strptime(
        date_text.strip(),
        "%d/%m/%Y"
    )

    time_value = datetime.strptime(
        time_text.strip(),
        "%H:%M"
    )

    return datetime(
        date_value.year,
        date_value.month,
        date_value.day,
        time_value.hour,
        time_value.minute,
        tzinfo=KSA
    )


def format_ksa(value):

    return value.astimezone(KSA).strftime(
        "%d/%m/%Y %H:%M KSA"
    )


def load_closes():

    os.makedirs(
        "data",
        exist_ok=True
    )

    if not os.path.exists(CLOSE_FILE):

        return []

    try:

        with open(
            CLOSE_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    except Exception as error:

        print(
            f"❌ Close file error: {error!r}"
        )

        return []


def save_closes(data):

    os.makedirs(
        "data",
        exist_ok=True
    )

    with open(
        CLOSE_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=4
        )


# =========================================================
# SCHEDULE SETUP VIEW
# =========================================================

class ScheduleSetupView(discord.ui.View):

    def __init__(self, cog):

        super().__init__(
            timeout=300
        )

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
    async def channels_selected(
        self,
        interaction: discord.Interaction,
        select: discord.ui.ChannelSelect
    ):

        try:

            self.channels = list(
                select.values
            )

            await interaction.response.send_message(
                f"✅ {len(self.channels)} channel(s) selected.",
                ephemeral=True
            )

        except Exception as error:

            print(
                f"❌ Channel selection error: {error!r}"
            )

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "❌ Error selecting channels.",
                    ephemeral=True
                )

    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="Select subscriber role",
        min_values=1,
        max_values=1
    )
    async def role_selected(
        self,
        interaction: discord.Interaction,
        select: discord.ui.RoleSelect
    ):

        try:

            self.role = select.values[0]

            await interaction.response.send_message(
                f"✅ Role selected: {self.role.mention}",
                ephemeral=True
            )

        except Exception as error:

            print(
                f"❌ Role selection error: {error!r}"
            )

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "❌ Error selecting role.",
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

        try:

            if not self.channels:

                await interaction.response.send_message(
                    "❌ Please select at least one channel.",
                    ephemeral=True
                )

                return

            if self.role is None:

                await interaction.response.send_message(
                    "❌ Please select a role.",
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

        except Exception as error:

            print(
                f"❌ Continue button error: {error!r}"
            )

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "❌ Something went wrong.",
                    ephemeral=True
                )


# =========================================================
# SCHEDULE MODAL
# =========================================================

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

    name = discord.ui.TextInput(
        label="Registration name",
        placeholder="Example: CLASH REGISTRATION",
        required=True,
        max_length=100
    )

    open_date = discord.ui.TextInput(
        label="Opening date - KSA",
        placeholder="DD/MM/YYYY",
        required=True,
        max_length=10
    )

    open_time = discord.ui.TextInput(
        label="Opening time - KSA",
        placeholder="20:00",
        required=True,
        max_length=5
    )

    close_datetime = discord.ui.TextInput(
        label="Closing date & time - KSA",
        placeholder="DD/MM/YYYY HH:MM",
        required=True,
        max_length=16
    )

    message = discord.ui.TextInput(
        label="Opening message",
        placeholder="Write the opening message",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1800
    )

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        try:

            opening = parse_ksa(
                self.open_date.value,
                self.open_time.value
            )

            closing = datetime.strptime(
                self.close_datetime.value.strip(),
                "%d/%m/%Y %H:%M"
            ).replace(
                tzinfo=KSA
            )

            if opening <= now_ksa():

                await interaction.response.send_message(
                    "❌ Opening time must be in the future.",
                    ephemeral=True
                )

                return

            if closing <= opening:

                await interaction.response.send_message(
                    "❌ Closing time must be after opening time.",
                    ephemeral=True
                )

                return

            # Database expects a list of channel IDs.
            channel_ids = [
                channel.id
                for channel in self.channels
            ]

            schedule_id = create_schedule(
                name=self.name.value.strip(),
                channel_ids=channel_ids,
                role_id=self.role.id,
                open_datetime=opening.isoformat(),
                close_datetime=closing.isoformat(),
                message=self.message.value.strip()
            )

            channel_text = " ".join(
                channel.mention
                for channel in self.channels
            )

            embed = discord.Embed(
                title="📅 Registration Scheduled",
                color=discord.Color.green()
            )

            embed.add_field(
                name="Registration",
                value=self.name.value,
                inline=False
            )

            embed.add_field(
                name="Channels",
                value=channel_text,
                inline=False
            )

            embed.add_field(
                name="Role",
                value=self.role.mention,
                inline=False
            )

            embed.add_field(
                name="Opening",
                value=format_ksa(opening),
                inline=True
            )

            embed.add_field(
                name="Closing",
                value=format_ksa(closing),
                inline=True
            )

            embed.set_footer(
                text=f"Schedule ID: {schedule_id}"
            )

            await interaction.response.send_message(
                embed=embed,
                ephemeral=True
            )

            print(
                f"✅ Schedule created: {schedule_id}"
            )

        except ValueError:

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "❌ Invalid date/time.\n\n"
                    "Opening date: `DD/MM/YYYY`\n"
                    "Opening time: `HH:MM`\n"
                    "Closing: `DD/MM/YYYY HH:MM`",
                    ephemeral=True
                )

        except Exception as error:

            print(
                f"❌ Schedule creation error: {error!r}"
            )

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "❌ Could not create the schedule.",
                    ephemeral=True
                )


# =========================================================
# CLOSE SETUP VIEW
# =========================================================

class CloseSetupView(discord.ui.View):

    def __init__(self, cog):

        super().__init__(
            timeout=300
        )

        self.cog = cog
        self.channel = None
        self.role = None

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        channel_types=[discord.ChannelType.text],
        placeholder="Select ONE registration channel",
        min_values=1,
        max_values=1
    )
    async def channel_selected(
        self,
        interaction: discord.Interaction,
        select: discord.ui.ChannelSelect
    ):

        try:

            self.channel = select.values[0]

            await interaction.response.send_message(
                f"✅ Channel: {self.channel.mention}",
                ephemeral=True
            )

        except Exception as error:

            print(
                f"❌ Close channel error: {error!r}"
            )

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "❌ Error selecting channel.",
                    ephemeral=True
                )

    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="Select subscriber role",
        min_values=1,
        max_values=1
    )
    async def role_selected(
        self,
        interaction: discord.Interaction,
        select: discord.ui.RoleSelect
    ):

        try:

            self.role = select.values[0]

            await interaction.response.send_message(
                f"✅ Role: {self.role.mention}",
                ephemeral=True
            )

        except Exception as error:

            print(
                f"❌ Close role error: {error!r}"
            )

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "❌ Error selecting role.",
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

        try:

            if self.channel is None:

                await interaction.response.send_message(
                    "❌ Select a channel first.",
                    ephemeral=True
                )

                return

            if self.role is None:

                await interaction.response.send_message(
                    "❌ Select a role first.",
                    ephemeral=True
                )

                return

            await interaction.response.send_modal(
                CloseModal(
                    self.channel,
                    self.role
                )
            )

        except Exception as error:

            print(
                f"❌ Close continue error: {error!r}"
            )

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "❌ Something went wrong.",
                    ephemeral=True
                )


# =========================================================
# CLOSE MODAL
# =========================================================

class CloseModal(discord.ui.Modal):

    def __init__(
        self,
        channel,
        role
    ):

        super().__init__(
            title="Schedule Registration Close"
        )

        self.channel = channel
        self.role = role

    close_datetime = discord.ui.TextInput(
        label="Closing date & time - KSA",
        placeholder="DD/MM/YYYY HH:MM",
        required=True,
        max_length=16
    )

    message = discord.ui.TextInput(
        label="Closing message",
        placeholder="Write the closing message",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1800
    )

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        try:

            closing = datetime.strptime(
                self.close_datetime.value.strip(),
                "%d/%m/%Y %H:%M"
            ).replace(
                tzinfo=KSA
            )

            if closing <= now_ksa():

                await interaction.response.send_message(
                    "❌ Closing time must be in the future.",
                    ephemeral=True
                )

                return

            closes = load_closes()

            next_id = 1

            if closes:

                next_id = max(
                    item["id"]
                    for item in closes
                ) + 1

            closes.append(
                {
                    "id": next_id,
                    "guild_id": self.channel.guild.id,
                    "channel_id": self.channel.id,
                    "role_id": self.role.id,
                    "close_datetime": closing.isoformat(),
                    "message": self.message.value.strip(),
                    "status": "scheduled"
                }
            )

            save_closes(closes)

            await interaction.response.send_message(
                "✅ **Registration close scheduled!**\n\n"
                f"Channel: {self.channel.mention}\n"
                f"Role: {self.role.mention}\n"
                f"Time: `{format_ksa(closing)}`",
                ephemeral=True
            )

        except ValueError:

            await interaction.response.send_message(
                "❌ Invalid date/time.\n\n"
                "Use: `DD/MM/YYYY HH:MM`",
                ephemeral=True
            )

        except Exception as error:

            print(
                f"❌ Close creation error: {error!r}"
            )

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "❌ Could not create closing schedule.",
                    ephemeral=True
                )


# =========================================================
# COG
# =========================================================

class RegistrationScheduler(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.scheduler.start()

    def cog_unload(self):

        self.scheduler.cancel()

    @tasks.loop(seconds=30)
    async def scheduler(self):

        try:

            await self.process_schedules()

            await self.process_independent_closes()

        except Exception as error:

            print(
                f"❌ Scheduler error: {error!r}"
            )

    @scheduler.before_loop
    async def before_scheduler(self):

        await self.bot.wait_until_ready()

    # =====================================================
    # SCHEDULE PROCESSING
    # =====================================================

    async def process_schedules(self):

        schedules = get_active_schedules()

        current = now_ksa()

        for schedule in schedules:

            try:

                opening = datetime.fromisoformat(
                    schedule["open_datetime"]
                )

                closing = None

                if schedule["close_datetime"]:

                    closing = datetime.fromisoformat(
                        schedule["close_datetime"]
                    )

                if (
                    schedule["status"] == "scheduled"
                    and current >= opening
                ):

                    await self.open_schedule(
                        schedule
                    )

                elif (
                    schedule["status"] == "open"
                    and closing is not None
                    and current >= closing
                ):

                    await self.close_schedule(
                        schedule
                    )

            except Exception as error:

                print(
                    f"❌ Schedule {schedule['id']} error: "
                    f"{error!r}"
                )

    async def get_channels(
        self,
        schedule
    ):

        result = []

        channel_ids = schedule["channel_ids"]

        if isinstance(
            channel_ids,
            str
        ):

            channel_ids = channel_ids.split(",")

        for channel_id in channel_ids:

            try:

                channel = self.bot.get_channel(
                    int(channel_id)
                )

                if channel:

                    result.append(channel)

            except Exception as error:

                print(
                    f"❌ Channel lookup error: {error!r}"
                )

        return result

    # =====================================================
    # OPEN SCHEDULE
    # =====================================================

    async def open_schedule(
        self,
        schedule
    ):

        channels = await self.get_channels(
            schedule
        )

        if not channels:

            print(
                f"❌ No channels found for schedule "
                f"{schedule['id']}"
            )

            return

        guild = channels[0].guild

        role = guild.get_role(
            int(schedule["role_id"])
        )

        if role is None:

            print(
                f"❌ Role not found for schedule "
                f"{schedule['id']}"
            )

            return

        for channel in channels:

            try:

                # Everyone cannot see the registration channel.
                await channel.set_permissions(
                    guild.default_role,
                    view_channel=False
                )

                # Subscriber role:
                # CAN SEE + CAN WRITE
                await channel.set_permissions(
                    role,
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                )

                await channel.send(
                    content=(
                        f"{role.mention}\n"
                        f"{schedule['message']}"
                    ),
                    allowed_mentions=discord.AllowedMentions(
                        roles=[role]
                    )
                )

                print(
                    f"🟢 Opened channel {channel.id}"
                )

            except Exception as error:

                print(
                    f"❌ Open channel error: {error!r}"
                )

        update_status(
            schedule["id"],
            "open"
        )

        print(
            f"🟢 Registration {schedule['id']} opened."
        )

    # =====================================================
    # CLOSE SCHEDULE
    # =====================================================

    async def close_schedule(
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
                # Subscribers STILL SEE the channel.
                # Subscribers CANNOT WRITE.
                await channel.set_permissions(
                    role,
                    view_channel=True,
                    send_messages=False,
                    read_message_history=True
                )

                await channel.send(
                    content=(
                        f"{role.mention}\n"
                        f"{DEFAULT_CLOSE_MESSAGE}"
                    ),
                    allowed_mentions=discord.AllowedMentions(
                        roles=[role]
                    )
                )

            except Exception as error:

                print(
                    f"❌ Close channel error: {error!r}"
                )

        update_status(
            schedule["id"],
            "closed"
        )

        print(
            f"🔴 Registration {schedule['id']} closed."
        )

    # =====================================================
    # INDEPENDENT CLOSE PROCESSING
    # =====================================================

    async def process_independent_closes(self):

        closes = load_closes()

        if not closes:

            return

        current = now_ksa()

        changed = False

        for item in closes:

            if item["status"] != "scheduled":

                continue

            try:

                closing = datetime.fromisoformat(
                    item["close_datetime"]
                )

                if current < closing:

                    continue

                channel = self.bot.get_channel(
                    int(item["channel_id"])
                )

                if channel is None:

                    continue

                role = channel.guild.get_role(
                    int(item["role_id"])
                )

                if role is None:

                    continue

                # STILL VISIBLE
                # CANNOT WRITE
                await channel.set_permissions(
                    role,
                    view_channel=True,
                    send_messages=False,
                    read_message_history=True
                )

                await channel.send(
                    content=(
                        f"{role.mention}\n"
                        f"{item['message']}"
                    ),
                    allowed_mentions=discord.AllowedMentions(
                        roles=[role]
                    )
                )

                item["status"] = "closed"

                changed = True

                print(
                    f"🔒 Independent close completed: "
                    f"{item['id']}"
                )

            except Exception as error:

                print(
                    f"❌ Independent close error: {error!r}"
                )

        if changed:

            save_closes(closes)

    # =====================================================
    # /SCHEDULE
    # =====================================================

    @app_commands.command(
        name="schedule",
        description="Create a registration schedule."
    )
    async def schedule_command(
        self,
        interaction: discord.Interaction
    ):

        try:

            if not is_admin(interaction):

                await interaction.response.send_message(
                    "❌ Administrator only.",
                    ephemeral=True
                )

                return

            embed = discord.Embed(
                title="📅 Registration Scheduler",
                description=(
                    "1️⃣ Select the registration channels.\n"
                    "2️⃣ Select the subscriber role.\n"
                    "3️⃣ Press **Continue**."
                ),
                color=discord.Color.blurple()
            )

            await interaction.response.send_message(
                embed=embed,
                view=ScheduleSetupView(self),
                ephemeral=True
            )

        except Exception as error:

            print(
                f"❌ /schedule error: {error!r}"
            )

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "❌ Something went wrong.",
                    ephemeral=True
                )

    # =====================================================
    # /CLOSE_REGISTRATION
    # =====================================================

    @app_commands.command(
        name="close_registration",
        description="Schedule an independent registration close."
    )
    async def close_registration_command(
        self,
        interaction: discord.Interaction
    ):

        try:

            if not is_admin(interaction):

                await interaction.response.send_message(
                    "❌ Administrator only.",
                    ephemeral=True
                )

                return

            embed = discord.Embed(
                title="🔒 Close Registration",
                description=(
                    "Select ONE registration channel "
                    "and the subscriber role."
                ),
                color=discord.Color.red()
            )

            await interaction.response.send_message(
                embed=embed,
                view=CloseSetupView(self),
                ephemeral=True
            )

        except Exception as error:

            print(
                f"❌ /close_registration error: {error!r}"
            )

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "❌ Something went wrong.",
                    ephemeral=True
                )

    # =====================================================
    # /OPEN_NOW
    # =====================================================

    @app_commands.command(
        name="open_now",
        description="Open a scheduled registration now."
    )
    @app_commands.describe(
        schedule_id="Schedule ID"
    )
    async def open_now(
        self,
        interaction: discord.Interaction,
        schedule_id: int
    ):

        try:

            if not is_admin(interaction):

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

            await self.open_schedule(
                schedule
            )

            await interaction.response.send_message(
                "🟢 Registration opened.",
                ephemeral=True
            )

        except Exception as error:

            print(
                f"❌ /open_now error: {error!r}"
            )

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "❌ Could not open registration.",
                    ephemeral=True
                )

    # =====================================================
    # /CLOSE_NOW
    # =====================================================

    @app_commands.command(
        name="close_now",
        description="Close a scheduled registration now."
    )
    @app_commands.describe(
        schedule_id="Schedule ID"
    )
    async def close_now(
        self,
        interaction: discord.Interaction,
        schedule_id: int
    ):

        try:

            if not is_admin(interaction):

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

            await self.close_schedule(
                schedule
            )

            await interaction.response.send_message(
                "🔴 Registration closed.",
                ephemeral=True
            )

        except Exception as error:

            print(
                f"❌ /close_now error: {error!r}"
            )

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "❌ Could not close registration.",
                    ephemeral=True
                )

    # =====================================================
    # /SCHEDULES
    # =====================================================

    @app_commands.command(
        name="schedules",
        description="Show registration schedules."
    )
    async def schedules_command(
        self,
        interaction: discord.Interaction
    ):

        try:

            if not is_admin(interaction):

                await interaction.response.send_message(
                    "❌ Administrator only.",
                    ephemeral=True
                )

                return

            schedules = get_active_schedules()

            if not schedules:

                await interaction.response.send_message(
                    "📭 No schedules.",
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

                closing = None

                if schedule["close_datetime"]:

                    closing = datetime.fromisoformat(
                        schedule["close_datetime"]
                    )

                closing_text = (
                    format_ksa(closing)
                    if closing
                    else "Not set"
                )

                embed.add_field(
                    name=(
                        f"{schedule['name']} "
                        f"(ID {schedule['id']})"
                    ),
                    value=(
                        f"Status: `{schedule['status']}`\n"
                        f"Open: `{format_ksa(opening)}`\n"
                        f"Close: `{closing_text}`"
                    ),
                    inline=False
                )

            await interaction.response.send_message(
                embed=embed,
                ephemeral=True
            )

        except Exception as error:

            print(
                f"❌ /schedules error: {error!r}"
            )

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "❌ Could not load schedules.",
                    ephemeral=True
                )

    # =====================================================
    # /CANCEL_SCHEDULE
    # =====================================================

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

        try:

            if not is_admin(interaction):

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

        except Exception as error:

            print(
                f"❌ /cancel_schedule error: {error!r}"
            )

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "❌ Could not cancel schedule.",
                    ephemeral=True
                )


# =========================================================
# SETUP
# =========================================================

async def setup(bot):

    await bot.add_cog(
        RegistrationScheduler(bot)
    )
