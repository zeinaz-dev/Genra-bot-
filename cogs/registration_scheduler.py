import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks

from database.schema import (
    create_schedule,
    get_active_schedules,
    update_status,
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


def format_ksa(dt: datetime) -> str:
    return dt.astimezone(KSA).strftime(
        "%d/%m/%Y %H:%M KSA"
    )


def load_independent_closes():
    os.makedirs("data", exist_ok=True)

    if not os.path.exists(INDEPENDENT_CLOSE_FILE):
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
    os.makedirs("data", exist_ok=True)

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
        max_values=25,
    )
    async def channel_select(
        self,
        interaction: discord.Interaction,
        select: discord.ui.ChannelSelect,
    ):
        self.channels = list(select.values)

        await interaction.response.send_message(
            f"✅ Selected {len(self.channels)} channel(s).",
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
        )class ScheduleModal(discord.ui.Modal):

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

    opening_message = discord.ui.TextInput(
        label="Opening message",
        placeholder="Write your opening message here",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1800,
    )

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ):
        try:
            opening_date_value = datetime.strptime(
                self.opening_date.value.strip(),
                "%d/%m/%Y",
            )

            opening_time_value = datetime.strptime(
                self.opening_time.value.strip(),
                "%H:%M",
            )

            closing_date_value = datetime.strptime(
                self.closing_date.value.strip(),
                "%d/%m/%Y",
            )

            closing_time_value = datetime.strptime(
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

        open_datetime = datetime(
            opening_date_value.year,
            opening_date_value.month,
            opening_date_value.day,
            opening_time_value.hour,
            opening_time_value.minute,
            tzinfo=KSA,
        )

        close_datetime = datetime(
            closing_date_value.year,
            closing_date_value.month,
            closing_date_value.day,
            closing_time_value.hour,
            closing_time_value.minute,
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
        self.channel = select.values[0]

        await interaction.response.send_message(
            f"✅ Selected channel: "
            f"{self.channel.mention}",
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


class IndependentCloseModal(discord.ui.Modal):

    def __init__(self, cog, channel, role):
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

        if close_datetime <= datetime.now(KSA):
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
                int(item["id"])
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
        )class RegistrationScheduler(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.scheduler_loop.start()

    def cog_unload(self):
        self.scheduler_loop.cancel()

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
            "✅ Registration scheduler started."
        )

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
                    f"{schedule.get('id', '?')} error: "
                    f"{error!r}"
                )

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

                if not isinstance(
                    channel,
                    discord.TextChannel
                ):
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
                    f"✅ Independent close "
                    f"{close_data['id']} completed."
                )

            except Exception as error:
                print(
                    f"❌ Independent close "
                    f"{close_data.get('id', '?')} error: "
                    f"{error!r}"
                )

        if changed:
            save_independent_closes(closes)

    async def get_channels(self, schedule):

        channels = []

        channel_ids = schedule.get(
            "channel_ids",
            ""
        )

        if isinstance(channel_ids, list):
            ids = channel_ids
        else:
            ids = str(channel_ids).split(",")

        for channel_id in ids:

            try:
                channel = self.bot.get_channel(
                    int(channel_id)
                )

                if channel is not None:
                    channels.append(channel)

            except (ValueError, TypeError):
                continue

        return channels

    async def open_registration(
        self,
        schedule,
    ):

        channels = await self.get_channels(
            schedule
        )

        if not channels:
            print(
                f"❌ Schedule {schedule['id']}: "
                "no channels found."
            )
            return

        role_id = int(
            schedule["role_id"]
        )

        role = None

        guild = channels[0].guild

        role = guild.get_role(role_id)

        if role is None:
            print(
                f"❌ Schedule {schedule['id']}: "
                "role not found."
            )
            return

        message = replace_placeholders(
            schedule["message"],
            role=role,
            name=schedule["name"],
            channels=channels,
        )

        for channel in channels:

            try:
                await channel.send(message)

                await self.set_channel_open(
                    channel
                )

            except discord.Forbidden:
                print(
                    f"❌ No permission in "
                    f"#{channel.name}"
                )

            except discord.HTTPException as error:
                print(
                    f"❌ Discord error in "
                    f"#{channel.name}: {error}"
                )

        try:
            update_status(
                schedule["id"],
                "open",
            )

        except Exception as error:
            print(
                f"❌ Could not update schedule "
                f"{schedule['id']}: {error}"
            )

        print(
            f"🟢 Schedule {schedule['id']} opened."
        )    async def close_registration(
        self,
        schedule,
    ):

        channels = await self.get_channels(
            schedule
        )

        if not channels:
            print(
                f"❌ Schedule {schedule['id']}: "
                "no channels found for closing."
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

        for channel in channels:

            try:
                await self.set_channel_closed(
                    channel
                )

                closing_message = replace_placeholders(
                    DEFAULT_CLOSING_MESSAGE,
                    role=role,
                    name=schedule["name"],
                    channels=channels,
                )

                await channel.send(
                    closing_message
                )

            except discord.Forbidden:
                print(
                    f"❌ No permission to close "
                    f"#{channel.name}"
                )

            except discord.HTTPException as error:
                print(
                    f"❌ Discord error closing "
                    f"#{channel.name}: {error}"
                )

        try:
            update_status(
                schedule["id"],
                "closed",
            )

        except Exception as error:
            print(
                f"❌ Could not update closed status "
                f"for {schedule['id']}: {error}"
            )

        print(
            f"🔴 Schedule {schedule['id']} closed."
        )

    async def close_single_channel(
        self,
        channel,
        role,
        message,
    ):

        await self.set_channel_closed(
            channel
        )

        final_message = replace_placeholders(
            message,
            role=role,
            channels=[channel],
        )

        await channel.send(
            final_message
        )

    async def set_channel_open(
        self,
        channel,
    ):

        guild = channel.guild

        everyone = guild.default_role

        overwrite = channel.overwrites_for(
            everyone
        )

        overwrite.send_messages = True

        await channel.set_permissions(
            everyone,
            overwrite=overwrite,
            reason="Registration opened by scheduler",
        )

    async def set_channel_closed(
        self,
        channel,
    ):

        guild = channel.guild

        everyone = guild.default_role

        overwrite = channel.overwrites_for(
            everyone
        )

        overwrite.send_messages = False

        await channel.set_permissions(
            everyone,
            overwrite=overwrite,
            reason="Registration closed by scheduler",
        )


async def setup(bot):

    await bot.add_cog(
        RegistrationScheduler(bot)
    )

    print(
        "✅ RegistrationScheduler cog loaded."
    )
