"""Accueil : bienvenue, règlement à valider, préférences de notifications, hiérarchie en direct."""
import asyncio

import discord
from discord.ext import commands

from bot import config
from bot.utils import a_role, embed, get_role, get_salon

REGLEMENT = """\
Bienvenue dans l'univers de **Chloé**, fondatrice de la **Villa Haussmann** et de la **Villa Jaurès**.

**I. Courtoisie.** Ici, on se parle avec élégance. Insultes, harcèlement et discriminations entraînent l'exclusion.
**II. Discrétion.** Ne partagez jamais d'informations personnelles réelles (adresse, téléphone, papiers, argent).
**III. Immersion.** Respectez le jeu et les personnages des autres. Le hors-jeu se fait entre parenthèses.
**IV. Hiérarchie.** Les décisions de la Fondation et des Responsables s'appliquent à tous.
**V. Publicité.** Aucune publicité, aucun lien d'invitation sans autorisation.
**VI. Entretiens.** L'accès à une villa se fait uniquement par une demande d'entretien.

*Ce serveur est un univers de roleplay : les personnages, les villas et la Fondation sont fictifs.*

En cliquant ci-dessous, vous acceptez ce règlement et recevez l'accès au hall d'entrée."""


def panneau_reglement():
    e = embed("Règlement de la maison", REGLEMENT)
    return e, ReglementView()


def panneau_preferences():
    e = embed("Vos préférences",
              "Choisissez les notifications que vous souhaitez recevoir. Cliquez à nouveau pour vous désabonner.")
    return e, PreferencesView()


class ReglementView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="J'accepte le règlement", emoji="🗝", style=discord.ButtonStyle.secondary,
                       custom_id="reglement:accepter")
    async def accepter(self, interaction: discord.Interaction, _):
        membre = interaction.user
        if a_role(membre, "membre") or a_role(membre, "visiteur"):
            await interaction.response.send_message("Vous avez déjà accepté le règlement.", ephemeral=True)
            return
        role = get_role(interaction.guild, "visiteur")
        if role is None:
            await interaction.response.send_message("Le serveur n'est pas encore installé.", ephemeral=True)
            return
        await membre.add_roles(role, reason="Règlement accepté")
        salon = await get_salon(interaction.client, interaction.guild, "entretien")
        suite = f" Rendez-vous dans {salon.mention} pour demander un entretien." if salon else ""
        await interaction.response.send_message(f"Bienvenue dans le hall d'entrée.{suite}", ephemeral=True)


class PreferencesView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _basculer(self, interaction: discord.Interaction, key: str):
        role = get_role(interaction.guild, key)
        if role is None:
            await interaction.response.send_message("Rôle introuvable, relancez /installer.", ephemeral=True)
            return
        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message(f"Vous ne recevrez plus : **{role.name}**.", ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"Abonnement activé : **{role.name}**.", ephemeral=True)

    @discord.ui.button(label="Annonces", emoji="📜", custom_id="pref:annonces")
    async def annonces(self, interaction, _):
        await self._basculer(interaction, "notif_annonces")

    @discord.ui.button(label="Événements", emoji="🥂", custom_id="pref:evenements")
    async def evenements(self, interaction, _):
        await self._basculer(interaction, "notif_evenements")

    @discord.ui.button(label="Giveaways", emoji="🎁", custom_id="pref:giveaways")
    async def giveaways(self, interaction, _):
        await self._basculer(interaction, "notif_giveaways")


def _liste(membres: list[discord.Member]) -> str:
    if not membres:
        return "*Poste vacant*"
    texte = ", ".join(m.mention for m in sorted(membres, key=lambda m: m.display_name.lower()))
    return texte if len(texte) <= 1000 else f"{len(membres)} membres"


async def rafraichir_hierarchie(bot, guild: discord.Guild):
    salon = await get_salon(bot, guild, "hierarchie")
    if salon is None:
        return
    groupes = {k: [] for k in config.HIERARCHIE}
    for m in guild.members:
        if m.bot:
            continue
        for k in config.HIERARCHIE:  # seul le rang le plus élevé compte
            if a_role(m, k):
                groupes[k].append(m)
                break
    e = embed("Hiérarchie de la maison")
    for k in config.HIERARCHIE:
        e.add_field(name=config.ROLE_NAMES[k], value=_liste(groupes[k]), inline=False)

    mid = await bot.db.get_config(guild.id, "msg_hierarchie")
    if mid:
        try:
            msg = await salon.fetch_message(int(mid))
            await msg.edit(embed=e)
            return
        except discord.HTTPException:
            pass
    msg = await salon.send(embed=e)
    await bot.db.set_config(guild.id, "msg_hierarchie", msg.id)


class Accueil(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._maj_hierarchie: dict[int, asyncio.Task] = {}
        bot.add_view(ReglementView())
        bot.add_view(PreferencesView())

    def _planifier_hierarchie(self, guild: discord.Guild):
        """Regroupe les changements de rôles rapprochés en une seule mise à jour."""
        tache = self._maj_hierarchie.get(guild.id)
        if tache and not tache.done():
            tache.cancel()

        async def plus_tard():
            await asyncio.sleep(10)
            await rafraichir_hierarchie(self.bot, guild)
        self._maj_hierarchie[guild.id] = asyncio.create_task(plus_tard())

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        salon = await get_salon(self.bot, member.guild, "bienvenue")
        if salon is None:
            return
        reglement = await get_salon(self.bot, member.guild, "reglement")
        e = embed(f"Bienvenue, {member.display_name}",
                  f"Les portes s'ouvrent pour {member.mention}.\n\n"
                  f"Prenez le temps de lire {reglement.mention if reglement else 'le règlement'} "
                  "avant d'entrer dans la maison.")
        e.set_thumbnail(url=member.display_avatar.url)
        e.add_field(name="Invités présents", value=str(member.guild.member_count))
        await salon.send(embed=e)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        salon = await get_salon(self.bot, member.guild, "bienvenue")
        if salon:
            await salon.send(embed=embed(description=f"*{member.display_name} a quitté la maison.*"))
        self._planifier_hierarchie(member.guild)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.roles != after.roles:
            self._planifier_hierarchie(after.guild)


async def setup(bot):
    await bot.add_cog(Accueil(bot))
