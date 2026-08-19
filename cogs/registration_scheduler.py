# =========================================================
# REGISTRATION SCHEDULER
# PART 1 / 6
# =========================================================

import json
import os
import traceback
from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands, tasks

from database.schema import (
    create_schedule,
    get_active_schedules,
    update_status,
)


# =========================================================
# TIMEZONE
# =========================================================

KSA = ZoneInfo("Asia/Riyadh")


# =========================================================
# FILES
# =========================================================

INDEPENDENT_CLOSE_FILE = "data/independent_closes.json"


# =========================================================
# STAFF ROLE IDs
# =========================================================

GENRA_TEAM_ROLE_ID = 1392127622430986392

OPERATION_MANAGER_ROLE_ID = 1392127621420027956

CEO_ROLE_ID = 1392127618815627466


STAFF_ROLE_IDS = {
    GENRA_TEAM_ROLE_ID,
    OPERATION_MANAGER_ROLE_ID,
    CEO_ROLE_ID,
}


# =========================================================
# DEFAULT CLOSING MESSAGE
# =========================================================

DEFAULT_CLOSING_MESSAGE = (
    "🔒 REGISTRATION IS NOW CLOSED!\n\n"
    "Please check the WhatsApp group for the Group ID 📱\n\n"
    "⚠️ If you have any problem or need assistance, "
    "please contact the room organizer.\n\n"
    "Thank you for your cooperation & good luck! 🏆❤️‍🔥\n\n"
    "━━━━━━━━━━━━━━\n\n"
    "🔒 التسجيل مغلق الآن!\n\n"
    "يرجى التوجه إلى مجموعة الواتساب للاطلاع على "
    "رقم المجموعة (Group ID) 📱\n\n"
    "⚠️ في حال وجود أي مشكلة أو استفسار، يرجى التواصل "
    "مع منظم الروم.\n\n"
    "شكرًا لتعاونكم وبالتوفيق للجميع! 🏆❤️‍🔥"
)


# =========================================================
# STAFF PERMISSION
# =========================================================

def is_staff(
    interaction: discord.Interaction,
) -> bool:

    if interaction.guild is None:
        return False

    member = interaction.user

    if not isinstance(
        member,
        discord.Member,
    ):
        return False

    # -----------------------------------------------------
    # DISCORD ADMINISTRATOR
    # -----------------------------------------------------

    if member.guild_permissions.administrator:
        return True

    # -----------------------------------------------------
    # GENRA TEAM / OPERATION MANAGER / CEO
    # -----------------------------------------------------

    return any(
        role.id in STAFF_ROLE_IDS
        for role in member.roles
    )


async def staff_only(
    interaction: discord.Interaction,
) -> bool:

    if is_staff(interaction):
        return True

    message = (
        "❌ You are not authorized to use this command."
    )

    try:

        if interaction.response.is_done():

            await interaction.followup.send(
                message,
                ephemeral=True,
            )

        else:

            await interaction.response.send_message(
                message,
                ephemeral=True,
            )

    except Exception:
        pass

    return False


# =========================================================
# SAFE ROW ACCESS
# =========================================================

def row_value(
    row,
    key,
    default=None,
):

    """
    Safely read values from:

    - sqlite3.Row
    - normal dictionaries
    - other mapping-like objects

    IMPORTANT:
    sqlite3.Row does NOT support .get()
    """

    try:

        if isinstance(row, dict):

            return row.get(
                key,
                default,
            )

        return row[key]

    except (
        KeyError,
        IndexError,
        TypeError,
    ):

        return default


# =========================================================
# FORMAT KSA DATE
# =========================================================

def format_ksa(
    dt: datetime,
) -> str:

    return dt.astimezone(
        KSA
    ).strftime(
        "%d/%m/%Y %H:%M KSA"
    )


# =========================================================
# INDEPENDENT CLOSE FILE
# =========================================================

def load_independent_closes():

    os.makedirs(
        "data",
        exist_ok=True,
    )

    if not os.path.exists(
        INDEPENDENT_CLOSE_FILE
    ):
        return []

    try:

        with open(
            INDEPENDENT_CLOSE_FILE,
            "r",
            encoding="utf-8",
        ) as file:

            data = json.load(file)

            if not isinstance(
                data,
                list,
            ):
                return []

            return data

    except Exception as error:

        print(
            "❌ Could not load independent closes: "
            f"{error!r}"
        )

        return []


def save_independent_closes(
    closes,
):

    os.makedirs(
        "data",
        exist_ok=True,
    )

    try:

        with open(
            INDEPENDENT_CLOSE_FILE,
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                closes,
                file,
                ensure_ascii=False,
                indent=4,
            )

    except Exception as error:

        print(
            "❌ Could not save independent closes: "
            f"{error!r}"
        )


# =========================================================
# PLACEHOLDERS
# =========================================================

