"""Économie RP en Louis d'or : solde, revenu quotidien, travail selon la villa, dons, fortune."""
import random

import discord
from discord import app_commands
from discord.ext import commands

from bot import config
from bot.utils import a_role, embed, format_duree, now, rang_requis

M = f"{config.MONNAIE_EMOJI} {config.MONNAIE}"
TRAVAUX = {
    "resident_haussmann": [
        "Vous concluez un partenariat au bureau des affaires",
        "Vous présentez votre projet à un investisseur autour d'un café",
        "Vous animez un atelier pour les autres entrepreneurs",
        "Vous bouclez une levée de fonds, champagne",
    ],
    "resident_jaures": [
        "Vous aidez en cuisine pour le dîner de la maison",
        "Vous entretenez le jardin d'hiver",
        "Vous donnez un coup de main à la bibliothèque",
        "Vous préparez le petit salon pour la soirée",
    ],
    None: [
        "Vous rendez service à la direction",
        "Vous organisez les archives de la Fondation",
        "Vous accueillez de nouveaux invités dans le hall",
    ],
}


def fmt(montant: int) -> str:
    return f"**{montant:,}".replace(",", " ") + f"** {M}"


class Economie(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _compte(self, guild_id: int, user_id: int):
        await self.bot.db.execute("INSERT OR IGNORE INTO economie (guild_id, user_id) VALUES (?, ?)", guild_id, user_id)
        return await self.bot.db.fetchone("SELECT * FROM economie WHERE guild_id = ? AND user_id = ?",
                                          guild_id, user_id)

    async def _crediter(self, guild_id: int, user_id: int, montant: int):
        await self._compte(guild_id, user_id)
        await self.bot.db.execute("UPDATE economie SET solde = solde + ? WHERE guild_id = ? AND user_id = ?",
                                  montant, guild_id, user_id)

    @app_commands.command(name="solde", description="Consulte votre fortune (ou celle d'un membre).")
    @app_commands.guild_only()
    async def solde(self, interaction: discord.Interaction, membre: discord.Member | None = None):
        membre = membre or interaction.user
        compte = await self._compte(interaction.guild.id, membre.id)
        await interaction.response.send_message(
            embed=embed(f"Coffre de {membre.display_name}", fmt(compte["solde"])))

    @app_commands.command(name="quotidien", description="Recevez votre rente quotidienne.")
    @app_commands.guild_only()
    async def quotidien(self, interaction: discord.Interaction):
        g, u = interaction.guild.id, interaction.user.id
        compte = await self._compte(g, u)
        reste = compte["dernier_quotidien"] + 86400 - now()
        if reste > 0:
            await interaction.response.send_message(f"Votre rente sera disponible dans {format_duree(reste)}.",
                                                    ephemeral=True)
            return
        gain = random.randint(*config.QUOTIDIEN_GAIN)
        await self.bot.db.execute("UPDATE economie SET solde = solde + ?, dernier_quotidien = ? "
                                  "WHERE guild_id = ? AND user_id = ?", gain, now(), g, u)
        await interaction.response.send_message(embed=embed("Rente quotidienne", f"Vous recevez {fmt(gain)}."))

    @app_commands.command(name="travailler", description="Rendez-vous utile à la maison (une fois par heure).")
    @app_commands.guild_only()
    async def travailler(self, interaction: discord.Interaction):
        g, u = interaction.guild.id, interaction.user.id
        compte = await self._compte(g, u)
        reste = compte["dernier_travail"] + config.TRAVAIL_COOLDOWN - now()
        if reste > 0:
            await interaction.response.send_message(f"Reposez-vous encore {format_duree(reste)}.", ephemeral=True)
            return
        villa = next((k for k in ("resident_haussmann", "resident_jaures") if a_role(interaction.user, k)), None)
        couleur = {"resident_haussmann": config.Couleurs.HAUSSMANN,
                   "resident_jaures": config.Couleurs.JAURES}.get(villa, config.Couleurs.FONDATION)
        gain = random.randint(*config.TRAVAIL_GAIN)
        await self.bot.db.execute("UPDATE economie SET solde = solde + ?, dernier_travail = ? "
                                  "WHERE guild_id = ? AND user_id = ?", gain, now(), g, u)
        await interaction.response.send_message(
            embed=embed(description=f"{random.choice(TRAVAUX[villa])}. Vous gagnez {fmt(gain)}.", color=couleur))

    @app_commands.command(name="donner", description="Offrez des Louis d'or à un membre.")
    @app_commands.guild_only()
    async def donner(self, interaction: discord.Interaction, membre: discord.Member,
                     montant: app_commands.Range[int, 1, 1_000_000]):
        if membre.bot or membre.id == interaction.user.id:
            await interaction.response.send_message("Destinataire invalide.", ephemeral=True)
            return
        g = interaction.guild.id
        compte = await self._compte(g, interaction.user.id)
        if compte["solde"] < montant:
            await interaction.response.send_message("Votre coffre n'est pas assez garni.", ephemeral=True)
            return
        await self._crediter(g, interaction.user.id, -montant)
        await self._crediter(g, membre.id, montant)
        await interaction.response.send_message(
            embed=embed(description=f"{interaction.user.mention} offre {fmt(montant)} à {membre.mention}."))

    @app_commands.command(name="fortune", description="Les 10 plus grandes fortunes de la maison.")
    @app_commands.guild_only()
    async def fortune(self, interaction: discord.Interaction):
        rows = await self.bot.db.fetchall(
            "SELECT user_id, solde FROM economie WHERE guild_id = ? AND solde > 0 ORDER BY solde DESC LIMIT 10",
            interaction.guild.id)
        lignes = [f"`{i + 1}.` <@{r['user_id']}> · {fmt(r['solde'])}" for i, r in enumerate(rows)]
        await interaction.response.send_message(
            embed=embed("Les grandes fortunes", "\n".join(lignes) or "Les coffres sont vides."))

    @app_commands.command(name="crediter", description="Ajoute (ou retire, montant négatif) des Louis d'or.")
    @app_commands.guild_only()
    @rang_requis(4)
    async def crediter(self, interaction: discord.Interaction, membre: discord.Member, montant: int):
        await self._crediter(interaction.guild.id, membre.id, montant)
        compte = await self._compte(interaction.guild.id, membre.id)
        await interaction.response.send_message(
            f"{membre.mention} : {'+' if montant >= 0 else ''}{montant} · nouveau solde {fmt(compte['solde'])}",
            ephemeral=True)


async def setup(bot):
    await bot.add_cog(Economie(bot))
