"""기사-종목 태그 확대: 코스피 전체 종목 이름·별칭으로 news_stocks를 붙인다 (설정 configs/stock_aliases.yaml).

  python -m backend.pipelines.news.stock_tagger --since 2026-11-01                     # dry-run: 붙을 건수 + 오탐 의심 표본 csv
  python -m backend.pipelines.news.stock_tagger --since 2026-11-01 --write --target 192.168.0.105:15432

- 기존 tagger(stocks.yaml 4종목, RSS 수집기 안)는 그대로 둔다. 이 모듈은 이미 태그가 있는 기사도 다시 보고 빠진 종목만 더한다
  (INSERT … ON CONFLICT DO NOTHING이라 여러 번 돌려도 안전하다. 기존 태그는 지우거나 고치지 않는다).
- 이름: stocks 테이블(코스피) 이름 + aliases. 우선주(…우·…우B, 종목코드 끝이 0이 아님)는 빼고 보통주로 붙인다.
- 긴 이름 우선: DART 상장사 이름(corpCode.xml)·blockers가 더 길게 겹치는 자리의 짧은 이름은 세지 않는다.
  영문 이름은 앞뒤가 영문자·숫자가 아닐 때만 ("ELS"의 "LS", "KTX"의 "KT"를 빼려고).
- 흔한 단어·지명(require_context, short_ok에 없는 2글자 한글 이름)은 앞뒤 context_window자 안에 주식 관련 말이 있을 때만.
- 그룹 이름과 같은 지주사(group_names)는 제목·리드에서만, 뒤에 "그룹·家·회장…"이 오면 붙이지 않는다.
- 2026-11-09 표본 O/X로 더한 규칙: 스포츠 구단과 같은 이름(sports_names)은 근처에 경기 말이 있으면 빼고, 짧은 이름·그룹 이름
  바로 뒤에 조사가 아닌 한글이 붙으면(비상장 계열사 "LS오토", "두산인베스트먼트", "기아대책") 빼고, 이름에 "증권"이 든 종목은
  제목에서만(기사 출처 "~증권에 따르면"), 2글자 영문 이름 바로 앞이 한글이면("울산TP") 뺀다.
- 붙이는 기준: 제목(score 1.0) / 본문 리드 lead_chars자 안 1번(0.8) / 본문 2번 이상(0.6). 본문 규칙 종목은 기사당 max_body_tags개.
  원문이 없는 기사는 제목만 본다.
- 공용 DB 쓰기는 --write --target host:port일 때만 (실제 대상과 다르면 멈춘다). 기본은 읽기 전용 dry-run.
"""
from __future__ import annotations

import argparse
import csv
import logging
import random
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml

log = logging.getLogger("stock_tagger")

CONFIG_PATH = Path("configs/stock_aliases.yaml")
CORP_CODE_PATH = Path("data/raw/dart/corpCode.xml")
SCORES = {"title": 1.0, "lead": 0.8, "body": 0.6}
_PREFERRED = re.compile(r"(\d?우[A-Z]?|우선주)$")
_LATIN = re.compile(r"[A-Za-z0-9]")
_HANGUL = re.compile(r"[가-힣]")
# 짧은 이름 바로 뒤에 붙어도 되는 글자 (조사·어미의 첫 글자). 이 밖의 한글이 붙으면 다른 회사 이름의 앞부분으로 본다
_PARTICLE_START = set("은는이가을를의에와과도로만랑께서며고및측")

ARTICLES_SQL = """SELECT a.id, a.title, b.body FROM news_articles a
LEFT JOIN news_article_bodies b ON b.news_id = a.id
WHERE a.published_at >= %(since)s AND a.published_at < %(until)s ORDER BY a.id"""
EXISTING_SQL = "SELECT news_id, symbol FROM news_stocks WHERE news_id = ANY(%(ids)s)"
INSERT_SQL = "INSERT INTO news_stocks (news_id, symbol, score) VALUES (%s, %s, %s) ON CONFLICT (news_id, symbol) DO NOTHING"


