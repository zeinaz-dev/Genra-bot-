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

CEO_ROLE_ID = 1392127618815627466
GENRA_TEAM_ROLE_ID = 1392127622430986392
OPERATION_MANAGER_ROLE_ID = 1392127621420027956

STAFF_ROLE_IDS = {
    CEO_ROLE_ID,
    GENRA_TEAM_ROLE_ID,
    OPERATION_MANAGER_ROLE_ID,
}


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
# DATE FORMAT
# =========================================================

def format_ksa(dt: datetime) -> str:

    return dt.astimezone(KSA).strftime(
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
# PLACEHOLDERS
# =========================================================

def replace_placeholders(
    message,
    role=None,
    name=None,
    channels=None,
):

    if not isinstance(message, str):
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

        channel_mentions = " ".join(
            channel.mention
            for channel in channels
        )

        message = message.replace(
            "{channels}",
            channel_mentions,
        )

    return message


# =========================================================
# CHANNEL PERMISSIONS
# =========================================================

async def set_registration_permissions(
    channel: discord.TextChannel,
    role: discord.Role,
    opened: bool,
):
    """
    CLOSED:
        @everyone -> cannot view
        selected role -> can view, cannot write

    OPEN:
        @everyone -> cannot view
        selected role -> can view, can write
    """

    guild = channel.guild
    everyone = guild.default_role

    await channel.set_permissions(
        everyone,
        view_channel=False,
        reason="Registration room access control",
    )

    if opened:

        await channel.set_permissions(
            role,
            view_channel=True,
            send_messages=True,
            reason="Registration opened",
        )

    else:

        await channel.set_permissions(
            role,
            view_channel=True,
            send_messages=False,
            reason="Registration closed",
        )


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

        await interaction.response.send_message(
            f"✅ Selected {len(self.channels)} channel(s).",
            ephemeral=True,
        )


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
            f"✅ Selected role: {self.role.mention}",
            ephemeral=True,
        )


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

        try:

            await interaction.response.send_modal(
                ScheduleModal(
                    self.cog,
                    self.channels,
                    self.role,
                )
            )

        except Exception as error:

            print(
                "❌ Could not open ScheduleModal:"
            )

            traceback.print_exc()

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "❌ Could not open the schedule form.",
                    ephemeral=True,
                )


    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        item,
    ):

        print(
            "❌ ScheduleView ERROR"
        )

        traceback.print_exception(
            type(error),
            error,
            error.__traceback__,
        )


# =========================================================
# SCHEDULE MODAL
# =========================================================

class ScheduleModal(discord.ui.Modal):

    def __init__(
        self,
        cog,
        channels,
        role,
    ):

        super().__init__(
            title="Create Registration Schedule"
        )

        self.cog = cog
        self.channels = list(channels)
        self.role = role

        self.registration_name = discord.ui.TextInput(
            label="Registration name",
            placeholder="Example: CLASH REGISTRATION",
            required=True,
            max_length=100,
        )

        self.opening_date = discord.ui.TextInput(
            label="Opening date",
            placeholder="DD/MM/YYYY",
            required=True,
            max_length=10,
        )

        self.opening_time = discord.ui.TextInput(
            label="Opening time - KSA",
            placeholder="20:00",
            required=True,
            max_length=5,
        )

        self.closing_time = discord.ui.TextInput(
            label="Closing time - KSA",
            placeholder="23:00",
            required=True,
            max_length=5,
        )

        self.opening_message = discord.ui.TextInput(
            label="Opening message",
            placeholder="Write your opening message here",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1800,
        )

        self.add_item(
            self.registration_name
        )

        self.add_item(
            self.opening_date
        )

        self.add_item(
            self.opening_time
        )

        self.add_item(
            self.closing_time
        )

        self.add_item(
            self.opening_message
        )    # =====================================================
    # SCHEDULE MODAL SUBMIT
    # =====================================================

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ):

        if not await staff_only(interaction):
            return

        try:

            date_value = datetime.strptime(
                self.opening_date.value.strip(),
                "%d/%m/%Y",
            )

            opening_time_value = datetime.strptime(
                self.opening_time.value.strip(),
                "%H:%M",
            )

            closing_time_value = datetime.strptime(
                self.closing_time.value.strip(),
                "%H:%M",
            )

        except ValueError:

            await interaction.response.send_message(
                "❌ Invalid date or time format.\n\n"
                "Date: `DD/MM/YYYY`\n"
                "Opening time: `HH:MM`\n"
                "Closing time: `HH:MM`\n\n"
                "Example:\n"
                "`25/08/2026`\n"
                "`20:00`\n"
                "`23:00`",
                ephemeral=True,
            )

            return

        # -------------------------------------------------
        # SAME DATE FOR OPENING AND CLOSING
        # -------------------------------------------------

        open_datetime = datetime(
            date_value.year,
            date_value.month,
            date_value.day,
            opening_time_value.hour,
            opening_time_value.minute,
            tzinfo=KSA,
        )

        close_datetime = datetime(
            date_value.year,
            date_value.month,
            date_value.day,
            closing_time_value.hour,
            closing_time_value.minute,
            tzinfo=KSA,
        )

        now = datetime.now(KSA)

        if open_datetime <= now:

            await interaction.response.send_message(
                "❌ The opening date/time must be "
                "in the future.",
                ephemeral=True,
            )

            return

        if close_datetime <= open_datetime:

            await interaction.response.send_message(
                "❌ The closing time must be after "
                "the opening time on the same date.",
                ephemeral=True,
            )

            return

        # -------------------------------------------------
        # DATABASE
        # -------------------------------------------------

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
                "❌ Could not create the schedule.\n"
                "Please check the database.",
                ephemeral=True,
            )

            return

        # -------------------------------------------------
        # EMBED
        # -------------------------------------------------

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

        traceback.print_exception(
            type(error),
            error,
            error.__traceback__,
        )

        try:

            if interaction.response.is_done():

                await interaction.followup.send(
                    "❌ An error occurred while creating "
                    "the schedule.",
                    ephemeral=True,
                )

            else:

                await interaction.response.send_message(
                    "❌ An error occurred while creating "
                    "the schedule.",
                    ephemeral=True,
                )

        except Exception:
            pass


