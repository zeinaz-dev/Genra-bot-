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
# CONFIGURATION
# =========================================================

KSA = ZoneInfo("Asia/Riyadh")

INDEPENDENT_CLOSE_FILE = "data/independent_closes.json"
AUTOCLEAR_FILE = "data/autoclear.json"


# =========================================================
# STAFF ROLE IDs
# =========================================================

GENRA_TEAM_ROLE_ID = 1392127622430986392
OPERATION_MANAGER_ROLE_ID = 1392127621420027956
CEO_ROLE_ID = 1392127618815627466


# =========================================================
# DEFAULT CLOSING MESSAGE
# =========================================================

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


# =========================================================
# STAFF PERMISSION
# =========================================================

def is_staff(interaction: discord.Interaction) -> bool:

    if interaction.guild is None:
        return False

    member = interaction.user

    if not isinstance(member, discord.Member):
        return False

    if member.guild_permissions.administrator:
        return True

    allowed_role_ids = {
        GENRA_TEAM_ROLE_ID,
        OPERATION_MANAGER_ROLE_ID,
        CEO_ROLE_ID,
    }

    return any(
        role.id in allowed_role_ids
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
# FORMAT DATE
# =========================================================

def format_ksa(dt: datetime) -> str:

    return dt.astimezone(KSA).strftime(
        "%d/%m/%Y %H:%M KSA"
    )


# =========================================================
# SAFE ROW ACCESS
# =========================================================
#
# sqlite3.Row does NOT support .get()
#
# Always use:
#     row["column"]
#
# This helper is only for optional values.
# =========================================================

def row_value(row, key, default=None):

    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return default


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

            if isinstance(data, list):
                return data

            return []

    except Exception as error:

        print(
            f"❌ Could not load independent closes: "
            f"{error!r}"
        )

        return []


def save_independent_closes(closes):

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
            f"❌ Could not save independent closes: "
            f"{error!r}"
        )


# =========================================================
# AUTOCLEAR FILE
# =========================================================

def load_autoclear_settings():

    os.makedirs(
        "data",
        exist_ok=True,
    )

    if not os.path.exists(
        AUTOCLEAR_FILE
    ):
        return []

    try:

        with open(
            AUTOCLEAR_FILE,
            "r",
            encoding="utf-8",
        ) as file:

            data = json.load(file)

            if isinstance(data, list):
                return data

            return []

    except Exception as error:

        print(
            f"❌ Could not load autoclear settings: "
            f"{error!r}"
        )

        return []