def replace_placeholders(
    message,
    role=None,
    name=None,
    channels=None,
):

    if not isinstance(
        message,
        str,
    ):
        message = str(
            message or ""
        )

    # -----------------------------------------------------
    # {role}
    # -----------------------------------------------------

    if role is not None:

        message = message.replace(
            "{role}",
            role.mention,
        )

    else:

        message = message.replace(
            "{role}",
            "",
        )

    # -----------------------------------------------------
    # {name}
    # -----------------------------------------------------

    if name is not None:

        message = message.replace(
            "{name}",
            str(name),
        )

    else:

        message = message.replace(
            "{name}",
            "",
        )

    # -----------------------------------------------------
    # {channels}
    # -----------------------------------------------------

    if channels:

        channel_mentions = " ".join(
            channel.mention
            for channel in channels
        )

        message = message.replace(
            "{channels}",
            channel_mentions,
        )

    else:

        message = message.replace(
            "{channels}",
            "",
        )

    return message


# =========================================================
# CHANNEL PERMISSIONS
# =========================================================

async def set_registration_permissions(
    channel,
    role,
    can_write: bool,
):

    """
    Registration channel permission system.

    OPEN:
        Selected role:
            view_channel = True
            send_messages = True
            send_messages_in_threads = True

    CLOSED:
        Selected role:
            view_channel = True
            send_messages = False
            send_messages_in_threads = False

    IMPORTANT:
        @everyone is NOT modified.
        Bot permissions are NOT modified.
    """

    if channel is None:
        return False

    if role is None:
        return False

    try:

        # -------------------------------------------------
        # Get existing overwrite for selected role
        # -------------------------------------------------

        overwrite = channel.overwrites_for(
            role
        )

        # -------------------------------------------------
        # ROLE CAN ALWAYS SEE THE CHANNEL
        # -------------------------------------------------

        overwrite.view_channel = True

        # -------------------------------------------------
        # OPEN / CLOSED WRITE PERMISSION
        # -------------------------------------------------

        overwrite.send_messages = can_write

        overwrite.send_messages_in_threads = (
            can_write
        )

        # -------------------------------------------------
        # APPLY ONLY TO SELECTED ROLE
        # -------------------------------------------------

        await channel.set_permissions(
            role,
            overwrite=overwrite,
            reason=(
                "Registration scheduler: "
                + (
                    "registration opened"
                    if can_write
                    else "registration closed"
                )
            ),
        )

        print(
            f"🔧 #{channel.name} → "
            f"{role.name}: "
            + (
                "VIEW + WRITE"
                if can_write
                else "VIEW ONLY"
            )
        )

        return True

    except discord.Forbidden:

        print(
            f"❌ Missing permission to edit "
            f"#{channel.name}"
        )

    except Exception as error:

        print(
            f"❌ Could not update permissions "
            f"for #{channel.name}: "
            f"{error!r}"
        )

        traceback.print_exc()

    return False# =========================================================
# SCHEDULE VIEW
# PART 2 / 6
# =========================================================

class ScheduleView(discord.ui.View):

    def __init__(
        self,
        cog,
    ):

        super().__init__(
            timeout=300
        )

        self.cog = cog
        self.channels = []
        self.role = None

    # =====================================================
    # CHANNEL SELECT
    # =====================================================

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        channel_types=[
            discord.ChannelType.text
        ],
        placeholder="Select registration channels",
        min_values=1,
        max_values=25,
    )
    async def channel_select(
        self,
        interaction: discord.Interaction,
        select: discord.ui.ChannelSelect,
    ):

        if not await staff_only(interaction):
            return

        self.channels = list(
            select.values
        )

        await interaction.response.send_message(
            f"✅ Selected {len(self.channels)} "
            f"registration channel(s).",
            ephemeral=True,
        )

    # =====================================================
    # ROLE SELECT
    # =====================================================

    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="Select registration role",
        min_values=1,
        max_values=1,
    )
    async def role_select(
        self,
        interaction: discord.Interaction,
        select: discord.ui.RoleSelect,
    ):

        if not await staff_only(interaction):
            return

        self.role = select.values[0]

        await interaction.response.send_message(
            f"✅ Selected registration role: "
            f"{self.role.mention}",
            ephemeral=True,
        )

    # =====================================================
    # CONTINUE
    # =====================================================

    @discord.ui.button(
        label="Continue",
        style=discord.ButtonStyle.green,
        emoji="➡️",
    )
    async def continue_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        if not await staff_only(interaction):
            return

        if not self.channels:

            await interaction.response.send_message(
                "❌ Select at least one channel.",
                ephemeral=True,
            )

            return

        if self.role is None:

            await interaction.response.send_message(
                "❌ Select a registration role.",
                ephemeral=True,
            )

            return

        await interaction.response.send_modal(
            ScheduleModal(
                self.cog,
                self.channels,
                self.role,
            )
        )

    # =====================================================
    # ERROR
    # =====================================================

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        item,
    ):

        print(
            "❌ ScheduleView ERROR"
        )

        traceback.print_exc()

        try:

            if interaction.response.is_done():

                await interaction.followup.send(
                    f"❌ Error: {error}",
                    ephemeral=True,
                )

            else:

                await interaction.response.send_message(
                    f"❌ Error: {error}",
                    ephemeral=True,
                )

        except Exception:
            pass# =========================================================
# SCHEDULE MODAL
# PART 3 / 6
# =========================================================

