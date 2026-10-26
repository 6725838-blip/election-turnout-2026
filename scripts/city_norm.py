"""Shared city-name normalization for baseline matching and live merge."""
import re
import unicodedata


def city_key(name):
    text = unicodedata.normalize('NFKC', str(name or ''))
    # GovMap often spells קריית as קרית
    text = text.replace('קריית', 'קרית')
    return re.sub(r'''[\s״׳'"־–-]''', '', text).lower()
