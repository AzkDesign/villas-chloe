"""Point d'entrée : python -m bot.main"""
import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot import config
from bot.db import Database

EXTENSIONS = [
    "bot.cogs.installation",
    "bot.cogs.accueil",
    "bot.cogs.tickets",
    "bot.cogs.moderation",
    "bot.cogs.journal",
    "bot.cogs.niveaux",
    "bot.cogs.economie",
    "bot.cogs.communaute",
]

log = logging.getLogger("villas")


class VillasBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)
        self.db = Database(config.DB_PATH)
        self.tree.on_error = self.on_app_command_error

    async def setup_hook(self):
        await self.db.connect()
        for ext in EXTENSIONS:
            await self.load_extension(ext)
        if config.GUILD_ID:
            guild = discord.Object(id=config.GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
        else:
            synced = await self.tree.sync()
        log.info("%d commandes slash synchronisées", len(synced))

    async def on_ready(self):
        log.info("Connecté en tant que %s", self.user)
        await self.change_presence(activity=discord.Activity(
            type=discord.ActivityType.watching, name="les villas de Chloé"))

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            msg = "Votre rang ne vous permet pas d'utiliser cette commande."
        elif isinstance(error, app_commands.CommandOnCooldown):
            msg = f"Patience… réessayez dans {int(error.retry_after)} s."
        else:
            log.exception("Erreur de commande", exc_info=error)
            msg = "Une erreur est survenue. La direction a été prévenue."
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except discord.HTTPException:
            pass

    async def close(self):
        await self.db.close()
        await super().close()


def main():
    if not config.TOKEN:
        raise SystemExit("DISCORD_TOKEN manquant : ajoutez-le dans .env (local) ou dans les variables Railway.")
    discord.utils.setup_logging(level=logging.INFO)
    VillasBot().run(config.TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
