"""Accès SQLite asynchrone. Une seule connexion partagée par tout le bot."""
import os

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS config (
    guild_id INTEGER NOT NULL,
    key TEXT NOT NULL,
    value TEXT,
    PRIMARY KEY (guild_id, key)
);
CREATE TABLE IF NOT EXISTS avertissements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    mod_id INTEGER NOT NULL,
    raison TEXT,
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS niveaux (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    xp INTEGER NOT NULL DEFAULT 0,
    niveau INTEGER NOT NULL DEFAULT 0,
    dernier_msg INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
);
CREATE TABLE IF NOT EXISTS economie (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    solde INTEGER NOT NULL DEFAULT 0,
    dernier_quotidien INTEGER NOT NULL DEFAULT 0,
    dernier_travail INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
);
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    channel_id INTEGER UNIQUE,
    user_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    statut TEXT NOT NULL DEFAULT 'en attente',
    ferme INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS giveaways (
    message_id INTEGER PRIMARY KEY,
    guild_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    lot TEXT NOT NULL,
    gagnants INTEGER NOT NULL,
    fin INTEGER NOT NULL,
    hote_id INTEGER NOT NULL,
    termine INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS giveaway_participants (
    message_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    PRIMARY KEY (message_id, user_id)
);
"""


class Database:
    def __init__(self, path: str):
        self.path = path
        self.conn: aiosqlite.Connection | None = None

    async def connect(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self.conn = await aiosqlite.connect(self.path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.executescript(SCHEMA)
        await self.conn.commit()

    async def close(self):
        if self.conn:
            await self.conn.close()

    async def execute(self, query: str, *args):
        cur = await self.conn.execute(query, args)
        await self.conn.commit()
        return cur

    async def fetchone(self, query: str, *args):
        async with self.conn.execute(query, args) as cur:
            return await cur.fetchone()

    async def fetchall(self, query: str, *args):
        async with self.conn.execute(query, args) as cur:
            return await cur.fetchall()

    async def get_config(self, guild_id: int, key: str) -> str | None:
        row = await self.fetchone("SELECT value FROM config WHERE guild_id = ? AND key = ?", guild_id, key)
        return row["value"] if row else None

    async def set_config(self, guild_id: int, key: str, value) -> None:
        await self.execute(
            "INSERT INTO config (guild_id, key, value) VALUES (?, ?, ?) "
            "ON CONFLICT(guild_id, key) DO UPDATE SET value = excluded.value",
            guild_id, key, str(value),
        )
