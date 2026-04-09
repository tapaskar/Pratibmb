from .base import Importer, pick_importer
from .whatsapp import WhatsAppTxt
from .facebook import FacebookDYI
from .instagram import InstagramDYI

ALL_IMPORTERS: list[Importer] = [
    WhatsAppTxt(),
    FacebookDYI(),
    InstagramDYI(),
]

__all__ = [
    "Importer",
    "pick_importer",
    "WhatsAppTxt",
    "FacebookDYI",
    "InstagramDYI",
    "ALL_IMPORTERS",
]