class ScheduleModal(
    discord.ui.Modal,
    title="Create Registration Schedule",
):

    registration_name = discord.ui.TextInput(
        label="Registration name",
        placeholder="Example: CLASH REGISTRATION",
        required=True,
        max_length=100,
    )

    opening_date = discord.ui.TextInput(
        label="Opening date",
        placeholder="DD/MM/YYYY",
        required=True,
        max_length=10,
    )

    opening_time = discord.ui.TextInput(
        label="Opening time - KSA",
        placeholder="20:00",
        required=True,
        max_length=5,
    )

    closing_time = discord.ui.TextInput(
        label="Closing time - KSA",
        placeholder="23:00",
        required=True,
        max_length=5,
    )

    opening_message = discord.ui.TextInput(
        label="Opening message",
        placeholder=(
            "Write your message here.\n"
            "You can use {role}, {name}, {channels}"
        ),
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1800,
    )

    def __init__(
        self,
        cog,
        channels,
        role,
    ):

        super().__init__()

        self.cog = cog

        self.channels = list(
            channels
        )

        self.role = role

    # =====================================================
    # SUBMIT
    # =====================================================

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ):

        if not await staff_only(interaction):
            return

        # -------------------------------------------------
        # READ VALUES
        # -------------------------------------------------

        registration_name = (
            self.registration_name.value.strip()
        )

        opening_date_text = (
            self.opening_date.value.strip()
        )

        opening_time_text = (
            self.opening_time.value.strip()
        )

        closing_time_text = (
            self.closing_time.value.strip()
        )

        opening_message = (
            self.opening_message.value.strip()
        )

        # -------------------------------------------------
        # PARSE DATE/TIME
        # -------------------------------------------------

        try:

            opening_date_value = datetime.strptime(
                opening_date_text,
                "%d/%m/%Y",
            )

            opening_time_value = datetime.strptime(
                opening_time_text,
                "%H:%M",
            )

            closing_time_value = datetime.strptime(
                closing_time_text,
                "%H:%M",
            )

        except ValueError:

            await interaction.response.send_message(
                "❌ Invalid date or time format.\n\n"
                "Opening date: `DD/MM/YYYY`\n"
                "Opening time: `HH:MM`\n"
                "Closing time: `HH:MM`",
                ephemeral=True,
            )

            return

        # -------------------------------------------------
        # OPEN DATETIME
        # -------------------------------------------------

        open_datetime = datetime(
            opening_date_value.year,
            opening_date_value.month,
            opening_date_value.day,
            opening_time_value.hour,
            opening_time_value.minute,
            tzinfo=KSA,
        )

        # -------------------------------------------------
        # CLOSE DATETIME
        #
        # Same date as opening date.
        # -------------------------------------------------

        close_datetime = datetime(
            opening_date_value.year,
            opening_date_value.month,
            opening_date_value.day,
            closing_time_value.hour,
            closing_time_value.minute,
            tzinfo=KSA,
        )

        now = datetime.now(KSA)

        # -------------------------------------------------
        # OPENING MUST BE FUTURE
        # -------------------------------------------------

        if open_datetime <= now:

            await interaction.response.send_message(
                "❌ The opening date/time "
                "must be in the future.",
                ephemeral=True,
            )

            return

        # -------------------------------------------------
        # CLOSE MUST BE AFTER OPEN
        # -------------------------------------------------

        if close_datetime <= open_datetime:

            await interaction.response.send_message(
                "❌ The closing time must be "
                "after the opening time.\n\n"
                "Both times use the same date.",
                ephemeral=True,
            )

            return

        # -------------------------------------------------
        # CREATE DATABASE SCHEDULE
        # -------------------------------------------------

        try:

            schedule_id = create_schedule(
                name=registration_name,
                channel_ids=[
                    channel.id
                    for channel in self.channels
                ],
                role_id=self.role.id,
                open_datetime=(
                    open_datetime.isoformat()
                ),
                close_datetime=(
                    close_datetime.isoformat()
                ),
                message=opening_message,
            )

        except Exception as error:

            print(
                "❌ Could not create schedule: "
                f"{error!r}"
            )

            traceback.print_exc()

            await interaction.response.send_message(
                "❌ Could not create the schedule.\n"
                "Please check the database.",
                ephemeral=True,
            )

            return

        # -------------------------------------------------
        # CHANNEL LIST
        # -------------------------------------------------

        channels_text = "\n".join(
            channel.mention
            for channel in self.channels
        )

        # -------------------------------------------------
        # EMBED
        # -------------------------------------------------

        embed = discord.Embed(
            title="✅ Registration Scheduled",
            color=discord.Color.green(),
        )

        embed.add_field(
            name="Registration",
            value=registration_name,
            inline=False,
        )

        embed.add_field(
            name="Opening",
            value=format_ksa(
                open_datetime
            ),
            inline=True,
        )

        embed.add_field(
            name="Closing",
            value=format_ksa(
                close_datetime
            ),
            inline=True,
        )

        embed.add_field(
            name="Registration Role",
            value=self.role.mention,
            inline=False,
        )

        embed.add_field(
            name="Channels",
            value=(
                channels_text[:1024]
                if channels_text
                else "None"
            ),
            inline=False,
        )

        embed.add_field(
            name="Opening Message",
            value=(
                opening_message[:1024]
                if opening_message
                else "None"
            ),
            inline=False,
        )

        embed.set_footer(
            text=(
                f"Schedule ID: {schedule_id} "
                f"• Closing uses opening date"
            )
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )

    # =====================================================
    # MODAL ERROR
    # =====================================================

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
    ):

        print(
            "❌ ScheduleModal ERROR"
        )

        traceback.print_exc()

        try:

            if interaction.response.is_done():

                await interaction.followup.send(
                    f"❌ Error: {error}",
                    ephemeral=True,
                )

            else:

                await interaction.response.send_message(
                    f"❌ Error: {error}",
                    ephemeral=True,
                )

        except Exception:
            pass# =========================================================
