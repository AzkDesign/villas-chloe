"""Configuration centrale : variables d'environnement, identité visuelle, rôles et salons."""
import os

from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID") or 0) or None
DATA_DIR = os.getenv("DATA_DIR", "data")
DB_PATH = os.path.join(DATA_DIR, "villas.db")

SIGNATURE = "La Fondation"
MONNAIE = "Louis d'or"
MONNAIE_EMOJI = "🪙"


class Couleurs:
    FONDATION = 0xB08D57  # laiton patiné, identité commune
    HAUSSMANN = 0xC9A96E  # or champagne, Art déco
    JAURES = 0x3F7A5C  # vert anglais
    IVOIRE = 0xF3EDE3
    SUCCES = 0x5E8C6A
    ALERTE = 0x8B2E3A  # bordeaux


# --- Rôles, du plus haut au plus bas -------------------------------------------------
# "rang" sert aux vérifications de permissions des commandes (0 = aucun pouvoir).
ROLES = [
    {"key": "fondation", "name": "Fondation", "color": Couleurs.FONDATION, "hoist": True, "rang": 5},
    {"key": "responsable", "name": "Responsable", "color": Couleurs.IVOIRE, "hoist": True, "rang": 4},
    {"key": "resp_haussmann", "name": "Responsable Haussmann", "color": Couleurs.HAUSSMANN, "hoist": True, "rang": 3},
    {"key": "resp_jaures", "name": "Responsable Jaurès", "color": Couleurs.JAURES, "hoist": True, "rang": 3},
    {"key": "gerant", "name": "Gérant", "color": 0x8A8175, "hoist": True, "rang": 2},
    {"key": "membre", "name": "Membre", "color": 0xD9CFC1, "hoist": True, "rang": 0},
    {"key": "resident_haussmann", "name": "Résident Haussmann", "color": Couleurs.HAUSSMANN, "hoist": False, "rang": 0},
    {"key": "resident_jaures", "name": "Résident Jaurès", "color": Couleurs.JAURES, "hoist": False, "rang": 0},
    {"key": "visiteur", "name": "Visiteur", "color": 0x6E6A63, "hoist": False, "rang": 0},
    {"key": "notif_annonces", "name": "🔔 Annonces", "color": 0, "hoist": False, "rang": 0},
    {"key": "notif_evenements", "name": "🔔 Événements", "color": 0, "hoist": False, "rang": 0},
    {"key": "notif_giveaways", "name": "🔔 Giveaways", "color": 0, "hoist": False, "rang": 0},
]
ROLE_NAMES = {r["key"]: r["name"] for r in ROLES}
HIERARCHIE = ["fondation", "responsable", "resp_haussmann", "resp_jaures", "gerant", "membre"]
STAFF = ["fondation", "responsable", "resp_haussmann", "resp_jaures", "gerant"]

# --- Salons ---------------------------------------------------------------------------
# Visibilités : voir bot/cogs/installation.py -> build_overwrites
CATEGORIES = [
    ("cat_accueil", "🏛 ACCUEIL", [
        ("bienvenue", "・bienvenue", "text", "public_ro"),
        ("reglement", "・règlement", "text", "public_ro"),
        ("entretien", "・demande-d-entretien", "text", "visiteur_ro"),
        ("annonces", "・annonces", "text", "verifie_ro"),
        ("hierarchie", "・hiérarchie", "text", "verifie_ro"),
    ]),
    ("cat_commun", "🍾 VIE COMMUNE", [
        ("general", "・la-grande-salle", "text", "membre"),
        ("preferences", "・préférences", "text", "membre_ro"),
        ("evenements", "・événements", "text", "membre_ro"),
        ("giveaways", "・giveaways", "text", "membre_ro"),
        ("sondages", "・sondages", "text", "membre_ro"),
        ("distinctions", "・distinctions", "text", "membre_ro"),
        ("commandes", "・commandes", "text", "membre"),
        ("vocal_commun", "Le Salon Commun", "voice", "membre"),
    ]),
    ("cat_haussmann", "⚜ VILLA HAUSSMANN", [
        ("h_salon", "✦・le-grand-salon", "text", "haussmann"),
        ("h_affaires", "✦・bureau-des-affaires", "text", "haussmann"),
        ("h_bibliotheque", "✦・la-bibliothèque", "text", "haussmann"),
        ("h_vocal", "Salle de réunion", "voice", "haussmann"),
    ]),
    ("cat_jaures", "❦ VILLA JAURÈS", [
        ("j_jardin", "❦・le-jardin-d-hiver", "text", "jaures"),
        ("j_salon", "❦・le-petit-salon", "text", "jaures"),
        ("j_cuisine", "❦・la-cuisine", "text", "jaures"),
        ("j_vocal", "Salon de musique", "voice", "jaures"),
    ]),
    ("cat_admin", "📜 ADMINISTRATION", [
        ("staff", "・direction", "text", "staff"),
        ("logs_moderation", "・logs-modération", "text", "staff"),
        ("logs_serveur", "・logs-serveur", "text", "staff"),
        ("transcripts", "・archives-entretiens", "text", "staff"),
    ]),
    ("cat_entretiens", "🗝 ENTRETIENS", []),
]

# --- Réglages des modules -------------------------------------------------------------
XP_MIN, XP_MAX, XP_COOLDOWN = 15, 25, 60  # XP par message, cooldown en secondes
SPAM_MESSAGES, SPAM_SECONDES = 6, 5  # 6 messages en 5 s = spam
RAID_JOINS, RAID_SECONDES = 8, 15  # 8 arrivées en 15 s = raid
RAID_AGE_MIN_JOURS = 7  # en mode raid, comptes plus jeunes expulsés
AVERTISSEMENTS_AVANT_SANCTION = 3
QUOTIDIEN_GAIN = (200, 300)
TRAVAIL_GAIN, TRAVAIL_COOLDOWN = (80, 200), 3600
