"""
The companion content pool's item model.

Every bucket is an APPEND-ONLY list of items. An item's position in its list
is its permanent index — the bit that tracks "seen" for each user (see
app/services/seen_store.py) — so items are never reordered or deleted:
an item that must go is marked ``retired`` and keeps its slot.

Two kinds of item:

  * universal — written once, translated to all four languages (en/de/ru/uk);
  * language-locked — exists in one language only (e.g. a pun that only
    works in German) and is offered only to users of that language.

Message variants (``app/data/pool/messages.py``) use the same model; their
text is a ``str.format`` template over the numbers Go sends, and ``when``
restricts a variant to a context (e.g. ``"calibrating"``: the first week of a
period, while the forecast is still collecting data).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional

LANGS: tuple[str, ...] = ("en", "de", "ru", "uk")


@dataclass(frozen=True)
class Item:
    id: str
    tr: Mapping[str, str] = field(default_factory=dict)  # universal: one text per language
    only: Optional[str] = None  # language-locked: the single language it exists in
    retired: bool = False
    when: Optional[str] = None  # message variants: only in this context

    def text_in(self, lang: str) -> Optional[str]:
        """The item's text in a language, or None when it has none there."""
        if self.retired:
            return None
        if self.only is not None and self.only != lang:
            return None
        return self.tr.get(lang)

    def translations(self) -> dict[str, str]:
        """Every language the item exists in (one entry for a locked item)."""
        return {lang: text for lang, text in self.tr.items() if not self.retired}


def U(id: str, en: str, de: str, ru: str, uk: str, *, when: Optional[str] = None, retired: bool = False) -> Item:
    """A universal item with its four translations."""
    return Item(id=id, tr={"en": en, "de": de, "ru": ru, "uk": uk}, when=when, retired=retired)


def L(id: str, lang: str, text: str, *, retired: bool = False) -> Item:
    """A language-locked item (shown only to users of ``lang``)."""
    assert lang in LANGS, lang
    return Item(id=id, tr={lang: text}, only=lang, retired=retired)