# INDEPENDENT CLOSE VIEW
# PART 4 / 6
# =========================================================

class IndependentCloseView(
    discord.ui.View
):

    def __init__(
        self,
        cog,
    ):

        super().__init__(
            timeout=300
        )

        self.cog = cog
        self.channels = []
        self.role = None

    # =====================================================
    # CHANNEL SELECT
    # =====================================================

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        channel_types=[
            discord.ChannelType.text
        ],
        placeholder="Select closing channels",
        min_values=1,
        max_values=25,
    )
    async def channel_select(
        self,
        interaction: discord.Interaction,
        select: discord.ui.ChannelSelect,
    ):

        if not await staff_only(interaction):
            return

        self.channels = list(
            select.values
        )

        await interaction.response.send_message(
            f"✅ Selected {len(self.channels)} "
            f"channel(s) for closing.",
            ephemeral=True,
        )

    # =====================================================
    # ROLE SELECT
    # =====================================================

    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="Select the role to mention",
        min_values=1,
        max_values=1,
    )
    async def role_select(
        self,
        interaction: discord.Interaction,
        select: discord.ui.RoleSelect,
    ):

        if not await staff_only(interaction):
            return

        self.role = select.values[0]

        await interaction.response.send_message(
            f"✅ Selected role: "
            f"{self.role.mention}",
            ephemeral=True,
        )

    # =====================================================
    # CONTINUE
    # =====================================================

    @discord.ui.button(
        label="Continue",
        style=discord.ButtonStyle.red,
        emoji="➡️",
    )
    async def continue_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        if not await staff_only(interaction):
            return

        if not self.channels:

            await interaction.response.send_message(
                "❌ Select at least one channel.",
                ephemeral=True,
            )

            return

        if self.role is None:

            await interaction.response.send_message(
                "❌ Select a role to mention.",
                ephemeral=True,
            )

            return

        await interaction.response.send_modal(
            IndependentCloseModal(
                self.cog,
                self.channels,
                self.role,
            )
        )

    # =====================================================
    # ERROR
    # =====================================================

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        item,
    ):

        print(
            "❌ IndependentCloseView ERROR"
        )

        traceback.print_exc()


# =========================================================
# INDEPENDENT CLOSE MODAL
# =========================================================

class IndependentCloseModal(
    discord.ui.Modal
):

    def __init__(
        self,
        cog,
        channels,
        role,
    ):

        super().__init__(
            title="Schedule Registration Close"
        )

        self.cog = cog
        self.channels = list(channels)
        self.role = role

    # =====================================================
    # CLOSING DATE
    # =====================================================

    closing_date = discord.ui.TextInput(
        label="Closing date",
        placeholder="DD/MM/YYYY",
        required=True,
        max_length=10,
    )

    # =====================================================
    # CLOSING TIME
    # =====================================================

    closing_time = discord.ui.TextInput(
        label="Closing time - KSA",
        placeholder="23:00",
        required=True,
        max_length=5,
    )

    # =====================================================
    # CLOSING MESSAGE
    # =====================================================

    closing_message = discord.ui.TextInput(
        label="Closing message",
        placeholder=(
            "Write your closing message here.\n"
            "You can use {role}, {channels}"
        ),
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1800,
    )

    # =====================================================
    # SUBMIT
    # =====================================================

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ):

        if not await staff_only(interaction):
            return

        try:

            date_value = datetime.strptime(
                self.closing_date.value.strip(),
                "%d/%m/%Y",
            )

            time_value = datetime.strptime(
                self.closing_time.value.strip(),
                "%H:%M",
            )

        except ValueError:

            await interaction.response.send_message(
                "❌ Invalid date or time.\n\n"
                "Date: `DD/MM/YYYY`\n"
                "Time: `HH:MM`",
                ephemeral=True,
            )

            return

        close_datetime = datetime(
            date_value.year,
            date_value.month,
            date_value.day,
            time_value.hour,
            time_value.minute,
            tzinfo=KSA,
        )

        now = datetime.now(KSA)

        if close_datetime <= now:

            await interaction.response.send_message(
                "❌ The closing date/time "
                "must be in the future.",
                ephemeral=True,
            )

            return

        # -------------------------------------------------
        # CREATE NEXT ID
        # -------------------------------------------------

        closes = load_independent_closes()

        next_id = 1

        if closes:

            valid_ids = []

            for item in closes:

                try:

                    valid_ids.append(
                        int(item["id"])
                    )

                except (
                    KeyError,
                    TypeError,
                    ValueError,
                ):

                    continue

            if valid_ids:

                next_id = max(
                    valid_ids
                ) + 1

        # -------------------------------------------------
        # SAVE CLOSE
        # -------------------------------------------------

        close_data = {
            "id": next_id,

            "channel_ids": [
                channel.id
                for channel in self.channels
            ],

            "role_id": self.role.id,

            "guild_id": (
                self.channels[0].guild.id
                if self.channels
                else 0
            ),

            "close_datetime": (
                close_datetime.isoformat()
            ),

            "message": (
                self.closing_message.value.strip()
            ),

            "status": "scheduled",
        }

        closes.append(
            close_data
        )

        save_independent_closes(
            closes
        )

        # -------------------------------------------------
        # CHANNEL LIST
        # -------------------------------------------------

        channels_text = "\n".join(
            channel.mention
            for channel in self.channels
        )

        # -------------------------------------------------
        # EMBED
        # -------------------------------------------------

        embed = discord.Embed(
            title="🔒 Registration Close Scheduled",
            color=discord.Color.red(),
        )

        embed.add_field(
            name="Channels",
            value=(
                channels_text[:1024]
                if channels_text
                else "None"
            ),
            inline=False,
        )

        embed.add_field(
            name="Mention Role",
            value=self.role.mention,
            inline=False,
        )

        embed.add_field(
            name="Closing",
            value=format_ksa(
                close_datetime
            ),
            inline=False,
        )

        embed.add_field(
            name="Closing Message",
            value=(
                self.closing_message.value[:1024]
            ),
            inline=False,
        )

        embed.set_footer(
            text=f"Close ID: {next_id}"
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )

    # =====================================================
    # ERROR
    # =====================================================

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
    ):

        print(
            "❌ IndependentCloseModal ERROR"
        )

        traceback.print_exc()

        try:

            if interaction.response.is_done():

                await interaction.followup.send(
                    f"❌ Error: {error}",
                    ephemeral=True,
                )

            else:

                await interaction.response.send_message(
                    f"❌ Error: {error}",
                    ephemeral=True,
                )

        except Exception:
            pass# =========================================================
