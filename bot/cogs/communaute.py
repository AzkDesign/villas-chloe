"""Vie commune : annonces, sondages, giveaways, aide."""
import random
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands, tasks

from bot import config
from bot.utils import embed, format_duree, get_role, get_salon, now, parse_duree, rang_requis

C = config.Couleurs


class AnnonceModal(discord.ui.Modal, title="Nouvelle annonce"):
    titre = discord.ui.TextInput(label="Titre", max_length=200)
    contenu = discord.ui.TextInput(label="Contenu", style=discord.TextStyle.paragraph, max_length=4000)

    def __init__(self, salon: discord.TextChannel, role: discord.Role | None):
        super().__init__()
        self.salon, self.role = salon, role

    async def on_submit(self, interaction: discord.Interaction):
        e = embed(self.titre.value, self.contenu.value)
        e.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        await self.salon.send(content=self.role.mention if self.role else None, embed=e,
                              allowed_mentions=discord.AllowedMentions(roles=True))
        await interaction.response.send_message(f"Annonce publiée dans {self.salon.mention}.", ephemeral=True)


class GiveawayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Participer", emoji="🎁", style=discord.ButtonStyle.secondary,
                       custom_id="giveaway:participer")
    async def participer(self, interaction: discord.Interaction, _):
        db, mid, uid = interaction.client.db, interaction.message.id, interaction.user.id
        gw = await db.fetchone("SELECT termine FROM giveaways WHERE message_id = ?", mid)
        if gw is None or gw["termine"]:
            await interaction.response.send_message("Ce giveaway est terminé.", ephemeral=True)
            return
        deja = await db.fetchone("SELECT 1 FROM giveaway_participants WHERE message_id = ? AND user_id = ?", mid, uid)
        if deja:
            await db.execute("DELETE FROM giveaway_participants WHERE message_id = ? AND user_id = ?", mid, uid)
            msg = "Vous vous êtes retiré du giveaway."
        else:
            await db.execute("INSERT INTO giveaway_participants (message_id, user_id) VALUES (?, ?)", mid, uid)
            msg = "Participation enregistrée. Bonne chance !"
        n = (await db.fetchone("SELECT COUNT(*) AS n FROM giveaway_participants WHERE message_id = ?", mid))["n"]
        e = interaction.message.embeds[0]
        e.set_field_at(2, name="Participants", value=str(n))
        await interaction.response.edit_message(embed=e)
        await interaction.followup.send(msg, ephemeral=True)


