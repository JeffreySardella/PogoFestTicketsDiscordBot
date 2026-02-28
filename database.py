import aiosqlite

DB_PATH = "bot_data.db"


class Database:
    def __init__(self):
        self.db_path = DB_PATH

    async def init(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS guild_configs (
                    guild_id    INTEGER PRIMARY KEY,
                    channel_id  INTEGER,
                    role_id     INTEGER
                )
            """)
            await db.commit()

    async def set_channel(self, guild_id: int, channel_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO guild_configs (guild_id, channel_id)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET channel_id = excluded.channel_id
            """, (guild_id, channel_id))
            await db.commit()

    async def set_role(self, guild_id: int, role_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO guild_configs (guild_id, role_id)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET role_id = excluded.role_id
            """, (guild_id, role_id))
            await db.commit()

    async def get_config(self, guild_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM guild_configs WHERE guild_id = ?", (guild_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_all_configs(self):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM guild_configs") as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def remove_config(self, guild_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM guild_configs WHERE guild_id = ?", (guild_id,)
            )
            await db.commit()
