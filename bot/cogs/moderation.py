"""Modération : sanctions, avertissements, anti-spam, anti-invitations, anti-raid."""
import re
import time
from collections import defaultdict, deque
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

from bot import config
from bot.utils import embed, format_duree, log, now, parse_duree, rang, rang_requis

C = config.Couleurs
INVITATION = re.compile(r"(discord\.gg|discord(app)?\.com/invite)/\S+", re.I)


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.messages: dict[tuple[int, int], deque] = defaultdict(lambda: deque(maxlen=config.SPAM_MESSAGES))
        self.arrivees: dict[int, deque] = defaultdict(lambda: deque(maxlen=config.RAID_JOINS))
        self.mode_raid: dict[int, float] = {}  # guild_id -> fin du mode raid (timestamp)

    # --- Outils -----------------------------------------------------------------------
    async def _hierarchie_ok(self, interaction: discord.Interaction, cible: discord.Member) -> bool:
        if cible.id == interaction.user.id:
            await interaction.response.send_message("Vous ne pouvez pas vous sanctionner vous-même.", ephemeral=True)
            return False
        if rang(cible) >= rang(interaction.user) or cible.top_role >= interaction.guild.me.top_role:
            await interaction.response.send_message("Ce membre est au-dessus de votre rang ou de celui du bot.",
                                                    ephemeral=True)
            return False
        return True

    async def _journal(self, guild, action: str, cible, moderateur, raison: str, couleur=C.ALERTE):
        e = embed(action, color=couleur)
        e.add_field(name="Membre", value=f"{cible.mention} (`{cible.id}`)")
        e.add_field(name="Par", value=moderateur.mention)
        e.add_field(name="Raison", value=raison or "Non précisée", inline=False)
        await log(self.bot, guild, "logs_moderation", e)

    async def _prevenir(self, membre, action: str, raison: str):
        try:
            await membre.send(embed=embed(action, f"**Serveur :** {membre.guild.name}\n**Raison :** {raison}",
                                          color=C.ALERTE))
        except discord.HTTPException:
            pass

    # --- Commandes --------------------------------------------------------------------
    @app_commands.command(name="avertir", description="Donne un avertissement à un membre.")
    @app_commands.guild_only()
    @rang_requis(2)
    async def avertir(self, interaction: discord.Interaction, membre: discord.Member, raison: str):
        if not await self._hierarchie_ok(interaction, membre):
            return
        await self.bot.db.execute(
            "INSERT INTO avertissements (guild_id, user_id, mod_id, raison, created_at) VALUES (?, ?, ?, ?, ?)",
            interaction.guild.id, membre.id, interaction.user.id, raison, now())
        row = await self.bot.db.fetchone("SELECT COUNT(*) AS n FROM avertissements WHERE guild_id = ? AND user_id = ?",
                                         interaction.guild.id, membre.id)
        n = row["n"]
        texte = f"{membre.mention} a reçu un avertissement ({n}). Raison : {raison}"
        if n % config.AVERTISSEMENTS_AVANT_SANCTION == 0:
            await membre.timeout(timedelta(hours=1), reason=f"{n} avertissements")
            texte += "\nSanction automatique : exclusion temporaire d'une heure."
        await interaction.response.send_message(embed=embed("Avertissement", texte, color=C.ALERTE))
        await self._prevenir(membre, "Vous avez reçu un avertissement", raison)
        await self._journal(interaction.guild, f"Avertissement n°{n}", membre, interaction.user, raison)

    @app_commands.command(name="avertissements", description="Liste les avertissements d'un membre.")
    @app_commands.guild_only()
    @rang_requis(2)
    async def avertissements(self, interaction: discord.Interaction, membre: discord.Member):
        rows = await self.bot.db.fetchall(
            "SELECT id, raison, mod_id, created_at FROM avertissements WHERE guild_id = ? AND user_id = ? "
            "ORDER BY id DESC LIMIT 15", interaction.guild.id, membre.id)
        if not rows:
            await interaction.response.send_message(f"{membre.mention} n'a aucun avertissement.", ephemeral=True)
            return
        lignes = [f"`#{r['id']}` <t:{r['created_at']}:d> par <@{r['mod_id']}> · {r['raison']}" for r in rows]
        await interaction.response.send_message(
            embed=embed(f"Avertissements · {membre.display_name}", "\n".join(lignes)), ephemeral=True)

    @app_commands.command(name="retirer-avertissement", description="Supprime un avertissement par son numéro.")
    @app_commands.guild_only()
    @rang_requis(3)
    async def retirer_avertissement(self, interaction: discord.Interaction, numero: int):
        cur = await self.bot.db.execute("DELETE FROM avertissements WHERE id = ? AND guild_id = ?",
                                        numero, interaction.guild.id)
        msg = f"Avertissement #{numero} supprimé." if cur.rowcount else "Numéro introuvable."
        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name="exclure-temp", description="Rend un membre muet temporairement (ex : 10m, 2h, 1j).")
    @app_commands.guild_only()
    @rang_requis(2)
    async def exclure_temp(self, interaction: discord.Interaction, membre: discord.Member, duree: str, raison: str):
        secondes = parse_duree(duree)
        if not secondes or secondes > 28 * 86400:
            await interaction.response.send_message("Durée invalide (max 28 jours). Exemple : 30m, 2h, 1j.",
                                                    ephemeral=True)
            return
        if not await self._hierarchie_ok(interaction, membre):
            return
        await membre.timeout(timedelta(seconds=secondes), reason=raison)
        await interaction.response.send_message(embed=embed(
            "Exclusion temporaire", f"{membre.mention} · {format_duree(secondes)}\nRaison : {raison}", color=C.ALERTE))
        await self._prevenir(membre, f"Exclusion temporaire ({format_duree(secondes)})", raison)
        await self._journal(interaction.guild, "Exclusion temporaire", membre, interaction.user,
                            f"{raison} · {format_duree(secondes)}")

    @app_commands.command(name="lever-exclusion", description="Met fin à une exclusion temporaire.")
    @app_commands.guild_only()
    @rang_requis(2)
    async def lever_exclusion(self, interaction: discord.Interaction, membre: discord.Member):
        await membre.timeout(None)
        await interaction.response.send_message(f"L'exclusion de {membre.mention} est levée.", ephemeral=True)
        await self._journal(interaction.guild, "Exclusion levée", membre, interaction.user, "", C.SUCCES)

    @app_commands.command(name="expulser", description="Expulse un membre du serveur.")
    @app_commands.guild_only()
    @rang_requis(3)
    async def expulser(self, interaction: discord.Interaction, membre: discord.Member, raison: str):
        if not await self._hierarchie_ok(interaction, membre):
            return
        await self._prevenir(membre, "Vous avez été expulsé", raison)
        await membre.kick(reason=raison)
        await interaction.response.send_message(embed=embed("Expulsion", f"{membre} · {raison}", color=C.ALERTE))
        await self._journal(interaction.guild, "Expulsion", membre, interaction.user, raison)

    @app_commands.command(name="bannir", description="Bannit définitivement un membre.")
    @app_commands.guild_only()
    @rang_requis(4)
    async def bannir(self, interaction: discord.Interaction, membre: discord.Member, raison: str):
        if not await self._hierarchie_ok(interaction, membre):
            return
        await self._prevenir(membre, "Vous avez été banni", raison)
        await membre.ban(reason=raison, delete_message_seconds=86400)
        await interaction.response.send_message(embed=embed("Bannissement", f"{membre} · {raison}", color=C.ALERTE))
        await self._journal(interaction.guild, "Bannissement", membre, interaction.user, raison)

    @app_commands.command(name="debannir", description="Lève le bannissement d'un utilisateur (identifiant).")
    @app_commands.guild_only()
    @rang_requis(4)
    async def debannir(self, interaction: discord.Interaction, identifiant: str):
        try:
            user = await self.bot.fetch_user(int(identifiant))
            await interaction.guild.unban(user)
        except (ValueError, discord.NotFound):
            await interaction.response.send_message("Utilisateur introuvable ou non banni.", ephemeral=True)
            return
        await interaction.response.send_message(f"{user} n'est plus banni.", ephemeral=True)
        await self._journal(interaction.guild, "Débannissement", user, interaction.user, "", C.SUCCES)

    @app_commands.command(name="effacer", description="Supprime les derniers messages du salon (max 100).")
    @app_commands.guild_only()
    @rang_requis(2)
    async def effacer(self, interaction: discord.Interaction, nombre: app_commands.Range[int, 1, 100],
                      membre: discord.Member | None = None):
        await interaction.response.defer(ephemeral=True)
        supprimes = await interaction.channel.purge(limit=nombre, check=lambda m: membre is None or m.author == membre)
        await interaction.followup.send(f"{len(supprimes)} messages supprimés.", ephemeral=True)
        await self._journal(interaction.guild, f"Purge de {len(supprimes)} messages", interaction.user,
                            interaction.user, f"Salon {interaction.channel.mention}", C.FONDATION)

    @app_commands.command(name="verrouillage", description="Active ou coupe le mode anti-raid manuellement.")
    @app_commands.guild_only()
    @rang_requis(4)
    async def verrouillage(self, interaction: discord.Interaction, actif: bool):
        if actif:
            self.mode_raid[interaction.guild.id] = time.time() + 3600
        else:
            self.mode_raid.pop(interaction.guild.id, None)
        etat = "activé pour 1 heure" if actif else "désactivé"
        await interaction.response.send_message(f"Mode anti-raid {etat}.", ephemeral=True)
        await self._journal(interaction.guild, f"Anti-raid {etat}", interaction.user, interaction.user, "",
                            C.FONDATION)

    # --- Protections automatiques ------------------------------------------------------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild or not isinstance(message.author, discord.Member):
            return
        if rang(message.author) >= 2:
            return
        if INVITATION.search(message.content):
            try:
                await message.delete()
            except discord.HTTPException:
                return
            await message.channel.send(f"{message.author.mention}, les invitations ne sont pas autorisées ici.",
                                       delete_after=6)
            await self._journal(message.guild, "Invitation supprimée", message.author, message.guild.me,
                                f"Dans {message.channel.mention}")
            return

        historique = self.messages[(message.guild.id, message.author.id)]
        historique.append(time.time())
        if len(historique) == config.SPAM_MESSAGES and historique[-1] - historique[0] < config.SPAM_SECONDES:
            historique.clear()
            try:
                await message.author.timeout(timedelta(minutes=5), reason="Anti-spam")
                await message.channel.purge(limit=config.SPAM_MESSAGES * 2, check=lambda m: m.author == message.author)
            except discord.HTTPException:
                return
            await message.channel.send(f"{message.author.mention} est réduit au silence 5 minutes (spam).",
                                       delete_after=10)
            await self._journal(message.guild, "Anti-spam", message.author, message.guild.me,
                                "Exclusion automatique de 5 minutes")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        arrivees = self.arrivees[guild.id]
        arrivees.append(time.time())
        if (len(arrivees) == config.RAID_JOINS and arrivees[-1] - arrivees[0] < config.RAID_SECONDES
                and self.mode_raid.get(guild.id, 0) < time.time()):
            self.mode_raid[guild.id] = time.time() + 600
            await log(self.bot, guild, "logs_moderation",
                      embed("🚨 Raid détecté", f"{config.RAID_JOINS} arrivées en moins de {config.RAID_SECONDES} s. "
                            f"Pendant 10 minutes, les comptes de moins de {config.RAID_AGE_MIN_JOURS} jours "
                            "seront expulsés automatiquement. `/verrouillage` pour ajuster.", color=C.ALERTE))

        if self.mode_raid.get(guild.id, 0) > time.time():
            age = (discord.utils.utcnow() - member.created_at).days
            if age < config.RAID_AGE_MIN_JOURS:
                await self._prevenir(member, "Accès temporairement fermé",
                                     "Le serveur est protégé contre un afflux inhabituel. Réessayez plus tard.")
                try:
                    await member.kick(reason="Anti-raid : compte trop récent")
                except discord.HTTPException:
                    pass


async def setup(bot):
    await bot.add_cog(Moderation(bot))