# =========================================================
# INDEPENDENT CLOSE VIEW
# =========================================================

class IndependentCloseView(
    discord.ui.View
):

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
        placeholder="Select channels to close",
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
            f"✅ Selected {len(self.channels)} channel(s).",
            ephemeral=True,
        )


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
            f"✅ Selected role: {self.role.mention}",
            ephemeral=True,
        )


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

        try:

            await interaction.response.send_modal(
                IndependentCloseModal(
                    self.cog,
                    self.channels,
                    self.role,
                )
            )

        except Exception:

            print(
                "❌ Could not open "
                "IndependentCloseModal:"
            )

            traceback.print_exc()

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "❌ Could not open the close form.",
                    ephemeral=True,
                )


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

        self.closing_date = discord.ui.TextInput(
            label="Closing date",
            placeholder="DD/MM/YYYY",
            required=True,
            max_length=10,
        )

        self.closing_time = discord.ui.TextInput(
            label="Closing time - KSA",
            placeholder="23:00",
            required=True,
            max_length=5,
        )

        self.closing_message = discord.ui.TextInput(
            label="Closing message",
            placeholder="Write your closing message here",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1800,
        )

        self.add_item(
            self.closing_date
        )

        self.add_item(
            self.closing_time
        )

        self.add_item(
            self.closing_message
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
                "❌ The closing date/time must be "
                "in the future.",
                ephemeral=True,
            )

            return

        # -------------------------------------------------
        # NEXT ID
        # -------------------------------------------------

        closes = load_independent_closes()

        next_id = 1

        if closes:

            valid_ids = []

            for item in closes:

                try:

                    valid_ids.append(
                        int(item.get("id", 0))
                    )

                except Exception:
                    pass

            if valid_ids:
                next_id = max(valid_ids) + 1

        # -------------------------------------------------
        # SAVE
        # -------------------------------------------------

        close_data = {
            "id": next_id,
            "channel_ids": [
                channel.id
                for channel in self.channels
            ],
            "role_id": self.role.id,
            "guild_id": self.channels[0].guild.id,
            "close_datetime": close_datetime.isoformat(),
            "message": self.closing_message.value.strip(),
            "status": "scheduled",
        }

        closes.append(
            close_data
        )

        save_independent_closes(
            closes
        )

        # -------------------------------------------------
        # EMBED
        # -------------------------------------------------

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

        traceback.print_exception(
            type(error),
            error,
            error.__traceback__,
        )

        try:

            if interaction.response.is_done():

                await interaction.followup.send(
                    "❌ An error occurred while scheduling "
                    "the registration close.",
                    ephemeral=True,
                )

            else:

                await interaction.response.send_message(
                    "❌ An error occurred while scheduling "
                    "the registration close.",
                    ephemeral=True,
                )

        except Exception:
            pass# =========================================================
# REGISTRATION SCHEDULER
# =========================================================

