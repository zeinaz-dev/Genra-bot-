import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.permissions import is_staff


DATABASE = "genra.db"

KSA = ZoneInfo("Asia/Riyadh")

PACKS = {
    "CLASH": "CLASH",
    "EMPIRE": "EMPIRE",
    "TRAINING": "TRAINING",
}


OPEN_MESSAGE = """# 🔓 REGISTRATION IS OPEN

**REGISTRATION IS NOW OPEN!**

Please write your **TEAM NAME** in this channel.
⏰ Register on time and respect your registration slot.
📌 Make sure to mention the corresponding role:

@CLASH
@EMPIRE
@TRAINING

━━━━━━━━━━━━━━━━━━━━

**التسجيل مفتوح الآن!**

يرجى كتابة **اسم الفريق** في هذه القناة.
⏰ احرص على التسجيل في الوقت المحدد واحترم الـ Slot الخاص بك.
📌 تأكد من عمل Mention للدور الخاص بالباقة:

@CLASH
@EMPIRE
@TRAINING

⚠️ **Only registered teams will be considered.**
⚠️ **سيتم اعتماد الفرق المسجلة فقط.**
"""


CLOSE_MESSAGE = """# 🔒 REGISTRATION IS CLOSED

**REGISTRATION IS NOW CLOSED!**

Please check the **WhatsApp group** for the **Group ID**.

⚠️ In case of any problem or issue, please **contact the organiser**.

━━━━━━━━━━━━━━━━━━━━

**التسجيل مغلق الآن!**

يرجى التوجه إلى **مجموعة WhatsApp** للحصول على **Group ID**.

⚠️ في حال وجود أي مشكلة، يرجى **التواصل مع المنظم**.
"""


def get_connection():
    return sqlite3.connect(DATABASE)


def get_pack_role(guild: discord.Guild, pack: str):

    for role in guild.roles:

        if role.name.upper() == pack.upper():
            return role

    return None


def parse_schedule_datetime(
    date_value,
    time_value
):
    return datetime.strptime(
        f"{date_value} {time_value}",
        "%d/%m/%Y %H:%M"
    ).replace(tzinfo=KSA)


class ChannelSelect(discord.ui.ChannelSelect):

    def __init__(
        self,
        pack,
        date_value,
        open_time,
        close_time
    ):

        self.pack = pack
        self.date_value = date_value
        self.open_time = open_time
        self.close_time = close_time

        super().__init__(
            placeholder="Select registration channels",
            min_values=1,
            max_values=25,
            channel_types=[
                discord.ChannelType.text
            ]
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        if not is_staff(interaction):

            await interaction.response.send_message(
                "❌ You are not allowed to use the Scheduler.",
                ephemeral=True
            )

            return

        try:

            start = parse_schedule_datetime(
                self.date_value,
                self.open_time
            )

            end = parse_schedule_datetime(
                self.date_value,
                self.close_time
            )

        except ValueError:

            await interaction.response.send_message(
                "❌ Invalid date or time format.",
                ephemeral=True
            )

            return

        now = datetime.now(KSA)

        if start < now:

            await interaction.response.send_message(
                "❌ The opening date/time cannot be in the past.",
                ephemeral=True
            )

            return

        if end <= start:

            await interaction.response.send_message(
                "❌ Closing time must be after opening time.",
                ephemeral=True
            )

            return

        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO schedules
            (
                pack,
                date,
                open_time,
                close_time,
                created_by
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                self.pack,
                self.date_value,
                self.open_time,
                self.close_time,
                interaction.user.id
            )
        )

        schedule_id = cursor.lastrowid

        for channel in self.values:

            cursor.execute(
                """
                INSERT OR IGNORE INTO schedule_channels
                (
                    schedule_id,
                    channel_id
                )
                VALUES (?, ?)
                """,
                (
                    schedule_id,
                    channel.id
                )
            )

        connection.commit()
        connection.close()

        mentions = " ".join(
            channel.mention
            for channel in self.values
        )

        await interaction.response.edit_message(
            content=(
                "## ✅ SCHEDULE CREATED\n\n"
                f"**ID:** `{schedule_id}`\n"
                f"**Pack:** `{self.pack}`\n"
                f"**Date:** `{self.date_value}`\n"
                f"**Opening:** `{self.open_time} KSA`\n"
                f"**Closing:** `{self.close_time} KSA`\n"
                f"**Channels:** {mentions}"
            ),
            view=None
        )


