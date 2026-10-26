"""판정 사전 로더 (configs/tracking_lexicon.yaml)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ..common.config import resolve_path
from .domain import load_vocab


DEFAULT_PATH = "configs/tracking_lexicon.yaml"


@dataclass(frozen=True)
class Lexicon:
    stock_names: dict[str, str]
    aliases: list[tuple[str, str]]  # (별칭 소문자, 종목코드), 긴 별칭부터
    profanity_stems: tuple[str, ...]
    profanity_prefixes: tuple[str, ...]
    vocatives: frozenset[str]
    filler_words: frozenset[str]
    spam_strong: tuple[str, ...]
    spam_with_link: tuple[str, ...]
    out_of_scope: tuple[str, ...]
    finance_words: tuple[str, ...]
    intent_markers: tuple[str, ...]
    price_below: tuple[str, ...]
    price_above: tuple[str, ...]
    action_words: tuple[str, ...]
    notify_words: tuple[str, ...]
    alias_pattern: re.Pattern = field(repr=False, default=None)
    domain_vocab: frozenset = field(repr=False, default=frozenset())

    def is_profanity(self, word: str) -> bool:
        """욕설 어절인가. 강조 접두사("개씨발", "존나씨발")를 떼고도 본다."""
        if word.startswith(self.profanity_stems):
            return True
        return any(word.startswith(p) and word[len(p):].startswith(self.profanity_stems) for p in self.profanity_prefixes)

    def find_symbols(self, text: str) -> list[str]:
        """본문에 나온 종목코드를 등장 순서대로 (중복 제거). 긴 별칭이 먼저 자리를 차지한다."""
        found: list[str] = []
        for match in self.alias_pattern.finditer(text):
            symbol = dict(self.aliases)[match.group(0).lower()]
            if symbol not in found:
                found.append(symbol)
        return found


def load_lexicon(path: str | Path = DEFAULT_PATH) -> Lexicon:
    with resolve_path(path).open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    names = {str(symbol): info["name"] for symbol, info in raw["stocks"].items()}
    aliases = sorted(
        {(alias.lower(), str(symbol)) for symbol, info in raw["stocks"].items() for alias in info["aliases"]},
        key=lambda pair: (-len(pair[0]), pair[0]),
    )
    # 한글 별칭은 앞뒤 글자와 붙어 있어도 맞춘다("삼전이"). 영문 별칭은 영문자 경계를 요구한다("KB"가 "KBS"에 걸리지 않게).
    parts = []
    for alias, _ in aliases:
        escaped = re.escape(alias)
        parts.append(rf"(?<![a-z]){escaped}(?![a-z])" if re.search(r"[a-z]", alias) else escaped)
    pattern = re.compile("|".join(parts), re.IGNORECASE)
    price = raw["price"]
    return Lexicon(
        stock_names=names,
        aliases=aliases,
        profanity_stems=tuple(raw["profanity_stems"]),
        profanity_prefixes=tuple(raw.get("profanity_prefixes", [])),
        vocatives=frozenset(word.lower() for word in raw["vocatives"]),
        filler_words=frozenset(raw["filler_words"]),
        spam_strong=tuple(raw["spam_strong"]),
        spam_with_link=tuple(raw["spam_with_link"]),
        out_of_scope=tuple(raw["out_of_scope"]),
        finance_words=tuple(raw["finance_words"]),
        intent_markers=tuple(raw.get("intent_markers", [])),
        domain_vocab=load_vocab(raw["domain_vocab"]) if raw.get("domain_vocab") else frozenset(),
        price_below=tuple(price["below"]),
        price_above=tuple(price["above"]),
        action_words=tuple(price["action_words"]),
        notify_words=tuple(price["notify_words"]),
        alias_pattern=pattern,
    )