class RegistrationScheduler(
    commands.Cog
):

    def __init__(self, bot):

        self.bot = bot

        self.scheduler_loop.start()


    def cog_unload(self):

        self.scheduler_loop.cancel()


    # =====================================================
    # AUTOMATIC SCHEDULER
    # =====================================================

    @tasks.loop(seconds=30)
    async def scheduler_loop(
        self
    ):

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
    async def before_scheduler(
        self
    ):

        await self.bot.wait_until_ready()

        print(
            "🟢 Registration scheduler started."
        )


    # =====================================================
    # GET CHANNELS
    # =====================================================

    async def get_channels(
        self,
        schedule
    ):

        channels = []

        channel_ids = schedule.get(
            "channel_ids",
            [],
        )

        if isinstance(
            channel_ids,
            str
        ):

            try:

                channel_ids = json.loads(
                    channel_ids
                )

            except Exception:

                channel_ids = [
                    item.strip()
                    for item in channel_ids.split(",")
                    if item.strip()
                ]

        if not isinstance(
            channel_ids,
            list
        ):
            return []

        for channel_id in channel_ids:

            try:

                channel = self.bot.get_channel(
                    int(channel_id)
                )

                if isinstance(
                    channel,
                    discord.TextChannel
                ):

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
    # PROCESS REGULAR SCHEDULES
    # =====================================================

    async def process_regular_schedules(
        self
    ):

        try:

            schedules = get_active_schedules()

        except Exception as error:

            print(
                f"❌ Could not load schedules: "
                f"{error!r}"
            )

            return

        if not schedules:
            return

        now = datetime.now(KSA)

        for schedule in schedules:

            try:

                open_datetime = (
                    datetime.fromisoformat(
                        schedule[
                            "open_datetime"
                        ]
                    )
                )

                close_datetime = (
                    datetime.fromisoformat(
                        schedule[
                            "close_datetime"
                        ]
                    )
                )

                status = schedule[
                    "status"
                ]

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
                    f"{schedule.get('id', '?')} "
                    f"error: {error!r}"
                )

                traceback.print_exc()


    # =====================================================
    # OPEN REGISTRATION
    # =====================================================

    async def open_registration(
        self,
        schedule
    ):

        channels = await self.get_channels(
            schedule
        )

        if not channels:

            print(
                f"❌ Schedule "
                f"{schedule['id']}: "
                f"no channels found."
            )

            return

        # -------------------------------------------------
        # ROLE
        # -------------------------------------------------

        role = None

        try:

            role = channels[
                0
            ].guild.get_role(
                int(
                    schedule[
                        "role_id"
                    ]
                )
            )

        except Exception:

            role = None

        if role is None:

            print(
                f"❌ Schedule "
                f"{schedule['id']}: "
                f"registration role not found."
            )

            return

        # -------------------------------------------------
        # OPEN PERMISSIONS
        # -------------------------------------------------

        successful_channels = []

        for channel in channels:

            try:

                await set_registration_permissions(
                    channel,
                    role,
                    opened=True,
                )

                successful_channels.append(
                    channel
                )

            except Exception as error:

                print(
                    f"❌ Could not open permissions "
                    f"for schedule "
                    f"{schedule['id']} "
                    f"in #{channel.name}: "
                    f"{error!r}"
                )

        # -------------------------------------------------
        # MESSAGE
        # -------------------------------------------------

        message = replace_placeholders(
            schedule["message"],
            role=role,
            name=schedule["name"],
            channels=channels,
        )

        for channel in successful_channels:

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
                    f"🟢 Registration opened: "
                    f"{schedule['id']} "
                    f"→ #{channel.name}"
                )

            except Exception as error:

                print(
                    f"❌ Could not send opening message "
                    f"for schedule "
                    f"{schedule['id']} "
                    f"in #{channel.name}: "
                    f"{error!r}"
                )

        # -------------------------------------------------
        # STATUS
        # -------------------------------------------------

        try:

            update_status(
                schedule["id"],
                "open",
            )

        except Exception as error:

            print(
                f"❌ Could not update schedule "
                f"{schedule['id']} status: "
                f"{error!r}"
            )


    # =====================================================
    # CLOSE REGISTRATION
    # =====================================================

    async def close_registration(
        self,
        schedule
    ):

        channels = await self.get_channels(
            schedule
        )

        if not channels:

            print(
                f"❌ Schedule "
                f"{schedule['id']}: "
                f"no channels found for closing."
            )

            return

        # -------------------------------------------------
        # ROLE
        # -------------------------------------------------

        role = None

        try:

            role = channels[
                0
            ].guild.get_role(
                int(
                    schedule[
                        "role_id"
                    ]
                )
            )

        except Exception:

            role = None

        if role is None:

            print(
                f"❌ Schedule "
                f"{schedule['id']}: "
                f"registration role not found."
            )

            return

        # -------------------------------------------------
        # CLOSE PERMISSIONS
        # -------------------------------------------------

        successful_channels = []

        for channel in channels:

            try:

                await set_registration_permissions(
                    channel,
                    role,
                    opened=False,
                )

                successful_channels.append(
                    channel
                )

            except Exception as error:

                print(
                    f"❌ Could not close permissions "
                    f"for schedule "
                    f"{schedule['id']} "
                    f"in #{channel.name}: "
                    f"{error!r}"
                )

        # -------------------------------------------------
        # CLOSING MESSAGE
        # -------------------------------------------------

        message = replace_placeholders(
            DEFAULT_CLOSING_MESSAGE,
            role=role,
            name=schedule["name"],
            channels=channels,
        )

        for channel in successful_channels:

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
                    f"🔴 Registration closed: "
                    f"{schedule['id']} "
                    f"→ #{channel.name}"
                )

            except Exception as error:

                print(
                    f"❌ Could not send closing message "
                    f"for schedule "
                    f"{schedule['id']} "
                    f"in #{channel.name}: "
                    f"{error!r}"
                )

        # -------------------------------------------------
        # STATUS
        # -------------------------------------------------

        try:

            update_status(
                schedule["id"],
                "closed",
            )

        except Exception as error:

            print(
                f"❌ Could not update close status "
                f"for {schedule['id']}: "
                f"{error!r}"
            )


    # =====================================================
    # PROCESS INDEPENDENT CLOSES
    # =====================================================

    async def process_independent_closes(
        self
    ):

        closes = load_independent_closes()

        if not closes:
            return

        now = datetime.now(KSA)

        changed = False

        for close_data in closes:

            if (
                close_data.get(
                    "status"
                )
                != "scheduled"
            ):
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
                # NEW FORMAT
                # -------------------------------------------------

                channel_ids = (
                    close_data.get(
                        "channel_ids"
                    )
                )

                # -------------------------------------------------
                # OLD FORMAT SUPPORT
                # -------------------------------------------------

                if not channel_ids:

                    old_channel_id = (
                        close_data.get(
                            "channel_id"
                        )
                    )

                    if old_channel_id:

                        channel_ids = [
                            old_channel_id
                        ]

                    else:

                        print(
                            f"❌ Independent close "
                            f"{close_data.get('id', '?')}: "
                            f"no channels."
                        )

                        close_data[
                            "status"
                        ] = "error"

                        changed = True

                        continue

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

                        if isinstance(
                            channel,
                            discord.TextChannel
                        ):

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
                        f"❌ Independent close "
                        f"{close_data['id']}: "
                        f"no channels found."
                    )

                    close_data[
                        "status"
                    ] = "error"

                    changed = True

                    continue

                # -------------------------------------------------
                # ROLE
                # -------------------------------------------------

                role = channels[
                    0
                ].guild.get_role(
                    int(
                        close_data[
                            "role_id"
                        ]
                    )
                )

                if role is None:

                    print(
                        f"❌ Independent close "
                        f"{close_data['id']}: "
                        f"role not found."
                    )

                    close_data[
                        "status"
                    ] = "error"

                    changed = True

                    continue

                # -------------------------------------------------
                # CLOSE ALL CHANNELS
                # -------------------------------------------------

                for channel in channels:

                    try:

                        await set_registration_permissions(
                            channel,
                            role,
                            opened=False,
                        )

                        message = (
                            replace_placeholders(
                                close_data[
                                    "message"
                                ],
                                role=role,
                                channels=[
                                    channel
                                ],
                            )
                        )

                        await channel.send(
                            message,
                            allowed_mentions=(
                                discord.AllowedMentions(
                                    roles=True
                                )
                            ),
                        )

                        print(
                            f"🔒 Independent close "
                            f"{close_data['id']} "
                            f"→ #{channel.name}"
                        )

                    except Exception as error:

                        print(
                            f"❌ Could not close "
                            f"independent channel "
                            f"#{channel.name}: "
                            f"{error!r}"
                        )

                close_data[
                    "status"
                ] = "closed"

                changed = True

                print(
                    f"🔒 Independent close "
                    f"{close_data['id']} completed."
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
            )# =========================================================
# /schedule
# =========================================================

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
            "and the registration role.\n\n"
            "🔒 Closed: role can see but cannot write.\n"
            "🟢 Open: role can see and write.",
            view=ScheduleView(self),
            ephemeral=True,
        )


# =========================================================
# /close
# =========================================================

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
            "Select one or more registration channels "
            "and the registration role.",
            view=IndependentCloseView(self),
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