def save_autoclear_settings(settings):

    os.makedirs(
        "data",
        exist_ok=True,
    )

    try:

        with open(
            AUTOCLEAR_FILE,
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                settings,
                file,
                ensure_ascii=False,
                indent=4,
            )

    except Exception as error:

        print(
            f"❌ Could not save autoclear settings: "
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

    if not message:
        return ""

    if role is not None:

        message = message.replace(
            "{role}",
            role.mention,
        )

    if name is not None:

        message = message.replace(
            "{name}",
            str(name),
        )

    if channels:

        message = message.replace(
            "{channels}",
            " ".join(
                channel.mention
                for channel in channels
            ),
        )

    return message


# =========================================================
# CHANNEL PERMISSIONS
# =========================================================

async def set_registration_permissions(
    channel,
    role,
    can_write,
):

    if channel is None:
        return False

    if role is None:
        return False

    try:

        # Do NOT explicitly add @everyone.
        #
        # This removes the existing @everyone overwrite,
        # allowing the server's normal @everyone permissions
        # to apply.
        #
        # The selected registration role is then given the
        # required visibility/write permissions.

        try:
            await channel.set_permissions(
                channel.guild.default_role,
                overwrite=None,
            )
        except Exception:
            pass

        if can_write:

            await channel.set_permissions(
                role,
                view_channel=True,
                send_messages=True,
                send_messages_in_threads=True,
                read_message_history=True,
            )

        else:

            await channel.set_permissions(
                role,
                view_channel=True,
                send_messages=False,
                send_messages_in_threads=False,
                read_message_history=True,
            )

        return True

    except discord.Forbidden:

        print(
            f"❌ Missing permission to edit "
            f"#{channel.name}"
        )

        return False

    except discord.HTTPException as error:

        print(
            f"❌ Discord error editing "
            f"#{channel.name}: {error!r}"
        )

        return False

    except Exception as error:

        print(
            f"❌ Permission error in "
            f"#{channel.name}: {error!r}"
        )

        return False


# =========================================================
# SCHEDULE VIEW
# =========================================================

class ScheduleView(discord.ui.View):

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

        await interaction.response.defer()

    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="Select the registration role",
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

        await interaction.response.defer()

    @discord.ui.button(
        label="Continue",
        style=discord.ButtonStyle.green,
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

    async def on_error(
        self,
        interaction,
        error,
        item,
    ):

        print("❌ ScheduleView ERROR")
        traceback.print_exc()


# =========================================================
# SCHEDULE MODAL
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

    closing_datetime = discord.ui.TextInput(
        label="Closing date & time - KSA",
        placeholder="DD/MM/YYYY HH:MM",
        required=True,
        max_length=16,
    )

    opening_message = discord.ui.TextInput(
        label="Opening message",
        placeholder="Write your message here",
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
        self.channels = channels
        self.role = role

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ):

        if not await staff_only(interaction):
            return

        try:

            opening_date_value = datetime.strptime(
                self.opening_date.value.strip(),
                "%d/%m/%Y",
            )

            opening_time_value = datetime.strptime(
                self.opening_time.value.strip(),
                "%H:%M",
            )

            closing_datetime_value = datetime.strptime(
                self.closing_datetime.value.strip(),
                "%d/%m/%Y %H:%M",
            )

        except ValueError:

            await interaction.response.send_message(
                "❌ Invalid date or time format.\n\n"
                "Opening date: `DD/MM/YYYY`\n"
                "Opening time: `HH:MM`\n"
                "Closing date & time: `DD/MM/YYYY HH:MM`",
                ephemeral=True,
            )

            return

        open_datetime = datetime(
            opening_date_value.year,
            opening_date_value.month,
            opening_date_value.day,
            opening_time_value.hour,
            opening_time_value.minute,
            tzinfo=KSA,
        )

        close_datetime = datetime(
            closing_datetime_value.year,
            closing_datetime_value.month,
            closing_datetime_value.day,
            closing_datetime_value.hour,
            closing_datetime_value.minute,
            tzinfo=KSA,
        )

        now = datetime.now(KSA)

        if open_datetime <= now:

            await interaction.response.send_message(
                "❌ The opening date/time must be in the future.",
                ephemeral=True,
            )

            return

        # Same date is allowed.
        # Only the actual closing datetime must be
        # after the opening datetime.

        if close_datetime <= open_datetime:

            await interaction.response.send_message(
                "❌ The closing date/time must be after "
                "the opening date/time.",
                ephemeral=True,
            )

            return

        try:

            schedule_id = create_schedule(
                name=self.registration_name.value.strip(),

                channel_ids=[
                    channel.id
                    for channel in self.channels
                ],

                role_id=self.role.id,

                open_datetime=open_datetime.isoformat(),

                close_datetime=close_datetime.isoformat(),

                message=self.opening_message.value.strip(),
            )

        except Exception as error:

            print(
                f"❌ Could not create schedule: "
                f"{error!r}"
            )

            await interaction.response.send_message(
                "❌ Could not create the schedule. "
                "Check the database.",
                ephemeral=True,
            )

            return

        channels_text = "\n".join(
            channel.mention
            for channel in self.channels
        )

        embed = discord.Embed(
            title="✅ Registration Scheduled",
            color=discord.Color.green(),
        )

        embed.add_field(
            name="Registration",
            value=self.registration_name.value,
            inline=False,
        )

        embed.add_field(
            name="Opening",
            value=format_ksa(open_datetime),
            inline=True,
        )

        embed.add_field(
            name="Closing",
            value=format_ksa(close_datetime),
            inline=True,
        )

        embed.add_field(
            name="Registration Role",
            value=self.role.mention,
            inline=False,
        )

        embed.add_field(
            name="Channels",
            value=channels_text[:1024],
            inline=False,
        )

        embed.add_field(
            name="Opening Message",
            value=self.opening_message.value[:1024],
            inline=False,
        )

        embed.set_footer(
            text=f"Schedule ID: {schedule_id}"
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )

    async def on_error(
        self,
        interaction,
        error,
    ):

        print("❌ ScheduleModal ERROR")
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
# =========================================================

class IndependentCloseView(discord.ui.View):

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
        placeholder="Select close channels",
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

        await interaction.response.defer()

    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="Select the registration role",
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

        await interaction.response.defer()

    @discord.ui.button(
        label="Continue",
        style=discord.ButtonStyle.red,
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
            IndependentCloseModal(
                self.cog,
                self.channels,
                self.role,
            )
        )


# =========================================================
# INDEPENDENT CLOSE MODAL
# =========================================================

class IndependentCloseModal(
    discord.ui.Modal,
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
        self.channels = channels
        self.role = role

    closing_date = discord.ui.TextInput(
        label="Closing date",
        placeholder="DD/MM/YYYY",
        required=True,
        max_length=10,
    )

    closing_time = discord.ui.TextInput(
        label="Closing time - KSA",
        placeholder="23:00",
        required=True,
        max_length=5,
    )

    closing_message = discord.ui.TextInput(
        label="Closing message",
        placeholder="Write your closing message here",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1800,
    )

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
                "Date format: `DD/MM/YYYY`\n"
                "Time format: `HH:MM`",
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
                "❌ The closing date/time must be "
                "in the future.",
                ephemeral=True,
            )

            return

        closes = load_independent_closes()

        next_id = 1

        if closes:

            ids = []

            for item in closes:

                try:
                    ids.append(
                        int(item["id"])
                    )
                except (
                    KeyError,
                    TypeError,
                    ValueError,
                ):
                    continue

            if ids:
                next_id = max(ids) + 1

        for channel in self.channels:

            close_data = {
                "id": next_id,
                "channel_id": channel.id,
                "role_id": self.role.id,
                "guild_id": channel.guild.id,
                "close_datetime": close_datetime.isoformat(),
                "message": self.closing_message.value.strip(),
                "status": "scheduled",
            }

            closes.append(close_data)

            next_id += 1

        save_independent_closes(closes)

        channels_text = "\n".join(
            channel.mention
            for channel in self.channels
        )

        embed = discord.Embed(
            title="🔒 Registration Close Scheduled",
            color=discord.Color.red(),
        )

        embed.add_field(
            name="Channels",
            value=channels_text[:1024],
            inline=False,
        )

        embed.add_field(
            name="Registration Role",
            value=self.role.mention,
            inline=False,
        )

        embed.add_field(
            name="Closing",
            value=format_ksa(close_datetime),
            inline=False,
        )

        embed.add_field(
            name="Closing Message",
            value=self.closing_message.value[:1024],
            inline=False,
        )

        embed.set_footer(
            text="Multiple channel close scheduled."
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )


# =========================================================
# AUTOCLEAR VIEW
# =========================================================

class AutoClearView(discord.ui.View):

    def __init__(self, cog):

        super().__init__(
            timeout=300
        )

        self.cog = cog
        self.channels = []

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        channel_types=[discord.ChannelType.text],
        placeholder="Select channels to auto-clear",
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

        await interaction.response.send_modal(
            AutoClearModal(
                self.cog,
                self.channels,
            )
        )


# =========================================================
# AUTOCLEAR MODAL
# =========================================================

class AutoClearModal(
    discord.ui.Modal,
):

    def __init__(
        self,
        cog,
        channels,
    ):

        super().__init__(
            title="Configure Auto Clear"
        )

        self.cog = cog
        self.channels = channels

    interval = discord.ui.TextInput(
        label="Clear interval in seconds",
        placeholder="Example: 60",
        required=True,
        max_length=6,
    )

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ):

        if not await staff_only(interaction):
            return

        try:

            interval = int(
                self.interval.value.strip()
            )

        except ValueError:

            await interaction.response.send_message(
                "❌ Interval must be a number.",
                ephemeral=True,
            )

            return

        if interval < 10:

            await interaction.response.send_message(
                "❌ Minimum interval is 10 seconds.",
                ephemeral=True,
            )

            return

        settings = load_autoclear_settings()

        for channel in self.channels:

            existing = None

            for item in settings:

                try:

                    if (
                        int(item["channel_id"])
                        == channel.id
                    ):
                        existing = item
                        break

                except (
                    KeyError,
                    TypeError,
                    ValueError,
                ):
                    continue

            if existing:

                existing["interval"] = interval
                existing["status"] = "active"
                existing["last_clear"] = 0

            else:

                settings.append(
                    {
                        "channel_id": channel.id,
                        "interval": interval,
                        "status": "active",
                        "last_clear": 0,
                    }
                )

        save_autoclear_settings(
            settings
        )

        channels_text = "\n".join(
            channel.mention
            for channel in self.channels
        )

        await interaction.response.send_message(
            "🧹 **AUTO CLEAR ENABLED**\n\n"
            f"**Channels:**\n{channels_text}\n\n"
            f"**Interval:** `{interval}` seconds\n\n"
            "👤 User messages → **DELETE**\n"
            "🤖 Bot messages → **KEEP**",
            ephemeral=True,
        )


# =========================================================
# AUTOCLEAR STOP VIEW
# =========================================================

class AutoClearStopView(discord.ui.View):

    def __init__(
        self,
        cog,
        channels,
    ):

        super().__init__(
            timeout=300
        )

        self.cog = cog
        self.channels = channels

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        channel_types=[discord.ChannelType.text],
        placeholder="Select channels to stop",
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

        selected_ids = {
            channel.id
            for channel in select.values
        }

        settings = load_autoclear_settings()

        stopped = 0

        for item in settings:

            try:

                if int(item["channel_id"]) in selected_ids:

                    if item.get("status") == "active":
                        item["status"] = "stopped"
                        stopped += 1

            except (
                KeyError,
                TypeError,
                ValueError,
            ):
                continue

        save_autoclear_settings(
            settings
        )

        await interaction.response.send_message(
            f"🛑 Auto Clear stopped in "
            f"**{stopped} channel(s)**.",
            ephemeral=True,
        )


# =========================================================
# REGISTRATION SCHEDULER
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
        self.autoclear_loop.start()

    def cog_unload(self):

        self.scheduler_loop.cancel()
        self.autoclear_loop.cancel()

    # =====================================================
    # AUTOMATIC SCHEDULER
    # =====================================================

    @tasks.loop(seconds=30)
    async def scheduler_loop(self):

        if not self.bot.is_ready():
            return

        try:

            await self.process_regular_schedules()

        except Exception as error:

            print(
                f"❌ Regular scheduler error: "
                f"{error!r}"
            )

            traceback.print_exc()

        try:

            await self.process_independent_closes()

        except Exception as error:

            print(
                f"❌ Independent close error: "
                f"{error!r}"
            )

            traceback.print_exc()

    @scheduler_loop.before_loop
    async def before_scheduler(self):

        await self.bot.wait_until_ready()

        print(
            "🟢 Registration scheduler started."
        )

    # =====================================================
    # AUTOCLEAR LOOP
    # =====================================================

    @tasks.loop(seconds=10)
    async def autoclear_loop(self):

        if not self.bot.is_ready():
            return

        settings = load_autoclear_settings()

        if not settings:
            return

        now_timestamp = datetime.now().timestamp()

        changed = False

        for setting in settings:

            if setting.get("status") != "active":
                continue

            try:

                channel_id = int(
                    setting["channel_id"]
                )

                interval = int(
                    setting["interval"]
                )

                last_clear = float(
                    setting.get(
                        "last_clear",
                        0,
                    )
                )

            except (
                KeyError,
                TypeError,
                ValueError,
            ):

                continue

            if (
                now_timestamp - last_clear
                < interval
            ):
                continue

            channel = self.bot.get_channel(
                channel_id
            )

            if channel is None:
                continue

            try:

                deleted = 0

                async for message in channel.history(
                    limit=100,
                ):

                    # =================================================
                    # IMPORTANT:
                    # NEVER DELETE BOT MESSAGES
                    # =================================================

                    if message.author.bot:
                        continue

                    try:

                        await message.delete()
                        deleted += 1

                    except discord.NotFound:
                        pass

                    except discord.Forbidden:

                        print(
                            f"❌ No permission to delete "
                            f"user messages in "
                            f"#{channel.name}"
                        )

                        break

                    except discord.HTTPException:
                        pass

                setting["last_clear"] = (
                    now_timestamp
                )

                changed = True

                print(
                    f"🧹 AutoClear: deleted "
                    f"{deleted} user message(s) "
                    f"in #{channel.name}"
                )

            except Exception as error:

                print(
                    f"❌ AutoClear error in "
                    f"#{channel.name}: "
                    f"{error!r}"
                )

        if changed:

            save_autoclear_settings(
                settings
            )

    @autoclear_loop.before_loop
    async def before_autoclear(self):

        await self.bot.wait_until_ready()

        print(
            "🧹 AutoClear system started."
        )

    # =====================================================
    # GET CHANNELS
    # =====================================================

    async def get_channels(
        self,
        schedule,
    ):

        channels = []

        # IMPORTANT:
        # sqlite3.Row DOES NOT support .get()
        channel_ids = row_value(
            schedule,
            "channel_ids",
            None,
        )

        if channel_ids is None:

            print(
                "❌ Schedule has no channel_ids."
            )

            return channels

        if isinstance(
            channel_ids,
            str,
        ):

            channel_ids = channel_ids.strip()

            if not channel_ids:
                return channels

            try:

                decoded = json.loads(
                    channel_ids
                )

                if isinstance(
                    decoded,
                    list,
                ):
                    channel_ids = decoded

                else:
                    channel_ids = [
                        channel_ids
                    ]

            except (
                json.JSONDecodeError,
                TypeError,
            ):

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

        return channels    # =====================================================
    # PROCESS REGULAR SCHEDULES
    # =====================================================

    async def process_regular_schedules(self):

        try:

            schedules = get_active_schedules()

        except Exception as error:

            print(
                f"❌ Could not load schedules: "
                f"{error!r}"
            )

            return

        now = datetime.now(KSA)

        for schedule in schedules:

            try:

                schedule_id = row_value(
                    schedule,
                    "id",
                    "?",
                )

                open_datetime = datetime.fromisoformat(
                    schedule["open_datetime"]
                )

                close_datetime = datetime.fromisoformat(
                    schedule["close_datetime"]
                )

                status = schedule["status"]

                if (
                    status == "scheduled"
                    and now >= open_datetime
                ):

                    await self.open_registration(
                        schedule
                    )

                elif (
                    status == "open"
                    and now >= close_datetime
                ):

                    await self.close_registration(
                        schedule
                    )

            except Exception as error:

                # IMPORTANT:
                # No schedule.get() here.
                # sqlite3.Row does not support .get()
                schedule_id = row_value(
                    schedule,
                    "id",
                    "?",
                )

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

        schedule_id = row_value(
            schedule,
            "id",
            "?",
        )

        channels = await self.get_channels(
            schedule
        )

        if not channels:

            print(
                f"❌ Schedule {schedule_id}: "
                f"no channels found."
            )

            return

        guild = channels[0].guild

        role = None

        try:

            role = guild.get_role(
                int(
                    schedule["role_id"]
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
                f"❌ Schedule {schedule_id}: "
                f"registration role not found."
            )

            return

        # =================================================
        # OPEN CHANNEL PERMISSIONS
        # =================================================

        for channel in channels:

            await set_registration_permissions(
                channel,
                role,
                can_write=True,
            )

        message = schedule["message"]

        message = replace_placeholders(
            message,
            role=role,
            name=schedule["name"],
            channels=channels,
        )

        # =================================================
        # SEND OPENING MESSAGE
        # =================================================

        for channel in channels:

            try:

                await channel.send(
                    message,
                    allowed_mentions=discord.AllowedMentions(
                        roles=True,
                    ),
                )

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

        # =================================================
        # UPDATE STATUS
        # =================================================

        try:

            update_status(
                schedule_id,
                "open",
            )

        except Exception as error:

            print(
                f"❌ Could not update schedule "
                f"{schedule_id}: {error!r}"
            )

    # =====================================================
    # CLOSE REGISTRATION
    # =====================================================

    async def close_registration(
        self,
        schedule,
    ):

        schedule_id = row_value(
            schedule,
            "id",
            "?",
        )

        channels = await self.get_channels(
            schedule
        )

        if not channels:

            print(
                f"❌ Schedule {schedule_id}: "
                f"no channels found for closing."
            )

            return

        guild = channels[0].guild

        role = None

        try:

            role = guild.get_role(
                int(
                    schedule["role_id"]
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
                f"❌ Schedule {schedule_id}: "
                f"registration role not found."
            )

            return

        # =================================================
        # CLOSE CHANNEL PERMISSIONS
        #
        # Role can SEE the channel.
        # Role CANNOT WRITE.
        # =================================================

        for channel in channels:

            await set_registration_permissions(
                channel,
                role,
                can_write=False,
            )

        message = DEFAULT_CLOSING_MESSAGE

        message = replace_placeholders(
            message,
            role=role,
            name=schedule["name"],
            channels=channels,
        )

        # =================================================
        # SEND CLOSING MESSAGE
        # =================================================

        for channel in channels:

            try:

                await channel.send(
                    message,
                    allowed_mentions=discord.AllowedMentions(
                        roles=True,
                    ),
                )

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

        # =================================================
        # UPDATE STATUS
        # =================================================

        try:

            update_status(
                schedule_id,
                "closed",
            )

        except Exception as error:

            print(
                f"❌ Could not update close status "
                f"for {schedule_id}: "
                f"{error!r}"
            )

    # =====================================================
    # PROCESS INDEPENDENT CLOSES
    # =====================================================

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

                close_datetime = datetime.fromisoformat(
                    close_data["close_datetime"]
                )

                if now < close_datetime:
                    continue

                channel = self.bot.get_channel(
                    int(
                        close_data["channel_id"]
                    )
                )

                if channel is None:

                    print(
                        f"❌ Independent close "
                        f"{close_data.get('id', '?')}: "
                        f"channel not found."
                    )

                    close_data["status"] = "error"
                    changed = True

                    continue

                role = channel.guild.get_role(
                    int(
                        close_data["role_id"]
                    )
                )

                if role is None:

                    print(
                        f"❌ Independent close "
                        f"{close_data.get('id', '?')}: "
                        f"role not found."
                    )

                    close_data["status"] = "error"
                    changed = True

                    continue

                # =========================================
                # CLOSED = VISIBLE + READ ONLY
                # =========================================

                await set_registration_permissions(
                    channel,
                    role,
                    can_write=False,
                )

                await self.close_single_channel(
                    channel,
                    role,
                    close_data["message"],
                )

                close_data["status"] = "closed"

                changed = True

                print(
                    f"🔒 Independent close "
                    f"{close_data.get('id', '?')} "
                    f"completed."
                )

            except Exception as error:

                print(
                    f"❌ Independent close "
                    f"{close_data.get('id', '?')} "
                    f"error: {error!r}"
                )

                traceback.print_exc()

        if changed:

            save_independent_closes(
                closes
            )

    # =====================================================
    # CLOSE ONE CHANNEL
    # =====================================================

    async def close_single_channel(
        self,
        channel,
        role,
        message,
    ):

        message = replace_placeholders(
            message,
            role=role,
            channels=[channel],
        )

        await channel.send(
            message,
            allowed_mentions=discord.AllowedMentions(
                roles=True,
            ),
        )

    # =====================================================
    # /schedule
    # =====================================================

    @app_commands.command(
        name="schedule",
        description="Create a registration schedule.",
    )
    async def schedule_command(
        self,
        interaction: discord.Interaction,
    ):

        if not await staff_only(interaction):
            return

        await interaction.response.send_message(
            "📅 **Create Registration Schedule**\n\n"
            "Select the registration channels "
            "and the registration role.",
            view=ScheduleView(self),
            ephemeral=True,
        )

    # =====================================================
    # /close
    # =====================================================

    @app_commands.command(
        name="close",
        description="Schedule an independent registration close.",
    )
    async def close_command(
        self,
        interaction: discord.Interaction,
    ):

        if not await staff_only(interaction):
            return

        await interaction.response.send_message(
            "🔒 **Schedule Registration Close**\n\n"
            "Select one or multiple channels "
            "and the registration role.",
            view=IndependentCloseView(self),
            ephemeral=True,
        )    # =====================================================
    # /autoclear
    # =====================================================

    @app_commands.command(
        name="autoclear",
        description=(
            "Automatically delete user messages "
            "from selected channels."
        ),
    )
    async def autoclear_command(
        self,
        interaction: discord.Interaction,
    ):

        if not await staff_only(interaction):
            return

        await interaction.response.send_message(
            "🧹 **AUTO CLEAR SETUP**\n\n"
            "Select the channels where user messages "
            "should be automatically deleted.\n\n"
            "🤖 Bot messages will NEVER be deleted.",
            view=AutoClearView(self),
            ephemeral=True,
        )

    # =====================================================
    # /autoclear_stop
    # =====================================================

    @app_commands.command(
        name="autoclear_stop",
        description="Stop auto clear in selected channels.",
    )
    async def autoclear_stop_command(
        self,
        interaction: discord.Interaction,
    ):

        if not await staff_only(interaction):
            return

        settings = load_autoclear_settings()

        active_channels = []

        for setting in settings:

            try:

                if setting.get(
                    "status"
                ) != "active":

                    continue

                channel = self.bot.get_channel(
                    int(
                        setting["channel_id"]
                    )
                )

                if channel is not None:

                    active_channels.append(
                        channel
                    )

            except (
                KeyError,
                TypeError,
                ValueError,
            ):

                continue

        if not active_channels:

            await interaction.response.send_message(
                "ℹ️ No auto-clear channels "
                "are currently active.",
                ephemeral=True,
            )

            return

        await interaction.response.send_message(
            "🛑 **STOP AUTO CLEAR**\n\n"
            "Select the channels you want to stop.",
            view=AutoClearStopView(
                self,
                active_channels,
            ),
            ephemeral=True,
        )


# =========================================================
# SETUP
# =========================================================

async def setup(bot):

    await bot.add_cog(
        RegistrationScheduler(bot)
    )

    print(
        "✅ registration_scheduler loaded successfully."
    )