# REGISTRATION SCHEDULER
# PART 5 / 6
# =========================================================

class RegistrationScheduler(
    commands.Cog
):

    def __init__(
        self,
        bot,
    ):

        self.bot = bot

        self.scheduler_loop.start()

    def cog_unload(self):

        self.scheduler_loop.cancel()

    # =====================================================
    # AUTOMATIC SCHEDULER
    # =====================================================

    @tasks.loop(seconds=30)
    async def scheduler_loop(self):

        if not self.bot.is_ready():
            return

        # -------------------------------------------------
        # REGULAR SCHEDULES
        # -------------------------------------------------

        try:

            await self.process_regular_schedules()

        except Exception as error:

            print(
                "❌ Regular scheduler error: "
                f"{error!r}"
            )

            traceback.print_exc()

        # -------------------------------------------------
        # INDEPENDENT CLOSES
        # -------------------------------------------------

        try:

            await self.process_independent_closes()

        except Exception as error:

            print(
                "❌ Independent close error: "
                f"{error!r}"
            )

            traceback.print_exc()

    # =====================================================
    # BEFORE LOOP
    # =====================================================

    @scheduler_loop.before_loop
    async def before_scheduler(self):

        await self.bot.wait_until_ready()

        print(
            "🟢 Registration scheduler started."
        )

    # =====================================================
    # GET CHANNELS
    # =====================================================

    async def get_channels(
        self,
        schedule,
    ):

        channels = []

        channel_ids = row_value(
            schedule,
            "channel_ids",
            [],
        )

        if channel_ids is None:

            return channels

        # -------------------------------------------------
        # SQLite may return JSON string
        # -------------------------------------------------

        if isinstance(
            channel_ids,
            str,
        ):

            text = channel_ids.strip()

            if not text:

                channel_ids = []

            else:

                # Try JSON first
                try:

                    parsed = json.loads(text)

                    if isinstance(
                        parsed,
                        list,
                    ):

                        channel_ids = parsed

                    else:

                        channel_ids = [
                            text
                        ]

                except Exception:

                    # Old comma-separated format
                    channel_ids = [
                        item.strip()
                        for item in text.split(",")
                        if item.strip()
                    ]

        # -------------------------------------------------
        # Single integer
        # -------------------------------------------------

        elif isinstance(
            channel_ids,
            int,
        ):

            channel_ids = [
                channel_ids
            ]

        # -------------------------------------------------
        # Find channels
        # -------------------------------------------------

        for channel_id in channel_ids:

            try:

                channel = self.bot.get_channel(
                    int(channel_id)
                )

                if channel is not None:

                    channels.append(
                        channel
                    )

            except (
                ValueError,
                TypeError,
            ):

                continue

        return channels

    # =====================================================
    # GET SCHEDULE ID
    # =====================================================

    def get_schedule_id(
        self,
        schedule,
    ):

        return row_value(
            schedule,
            "id",
            "?",
        )

    # =====================================================
    # PROCESS REGULAR SCHEDULES
    # =====================================================

    async def process_regular_schedules(
        self,
    ):

        try:

            schedules = get_active_schedules()

        except Exception as error:

            print(
                "❌ Could not load schedules: "
                f"{error!r}"
            )

            traceback.print_exc()

            return

        now = datetime.now(KSA)

        for schedule in schedules:

            schedule_id = (
                self.get_schedule_id(
                    schedule
                )
            )

            try:

                open_text = row_value(
                    schedule,
                    "open_datetime",
                )

                close_text = row_value(
                    schedule,
                    "close_datetime",
                )

                status = row_value(
                    schedule,
                    "status",
                )

                if not open_text or not close_text:

                    print(
                        f"❌ Schedule "
                        f"{schedule_id}: "
                        "missing datetime."
                    )

                    continue

                open_datetime = (
                    datetime.fromisoformat(
                        open_text
                    )
                )

                close_datetime = (
                    datetime.fromisoformat(
                        close_text
                    )
                )

                # -------------------------------------------------
                # OPEN
                # -------------------------------------------------

                if (
                    status == "scheduled"
                    and now >= open_datetime
                ):

                    await self.open_registration(
                        schedule
                    )

                # -------------------------------------------------
                # CLOSE
                # -------------------------------------------------

                elif (
                    status == "open"
                    and now >= close_datetime
                ):

                    await self.close_registration(
                        schedule
                    )

            except Exception as error:

                print(
                    f"❌ Schedule "
                    f"{schedule_id} "
                    f"error: {error!r}"
                )

                traceback.print_exc()

    # =====================================================
    # OPEN REGISTRATION
    # =====================================================

    async def open_registration(
        self,
        schedule,
    ):

        schedule_id = (
            self.get_schedule_id(
                schedule
            )
        )

        channels = await self.get_channels(
            schedule
        )

        if not channels:

            print(
                f"❌ Schedule "
                f"{schedule_id}: "
                "no channels found."
            )

            return

        # -------------------------------------------------
        # GUILD
        # -------------------------------------------------

        guild = channels[0].guild

        # -------------------------------------------------
        # ROLE
        # -------------------------------------------------

        role_id = row_value(
            schedule,
            "role_id",
        )

        role = None

        try:

            role = guild.get_role(
                int(role_id)
            )

        except (
            TypeError,
            ValueError,
        ):

            role = None

        if role is None:

            print(
                f"❌ Schedule "
                f"{schedule_id}: "
                "registration role not found."
            )

            return

        # -------------------------------------------------
        # ENABLE WRITE PERMISSION
        # -------------------------------------------------

        permission_success = 0

        for channel in channels:

            if await set_registration_permissions(
                channel,
                role,
                True,
            ):

                permission_success += 1

        # -------------------------------------------------
        # MESSAGE
        # -------------------------------------------------

        message = row_value(
            schedule,
            "message",
            "",
        )

        name = row_value(
            schedule,
            "name",
            "",
        )

        message = replace_placeholders(
            message,
            role=role,
            name=name,
            channels=channels,
        )

        # -------------------------------------------------
        # SEND OPENING MESSAGE
        # -------------------------------------------------

        successful_channels = 0

        for channel in channels:

            try:

                await channel.send(
                    message,
                    allowed_mentions=(
                        discord.AllowedMentions(
                            roles=True
                        )
                    ),
                )

                successful_channels += 1

                print(
                    f"🟢 Registration opened: "
                    f"{schedule_id} "
                    f"→ #{channel.name}"
                )

            except Exception as error:

                print(
                    f"❌ Could not open "
                    f"schedule {schedule_id} "
                    f"in #{channel.name}: "
                    f"{error!r}"
                )

        # -------------------------------------------------
        # MARK OPEN
        # -------------------------------------------------

        if (
            successful_channels > 0
            or permission_success > 0
        ):

            try:

                update_status(
                    schedule_id,
                    "open",
                )

            except Exception as error:

                print(
                    f"❌ Could not update "
                    f"schedule {schedule_id}: "
                    f"{error!r}"
                )

    # =====================================================
    # CLOSE REGISTRATION
    # =====================================================

    async def close_registration(
        self,
        schedule,
    ):

        schedule_id = (
            self.get_schedule_id(
                schedule
            )
        )

        channels = await self.get_channels(
            schedule
        )

        if not channels:

            print(
                f"❌ Schedule "
                f"{schedule_id}: "
                "no channels found for closing."
            )

            return

        guild = channels[0].guild

        # -------------------------------------------------
        # ROLE
        # -------------------------------------------------

        role_id = row_value(
            schedule,
            "role_id",
        )

        role = None

        try:

            role = guild.get_role(
                int(role_id)
            )

        except (
            TypeError,
            ValueError,
        ):

            role = None

        if role is None:

            print(
                f"❌ Schedule "
                f"{schedule_id}: "
                "registration role not found."
            )

            return

        # -------------------------------------------------
        # DISABLE WRITE
        #
        # ROLE CAN STILL SEE CHANNEL
        # -------------------------------------------------

        permission_success = 0

        for channel in channels:

            if await set_registration_permissions(
                channel,
                role,
                False,
            ):

                permission_success += 1

        # -------------------------------------------------
        # CLOSING MESSAGE
        # -------------------------------------------------

        message = DEFAULT_CLOSING_MESSAGE

        name = row_value(
            schedule,
            "name",
            "",
        )

        message = replace_placeholders(
            message,
            role=role,
            name=name,
            channels=channels,
        )

        # -------------------------------------------------
        # SEND CLOSING MESSAGE
        # -------------------------------------------------

        successful_channels = 0

        for channel in channels:

            try:

                await channel.send(
                    message,
                    allowed_mentions=(
                        discord.AllowedMentions(
                            roles=True
                        )
                    ),
                )

                successful_channels += 1

                print(
                    f"🔴 Registration closed: "
                    f"{schedule_id} "
                    f"→ #{channel.name}"
                )

            except Exception as error:

                print(
                    f"❌ Could not close "
                    f"schedule {schedule_id} "
                    f"in #{channel.name}: "
                    f"{error!r}"
                )

        # -------------------------------------------------
        # MARK CLOSED
        # -------------------------------------------------

        if (
            successful_channels > 0
            or permission_success > 0
        ):

            try:

                update_status(
                    schedule_id,
                    "closed",
                )

            except Exception as error:

                print(
                    f"❌ Could not update close "
                    f"status for "
                    f"{schedule_id}: "
                    f"{error!r}"
                )# =========================================================