class Communaute(commands.Cog):
    giveaway = app_commands.Group(name="giveaway", description="Gestion des giveaways", guild_only=True)

    def __init__(self, bot):
        self.bot = bot
        bot.add_view(GiveawayView())
        self.verifier_giveaways.start()

    def cog_unload(self):
        self.verifier_giveaways.cancel()

    # --- Annonces & sondages ----------------------------------------------------------
    @app_commands.command(name="annonce", description="Publie une annonce mise en forme.")
    @app_commands.guild_only()
    @app_commands.choices(destination=[
        app_commands.Choice(name="Annonces", value="annonces"),
        app_commands.Choice(name="Événements", value="evenements"),
        app_commands.Choice(name="Ce salon", value="ici"),
    ])
    @rang_requis(3)
    async def annonce(self, interaction: discord.Interaction, destination: app_commands.Choice[str],
                      mentionner: bool = True):
        if destination.value == "ici":
            salon, role = interaction.channel, None
        else:
            salon = await get_salon(self.bot, interaction.guild, destination.value)
            role = get_role(interaction.guild, f"notif_{destination.value}") if mentionner else None
        if salon is None:
            await interaction.response.send_message("Salon introuvable, lancez /installer.", ephemeral=True)
            return
        await interaction.response.send_modal(AnnonceModal(salon, role))

    @app_commands.command(name="sondage", description="Crée un sondage (choix séparés par ;).")
    @app_commands.guild_only()
    @rang_requis(2)
    async def sondage(self, interaction: discord.Interaction, question: str, choix: str,
                      heures: app_commands.Range[int, 1, 768] = 24, plusieurs_reponses: bool = False):
        options = [c.strip() for c in choix.split(";") if c.strip()]
        if not 2 <= len(options) <= 10:
            await interaction.response.send_message("Il faut entre 2 et 10 choix, séparés par ;", ephemeral=True)
            return
        poll = discord.Poll(question=question[:300], duration=timedelta(hours=heures), multiple=plusieurs_reponses)
        for option in options:
            poll.add_answer(text=option[:55])
        salon = await get_salon(self.bot, interaction.guild, "sondages") or interaction.channel
        await salon.send(poll=poll)
        await interaction.response.send_message(f"Sondage publié dans {salon.mention}.", ephemeral=True)

    # --- Giveaways --------------------------------------------------------------------
    @giveaway.command(name="lancer", description="Lance un giveaway (durée : 30m, 2h, 1j…).")
    @rang_requis(3)
    async def lancer(self, interaction: discord.Interaction, lot: str, duree: str,
                     gagnants: app_commands.Range[int, 1, 20] = 1):
        secondes = parse_duree(duree)
        if not secondes:
            await interaction.response.send_message("Durée invalide. Exemple : 30m, 2h, 1j.", ephemeral=True)
            return
        salon = await get_salon(self.bot, interaction.guild, "giveaways") or interaction.channel
        fin = now() + secondes
        e = embed(f"🎁 {lot}", f"Cliquez sur **Participer** pour tenter votre chance.\nOrganisé par "
                              f"{interaction.user.mention}", color=C.HAUSSMANN)
        e.add_field(name="Fin", value=f"<t:{fin}:R>")
        e.add_field(name="Gagnants", value=str(gagnants))
        e.add_field(name="Participants", value="0")
        role = get_role(interaction.guild, "notif_giveaways")
        msg = await salon.send(content=role.mention if role else None, embed=e, view=GiveawayView(),
                               allowed_mentions=discord.AllowedMentions(roles=True))
        await self.bot.db.execute(
            "INSERT INTO giveaways (message_id, guild_id, channel_id, lot, gagnants, fin, hote_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)", msg.id, interaction.guild.id, salon.id, lot, gagnants, fin,
            interaction.user.id)
        await interaction.response.send_message(
            f"Giveaway lancé dans {salon.mention} pour {format_duree(secondes)}.", ephemeral=True)

    @giveaway.command(name="terminer", description="Termine un giveaway immédiatement.")
    @rang_requis(3)
    async def terminer(self, interaction: discord.Interaction, message_id: str):
        gw = await self.bot.db.fetchone("SELECT * FROM giveaways WHERE message_id = ? AND termine = 0",
                                        int(message_id) if message_id.isdigit() else 0)
        if gw is None:
            await interaction.response.send_message("Giveaway en cours introuvable.", ephemeral=True)
            return
        await interaction.response.send_message("Tirage en cours…", ephemeral=True)
        await self._tirer(gw)

    @giveaway.command(name="relancer", description="Tire de nouveaux gagnants pour un giveaway terminé.")
    @rang_requis(3)
    async def relancer(self, interaction: discord.Interaction, message_id: str):
        gw = await self.bot.db.fetchone("SELECT * FROM giveaways WHERE message_id = ? AND termine = 1",
                                        int(message_id) if message_id.isdigit() else 0)
        if gw is None:
            await interaction.response.send_message("Giveaway terminé introuvable.", ephemeral=True)
            return
        await interaction.response.send_message("Nouveau tirage…", ephemeral=True)
        await self._tirer(gw, relance=True)

    async def _tirer(self, gw, relance: bool = False):
        await self.bot.db.execute("UPDATE giveaways SET termine = 1 WHERE message_id = ?", gw["message_id"])
        guild = self.bot.get_guild(gw["guild_id"])
        salon = guild.get_channel(gw["channel_id"]) if guild else None
        if salon is None:
            return
        rows = await self.bot.db.fetchall("SELECT user_id FROM giveaway_participants WHERE message_id = ?",
                                          gw["message_id"])
        candidats = [m for r in rows if (m := guild.get_member(r["user_id"]))]
        gagnants = random.sample(candidats, min(gw["gagnants"], len(candidats)))
        texte = ", ".join(g.mention for g in gagnants) if gagnants else "Aucun participant."

        if not relance:
            try:
                msg = await salon.fetch_message(gw["message_id"])
                e = msg.embeds[0]
                e.description = f"Terminé. Gagnant(s) : {texte}"
                e.set_field_at(0, name="Fin", value="Terminé")
                await msg.edit(embed=e, view=None)
            except discord.HTTPException:
                pass
        if gagnants:
            await salon.send(f"🎉 Félicitations {texte} : vous remportez **{gw['lot']}** !",
                             reference=discord.MessageReference(message_id=gw["message_id"], channel_id=salon.id,
                                                                fail_if_not_exists=False))
        else:
            await salon.send(f"Personne n'a participé au giveaway **{gw['lot']}**.")

    @tasks.loop(seconds=20)
    async def verifier_giveaways(self):
        rows = await self.bot.db.fetchall("SELECT * FROM giveaways WHERE termine = 0 AND fin <= ?", now())
        for gw in rows:
            await self._tirer(gw)

    @verifier_giveaways.before_loop
    async def avant(self):
        await self.bot.wait_until_ready()

    # --- Aide -------------------------------------------------------------------------
    @app_commands.command(name="aide", description="Liste des commandes disponibles.")
    async def aide(self, interaction: discord.Interaction):
        e = embed("Le carnet de la maison")
        e.add_field(name="Pour tous", inline=False, value=(
            "`/rang` `/classement` · niveaux\n"
            "`/solde` `/quotidien` `/travailler` `/donner` `/fortune` · Louis d'or"))
        e.add_field(name="Gérants", inline=False, value=(
            "`/avertir` `/avertissements` `/exclure-temp` `/lever-exclusion` `/effacer` `/sondage`"))
        e.add_field(name="Responsables de villa", inline=False, value=(
            "`/expulser` `/retirer-avertissement` `/annonce` `/giveaway lancer|terminer|relancer`\n"
            "Accepter ou refuser les entretiens de leur villa"))
        e.add_field(name="Responsables et Fondation", inline=False, value=(
            "`/bannir` `/debannir` `/verrouillage` `/crediter` · `/installer` (Fondation)"))
        await interaction.response.send_message(embed=e, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Communaute(bot))