@dataclass
class Rules:
    names: dict[str, str]                       # 이름·별칭 → 종목코드
    blockers: list[str]                         # 긴 이름부터 (우리 이름 + 막는 이름)
    group_names: set[str] = field(default_factory=set)
    group_suffixes: tuple[str, ...] = ()
    require_context: set[str] = field(default_factory=set)
    context_words: tuple[str, ...] = ()
    context_window: int = 30
    max_body_tags: int = 5
    lead_chars: int = 200
    sports_names: set[str] = field(default_factory=set)
    sports_words: tuple[str, ...] = ()
    prefix_check: set[str] = field(default_factory=set)     # 바로 뒤 글자를 보는 이름 (짧은 이름·그룹 이름)
    title_only: set[str] = field(default_factory=set)       # 제목에서만 붙이는 이름 ("증권"이 든 종목, 네이버)
    context_after_window: int = 10                           # 리드·본문의 흔한 단어 이름: 바로 뒤 이 글자 수 안의 주식 낱말만
    skip_title: tuple[re.Pattern, ...] = ()                  # 이 제목의 기사는 건너뛴다 ([인사]·[부고])
    group_list_words: tuple[str, ...] = ()                   # "삼성·LG"처럼 그룹 이름 나열로 보는 말
    group_list_tail: tuple[str, ...] = ()                    # 나열 끝에 오면 그룹 이야기 ("…LG그룹", "… 등 주요 대기업")
    sports_re: re.Pattern | None = None                      # sports_words (정규식)
    name_suffix_block: tuple[str, ...] = ()                  # 이름 바로 뒤에 붙으면 다른 기관 ("한국공항공사", "기업은행챔버홀")
    spaced_suffix_re: re.Pattern | None = None               # 한 칸 띄고 오는 시설 이름 ("기업은행 챔버홀", "LG 시그니처홀")
    group_product_re: re.Pattern | None = None               # 그룹 이름 뒤 제품·매장 낱말 ("LG 올레드", "LG 베스트샵")
    body_with_stock_words: set[str] = field(default_factory=set)   # 제목 전용이지만 본문에서 바로 뒤 주식 낱말이면 붙이는 이름 (네이버)


@dataclass(frozen=True)
class Hit:
    symbol: str
    name: str
    rule: str                                   # title | lead | body
    count: int                                  # 본문 등장 횟수 (title이면 제목 횟수)
    context: str                                # 처음 걸린 자리 앞뒤 글

    @property
    def score(self) -> float:
        return SCORES[self.rule]


def is_preferred(symbol: str, name: str) -> bool:
    return not symbol.endswith("0") and bool(_PREFERRED.search(name))


def listed_names(path: Path = CORP_CODE_PATH) -> set[str]:
    """DART corpCode.xml의 상장사 이름 (긴 이름 우선에 쓴다). 파일이 없으면 빈 집합."""
    if not path.is_file():
        return set()
    out = set()
    for _, el in ET.iterparse(path):
        if el.tag == "list":
            if (el.findtext("stock_code") or "").strip() and (el.findtext("corp_name") or "").strip():
                out.add(el.findtext("corp_name").strip())
            el.clear()
    return out


def build_rules(stocks: dict[str, str], cfg: dict, dart_names: set[str] = frozenset()) -> Rules:
    names: dict[str, str] = {}
    for sym, name in stocks.items():
        if name and not is_preferred(sym, name):
            names.setdefault(name, sym)
    for sym, aliases in (cfg.get("aliases") or {}).items():
        if sym in stocks:
            for a in aliases:
                names.setdefault(a, sym)
    extra = set(cfg.get("blockers") or [])
    # 막는 이름: 우리 이름을 품은 더 긴 이름만 (전부 넣으면 느리다). 우선주 이름은 막지 않는다 ("삼성전자우" → 삼성전자)
    longer = {d for d in dart_names | extra if d not in names and any(n in d for n in names if n != d)}
    short = {n for n in names if len(n) <= 2 and not _LATIN.search(n)}
    groups = set(cfg.get("group_names") or [])
    return Rules(names=names, blockers=sorted(set(names) | longer, key=len, reverse=True),
                 group_names=set(cfg.get("group_names") or []), group_suffixes=tuple(cfg.get("group_suffixes") or ()),
                 require_context=(set(cfg.get("require_context") or []) | (short - set(cfg.get("short_ok") or []))) & set(names),
                 context_words=tuple(cfg.get("context_words") or ()), context_window=int(cfg.get("context_window", 30)),
                 max_body_tags=int(cfg.get("max_body_tags", 5)), lead_chars=int(cfg.get("lead_chars", 200)),
                 sports_names=set(cfg.get("sports_names") or []) & set(names),
                 sports_words=tuple(cfg.get("sports_words") or ()),
                 prefix_check={n for n in names if len(n) <= int(cfg.get("prefix_check_max_len", 3)) or n in groups},
                 title_only=({n for n in names if any(w in n for w in (cfg.get("title_only_words") or []))}
                             | (set(cfg.get("title_only_names") or []) & set(names))),
                 context_after_window=int(cfg.get("context_after_window", 10)),
                 skip_title=tuple(re.compile(p) for p in (cfg.get("skip_title_patterns") or [])),
                 group_list_words=tuple(sorted(set(cfg.get("group_list_words") or []), key=len, reverse=True)),
                 group_list_tail=tuple(cfg.get("group_list_tail") or ()),
                 sports_re=re.compile("|".join(f"(?:{w})" for w in (cfg.get("sports_words") or []))) if cfg.get("sports_words") else None,
                 name_suffix_block=tuple(cfg.get("name_suffix_block") or ()),
                 spaced_suffix_re=_words_re(cfg.get("spaced_suffix_block"), r"\s"),
                 group_product_re=_words_re(cfg.get("group_product_words"), r"\s?"),
                 body_with_stock_words=set(cfg.get("title_only_names") or []) & set(names))


