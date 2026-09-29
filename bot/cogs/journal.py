"""Journal du serveur : arrivées, départs, messages modifiés ou supprimés, changements de rôles."""
import discord
from discord.ext import commands

from bot import config
from bot.utils import embed, log

C = config.Couleurs


def _court(texte: str, limite: int = 1000) -> str:
    texte = texte or "*(vide)*"
    return texte if len(texte) <= limite else texte[:limite] + "…"


class Journal(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        age = (discord.utils.utcnow() - member.created_at).days
        e = embed("Arrivée", f"{member.mention} · `{member.id}`\nCompte créé il y a {age} jours", color=C.SUCCES)
        e.set_thumbnail(url=member.display_avatar.url)
        await log(self.bot, member.guild, "logs_serveur", e)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        roles = ", ".join(r.name for r in member.roles[1:]) or "aucun"
        await log(self.bot, member.guild, "logs_serveur",
                  embed("Départ", f"{member} · `{member.id}`\nRôles : {roles}", color=C.ALERTE))

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        e = embed("Message supprimé", f"De {message.author.mention} dans {message.channel.mention}",
                  color=C.ALERTE)
        e.add_field(name="Contenu", value=_court(message.content), inline=False)
        await log(self.bot, message.guild, "logs_serveur", e)

    @commands.Cog.listener()
    async def on_message_edit(self, avant: discord.Message, apres: discord.Message):
        if not avant.guild or avant.author.bot or avant.content == apres.content:
            return
        e = embed("Message modifié", f"De {avant.author.mention} dans {avant.channel.mention} · "
                                     f"[voir]({apres.jump_url})")
        e.add_field(name="Avant", value=_court(avant.content, 500), inline=False)
        e.add_field(name="Après", value=_court(apres.content, 500), inline=False)
        await log(self.bot, avant.guild, "logs_serveur", e)

    @commands.Cog.listener()
    async def on_member_update(self, avant: discord.Member, apres: discord.Member):
        ajoutes = [r.mention for r in apres.roles if r not in avant.roles]
        retires = [r.mention for r in avant.roles if r not in apres.roles]
        if not ajoutes and not retires and avant.nick == apres.nick:
            return
        e = embed("Membre mis à jour", apres.mention)
        if ajoutes:
            e.add_field(name="Rôles ajoutés", value=" ".join(ajoutes))
        if retires:
            e.add_field(name="Rôles retirés", value=" ".join(retires))
        if avant.nick != apres.nick:
            e.add_field(name="Surnom", value=f"{avant.nick or '—'} → {apres.nick or '—'}", inline=False)
        await log(self.bot, apres.guild, "logs_serveur", e)


async def setup(bot):
    await bot.add_cog(Journal(bot))
