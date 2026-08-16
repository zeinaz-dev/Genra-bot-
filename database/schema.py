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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS packs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            price REAL DEFAULT 0,
            max_teams INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subscribers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            pack TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

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