def _words_re(words, prefix: str) -> re.Pattern | None:
    """prefix + (낱말 중 하나). 낱말이 없으면 None."""
    return re.compile(prefix + "(?:" + "|".join(map(re.escape, sorted(words, key=len, reverse=True))) + ")") if words else None


def _latin_ok(text: str, a: int, b: int, name: str) -> bool:
    if _LATIN.match(name[0]) and a > 0 and _LATIN.match(text[a - 1]):
        return False
    if len(name) <= 2 and _LATIN.match(name[0]) and a > 0 and _HANGUL.match(text[a - 1]):
        return False                                         # "울산TP": 2글자 영문 이름 바로 앞이 한글
    if _LATIN.match(name[-1]) and b < len(text) and re.match(r"[A-Za-z]", text[b]):
        return False
    return True


def find(text: str, rules: Rules) -> list[tuple[int, int, str]]:
    """(시작, 끝, 이름) — 긴 이름이 먼저 자리를 차지하고, 그 안의 짧은 이름은 버린다. 막는 이름은 자리만 차지한다."""
    taken: list[tuple[int, int]] = []
    out = []
    for name in rules.blockers:
        start = text.find(name)
        while start != -1:
            a, b = start, start + len(name)
            start = text.find(name, a + 1)
            if any(x < b and a < y for x, y in taken) or not _latin_ok(text, a, b, name):
                continue
            taken.append((a, b))
            if name in rules.names:
                out.append((a, b, name))
    return sorted(out)


_CODE_AFTER = re.compile(r"\s*[(\[]\s*\d{6}\s*[)\]]")      # "대상(001680)"


def _sports_at(text: str, a: int, b: int, rules: Rules) -> bool:
    """이 자리 앞뒤 context_window자 안에 스포츠 낱말이 있는가."""
    w = rules.context_window
    around = text[max(0, a - w):a] + " " + text[b:b + w]
    return bool(rules.sports_re.search(around)) if rules.sports_re else any(word in around for word in rules.sports_words)


def _stock_after(text: str, b: int, rules: Rules) -> bool:
    """이름 바로 뒤 context_after_window자 안에 주식 낱말이나 종목코드가 있는가 ("네이버 주가", "네이버(035420)")."""
    return bool(_CODE_AFTER.match(text, b)) or any(w in text[b:b + rules.context_after_window] for w in rules.context_words)


