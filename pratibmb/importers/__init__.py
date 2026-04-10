from .base import Importer, pick_importer
from .whatsapp import WhatsAppTxt
from .facebook import FacebookDYI
from .instagram import InstagramDYI
from .discord import DiscordExport
from .telegram import TelegramExport
from .twitter import TwitterArchive
from .gmail import GmailMbox
from .imessage import IMessageDB

ALL_IMPORTERS: list[Importer] = [
    WhatsAppTxt(),
    FacebookDYI(),
    InstagramDYI(),
    DiscordExport(),
    TelegramExport(),
    TwitterArchive(),
    GmailMbox(),
    IMessageDB(),
]

__all__ = [
    "Importer",
    "pick_importer",
    "WhatsAppTxt",
    "FacebookDYI",
    "InstagramDYI",
    "DiscordExport",
    "TelegramExport",
    "TwitterArchive",
    "GmailMbox",
    "IMessageDB",
    "ALL_IMPORTERS",
]
