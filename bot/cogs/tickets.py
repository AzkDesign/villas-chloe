"""Demandes d'entretien : formulaire, salon privé, décision (accepter/refuser), archive à la fermeture."""
import asyncio
import io

import discord
from discord.ext import commands

from bot import config
from bot.utils import a_role, embed, get_role, get_salon, log, now, rang

C = config.Couleurs
TYPES = {
    "haussmann": {
        "titre": "Entretien · Villa Haussmann", "couleur": C.HAUSSMANN, "resident": "resident_haussmann",
        "equipe": ["responsable", "resp_haussmann", "gerant"], "decideurs": ["resp_haussmann"],
        "questions": [("Nom de votre personnage", False), ("Votre activité ou votre projet", True),
                      ("Pourquoi la Villa Haussmann ?", True)],
    },
    "jaures": {
        "titre": "Entretien · Villa Jaurès", "couleur": C.JAURES, "resident": "resident_jaures",
        "equipe": ["responsable", "resp_jaures", "gerant"], "decideurs": ["resp_jaures"],
        "questions": [("Nom de votre personnage", False), ("L'histoire de votre personnage", True),
                      ("Ce que vous attendez de la Villa Jaurès", True)],
    },
    "direction": {
        "titre": "Contact · Direction", "couleur": C.FONDATION, "resident": None,
        "equipe": ["responsable"], "decideurs": [],
        "questions": [("Objet", False), ("Votre message", True)],
    },
}


def panneau_entretien():
    e = embed("Demandes d'entretien",
              "Chaque résident est reçu en entretien avant de rejoindre une maison.\n\n"
              "⚜ **Villa Haussmann** · la maison des entrepreneurs de l'équipe.\n"
              "❦ **Villa Jaurès** · une maison pour souffler, se reconstruire et être entouré.\n\n"
              "Choisissez ci-dessous. Un formulaire s'ouvrira, puis un salon privé avec la direction.")
    return e, PanneauEntretienView()


def peut_decider(membre: discord.Member, t: dict) -> bool:
    return rang(membre) >= 4 or any(a_role(membre, k) for k in t["decideurs"])


