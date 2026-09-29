"""Fonctions partagées : embeds, rangs, accès aux rôles/salons configurés, durées."""
import re
from datetime import datetime, timezone

import discord
from discord import app_commands

from bot import config

RANGS = {r["name"]: r["rang"] for r in config.ROLES}


def embed(title=None, description=None, color=config.Couleurs.FONDATION) -> discord.Embed:
    e = discord.Embed(title=title, description=description, color=color, timestamp=datetime.now(timezone.utc))
    e.set_footer(text=config.SIGNATURE)
    return e


def rang(member: discord.Member) -> int:
    if member.guild_permissions.administrator or member.id == member.guild.owner_id:
        return 5
    return max((RANGS.get(r.name, 0) for r in member.roles), default=0)


def a_role(member: discord.Member, key: str) -> bool:
    return any(r.name == config.ROLE_NAMES[key] for r in member.roles)


def rang_requis(minimum: int):
    """Décorateur de commande slash : rang minimum (2 = Gérant, 3 = Resp. villa, 4 = Responsable, 5 = Fondation)."""
    async def predicate(interaction: discord.Interaction) -> bool:
        return isinstance(interaction.user, discord.Member) and rang(interaction.user) >= minimum
    return app_commands.check(predicate)


def get_role(guild: discord.Guild, key: str) -> discord.Role | None:
    return discord.utils.get(guild.roles, name=config.ROLE_NAMES[key])


async def get_salon(bot, guild: discord.Guild, key: str):
    cid = await bot.db.get_config(guild.id, f"salon_{key}")
    return guild.get_channel(int(cid)) if cid else None


async def log(bot, guild: discord.Guild, key: str, e: discord.Embed, **kwargs):
    salon = await get_salon(bot, guild, key)
    if salon:
        try:
            await salon.send(embed=e, **kwargs)
        except discord.HTTPException:
            pass


_DUREE = re.compile(r"(\d+)\s*(s|m|h|j|d|sem|w)", re.I)
_UNITES = {"s": 1, "m": 60, "h": 3600, "j": 86400, "d": 86400, "sem": 604800, "w": 604800}


def parse_duree(texte: str) -> int | None:
    """'1j2h30m' -> secondes. None si illisible."""
    total = sum(int(n) * _UNITES[u.lower()] for n, u in _DUREE.findall(texte))
    return total or None


def format_duree(secondes: int) -> str:
    parts = []
    for nom, val in (("j", 86400), ("h", 3600), ("min", 60)):
        if secondes >= val:
            parts.append(f"{secondes // val} {nom}")
            secondes %= val
    return " ".join(parts) or f"{secondes} s"


def now() -> int:
    return int(datetime.now(timezone.utc).timestamp())