def _group_talk(text: str, a: int, b: int, name: str, rules: Rules) -> bool:
    """그룹 이름 자리가 그룹 이야기인가 (2026-11-18): 뒤에 영문 계열사 낱말 / 그룹 이름 나열 / 나열 끝의 그룹·대기업."""
    after = text[b:b + 30]
    if re.match(r"\s?[A-Za-z]", after):
        return True                                          # "LG CNS", "SK C&C", "SK AX", "SK u타워": 영문 계열사·시설
    if rules.group_product_re and rules.group_product_re.match(after):
        return True                                          # "LG 올레드 TV", "LG 베스트샵": 계열사 제품·매장 브랜드
    if text[max(0, a - 1):a] == "범":
        return True                                          # "범LG家": 그룹 일가
    words = "|".join(map(re.escape, rules.group_list_words))
    if words and (re.search(rf"(?:{words})\s*[·・,]\s*$", text[max(0, a - 8):a])
                  or re.match(rf"\s*[·・,]\s*(?:{words})(?![가-힣])", after)):
        return True                                          # "삼성·LG", "삼성·SK·LG"
    tail = "|".join(map(re.escape, rules.group_list_tail))
    return bool(tail and re.match(rf"(?:\s*[·・,/]\s*[가-힣A-Za-z]{{1,6}}?)*\s*(?:등\s*)?(?:주요\s*)?(?:{tail})", after))


def _valid(text: str, a: int, b: int, name: str, rules: Rules, in_title: bool = True) -> bool:
    if name in rules.prefix_check and b < len(text) and _HANGUL.match(text[b]) and text[b] not in _PARTICLE_START:
        return False                                         # "LS오토", "두산인베스트먼트", "기아대책": 다른 이름의 앞부분
    if name in rules.prefix_check and _HANGUL.match(name[0]) and a > 0 and _HANGUL.match(text[a - 1]):
        return False                                         # "경영인대상", "평생학습대상": 다른 낱말의 뒷부분
    if any(text.startswith(s, b) for s in rules.name_suffix_block):
        return False                                         # "한국공항공사", "IBK기업은행챔버홀": 다른 기관·시설
    if rules.spaced_suffix_re and rules.spaced_suffix_re.match(text, b):
        return False                                         # "IBK기업은행 챔버홀", "LG 시그니처홀": 띄어 쓴 시설 이름
    if b < len(text) and text[b].isdigit() and not name[-1].isdigit():
        return False                                         # "이마트24": 숫자가 붙은 다른 회사 이름
    if name in rules.sports_names and _sports_at(text, a, b, rules):
        return False                                         # 프로야구·농구·배구 구단
    if name in rules.group_names:
        after = text[b:b + 6].lstrip()
        if any(after.startswith(s) for s in rules.group_suffixes):
            return False                                     # "SK그룹", "LG家", "한화 회장" → 그룹 이야기
        if _group_talk(text, a, b, name, rules):
            return False
    if name in rules.require_context:
        if a > 0 and text[a - 1].isalnum():
            return False                                     # "한국PR대상": 영문·숫자 바로 뒤에 붙은 흔한 단어 이름
        if in_title:
            w = rules.context_window
            around = text[max(0, a - w):a] + " " + text[b:b + w]
            if not any(word in around for word in rules.context_words):
                return False
        else:                                                # 리드·본문: 바로 뒤 주식 낱말·종목코드·㈜만
            after = text[b:b + rules.context_after_window]
            if not (any(word in after for word in rules.context_words) or _CODE_AFTER.match(text, b)
                    or "㈜" in text[max(0, a - 2):a] or "(주)" in text[max(0, a - 4):a]):
                return False
    return True


def _snippet(text: str, a: int, b: int, width: int = 40) -> str:
    return (text[max(0, a - width):a] + "[" + text[a:b] + "]" + text[b:b + width]).replace("\n", " ")


