"""Niveaux : XP par message (avec délai anti-farm), montée de niveau, rang et classement."""
import random

import discord
from discord import app_commands
from discord.ext import commands

from bot import config
from bot.utils import embed, get_salon, now


def xp_pour_niveau(niveau: int) -> int:
    """XP nécessaire pour passer du niveau n au niveau n+1."""
    return 5 * niveau ** 2 + 50 * niveau + 100


def niveau_depuis_xp(xp: int) -> tuple[int, int, int]:
    """Renvoie (niveau, xp dans le niveau, xp requis pour le suivant)."""
    niveau = 0
    while xp >= xp_pour_niveau(niveau):
        xp -= xp_pour_niveau(niveau)
        niveau += 1
    return niveau, xp, xp_pour_niveau(niveau)


def barre(actuel: int, total: int, largeur: int = 14) -> str:
    plein = round(largeur * actuel / total) if total else 0
    return "▰" * plein + "▱" * (largeur - plein)


class Niveaux(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        db, g, u = self.bot.db, message.guild.id, message.author.id
        row = await db.fetchone("SELECT xp, niveau, dernier_msg FROM niveaux WHERE guild_id = ? AND user_id = ?", g, u)
        if row and now() - row["dernier_msg"] < config.XP_COOLDOWN:
            return
        xp = (row["xp"] if row else 0) + random.randint(config.XP_MIN, config.XP_MAX)
        ancien = row["niveau"] if row else 0
        niveau = niveau_depuis_xp(xp)[0]
        await db.execute(
            "INSERT INTO niveaux (guild_id, user_id, xp, niveau, dernier_msg) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(guild_id, user_id) DO UPDATE SET xp = excluded.xp, niveau = excluded.niveau, "
            "dernier_msg = excluded.dernier_msg", g, u, xp, niveau, now())

        if niveau > ancien:
            salon = await get_salon(self.bot, message.guild, "distinctions") or message.channel
            await salon.send(embed=embed(
                description=f"🏅 {message.author.mention} accède au **niveau {niveau}**. Toutes nos félicitations."))

    @app_commands.command(name="rang", description="Affiche votre niveau (ou celui d'un membre).")
    @app_commands.guild_only()
    async def rang(self, interaction: discord.Interaction, membre: discord.Member | None = None):
        membre = membre or interaction.user
        row = await self.bot.db.fetchone("SELECT xp FROM niveaux WHERE guild_id = ? AND user_id = ?",
                                         interaction.guild.id, membre.id)
        xp_total = row["xp"] if row else 0
        niveau, actuel, requis = niveau_depuis_xp(xp_total)
        position = await self.bot.db.fetchone(
            "SELECT COUNT(*) + 1 AS p FROM niveaux WHERE guild_id = ? AND xp > ?", interaction.guild.id, xp_total)
        e = embed(membre.display_name, color=membre.colour.value or config.Couleurs.FONDATION)
        e.set_thumbnail(url=membre.display_avatar.url)
        e.add_field(name="Niveau", value=str(niveau))
        e.add_field(name="Classement", value=f"#{position['p']}")
        e.add_field(name="XP totale", value=str(xp_total))
        e.add_field(name="Progression", value=f"{barre(actuel, requis)}  {actuel}/{requis}", inline=False)
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="classement", description="Les 10 membres les plus actifs.")
    @app_commands.guild_only()
    async def classement(self, interaction: discord.Interaction):
        rows = await self.bot.db.fetchall(
            "SELECT user_id, xp, niveau FROM niveaux WHERE guild_id = ? ORDER BY xp DESC LIMIT 10",
            interaction.guild.id)
        medailles = ["🥇", "🥈", "🥉"]
        lignes = [f"{medailles[i] if i < 3 else f'`{i + 1}.`'} <@{r['user_id']}> · niveau {r['niveau']} ({r['xp']} XP)"
                  for i, r in enumerate(rows)]
        await interaction.response.send_message(
            embed=embed("Tableau d'honneur", "\n".join(lignes) or "Personne n'a encore parlé."))


async def setup(bot):
    await bot.add_cog(Niveaux(bot))
