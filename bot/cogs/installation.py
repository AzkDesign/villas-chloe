"""/installer : crée ou répare rôles, catégories, salons, permissions et panneaux. Relançable sans risque."""
import discord
from discord import app_commands
from discord.ext import commands

from bot import config
from bot.cogs.accueil import panneau_preferences, panneau_reglement, rafraichir_hierarchie
from bot.cogs.tickets import panneau_entretien
from bot.utils import embed, get_role, rang_requis

P = discord.Permissions
PERMISSIONS = {
    "fondation": P(administrator=True),
    "responsable": P(manage_channels=True, manage_roles=True, kick_members=True, ban_members=True,
                     moderate_members=True, manage_messages=True, view_audit_log=True, mention_everyone=True,
                     manage_nicknames=True, move_members=True, mute_members=True, manage_threads=True),
    "resp_haussmann": P(kick_members=True, moderate_members=True, manage_messages=True, mention_everyone=True,
                        manage_nicknames=True, move_members=True, mute_members=True, manage_threads=True),
    "resp_jaures": P(kick_members=True, moderate_members=True, manage_messages=True, mention_everyone=True,
                     manage_nicknames=True, move_members=True, mute_members=True, manage_threads=True),
    "gerant": P(moderate_members=True, manage_messages=True, manage_threads=True),
}
VISIBILITE_CATEGORIES = {
    "cat_accueil": "public_ro", "cat_commun": "membre_ro", "cat_haussmann": "haussmann",
    "cat_jaures": "jaures", "cat_admin": "staff", "cat_entretiens": "staff",
}


def build_overwrites(guild: discord.Guild, visibilite: str):
    r = {k: get_role(guild, k) for k in config.ROLE_NAMES}
    lire = discord.PermissionOverwrite(view_channel=True, send_messages=False, add_reactions=True,
                                       connect=False, create_public_threads=False)
    ecrire = discord.PermissionOverwrite(view_channel=True, send_messages=True, connect=True, speak=True)
    cache = discord.PermissionOverwrite(view_channel=False)

    ow = {guild.default_role: cache,
          guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True,
                                                manage_messages=True, embed_links=True, attach_files=True,
                                                connect=True)}
    staff = [r[k] for k in config.STAFF]

    def donner(roles, perm):
        for role in roles:
            if role:
                ow[role] = perm

    if visibilite == "public_ro":
        ow[guild.default_role] = discord.PermissionOverwrite(view_channel=True, send_messages=False,
                                                             add_reactions=False, create_public_threads=False)
        donner(staff, ecrire)
    elif visibilite == "visiteur_ro":
        donner([r["visiteur"], r["membre"]], lire)
        donner(staff, ecrire)
    elif visibilite == "verifie_ro":
        donner([r["visiteur"], r["membre"]], lire)
        donner(staff, ecrire)
    elif visibilite == "membre":
        donner([r["membre"]], ecrire)
        donner(staff, ecrire)
    elif visibilite == "membre_ro":
        donner([r["membre"]], lire)
        donner(staff, ecrire)
    elif visibilite == "haussmann":
        donner([r["resident_haussmann"], r["resp_haussmann"], r["responsable"], r["gerant"]], ecrire)
    elif visibilite == "jaures":
        donner([r["resident_jaures"], r["resp_jaures"], r["responsable"], r["gerant"]], ecrire)
    elif visibilite == "staff":
        donner(staff, ecrire)
    return ow


class Installation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _roles(self, guild: discord.Guild, rapport: list[str]):
        # Création du plus bas au plus haut : chaque nouveau rôle arrive en bas de la liste.
        for spec in reversed(config.ROLES):
            role = get_role(guild, spec["key"])
            perms = PERMISSIONS.get(spec["key"], P.none())
            if role is None:
                await guild.create_role(name=spec["name"], colour=discord.Colour(spec["color"]),
                                        hoist=spec["hoist"], permissions=perms, reason="Installation")
                rapport.append(f"Rôle créé : **{spec['name']}**")
            elif role < guild.me.top_role:
                await role.edit(colour=discord.Colour(spec["color"]), hoist=spec["hoist"], permissions=perms)

        # Remet les rôles dans le bon ordre, juste sous le rôle du bot.
        roles = [get_role(guild, s["key"]) for s in config.ROLES]
        roles = [r for r in roles if r and r < guild.me.top_role]
        top = guild.me.top_role.position
        try:
            await guild.edit_role_positions({role: top - 1 - i for i, role in enumerate(roles)})
        except discord.HTTPException:
            rapport.append("⚠️ Ordre des rôles non modifié : placez le rôle du bot tout en haut.")

    async def _salons(self, guild: discord.Guild, rapport: list[str]):
        db = self.bot.db
        for cat_key, cat_nom, salons in config.CATEGORIES:
            cat = guild.get_channel(int(await db.get_config(guild.id, f"salon_{cat_key}") or 0))
            if cat is None:
                cat = discord.utils.get(guild.categories, name=cat_nom)
            cat_ow = build_overwrites(guild, VISIBILITE_CATEGORIES[cat_key])
            if cat is None:
                cat = await guild.create_category(cat_nom, overwrites=cat_ow, reason="Installation")
                rapport.append(f"Catégorie créée : **{cat_nom}**")
            else:
                await cat.edit(overwrites=cat_ow)
            await db.set_config(guild.id, f"salon_{cat_key}", cat.id)

            for key, nom, kind, vis in salons:
                ow = build_overwrites(guild, vis)
                salon = guild.get_channel(int(await db.get_config(guild.id, f"salon_{key}") or 0))
                if salon is None:
                    salon = discord.utils.get(cat.channels, name=nom)
                if salon is None:
                    creer = cat.create_voice_channel if kind == "voice" else cat.create_text_channel
                    salon = await creer(nom, overwrites=ow, reason="Installation")
                    rapport.append(f"Salon créé : {salon.mention}")
                else:
                    await salon.edit(overwrites=ow, category=cat)
                await db.set_config(guild.id, f"salon_{key}", salon.id)

    async def _panneau(self, guild, salon_key: str, cle: str, e: discord.Embed, view: discord.ui.View):
        salon = guild.get_channel(int(await self.bot.db.get_config(guild.id, f"salon_{salon_key}") or 0))
        if salon is None:
            return
        mid = await self.bot.db.get_config(guild.id, cle)
        if mid:
            try:
                msg = await salon.fetch_message(int(mid))
                await msg.edit(embed=e, view=view)
                return
            except discord.HTTPException:
                pass
        msg = await salon.send(embed=e, view=view)
        await self.bot.db.set_config(guild.id, cle, msg.id)

    @app_commands.command(name="installer", description="Crée ou répare toute la structure du serveur (Fondation).")
    @app_commands.guild_only()
    @rang_requis(5)
    async def installer(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        guild = interaction.guild
        if not guild.me.guild_permissions.administrator:
            await interaction.followup.send("Le bot a besoin de la permission **Administrateur** pour l'installation.")
            return
        rapport: list[str] = []
        await self._roles(guild, rapport)
        await self._salons(guild, rapport)
        await self._panneau(guild, "reglement", "msg_reglement", *panneau_reglement())
        await self._panneau(guild, "entretien", "msg_entretien", *panneau_entretien())
        await self._panneau(guild, "preferences", "msg_preferences", *panneau_preferences())
        await rafraichir_hierarchie(self.bot, guild)

        resume = "\n".join(rapport[-25:]) or "Tout était déjà en place : permissions et panneaux mis à jour."
        await interaction.followup.send(embed=embed("Installation terminée", resume))


async def setup(bot):
    await bot.add_cog(Installation(bot))