# INDEPENDENT CLOSES
# PART 6 / 6
# =========================================================

    async def process_independent_closes(
        self,
    ):

        closes = load_independent_closes()

        if not closes:
            return

        now = datetime.now(KSA)

        changed = False

        for close_data in closes:

            if close_data.get(
                "status"
            ) != "scheduled":

                continue

            try:

                close_datetime = (
                    datetime.fromisoformat(
                        close_data[
                            "close_datetime"
                        ]
                    )
                )

                if now < close_datetime:
                    continue

                # -------------------------------------------------
                # CHANNEL IDS
                # -------------------------------------------------

                if "channel_ids" in close_data:

                    channel_ids = close_data[
                        "channel_ids"
                    ]

                elif "channel_id" in close_data:

                    channel_ids = [
                        close_data[
                            "channel_id"
                        ]
                    ]

                else:

                    print(
                        "❌ Independent close "
                        f"{close_data.get('id', '?')}: "
                        "no channels."
                    )

                    close_data[
                        "status"
                    ] = "error"

                    changed = True

                    continue

                # -------------------------------------------------
                # NORMALIZE CHANNEL IDS
                # -------------------------------------------------

                if isinstance(
                    channel_ids,
                    str,
                ):

                    try:

                        parsed = json.loads(
                            channel_ids
                        )

                        if isinstance(
                            parsed,
                            list,
                        ):

                            channel_ids = parsed

                        else:

                            channel_ids = [
                                channel_ids
                            ]

                    except Exception:

                        channel_ids = [
                            item.strip()
                            for item in channel_ids.split(",")
                            if item.strip()
                        ]

                elif isinstance(
                    channel_ids,
                    int,
                ):

                    channel_ids = [
                        channel_ids
                    ]

                # -------------------------------------------------
                # GET CHANNELS
                # -------------------------------------------------

                channels = []

                for channel_id in channel_ids:

                    try:

                        channel = (
                            self.bot.get_channel(
                                int(channel_id)
                            )
                        )

                        if channel is not None:

                            channels.append(
                                channel
                            )

                    except (
                        ValueError,
                        TypeError,
                    ):

                        continue

                if not channels:

                    print(
                        "❌ Independent close "
                        f"{close_data.get('id', '?')}: "
                        "channels not found."
                    )

                    close_data[
                        "status"
                    ] = "error"

                    changed = True

                    continue

                # -------------------------------------------------
                # GET ROLE
                # -------------------------------------------------

                role = None

                try:

                    role = channels[
                        0
                    ].guild.get_role(
                        int(
                            close_data[
                                "role_id"
                            ]
                        )
                    )

                except (
                    KeyError,
                    TypeError,
                    ValueError,
                ):

                    role = None

                if role is None:

                    print(
                        "❌ Independent close "
                        f"{close_data.get('id', '?')}: "
                        "role not found."
                    )

                    close_data[
                        "status"
                    ] = "error"

                    changed = True

                    continue

                # -------------------------------------------------
                # CLOSE PERMISSIONS
                #
                # ROLE CAN SEE
                # ROLE CANNOT WRITE
                # -------------------------------------------------

                for channel in channels:

                    await set_registration_permissions(
                        channel,
                        role,
                        False,
                    )

                # -------------------------------------------------
                # SEND CLOSE MESSAGE
                # -------------------------------------------------

                await self.close_multiple_channels(
                    channels,
                    role,
                    close_data.get(
                        "message",
                        DEFAULT_CLOSING_MESSAGE,
                    ),
                )

                close_data[
                    "status"
                ] = "closed"

                changed = True

                print(
                    "🔒 Independent close "
                    f"{close_data.get('id', '?')} "
                    "completed."
                )

            except Exception as error:

                close_id = close_data.get(
                    "id",
                    "?",
                )

                print(
                    f"❌ Independent close "
                    f"{close_id} "
                    f"error: {error!r}"
                )

                traceback.print_exc()

        if changed:

            save_independent_closes(
                closes
            )

    # =====================================================
    # CLOSE MULTIPLE CHANNELS
    # =====================================================

    async def close_multiple_channels(
        self,
        channels,
        role,
        message,
    ):

        message = replace_placeholders(
            message,
            role=role,
            channels=channels,
        )

        for channel in channels:

            try:

                await channel.send(
                    message,
                    allowed_mentions=(
                        discord.AllowedMentions(
                            roles=True
                        )
                    ),
                )

                print(
                    f"🔒 Close message sent "
                    f"→ #{channel.name}"
                )

            except Exception as error:

                print(
                    f"❌ Could not send close "
                    f"message in "
                    f"#{channel.name}: "
                    f"{error!r}"
                )

    # =====================================================
    # /schedule
    # =====================================================

    @app_commands.command(
        name="schedule",
        description=(
            "Create a registration schedule."
        ),
    )
    async def schedule_command(
        self,
        interaction: discord.Interaction,
    ):

        if not await staff_only(
            interaction
        ):
            return

        await interaction.response.send_message(
            "📅 **Create Registration Schedule**\n\n"
            "Select the registration channels "
            "and the role to receive access.\n\n"
            "🟢 When registration opens, "
            "the selected role can see and write.\n"
            "🔴 When registration closes, "
            "the selected role can still see "
            "but cannot write.\n\n"
            "⏰ Closing date automatically uses "
            "the same date as the opening date.",
            view=ScheduleView(self),
            ephemeral=True,
        )

    # =====================================================
    # /close
    # =====================================================

    @app_commands.command(
        name="close",
        description=(
            "Schedule an independent "
            "registration close."
        ),
    )
    async def close_command(
        self,
        interaction: discord.Interaction,
    ):

        if not await staff_only(
            interaction
        ):
            return

        await interaction.response.send_message(
            "🔒 **Schedule Registration Close**\n\n"
            "Select the channels and the role "
            "to mention.\n\n"
            "The selected role will keep "
            "channel visibility but will "
            "lose write permission.",
            view=IndependentCloseView(self),
            ephemeral=True,
        )

    # =====================================================
    # /clear_users
    #
    # Deletes USER messages only.
    # BOT messages are kept.
    # =====================================================

    @app_commands.command(
        name="clear_users",
        description=(
            "Delete user messages from "
            "selected channels."
        ),
    )
    async def clear_users_command(
        self,
        interaction: discord.Interaction,
    ):

        if not await staff_only(
            interaction
        ):
            return

        await interaction.response.send_message(
            "🧹 **Clear User Messages**\n\n"
            "Select the channels where you want "
            "to delete user messages.\n\n"
            "🤖 Bot messages will NOT be deleted.",
            view=ClearUsersView(self),
            ephemeral=True,
        )