class Candidature(discord.ui.Modal):
    def __init__(self, type_: str):
        self.type_ = type_
        super().__init__(title=TYPES[type_]["titre"][:45])
        self.champs = []
        for label, long in TYPES[type_]["questions"]:
            champ = discord.ui.TextInput(label=label, max_length=1000 if long else 100,
                                         style=discord.TextStyle.paragraph if long else discord.TextStyle.short)
            self.add_item(champ)
            self.champs.append(champ)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        bot, guild, user, t = interaction.client, interaction.guild, interaction.user, TYPES[self.type_]
        categorie = await get_salon(bot, guild, "cat_entretiens")
        if categorie is None:
            await interaction.followup.send("Le serveur n'est pas encore installé.", ephemeral=True)
            return

        cur = await bot.db.execute("INSERT INTO tickets (guild_id, user_id, type, created_at) VALUES (?, ?, ?, ?)",
                                   guild.id, user.id, self.type_, now())
        numero = cur.lastrowid
        ow = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True,
                                                  attach_files=True, embed_links=True),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
        }
        for k in t["equipe"]:
            role = get_role(guild, k)
            if role:
                ow[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
        salon = await categorie.create_text_channel(f"{self.type_}-{numero:04d}", overwrites=ow,
                                                    topic=f"Demande de {user} ({user.id})")
        await bot.db.execute("UPDATE tickets SET channel_id = ? WHERE id = ?", salon.id, numero)

        e = embed(t["titre"], f"Demande de {user.mention}", color=t["couleur"])
        for champ in self.champs:
            e.add_field(name=champ.label, value=champ.value, inline=False)
        mentions = " ".join(r.mention for k in t["equipe"] if (r := get_role(guild, k)))
        await salon.send(content=f"{user.mention} {mentions}", embed=e,
                         view=TicketView(decision=bool(t["resident"])),
                         allowed_mentions=discord.AllowedMentions(roles=True, users=True))
        await interaction.followup.send(f"Votre demande est ouverte : {salon.mention}", ephemeral=True)


class PanneauEntretienView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _ouvrir(self, interaction: discord.Interaction, type_: str):
        t = TYPES[type_]
        if t["resident"] and a_role(interaction.user, t["resident"]):
            await interaction.response.send_message("Vous résidez déjà dans cette villa.", ephemeral=True)
            return
        rows = await interaction.client.db.fetchall(
            "SELECT channel_id FROM tickets WHERE guild_id = ? AND user_id = ? AND type = ? AND ferme = 0",
            interaction.guild.id, interaction.user.id, type_)
        for row in rows:
            salon = interaction.guild.get_channel(row["channel_id"] or 0)
            if salon:
                await interaction.response.send_message(f"Une demande est déjà ouverte : {salon.mention}",
                                                        ephemeral=True)
                return
        await interaction.response.send_modal(Candidature(type_))

    @discord.ui.button(label="Villa Haussmann", emoji="⚜", custom_id="entretien:haussmann")
    async def haussmann(self, interaction, _):
        await self._ouvrir(interaction, "haussmann")

    @discord.ui.button(label="Villa Jaurès", emoji="❦", custom_id="entretien:jaures")
    async def jaures(self, interaction, _):
        await self._ouvrir(interaction, "jaures")

    @discord.ui.button(label="Contacter la direction", emoji="✉", custom_id="entretien:direction")
    async def direction(self, interaction, _):
        await self._ouvrir(interaction, "direction")


class MotifRefus(discord.ui.Modal, title="Motif du refus"):
    motif = discord.ui.TextInput(label="Motif (transmis au candidat)", style=discord.TextStyle.paragraph,
                                 max_length=500)

    def __init__(self, ticket):
        super().__init__()
        self.ticket = ticket

    async def on_submit(self, interaction: discord.Interaction):
        bot, guild = interaction.client, interaction.guild
        await bot.db.execute("UPDATE tickets SET statut = 'refusé' WHERE id = ?", self.ticket["id"])
        e = embed("Demande refusée", f"Décision de {interaction.user.mention}\n\n> {self.motif.value}",
                  color=C.ALERTE)
        await interaction.response.send_message(embed=e)
        membre = guild.get_member(self.ticket["user_id"])
        if membre:
            try:
                await membre.send(embed=embed(f"{TYPES[self.ticket['type']]['titre']}",
                                              f"Votre demande n'a pas été retenue.\n\n> {self.motif.value}",
                                              color=C.ALERTE))
            except discord.HTTPException:
                pass


class TicketView(discord.ui.View):
    """Boutons du salon d'entretien. decision=False : uniquement « Fermer »."""

    def __init__(self, decision: bool = True):
        super().__init__(timeout=None)
        if not decision:
            self.remove_item(self.accepter)
            self.remove_item(self.refuser)

    async def _ticket(self, interaction):
        return await interaction.client.db.fetchone("SELECT * FROM tickets WHERE channel_id = ?",
                                                    interaction.channel.id)

    async def _verifier_decideur(self, interaction, ticket) -> bool:
        if ticket is None:
            await interaction.response.send_message("Demande introuvable.", ephemeral=True)
            return False
        if ticket["statut"] != "en attente":
            await interaction.response.send_message(f"Cette demande a déjà été traitée ({ticket['statut']}).",
                                                    ephemeral=True)
            return False
        if not peut_decider(interaction.user, TYPES[ticket["type"]]):
            await interaction.response.send_message("Seuls les responsables de cette villa peuvent décider.",
                                                    ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Accepter", emoji="✔", style=discord.ButtonStyle.success, custom_id="ticket:accepter")
    async def accepter(self, interaction: discord.Interaction, _):
        ticket = await self._ticket(interaction)
        if not await self._verifier_decideur(interaction, ticket):
            return
        bot, guild, t = interaction.client, interaction.guild, TYPES[ticket["type"]]
        membre = guild.get_member(ticket["user_id"])
        if membre is None:
            await interaction.response.send_message("Le candidat a quitté le serveur.", ephemeral=True)
            return
        await interaction.response.defer()
        ajouts = [r for r in (get_role(guild, "membre"), get_role(guild, t["resident"])) if r]
        await membre.add_roles(*ajouts, reason=f"Entretien accepté par {interaction.user}")
        visiteur = get_role(guild, "visiteur")
        if visiteur in membre.roles:
            await membre.remove_roles(visiteur)
        await bot.db.execute("UPDATE tickets SET statut = 'accepté' WHERE id = ?", ticket["id"])

        villa = t["titre"].split("·")[-1].strip()
        await interaction.followup.send(embed=embed("Demande acceptée",
            f"{membre.mention} rejoint la **{villa}**. Décision de {interaction.user.mention}.", color=C.SUCCES))
        try:
            await membre.send(embed=embed("Bienvenue dans la maison",
                                          f"Votre entretien est accepté : les portes de la **{villa}** "
                                          "vous sont ouvertes.", color=t["couleur"]))
        except discord.HTTPException:
            pass
        general = await get_salon(bot, guild, "general")
        if general:
            await general.send(embed=embed(description=f"✨ {membre.mention} s'installe à la **{villa}**. "
                                                       "Faites-lui bon accueil.", color=t["couleur"]))

    @discord.ui.button(label="Refuser", emoji="✖", style=discord.ButtonStyle.danger, custom_id="ticket:refuser")
    async def refuser(self, interaction: discord.Interaction, _):
        ticket = await self._ticket(interaction)
        if await self._verifier_decideur(interaction, ticket):
            await interaction.response.send_modal(MotifRefus(ticket))

    @discord.ui.button(label="Fermer", emoji="🔒", style=discord.ButtonStyle.secondary, custom_id="ticket:fermer")
    async def fermer(self, interaction: discord.Interaction, _):
        ticket = await self._ticket(interaction)
        if ticket is None:
            await interaction.response.send_message("Demande introuvable.", ephemeral=True)
            return
        if interaction.user.id != ticket["user_id"] and rang(interaction.user) < 2:
            await interaction.response.send_message("Vous ne pouvez pas fermer cette demande.", ephemeral=True)
            return
        await interaction.response.send_message("Archivage en cours, fermeture dans 5 secondes…")
        bot, guild, salon = interaction.client, interaction.guild, interaction.channel

        lignes = [f"{salon.name} · {TYPES[ticket['type']]['titre']} · statut : {ticket['statut']}\n"]
        async for m in salon.history(limit=None, oldest_first=True):
            contenu = m.content or ""
            for em in m.embeds:
                contenu += f" [embed: {em.title or ''} {em.description or ''}]"
                contenu += "".join(f" [{f.name}: {f.value}]" for f in em.fields)
            lignes.append(f"[{m.created_at:%d/%m/%Y %H:%M}] {m.author}: {contenu}")
        fichier = discord.File(io.BytesIO("\n".join(lignes).encode("utf-8")), filename=f"{salon.name}.txt")
        auteur = guild.get_member(ticket["user_id"])
        await log(bot, guild, "transcripts",
                  embed(f"Archive · {salon.name}",
                        f"Candidat : {auteur.mention if auteur else ticket['user_id']}\n"
                        f"Statut : **{ticket['statut']}**\nFermé par : {interaction.user.mention}"),
                  file=fichier)
        await bot.db.execute("UPDATE tickets SET ferme = 1 WHERE id = ?", ticket["id"])
        await asyncio.sleep(5)
        await salon.delete(reason=f"Demande fermée par {interaction.user}")


class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.add_view(PanneauEntretienView())
        bot.add_view(TicketView())


async def setup(bot):
    await bot.add_cog(Tickets(bot))
