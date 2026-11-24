"""memo_followup_check 결과 폴더 → 한 페이지 보고서 report.html (파일만 읽음, DB 접속 없음) (2026-11-12).

    PYTHONPATH=backend python -m pipelines.updates.memo_followup_report results/updates/memo_followup_<시각>

메모 버전마다: 메모 본문 · 분석 결과(새 항목·done) · 항목 표(상태·마지막 확인) · 항목별 응답 유형과 이유 ·
LLM에 넘긴 근거(outcomes.jsonl) · 관련성 판정 집계와 O 후보(candidates.csv) · 새 카드(제목·when·사실·연결·자료 범위·근거 발행일).
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from html import escape
from pathlib import Path

CSS = """
:root{--bg:#fff;--fg:#1d1d1f;--muted:#6b6b70;--line:#e3e3e6;--card:#f6f7f9;--ok:#1f7a3d;--bad:#b3261e;--warn:#8a5a00;--acc:#2456c9}
@media (prefers-color-scheme: dark){:root{--bg:#141416;--fg:#ececef;--muted:#9a9aa2;--line:#2c2c31;--card:#1d1d21;--ok:#6fcf8f;--bad:#ff8a80;--warn:#e0b25a;--acc:#8fb0ff}}
body{background:var(--bg);color:var(--fg);font:14px/1.6 -apple-system,"Segoe UI","Malgun Gothic",sans-serif;margin:0;padding:24px 16px}
main{max-width:980px;margin:0 auto}h1{font-size:22px;margin:0 0 4px}h2{font-size:18px;margin:36px 0 8px;padding-top:16px;border-top:2px solid var(--line)}
h3{font-size:15px;margin:18px 0 6px}.muted{color:var(--muted)}pre{background:var(--card);padding:10px 12px;border-radius:8px;white-space:pre-wrap;margin:6px 0}
table{border-collapse:collapse;width:100%;font-size:13px;margin:6px 0}td,th{border-bottom:1px solid var(--line);padding:5px 6px;text-align:left;vertical-align:top}
th{color:var(--muted);font-weight:600}.tag{display:inline-block;padding:0 7px;border-radius:9px;font-size:12px;border:1px solid var(--line)}
.active{color:var(--ok)}.done{color:var(--muted);text-decoration:line-through}.update_card{color:var(--ok);font-weight:600}.no_new_info{color:var(--warn)}
.card{border:1px solid var(--line);border-left:4px solid var(--acc);border-radius:10px;padding:12px 14px;margin:10px 0;background:var(--card)}
.card .h{font-weight:700;font-size:15px}.card ul{margin:6px 0 6px 18px;padding:0}a{color:var(--acc)}.scroll{overflow-x:auto}
"""


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()] if path.is_file() else []


def _candidates(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _card_html(u: dict) -> str:
    card = u.get("card") or {}
    facts = "".join(f"<li>{escape(f.get('text') or '')} <span class='muted'>({escape(f.get('ref') or '근거 없음')})</span></li>"
                    for f in card.get("facts") or [])
    srcs = "".join(
        f"<li>{escape(str(s.get('published_at'))[:10])} {escape(s.get('source') or '')} "
        + (f"<a href='{escape(s['url'])}' target='_blank' rel='noopener'>{escape(s.get('title') or '')}</a>" if s.get("url")
           else escape(s.get("title") or "")) + "</li>"
        for s in u.get("sources") or [])
    return (f"<div class='card'><div class='h'>{escape(u.get('headline') or u.get('title') or '')}</div>"
            f"<div class='muted'>when {escape(str(card.get('when')))} · 대표 근거 발행 {escape(str(u.get('published_at'))[:10])}"
            f" · 카드 만든 시각 {escape(str(u.get('created_at'))[:16])} · 메모 버전 {u.get('memo_version')}</div>"
            f"<ul>{facts}</ul>"
            + (f"<div><b>연결</b> {escape(card.get('memo_link') or '')}</div>" if card.get("memo_link") else "")
            + (f"<div class='muted'>자료 범위: {escape(card['coverage'])}</div>" if card.get("coverage") else "")
            + (f"<div style='margin-top:6px'><b>근거</b><ul>{srcs}</ul></div>" if srcs else "") + "</div>")


def build(folder: Path) -> str:
    created = json.loads((folder / "created.json").read_text(encoding="utf-8"))
    root = folder.parent
    scen = created.get("scenario") or {}
    vers = scen.get("versions") or []
    parts = [f"<h1>메모 이어쓰기 점검</h1><div class='muted'>{escape(folder.name)} · 대상 {escape(str(created.get('target')))}"
             f" · 테스트 사용자 {created.get('user_id')} · 메모 {created.get('memo_ids')} · 종목 {escape(scen.get('symbol', ''))}"
             f" · 시작 {escape(str(created.get('started_at'))[:16])} · 카드 설정 {escape(Path(str(created.get('config'))).name)}</div>"]
    total = 0.0
    for n, v in enumerate(created.get("versions") or [], 1):
        body = vers[n - 1]["body"] if n - 1 < len(vers) else ""
        a = v.get("analysis") or {}
        parts.append(f"<h2>{escape(v.get('label') or f'v{n}')}</h2><pre>{escape(body)}</pre>"
                     f"<div class='muted'>분석 {escape(str(a.get('status')))} · 새 항목 {a.get('created')} · done {a.get('done')}"
                     f" · 확인 질문 {len(a.get('confirmations') or [])} · 범위 밖 {a.get('out_of_scope')}"
                     + (f" · 카드 생성 비용 ${v['usd']}" if v.get("usd") is not None else "") + "</div>")
        total += v.get("usd") or 0
        runs = v.get("card_run") or []
        responses = {r["item_id"]: r for run in runs for r in _read_jsonl(root / run / "responses.jsonl")}
        outcomes = {o["item_id"]: o for run in runs for o in _read_jsonl(root / run / "outcomes.jsonl")}
        cands = [c for run in runs for c in _candidates(root / run / "candidates.csv")]
        rows = []
        for it in v.get("items") or []:
            iid = str(it["id"])
            r = responses.get(iid)
            resp = (f"<span class='{escape(r['type'])}'>{escape(r['type'])}</span> <span class='muted'>{escape(r.get('reason') or '')}"
                    f" {escape(' '.join(r.get('fail_codes') or []))}</span>") if r else "<span class='muted'>-</span>"
            rows.append(f"<tr><td>{iid}</td><td class='{escape(it['status'])}'>{escape(it['status'])}</td><td>{escape(it['description'] or '')}</td>"
                        f"<td>{escape(str(it.get('last_checked_at') or '없음(첫 확인)')[:16])}</td><td>{resp}</td></tr>")
        parts.append("<h3>추적 항목</h3><div class='scroll'><table><tr><th>id</th><th>상태</th><th>설명</th><th>마지막 확인(분석 직후)</th>"
                      "<th>이번 응답</th></tr>" + "".join(rows) + "</table></div>")
        for iid, o in outcomes.items():
            mine = [c for c in cands if c.get("item_id") == iid]
            cnt = Counter(c.get("판정(O/X)") or "판정 안 함" for c in mine)
            codes = Counter(c.get("판정코드") for c in mine if c.get("판정코드"))
            ev = "".join(f"<tr><td>{escape(e['eid'])}</td><td>{escape(e.get('date') or '')}</td><td>{escape(e.get('kind') or '')}</td>"
                         f"<td>{e.get('similarity', 0):.3f}</td><td>{escape(e.get('title') or '')}</td></tr>" for e in o.get("evidence") or [])
            oks = [c for c in mine if c.get("판정(O/X)") == "O"]
            ok_rows = "".join(f"<tr><td>{escape(c['날짜'])}</td><td>{escape(c['종류'])}</td><td>{escape(c['유사도'])}</td>"
                              f"<td>{escape(c['제목'][:80])}</td></tr>" for c in oks[:20])
            parts.append(f"<h3>항목 {escape(iid)} · {escape(o.get('description') or '')}</h3>"
                         f"<div class='muted'>후보 {len(mine)}건 · 판정 {dict(cnt)} · 판정 코드 {dict(codes)}</div>"
                         + (f"<div><b>LLM에 넘긴 근거</b></div><div class='scroll'><table><tr><th></th><th>날짜</th><th>종류</th><th>유사도</th>"
                            f"<th>제목</th></tr>{ev}</table></div>" if ev else "<div class='muted'>LLM에 넘긴 근거 없음</div>")
                         + (f"<details><summary>관련 있음(O) 후보 {len(oks)}건</summary><div class='scroll'><table><tr><th>날짜</th>"
                            f"<th>종류</th><th>유사도</th><th>제목</th></tr>{ok_rows}</table></div></details>" if oks else ""))
        new = v.get("new_cards") or []
        parts.append(f"<h3>이번 버전에서 새로 나온 카드 {len(new)}장</h3>" + ("".join(_card_html(u) for u in new)
                                                                      or "<div class='muted'>없음</div>"))
    parts.append(f"<h2>합계</h2><div>카드 생성 LLM 비용 약 ${total:.4f} (메모 분석 호출 비용은 별도)</div>")
    return ("<!doctype html><html lang='ko'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>메모 이어쓰기 점검</title><style>{CSS}</style></head><body><main>{''.join(parts)}</main></body></html>")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="memo_followup_check 결과 → report.html")
    ap.add_argument("folder")
    args = ap.parse_args(argv)
    folder = Path(args.folder)
    out = folder / "report.html"
    out.write_text(build(folder), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