# =========================================================
# CLEAR USERS VIEW
# =========================================================

class ClearUsersView(
    discord.ui.View
):

    def __init__(
        self,
        cog,
    ):

        super().__init__(
            timeout=300
        )

        self.cog = cog
        self.channels = []

    # =====================================================
    # CHANNEL SELECT
    # =====================================================

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        channel_types=[
            discord.ChannelType.text
        ],
        placeholder="Select channels to clear",
        min_values=1,
        max_values=25,
    )
    async def channel_select(
        self,
        interaction: discord.Interaction,
        select: discord.ui.ChannelSelect,
    ):

        if not await staff_only(
            interaction
        ):
            return

        self.channels = list(
            select.values
        )

        await interaction.response.send_message(
            f"✅ Selected "
            f"{len(self.channels)} "
            f"channel(s).",
            ephemeral=True,
        )

    # =====================================================
    # CLEAR BUTTON
    # =====================================================

    @discord.ui.button(
        label="Clear User Messages",
        style=discord.ButtonStyle.danger,
        emoji="🧹",
    )
    async def clear_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        if not await staff_only(
            interaction
        ):
            return

        if not self.channels:

            await interaction.response.send_message(
                "❌ Select at least one channel.",
                ephemeral=True,
            )

            return

        await interaction.response.defer(
            ephemeral=True
        )

        total_deleted = 0

        for channel in self.channels:

            try:

                deleted = 0

                # -------------------------------------------------
                # CHECK CHANNEL HISTORY
                # -------------------------------------------------

                async for message in channel.history(
                    limit=None
                ):

                    # -------------------------------------------------
                    # KEEP BOT MESSAGES
                    # -------------------------------------------------

                    if message.author.bot:
                        continue

                    try:

                        await message.delete()

                        deleted += 1

                    except discord.NotFound:

                        continue

                    except discord.Forbidden:

                        print(
                            f"❌ No permission to "
                            f"delete messages in "
                            f"#{channel.name}"
                        )

                        break

                    except discord.HTTPException:

                        continue

                total_deleted += deleted

                print(
                    f"🧹 Cleared {deleted} "
                    f"user messages from "
                    f"#{channel.name}"
                )

            except Exception as error:

                print(
                    f"❌ Could not clear "
                    f"#{channel.name}: "
                    f"{error!r}"
                )

                traceback.print_exc()

        # -------------------------------------------------
        # RESULT
        # -------------------------------------------------

        await interaction.followup.send(
            "🧹 **Clear completed!**\n\n"
            f"Deleted **{total_deleted}** "
            "user message(s).\n\n"
            "🤖 Bot messages were kept.",
            ephemeral=True,
        )


# =========================================================
# SETUP
# =========================================================

async def setup(
    bot,
):

    await bot.add_cog(
        RegistrationScheduler(bot)
    )

    print(
        "✅ registration_scheduler "
        "loaded successfully."
    )
