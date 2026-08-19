import json
import os
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


KSA = ZoneInfo("Asia/Riyadh")

INDEPENDENT_CLOSE_FILE = "data/independent_closes.json"


# =========================================================
# STAFF ROLE IDs
# =========================================================

GENRA_TEAM_ROLE_ID = 1392127622430986392
OPERATION_MANAGER_ROLE_ID = 1392127621420027956


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

    # Discord Administrator permission
    if member.guild_permissions.administrator:
        return True

    # GENRA TEAM / OPERATION MANAGER
    allowed_role_ids = {
        GENRA_TEAM_ROLE_ID,
        OPERATION_MANAGER_ROLE_ID,
    }

    return any(
        role.id in allowed_role_ids
        for role in member.roles
    )


async def staff_only(
    interaction: discord.Interaction
) -> bool:

    if is_staff(interaction):
        return True

    if interaction.response.is_done():
        await interaction.followup.send(
            "❌ You are not authorized to use this command.",
            ephemeral=True,
        )
    else:
        await interaction.response.send_message(
            "❌ You are not authorized to use this command.",
            ephemeral=True,
        )

    return False


# =========================================================
# FORMAT DATE
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
            encoding="utf-8",
        ) as file:

            return json.load(file)

    except Exception as error:

        print(
            f"❌ Could not load independent closes: {error}"
        )

        return []


def save_independent_closes(closes):

    os.makedirs(
        "data",
        exist_ok=True
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
            f"❌ Could not save independent closes: {error}"
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

    if role is not None:

        message = message.replace(
            "{role}",
            role.mention,
        )

    if name is not None:

        message = message.replace(
            "{name}",
            name,
        )

    if channels:

        message = message.replace(
            "{channels}",
            " ".join(
                channel.mention
                for channel in channels
            ),
        )

    return message# =========================================================
# SCHEDULE VIEW
# =========================================================

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
        max_values=25,
    )
    async def channel_select(
        self,
        interaction: discord.Interaction,
        select: discord.ui.ChannelSelect,
    ):

        if not await staff_only(interaction):
            return

        self.channels = select.values

        await interaction.response.defer()

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
                "❌ Select a role to mention.",
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
        interaction: discord.Interaction,
        error: Exception,
        item,
    ):
        import traceback

        print("❌ ScheduleView ERROR")
        traceback.print_exc()

# =========================================================
# SCHEDULE MODAL
# =========================================================

class ScheduleModal(discord.ui.Modal, title="Create Registration Schedule"):

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
        placeholder="Write your opening message here",
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

        if close_datetime <= open_datetime:

            await interaction.response.send_message(
                "❌ The closing date/time must be after the opening date/time.",
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
                f"❌ Could not create schedule: {error}"
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
            name="Mention Role",
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
        interaction: discord.Interaction,
        error: Exception,
    ):

        import traceback

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
            pass        
        

        

            
    



    
        
# =========================================================
# INDEPENDENT CLOSE VIEW
# =========================================================

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
        max_values=1,
    )
    async def channel_select(
        self,
        interaction: discord.Interaction,
        select: discord.ui.ChannelSelect,
    ):

        if not await staff_only(interaction):
            return

        self.channel = select.values[0]

        await interaction.response.send_message(
            f"✅ Selected channel: {self.channel.mention}",
            ephemeral=True,
        )

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

        if self.channel is None:

            await interaction.response.send_message(
                "❌ Select one channel.",
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
                self.channel,
                self.role,
            )
        )


# =========================================================
# INDEPENDENT CLOSE MODAL
# =========================================================

