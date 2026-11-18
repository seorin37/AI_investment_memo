"""미리보기 페이지: 만들어진 카드를 실제 사용자 화면처럼 한 장의 HTML로 모아 본다.

- 사용자에게 보이는 것만 담는다: 종류, 종목, 제목, AI 요약, 연결된 내 메모, 출처 줄, 관련 기사.
  유사도·[E1] 태그·검사 실패 코드·LLM 원문은 담지 않는다 (그건 report.md).
- 카드가 만들어지지 않은 메모는 "근거를 찾을 수 없어요"로 따로 모아 보여 준다 (AI 업데이트 탭이 빌 때의 모습).
- 파일 하나로 열린다 (외부 주소·글꼴 없음). 결과 폴더에 preview.html로 저장하고 DB는 쓰지 않는다.

사용:  PYTHONPATH=backend python -m pipelines.updates.preview results/updates/run_<시각>
       (experiment가 끝나면 같은 폴더에 preview.html을 자동으로 만든다)
"""

from __future__ import annotations

import json
import sys
from html import escape
from pathlib import Path

from .models import Candidate, TrackingItem, UpdateDraft
from .results import draft_to_dict

TYPE_LABEL = {"disclosure": "공시", "news": "뉴스", "price_condition": "주가"}
EMPTY_REASON = {
    "no_update": "관련된 새 소식을 찾지 못했어요",
    "no_candidates": "우리 데이터에서는 근거를 찾을 수 없어요",
    "already_shown": "새로 올라온 소식이 없어요",
    "price_no_card": "아직 조건가에 가깝지 않아요",
    "price_no_data": "주가 자료가 없어요",
    "not_called": "아직 확인하지 않았어요",
}

CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#1a1d23;--sub:#5b6472;--line:#e3e6eb;--accent:#1a3c6e;
--chip-d:#e8edf5;--chip-n:#eef3ec;--chip-p:#f6ece8;--memo:#f3f5f8;--warn:#8a5a00}
@media (prefers-color-scheme:dark){:root{--bg:#14161a;--card:#1d2026;--ink:#eceff4;--sub:#a3acba;--line:#2b3038;
--accent:#8fb2e8;--chip-d:#26324a;--chip-n:#27342a;--chip-p:#3a2b25;--memo:#252932;--warn:#e0b25a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.6 -apple-system,"Malgun Gothic","Apple SD Gothic Neo",sans-serif}
main{max-width:640px;margin:0 auto;padding:20px 16px 48px}
h1{font-size:20px;margin:8px 0 4px}h2{font-size:15px;margin:28px 0 10px;color:var(--sub);font-weight:600}
.meta{color:var(--sub);font-size:13px;margin:0 0 14px}
.tabs{display:flex;gap:8px;margin:0 0 14px;flex-wrap:wrap}
.tab{border:1px solid var(--line);background:var(--card);color:var(--sub);border-radius:999px;padding:5px 14px;
font-size:13px;cursor:pointer}.tab[aria-pressed=true]{background:var(--accent);border-color:var(--accent);color:#fff}
@media (prefers-color-scheme:dark){.tab[aria-pressed=true]{color:#14161a}}
details.card{background:var(--card);border:1px solid var(--line);border-radius:12px;margin:0 0 10px;padding:0}
details.card>summary{list-style:none;cursor:pointer;padding:14px 16px}
details.card>summary::-webkit-details-marker{display:none}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-size:12px;color:var(--sub)}
.chip{border-radius:6px;padding:1px 8px;font-weight:600;color:var(--ink)}
.chip.disclosure{background:var(--chip-d)}.chip.news{background:var(--chip-n)}.chip.price_condition{background:var(--chip-p)}
.title{font-size:16px;font-weight:700;margin:6px 0 0}
.body{padding:0 16px 16px;border-top:1px solid var(--line)}
.label{font-size:12px;color:var(--sub);margin:14px 0 4px}
.memo{background:var(--memo);border-radius:8px;padding:8px 12px}
.src{font-size:13px;margin:4px 0;color:var(--sub)}.src a{color:var(--accent)}
.fact{display:block;font-size:12px;color:var(--sub);margin-left:2px}
.note{font-size:12px;color:var(--sub);margin-top:14px}
.dev{font-size:11px;color:var(--warn);border:1px solid var(--warn);border-radius:6px;padding:0 6px}
.empty{background:var(--card);border:1px dashed var(--line);border-radius:12px;padding:10px 14px;margin:0 0 8px}
.empty b{display:block}.empty span{color:var(--sub);font-size:13px}
footer{margin-top:28px;color:var(--sub);font-size:12px}
ul.facts{margin:4px 0 0;padding-left:20px}ul.facts li{margin:2px 0}.fsrc{font-size:11px;color:var(--sub)}
"""

JS = """
const tabs=document.querySelectorAll('.tab'),cards=document.querySelectorAll('details.card');
tabs.forEach(t=>t.addEventListener('click',()=>{tabs.forEach(x=>x.setAttribute('aria-pressed',x===t));
const k=t.dataset.k;cards.forEach(c=>{c.hidden=!(k==='all'||c.dataset.type===k)})}));
"""


def refs_from_candidates(rows: list[tuple[TrackingItem, Candidate]]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for _, c in rows:
        out.setdefault(c.ref, {"kind": c.kind, "title": c.title, "date": c.date, "url": c.url, "source": c.source})
    return out


def _safe_url(url: str | None) -> str | None:
    return url if url and url.lower().startswith(("http://", "https://")) else None


def _source_line(ref: str, quote: str | None, refs: dict[str, dict]) -> str:
    if ref.startswith("cmp:"):                      # compare_prior: DB에서 찾은 직전 같은 기간 값
        fact = f'<span class="fact">근거: {escape(quote)}</span>' if quote else ""
        return f'<div class="src">금융감독원 DART · 직전 같은 기간 비교(memo\'s 정리값){fact}</div>'
    info = refs.get(ref, {})
    title = escape(info.get("title") or ref)
    url = _safe_url(info.get("url"))
    if info.get("kind") == "disclosure":
        head = f"금융감독원 DART · {title} · {escape(info.get('date') or '')}"
    else:
        label = f"{escape(info.get('source') or '뉴스')} · {title} · {escape(info.get('date') or '')}"
        head = f'<a href="{escape(url)}" target="_blank" rel="noopener">{label}</a>' if url else label
    fact = f'<span class="fact">근거: {escape(quote)}</span>' if quote else ""
    return f'<div class="src">{head}{fact}</div>'


def _card_html(c: dict, refs: dict[str, dict]) -> str:
    utype = c.get("update_type") or "news"
    label = TYPE_LABEL.get(utype, utype)
    name = escape(c.get("company_name") or c.get("symbol") or "")
    when = c.get("observed_trade_date") or ""
    if not when:
        dates = [refs.get(s["ref"], {}).get("date") for s in c.get("sources", [])]
        when = max([d for d in dates if d] or [""])
    dev = ' <span class="dev">고정 문구</span>' if c.get("origin") == "fixed" and utype != "price_condition" else ""
    src_lines = "".join(_source_line(s["ref"], s.get("quote"), refs) for s in c.get("sources", []))
    if utype == "price_condition":
        src_lines = f'<div class="src">KRX · {escape(str(when))} 종가 기준</div>'
    related = "".join(_source_line(r["ref"], None, {**refs, r["ref"]: {**refs.get(r["ref"], {}), "title": r.get("title") or ""}})
                      for r in c.get("related_news", []))
    related_html = f'<div class="label">관련 기사</div>{related}' if related else ""
    same = "".join(_source_line(r["ref"], None, {r["ref"]: {"kind": "news", **r}}) for r in c.get("supporting_news") or [])
    related_html = (f'<div class="label">같은 사건 기사</div>{same}' if same else "") + related_html
    reason = f'<div class="note">{escape(c["reason"])}</div>' if c.get("reason") and utype != "price_condition" else ""
    if c.get("card_schema") == "v2":
        return _card_v2_html(c, refs, label, name, dev, src_lines, related_html)
    return (
        f'<details class="card" data-type="{escape(utype)}"><summary>'
        f'<div class="row"><span class="chip {escape(utype)}">{label}</span><span>{name}</span>'
        f'<span>{escape(str(when))}</span>{dev}</div>'
        f'<div class="title">{escape(c.get("title") or "")}</div></summary>'
        f'<div class="body"><div class="label">AI 요약</div><div>{escape(c.get("summary") or "")}</div>{reason}'
        f'<div class="label">연결된 내 메모</div><div class="memo">{escape(c.get("memo_text") or "")}</div>'
        f'<div class="label">출처</div>{src_lines}{related_html}'
        f'<div class="note">AI가 요약했어요. 자세히에서 메모와 출처를 볼 수 있어요.</div></div></details>'
    )


def _fact_source(ref: str, refs: dict[str, dict]) -> str:
    if not ref:
        return ""
    if ref.startswith("cmp:"):
        return "DART 직전 같은 기간 값"
    info = refs.get(ref, {})
    who = "DART" if info.get("kind") == "disclosure" else (info.get("source") or "뉴스")
    return f"{who} · {info.get('date') or ''}"


def _card_v2_html(c: dict, refs: dict[str, dict], label: str, name: str, dev: str, src_lines: str, related_html: str) -> str:
    """v2 카드: 제목(headline) · 사건 날짜(when) · 사실 문장마다 출처 · 메모와의 연결(memo_link)."""
    utype = c.get("update_type") or "news"
    facts = "".join(f'<li>{escape(f["text"])}'
                    + (f' <span class="fsrc">{escape(_fact_source(f.get("ref") or "", refs))}</span>' if f.get("ref") else "")
                    + "</li>" for f in c.get("facts") or [])
    merged = "".join(f"<li>{escape(m.get('description') or m.get('item_id') or '')}</li>" for m in c.get("merged_items") or [])
    merged_html = f'<div class="label">같은 근거라 함께 묶은 관심사</div><ul class="facts">{merged}</ul>' if merged else ""
    link = f'<div class="label">내 메모와의 연결</div><div>{escape(c.get("memo_link") or "")}</div>' if c.get("memo_link") else ""
    cov = f'<div class="note">자료 범위: {escape(c["coverage"])}</div>' if c.get("coverage") else ""
    return (
        f'<details class="card" data-type="{escape(utype)}"><summary>'
        f'<div class="row"><span class="chip {escape(utype)}">{label}</span><span>{name}</span>'
        f'<span>{escape(c.get("when") or "")}</span>{dev}</div>'
        f'<div class="title">{escape(c.get("headline") or c.get("title") or "")}</div></summary>'
        f'<div class="body"><div class="label">확인된 사실</div><ul class="facts">{facts}</ul>{link}'
        f'<div class="label">연결된 내 메모</div><div class="memo">{escape(c.get("memo_text") or "")}</div>{merged_html}'
        f'<div class="label">출처</div>{src_lines}{related_html}{cov}'
        f'<div class="note">AI가 요약했어요. 자세히에서 메모와 출처를 볼 수 있어요.</div></div></details>'
    )


def _empty_html(e: dict) -> str:
    name = escape(e.get("company_name") or e.get("symbol") or "")
    return (f'<div class="empty"><b>{name} · {escape(e.get("description") or "")}</b>'
            f'<span>메모: {escape(e.get("memo_text") or "")}</span><br>'
            f'<span>{escape(EMPTY_REASON.get(e.get("kind", ""), "카드가 없어요"))}</span></div>')


def build_preview(cards: list[dict], refs: dict[str, dict], empties: list[dict], info: str = "") -> str:
    counts = {k: sum(1 for c in cards if c.get("update_type") == k) for k in TYPE_LABEL}
    order = sorted(cards, key=lambda c: c.get("observed_trade_date") or max(
        [refs.get(s["ref"], {}).get("date") or "" for s in c.get("sources", [])] or [""]), reverse=True)
    tabs = ['<button class="tab" data-k="all" aria-pressed="true">전체 %d</button>' % len(cards)] + [
        f'<button class="tab" data-k="{k}" aria-pressed="false">{TYPE_LABEL[k]} {n}</button>' for k, n in counts.items() if n]
    cards_html = "".join(_card_html(c, refs) for c in order) or '<div class="empty"><b>만들어진 카드가 없어요</b></div>'
    empty_html = "".join(_empty_html(e) for e in empties)
    empty_block = f'<h2>카드가 없는 메모 {len(empties)}건</h2>{empty_html}' if empties else ""
    return (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>AI 업데이트 미리보기</title><style>{CSS}</style></head><body><main>"
        f'<h1>최신 업데이트</h1><p class="meta">사용자 화면 미리보기 · {escape(info)}</p>'
        f'<div class="tabs">{"".join(tabs)}</div>{cards_html}{empty_block}'
        "<footer>뉴스: 네이버 API·4개 매체 RSS · 공시: 금융감독원 DART · 주가: KRX. 제공 정보는 참고용이며 투자 권유가 아니에요.</footer>"
        f"</main><script>{JS}</script></body></html>"
    )


def write_preview(run_dir: Path, drafts: list[UpdateDraft], cand_rows: list[tuple[TrackingItem, Candidate]],
                  empties: list[dict], info: str = "") -> Path:
    """결과 폴더에 refs.json·no_cards.json·preview.html을 쓴다 (나중에 폴더만으로 다시 그릴 수 있게)."""
    refs = refs_from_candidates(cand_rows)
    (run_dir / "refs.json").write_text(json.dumps(refs, ensure_ascii=False, indent=1), encoding="utf-8")
    (run_dir / "no_cards.json").write_text(json.dumps(empties, ensure_ascii=False, indent=1), encoding="utf-8")
    path = run_dir / "preview.html"
    path.write_text(build_preview([draft_to_dict(d) for d in drafts], refs, empties, info), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print("사용: python -m pipelines.updates.preview results/updates/run_<시각>")
        return 2
    run = Path(args[0])
    cards = [json.loads(line) for line in (run / "cards.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    refs = json.loads((run / "refs.json").read_text(encoding="utf-8")) if (run / "refs.json").exists() else {}
    empties = json.loads((run / "no_cards.json").read_text(encoding="utf-8")) if (run / "no_cards.json").exists() else []
    path = run / "preview.html"
    path.write_text(build_preview(cards, refs, empties, run.name), encoding="utf-8")
    print(f"미리보기: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