def match_article(title: str, body: str | None, rules: Rules) -> list[Hit]:
    """한 기사에 붙일 종목. 제목 규칙 → 리드 규칙 → 본문 2번 이상 순으로 강한 규칙 하나만 남긴다."""
    hits: dict[str, Hit] = {}
    if any(p.search(title or "") for p in rules.skip_title):
        return []                                            # [인사]·[부고]: 계열사를 여러 개 나열한다
    # 스포츠 문맥이 한 자리라도 있는 구단 이름은 기사 전체에서 뺀다 (배구 기사 뒤쪽의 "현대건설도 분위기…")
    sports = {name for text in (title or "", body or "") for a, b, name in find(text, rules)
              if name in rules.sports_names and _sports_at(text, a, b, rules)}
    for a, b, name in find(title or "", rules):
        sym = rules.names[name]
        if name not in sports and sym not in hits and _valid(title, a, b, name, rules):
            hits[sym] = Hit(sym, name, "title", 1, _snippet(title, a, b))
    if body:
        counts: Counter = Counter()
        first: dict[str, tuple[int, int, str]] = {}
        for a, b, name in find(body, rules):
            if name in sports or not _valid(body, a, b, name, rules, in_title=False):
                continue
            # 제목에서만 붙이는 이름: "증권"이 든 이름은 본문에서 빼고, 네이버는 바로 뒤 주식 낱말·종목코드가 있으면 붙인다
            if name in rules.title_only and not (name in rules.body_with_stock_words and _stock_after(body, b, rules)):
                continue
            sym = rules.names[name]
            counts[sym] += 1
            first.setdefault(sym, (a, b, name))
        body_hits = []
        for sym, n in counts.items():
            if sym in hits:
                continue
            a, b, name = first[sym]
            if a < rules.lead_chars:
                body_hits.append(Hit(sym, name, "lead", n, _snippet(body, a, b)))
            elif n >= 2 and name not in rules.group_names:     # 그룹 이름 지주사는 제목·리드에서만
                body_hits.append(Hit(sym, name, "body", n, _snippet(body, a, b)))
        body_hits.sort(key=lambda h: (-h.score, -h.count, h.symbol))
        for h in body_hits[:rules.max_body_tags]:
            hits[h.symbol] = h
    return list(hits.values())


def load_rules(conn, config_path: Path = CONFIG_PATH, corp_path: Path = CORP_CODE_PATH) -> Rules:
    with conn.cursor() as cur:
        cur.execute("SELECT symbol, name FROM stocks")
        stocks = {s.strip(): n for s, n in cur.fetchall()}
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return build_rules(stocks, cfg, listed_names(corp_path))


def tag_window(conn, rules: Rules, since: datetime, until: datetime, write: bool = False) -> dict:
    """기간 안 기사를 훑어 새로 붙일 (기사, 종목, 규칙)을 센다. write면 news_stocks에 더한다 (기존 태그는 그대로)."""
    with conn.cursor() as cur:
        cur.execute(ARTICLES_SQL, {"since": since, "until": until})
        arts = cur.fetchall()
        cur.execute(EXISTING_SQL, {"ids": [a[0] for a in arts]})
        existing = defaultdict(set)
        for nid, sym in cur.fetchall():
            existing[nid].add(sym.strip())
    new: list[tuple[int, str, str, Hit]] = []
    for nid, title, body in arts:
        for h in match_article(title or "", body, rules):
            if h.symbol not in existing[nid]:
                new.append((nid, title or "", "body" if body else "title_only", h))
    stats = {"articles": len(arts), "with_body": sum(1 for a in arts if a[2]),
             "already_tagged_articles": sum(1 for a in arts if existing[a[0]]),
             "new_links": len(new), "new_articles": len({n for n, *_ in new}),
             "by_rule": dict(Counter(h.rule for *_, h in new))}
    if write and new:
        with conn.transaction(), conn.cursor() as cur:
            cur.executemany(INSERT_SQL, [(nid, h.symbol, h.score) for nid, _, _, h in new])
    stats["written"] = len(new) if write else 0
    stats["_new"] = new
    return stats


def suspicious(new, rules: Rules, k: int = 30, seed: int = 7) -> list[tuple[str, int, str, Hit]]:
    """오탐 의심 표본: 흔한 단어·지명 / 그룹 이름 / 2글자 / 영문 / 본문 딱 2번 / 태그 많은 기사. 종목당 2개까지 골고루."""
    per_article = Counter(nid for nid, *_ in new)
    flagged = []
    for nid, title, _, h in new:
        reasons = []
        if h.name in rules.require_context:
            reasons.append("흔한 단어·지명")
        if h.name in rules.group_names:
            reasons.append("그룹 이름")
        if len(h.name) <= 2:
            reasons.append("2글자")
        if _LATIN.search(h.name):
            reasons.append("영문")
        if h.rule == "body" and h.count == 2:
            reasons.append("본문 2번")
        if per_article[nid] >= 5:
            reasons.append(f"기사 태그 {per_article[nid]}개")
        if reasons:
            flagged.append((", ".join(reasons), nid, title, h))
    random.Random(seed).shuffle(flagged)
    out, per_sym, per_reason = [], Counter(), Counter()
    for f in sorted(flagged, key=lambda f: per_reason[f[0]]):
        if len(out) >= k:
            break
        if per_sym[f[3].symbol] >= 2:
            continue
        out.append(f)
        per_sym[f[3].symbol] += 1
        per_reason[f[0]] += 1
    return out


