import sqlite3

DATABASE = "genra.db"


def add_column_if_missing(
    cursor,
    table,
    column,
    definition
):
    cursor.execute(
        f"PRAGMA table_info({table})"
    )

    columns = [
        row[1]
        for row in cursor.fetchall()
    ]

    if column not in columns:
        cursor.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
        )


async def create_tables():

    connection = sqlite3.connect(DATABASE)
    cursor = connection.cursor()

    # =========================
    # PACKS
    # =========================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS packs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            price REAL DEFAULT 0,
            max_teams INTEGER DEFAULT 0
        )
    """)

    # =========================
    # SUBSCRIBERS
    # =========================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subscribers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            pack TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # =========================
    # TEAMS
    # =========================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_name TEXT NOT NULL,
            discord_id INTEGER NOT NULL,
            pack TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    add_column_if_missing(
        cursor,
        "teams",
        "group_name",
        "TEXT DEFAULT 'A'"
    )

    add_column_if_missing(
        cursor,
        "teams",
        "message_id",
        "INTEGER"
    )

    add_column_if_missing(
        cursor,
        "teams",
        "channel_id",
        "INTEGER"
    )

    add_column_if_missing(
        cursor,
        "teams",
        "username",
        "TEXT"
    )

    # =========================
    # ROLE HISTORY
    # =========================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS role_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            package TEXT NOT NULL,
            obtained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(discord_id, role_id)
        )
    """)

    # =========================
    # SCHEDULES
    # =========================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pack TEXT NOT NULL,
            date TEXT NOT NULL,
            open_time TEXT NOT NULL,
            close_time TEXT NOT NULL,
            created_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            opened_at TEXT,
            closed_at TEXT
        )
    """)

    # =========================
    # SCHEDULE CHANNELS
    # =========================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schedule_channels (
            schedule_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            PRIMARY KEY (schedule_id, channel_id),
            FOREIGN KEY (schedule_id)
                REFERENCES schedules(id)
                ON DELETE CASCADE
        )
    """)

    # =========================
    # DEFAULT PACKS
    # =========================

    default_packs = [
        ("CLASH", 24.99, 0),
        ("EMPIRE", 19.99, 0),
        ("TRAINING", 9.99, 0)
    ]

    for pack in default_packs:

        cursor.execute(
            """
            INSERT OR IGNORE INTO packs
            (name, price, max_teams)
            VALUES (?, ?, ?)
            """,
            pack
        )

    connection.commit()
    connection.close()