class IndependentCloseModal(discord.ui.Modal):

    def __init__(
        self,
        cog,
        channel,
        role,
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

            next_id = max(
                item["id"]
                for item in closes
            ) + 1

        close_data = {
            "id": next_id,
            "channel_id": self.channel.id,
            "role_id": self.role.id,
            "guild_id": self.channel.guild.id,
            "close_datetime": close_datetime.isoformat(),
            "message": self.closing_message.value.strip(),
            "status": "scheduled",
        }

        closes.append(close_data)

        save_independent_closes(closes)

        embed = discord.Embed(
            title="🔒 Registration Close Scheduled",
            color=discord.Color.red(),
        )

        embed.add_field(
            name="Channel",
            value=self.channel.mention,
            inline=False,
        )

        embed.add_field(
            name="Mention Role",
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
        )# =========================================================
# REGISTRATION SCHEDULER
# =========================================================

class RegistrationScheduler(commands.Cog):

    def __init__(self, bot):
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

        try:
            await self.process_regular_schedules()
        except Exception as error:
            print(
                f"❌ Regular scheduler error: {error!r}"
            )

        try:
            await self.process_independent_closes()
        except Exception as error:
            print(
                f"❌ Independent close error: {error!r}"
            )

    @scheduler_loop.before_loop
    async def before_scheduler(self):

        await self.bot.wait_until_ready()

        print(
            "🟢 Registration scheduler started."
        )

    # =====================================================
    # GET CHANNELS
    # =====================================================

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

                if channel is not None:
                    channels.append(channel)

            except (ValueError, TypeError):
                continue

        return channels

    # =====================================================
    # PROCESS REGULAR SCHEDULES
    # =====================================================

    async def process_regular_schedules(self):

        try:

            schedules = get_active_schedules()

        except Exception as error:

            print(
                f"❌ Could not load schedules: {error!r}"
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

                print(
                    f"❌ Schedule "
                    f"{schedule.get('id', '?')} "
                    f"error: {error!r}"
                )

    # =====================================================
    # OPEN REGISTRATION
    # =====================================================

    async def open_registration(self, schedule):

        channels = await self.get_channels(
            schedule
        )

        if not channels:

            print(
                f"❌ Schedule {schedule['id']}: "
                f"no channels found."
            )

            return

        role = None

        guild = channels[0].guild

        try:

            role = guild.get_role(
                int(schedule["role_id"])
            )

        except Exception:

            role = None

        message = schedule["message"]

        message = replace_placeholders(
            message,
            role=role,
            name=schedule["name"],
            channels=channels,
        )

        for channel in channels:

            try:

                await channel.send(
                    message,
                    allowed_mentions=discord.AllowedMentions(
                        roles=True
                    ),
                )

                print(
                    f"🟢 Registration opened: "
                    f"{schedule['id']} "
                    f"→ #{channel.name}"
                )

            except Exception as error:

                print(
                    f"❌ Could not open "
                    f"schedule {schedule['id']} "
                    f"in #{channel.name}: "
                    f"{error!r}"
                )

        try:

            update_status(
                schedule["id"],
                "open"
            )

        except Exception as error:

            print(
                f"❌ Could not update schedule "
                f"{schedule['id']}: {error!r}"
            )

    # =====================================================
    # CLOSE REGISTRATION
    # =====================================================

    async def close_registration(self, schedule):

        channels = await self.get_channels(
            schedule
        )

        if not channels:

            print(
                f"❌ Schedule {schedule['id']}: "
                f"no channels found for closing."
            )

            return

        guild = channels[0].guild

        role = None

        try:

            role = guild.get_role(
                int(schedule["role_id"])
            )

        except Exception:

            role = None

        message = DEFAULT_CLOSING_MESSAGE

        message = replace_placeholders(
            message,
            role=role,
            name=schedule["name"],
            channels=channels,
        )

        for channel in channels:

            try:

                await channel.send(
                    message,
                    allowed_mentions=discord.AllowedMentions(
                        roles=True
                    ),
                )

                print(
                    f"🔴 Registration closed: "
                    f"{schedule['id']} "
                    f"→ #{channel.name}"
                )

            except Exception as error:

                print(
                    f"❌ Could not close "
                    f"schedule {schedule['id']} "
                    f"in #{channel.name}: "
                    f"{error!r}"
                )

        try:

            update_status(
                schedule["id"],
                "closed"
            )

        except Exception as error:

            print(
                f"❌ Could not update close status "
                f"for {schedule['id']}: {error!r}"
            )

    # =====================================================
    # INDEPENDENT CLOSES
    # =====================================================

    async def process_independent_closes(self):

        closes = load_independent_closes()

        if not closes:
            return

        now = datetime.now(KSA)

        changed = False

        for close_data in closes:

            if close_data.get("status") != "scheduled":
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

                    print(
                        f"❌ Independent close "
                        f"{close_data['id']}: "
                        f"channel not found."
                    )

                    close_data["status"] = "error"
                    changed = True

                    continue

                role = channel.guild.get_role(
                    int(close_data["role_id"])
                )

                if role is None:

                    print(
                        f"❌ Independent close "
                        f"{close_data['id']}: "
                        f"role not found."
                    )

                    close_data["status"] = "error"
                    changed = True

                    continue

                await self.close_single_channel(
                    channel,
                    role,
                    close_data["message"],
                )

                close_data["status"] = "closed"

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
                roles=True
            ),
        )

    # =====================================================
    # /schedule
    # =====================================================

    @app_commands.command(
        name="schedule",
        description="Create a registration schedule."
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
            "and the role to mention.",
            view=ScheduleView(self),
            ephemeral=True,
        )

    # =====================================================
    # /close
    # =====================================================

    @app_commands.command(
        name="close",
        description="Schedule an independent registration close."
    )
    async def close_command(
        self,
        interaction: discord.Interaction,
    ):

        if not await staff_only(interaction):
            return

        await interaction.response.send_message(
            "🔒 **Schedule Registration Close**\n\n"
            "Select the channel and the role to mention.",
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
