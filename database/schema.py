import sqlite3

DATABASE = "registrations.db"


def get_connection():
    connection = sqlite3.connect(DATABASE)

    connection.row_factory = sqlite3.Row

    return connection


def create_tables():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            channel_ids TEXT NOT NULL,
            role_id INTEGER NOT NULL,
            open_datetime TEXT NOT NULL,
            close_datetime TEXT,
            message TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'scheduled'
        )
        """
    )

    connection.commit()
    connection.close()


def create_schedule(
    name,
    channel_ids,
    role_id,
    open_datetime,
    close_datetime,
    message
):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO schedules
        (
            name,
            channel_ids,
            role_id,
            open_datetime,
            close_datetime,
            message,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, 'scheduled')
        """,
        (
            name,
            ",".join(str(x) for x in channel_ids),
            role_id,
            open_datetime,
            close_datetime,
            message
        )
    )

    schedule_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return schedule_id


def get_schedule(schedule_id):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM schedules WHERE id = ?",
        (schedule_id,)
    )

    schedule = cursor.fetchone()

    connection.close()

    return schedule


def get_active_schedules():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM schedules
        WHERE status IN ('scheduled', 'open')
        ORDER BY open_datetime ASC
        """
    )

    schedules = cursor.fetchall()

    connection.close()

    return schedules


def update_status(schedule_id, status):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE schedules
        SET status = ?
        WHERE id = ?
        """,
        (
            status,
            schedule_id
        )
    )

    connection.commit()
    connection.close()


def delete_schedule(schedule_id):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        "DELETE FROM schedules WHERE id = ?",
        (schedule_id,)
    )

    connection.commit()
    connection.close()