def main(argv=None) -> int:
    from ..common.db import get_dsn, get_read_dsn, load_env
    from .fulltext_load import dsn_target

    ap = argparse.ArgumentParser(description="기사-종목 태그 확대 (기본 dry-run)")
    ap.add_argument("--since", required=True, help="발행일 시작 YYYY-MM-DD (KST)")
    ap.add_argument("--until", help="발행일 끝(포함 안 함) YYYY-MM-DD (KST, 기본: 지금)")
    ap.add_argument("--config", type=Path, default=CONFIG_PATH)
    ap.add_argument("--sample-out", type=Path, help="오탐 의심 표본 csv 경로")
    ap.add_argument("--sample", type=int, default=30)
    ap.add_argument("--links-out", type=Path,
                    help="새로 붙일 연결 전체(news_id, symbol, score, 규칙, 이름)를 csv로. --write 전에 남겨 두면 그대로 되돌릴 수 있다")
    ap.add_argument("--write", action="store_true", help="news_stocks에 실제로 더한다 (--target 필수)")
    ap.add_argument("--target", help="--write일 때 접속 대상 host:port. 다르면 쓰지 않고 멈춘다")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    load_env()
    import psycopg
    from zoneinfo import ZoneInfo

    kst = ZoneInfo("Asia/Seoul")
    since = datetime.fromisoformat(args.since).replace(tzinfo=kst)
    until = datetime.fromisoformat(args.until).replace(tzinfo=kst) if args.until else datetime.now(timezone.utc)
    dsn = get_dsn() if args.write else get_read_dsn()
    target = dsn_target(dsn)
    print(f"접속 대상: {target}  ({'쓰기' if args.write else 'dry-run: 읽기만'})")
    if args.write and (not args.target or not target.startswith(args.target + "/")):
        print(f"--target({args.target})이 실제 접속 대상({target})과 달라 쓰지 않고 멈춥니다.")
        return 3
    with psycopg.connect(dsn) as conn:
        conn.read_only = not args.write
        rules = load_rules(conn, args.config)
        stats = tag_window(conn, rules, since, until, write=False)
        new = stats.pop("_new")
        if args.links_out:                                   # 쓰기 전에 넣을 연결을 남긴다 (되돌리기: 이 파일의 쌍만 지운다)
            args.links_out.parent.mkdir(parents=True, exist_ok=True)
            with args.links_out.open("w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                w.writerow(["news_id", "symbol", "score", "rule", "name"])
                w.writerows((nid, h.symbol, h.score, h.rule, h.name) for nid, _, _, h in new)
            print(f"넣을 연결 {len(new)}개 → {args.links_out}")
        if args.write and new:
            with conn.transaction(), conn.cursor() as cur:
                cur.executemany(INSERT_SQL, [(nid, h.symbol, h.score) for nid, _, _, h in new])
            stats["written"] = len(new)
        if not args.write:
            conn.rollback()
    print(f"이름 {len(rules.names)}개 (막는 긴 이름 포함 {len(rules.blockers)}), 문맥 필요 {len(rules.require_context)}개")
    print({k: v for k, v in stats.items()})
    per_sym = Counter(h.symbol for *_, h in new)
    names = {s: n for n, s in rules.names.items()}
    print("새로 붙는 종목 수:", len(per_sym), "/ 상위:", [(names.get(s, s), n) for s, n in per_sym.most_common(20)])
    if args.sample_out:
        rows = suspicious(new, rules, args.sample)
        args.sample_out.parent.mkdir(parents=True, exist_ok=True)
        with args.sample_out.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["맞음(O/X)", "의심 이유", "종목코드", "이름", "규칙", "본문 횟수", "기사 제목", "문맥", "news_id"])
            for reason, nid, title, h in rows:
                w.writerow(["", reason, h.symbol, h.name, h.rule, h.count, title, h.context, nid])
        print(f"오탐 의심 표본 {len(rows)}개 → {args.sample_out}")
    print("공용 DB에 썼습니다." if args.write else "dry-run이라 DB에 쓰지 않았습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