class ChannelSelectView(discord.ui.View):

    def __init__(
        self,
        pack,
        date_value,
        open_time,
        close_time
    ):

        super().__init__(
            timeout=180
        )

        self.add_item(
            ChannelSelect(
                pack,
                date_value,
                open_time,
                close_time
            )
        )


class Scheduler(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.scheduler_loop.start()

    def cog_unload(self):

        self.scheduler_loop.cancel()

    schedule = app_commands.Group(
        name="schedule",
        description="Manage registration schedules"
    )

    # =========================
    # SCHEDULE ADD
    # =========================

    @schedule.command(
        name="add",
        description="Create a registration schedule"
    )
    @app_commands.describe(
        pack="Registration pack",
        date="Date: DD/MM/YYYY",
        open_time="Opening time in KSA: HH:MM",
        close_time="Closing time in KSA: HH:MM"
    )
    @app_commands.choices(
        pack=[
            app_commands.Choice(
                name="CLASH",
                value="CLASH"
            ),
            app_commands.Choice(
                name="EMPIRE",
                value="EMPIRE"
            ),
            app_commands.Choice(
                name="TRAINING",
                value="TRAINING"
            )
        ]
    )
    async def schedule_add(
        self,
        interaction: discord.Interaction,
        pack: app_commands.Choice[str],
        date: str,
        open_time: str,
        close_time: str
    ):

        if not is_staff(interaction):

            await interaction.response.send_message(
                "❌ You are not allowed to use the Scheduler.",
                ephemeral=True
            )

            return

        try:

            start = parse_schedule_datetime(
                date,
                open_time
            )

            end = parse_schedule_datetime(
                date,
                close_time
            )

        except ValueError:

            await interaction.response.send_message(
                "❌ Invalid format.\n\n"
                "Date: `DD/MM/YYYY`\n"
                "Time: `HH:MM`",
                ephemeral=True
            )

            return

        now = datetime.now(KSA)

        if start < now:

            await interaction.response.send_message(
                "❌ The opening time is already in the past.",
                ephemeral=True
            )

            return

        if end <= start:

            await interaction.response.send_message(
                "❌ Closing time must be after opening time.",
                ephemeral=True
            )

            return

        await interaction.response.send_message(
            (
                "## 📅 SCHEDULE SETUP\n\n"
                f"**Pack:** `{pack.value}`\n"
                f"**Date:** `{date}`\n"
                f"**Opening:** `{open_time} KSA`\n"
                f"**Closing:** `{close_time} KSA`\n\n"
                "Select **one or more registration channels**:"
            ),
            view=ChannelSelectView(
                pack.value,
                date,
                open_time,
                close_time
            ),
            ephemeral=True
        )

    # =========================
    # SCHEDULE LIST
    # =========================

    @schedule.command(
        name="list",
        description="Show scheduled registrations"
    )
    async def schedule_list(
        self,
        interaction: discord.Interaction
    ):

        if not is_staff(interaction):

            await interaction.response.send_message(
                "❌ You are not allowed to use the Scheduler.",
                ephemeral=True
            )

            return

        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                id,
                pack,
                date,
                open_time,
                close_time
            FROM schedules
            ORDER BY date, open_time
            """
        )

        schedules = cursor.fetchall()

        result = []

        for schedule in schedules:

            schedule_id = schedule[0]
            pack = schedule[1]
            date = schedule[2]
            open_time = schedule[3]
            close_time = schedule[4]

            cursor.execute(
                """
                SELECT channel_id
                FROM schedule_channels
                WHERE schedule_id = ?
                """,
                (schedule_id,)
            )

            channels = cursor.fetchall()

            channel_mentions = []

            for row in channels:

                channel = interaction.guild.get_channel(
                    row[0]
                )

                if channel:
                    channel_mentions.append(
                        channel.mention
                    )

            if channel_mentions:
                channel_text = " ".join(
                    channel_mentions
                )
            else:
                channel_text = "No channels"

            result.append(
                (
                    f"**#{schedule_id} — {pack}**\n"
                    f"📅 {date}\n"
                    f"🟢 {open_time} KSA\n"
                    f"🔴 {close_time} KSA\n"
                    f"📢 {channel_text}"
                )
            )

        connection.close()

        if not result:

            await interaction.response.send_message(
                "📭 No schedules found.",
                ephemeral=True
            )

            return

        text = "\n\n".join(result)

        if len(text) > 3900:
            text = text[:3900] + "\n..."

        embed = discord.Embed(
            title="📅 GENRA SCHEDULES",
            description=text
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

    # =========================
    # SCHEDULE REMOVE
    # =========================

    @schedule.command(
        name="remove",
        description="Remove a registration schedule"
    )
    @app_commands.describe(
        schedule_id="Schedule ID"
    )
    async def schedule_remove(
        self,
        interaction: discord.Interaction,
        schedule_id: int
    ):

        if not is_staff(interaction):

            await interaction.response.send_message(
                "❌ You are not allowed to use the Scheduler.",
                ephemeral=True
            )

            return

        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT id
            FROM schedules
            WHERE id = ?
            """,
            (schedule_id,)
        )

        schedule = cursor.fetchone()

        if not schedule:

            connection.close()

            await interaction.response.send_message(
                "❌ Schedule not found.",
                ephemeral=True
            )

            return

        cursor.execute(
            """
            DELETE FROM schedule_channels
            WHERE schedule_id = ?
            """,
            (schedule_id,)
        )

        cursor.execute(
            """
            DELETE FROM schedules
            WHERE id = ?
            """,
            (schedule_id,)
        )

        connection.commit()
        connection.close()

        await interaction.response.send_message(
            f"✅ Schedule **#{schedule_id}** removed.",
            ephemeral=True
        )

    # =========================
    # SCHEDULER LOOP
    # =========================

    @tasks.loop(seconds=30)
    async def scheduler_loop(self):

        now = datetime.now(KSA)

        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                id,
                pack,
                date,
                open_time,
                close_time,
                opened_at,
                closed_at
            FROM schedules
            """
        )

        schedules = cursor.fetchall()

        for schedule in schedules:

            (
                schedule_id,
                pack,
                date,
                open_time,
                close_time,
                opened_at,
                closed_at
            ) = schedule

            try:

                start = parse_schedule_datetime(
                    date,
                    open_time
                )

                end = parse_schedule_datetime(
                    date,
                    close_time
                )

            except ValueError:

                continue

            cursor.execute(
                """
                SELECT channel_id
                FROM schedule_channels
                WHERE schedule_id = ?
                """,
                (schedule_id,)
            )

            channel_rows = cursor.fetchall()

            # =========================
            # OPEN
            # =========================

            if start <= now < end:

                if opened_at is None:

                    for row in channel_rows:

                        channel = self.bot.get_channel(
                            row[0]
                        )

                        if channel:

                            await self.open_channel(
                                channel,
                                pack
                            )

                            try:

                                await channel.send(
                                    self.build_open_message(
                                        channel.guild
                                    )
                                )

                            except discord.HTTPException:
                                pass

                    cursor.execute(
                        """
                        UPDATE schedules
                        SET opened_at = ?
                        WHERE id = ?
                        """,
                        (
                            now.isoformat(),
                            schedule_id
                        )
                    )

                else:

                    for row in channel_rows:

                        channel = self.bot.get_channel(
                            row[0]
                        )

                        if channel:

                            await self.reconcile_channel(
                                channel
                            )

            # =========================
            # CLOSE
            # =========================

            elif now >= end:

                if closed_at is None:

                    for row in channel_rows:

                        channel = self.bot.get_channel(
                            row[0]
                        )

                        if channel:

                            await self.close_channel(
                                channel,
                                pack
                            )

                            try:

                                await channel.send(
                                    CLOSE_MESSAGE
                                )

                            except discord.HTTPException:
                                pass

                    cursor.execute(
                        """
                        UPDATE schedules
                        SET closed_at = ?
                        WHERE id = ?
                        """,
                        (
                            now.isoformat(),
                            schedule_id
                        )
                    )

        connection.commit()
        connection.close()

    @scheduler_loop.before_loop
    async def before_scheduler_loop(self):

        await self.bot.wait_until_ready()

    # =========================
    # OPEN CHANNEL
    # =========================

    async def open_channel(
        self,
        channel,
        pack
    ):

        role = get_pack_role(
            channel.guild,
            pack
        )

        if role is None:
            return

        try:

            await channel.set_permissions(
                channel.guild.default_role,
                send_messages=False
            )

            await channel.set_permissions(
                role,
                send_messages=True
            )

        except discord.Forbidden:

            print(
                f"Missing permissions for #{channel.name}"
            )

        except discord.HTTPException as error:

            print(
                f"Channel permission error: {error}"
            )

    # =========================
    # CLOSE CHANNEL
    # =========================

    async def close_channel(
        self,
        channel,
        pack
    ):

        role = get_pack_role(
            channel.guild,
            pack
        )

        if role is None:
            return

        try:

            await channel.set_permissions(
                role,
                send_messages=False
            )

        except discord.Forbidden:

            print(
                f"Missing permissions for #{channel.name}"
            )

        except discord.HTTPException as error:

            print(
                f"Channel permission error: {error}"
            )

    # =========================
    # RECONCILE CHANNEL
    # =========================

    async def reconcile_channel(
        self,
        channel
    ):

        now = datetime.now(KSA)

        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                pack,
                date,
                open_time,
                close_time
            FROM schedules
            INNER JOIN schedule_channels
                ON schedules.id = schedule_channels.schedule_id
            WHERE schedule_channels.channel_id = ?
            """,
            (channel.id,)
        )

        schedules = cursor.fetchall()

        connection.close()

        active_packs = set()

        for schedule in schedules:

            pack = schedule[0]
            date = schedule[1]
            open_time = schedule[2]
            close_time = schedule[3]

            try:

                start = parse_schedule_datetime(
                    date,
                    open_time
                )

                end = parse_schedule_datetime(
                    date,
                    close_time
                )

            except ValueError:

                continue

            if start <= now < end:
                active_packs.add(pack)

        for pack in PACKS:

            role = get_pack_role(
                channel.guild,
                pack
            )

            if role is None:
                continue

            try:

                await channel.set_permissions(
                    role,
                    send_messages=(
                        pack in active_packs
                    )
                )

            except discord.HTTPException:
                pass

        try:

            await channel.set_permissions(
                channel.guild.default_role,
                send_messages=False
            )

        except discord.HTTPException:
            pass

    # =========================
    # OPEN MESSAGE
    # =========================

    def build_open_message(
        self,
        guild
    ):

        clash = get_pack_role(
            guild,
            "CLASH"
        )

        empire = get_pack_role(
            guild,
            "EMPIRE"
        )

        training = get_pack_role(
            guild,
            "TRAINING"
        )

        clash_text = (
            clash.mention
            if clash
            else "@CLASH"
        )

        empire_text = (
            empire.mention
            if empire
            else "@EMPIRE"
        )

        training_text = (
            training.mention
            if training
            else "@TRAINING"
        )

        return OPEN_MESSAGE.replace(
            "@CLASH",
            clash_text
        ).replace(
            "@EMPIRE",
            empire_text
        ).replace(
            "@TRAINING",
            training_text
        )


async def setup(bot):

    await bot.add_cog(
        Scheduler(bot)
    )
