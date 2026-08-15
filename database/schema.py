import sqlite3

DATABASE = "genra.db"


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

    default_packs = [
        ("CLASH", 24.99, 0),
        ("EMPIRE", 19.99, 0),
        ("TRAINING", 5.00, 0)
    ]

    for pack in default_packs:
        cursor.execute(
            """
            INSERT OR IGNORE INTO packs (name, price, max_teams)
            VALUES (?, ?, ?)
            """,
            pack
        )

    connection.commit()
    connection.close()
