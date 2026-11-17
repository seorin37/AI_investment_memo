"""memo_intent_eval_v1 predictions.jsonl을 사람이 검토할 HTML로 렌더링한다."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


def esc(value) -> str:
    return html.escape(str(value or ""))


def item_text(items: list[dict]) -> str:
    if not items:
        return "없음"
    return "<br>".join(f"<code>{esc(i.get('type'))}</code> {esc(i.get('description'))}" for i in items)


def render(run_dir: Path) -> Path:
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in (run_dir / "predictions.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    cards = []
    for row in rows:
        intent_rows = []
        for rec in row["intents"]:
            expected, pred = rec["expected"], rec.get("prediction") or {}
            ok = rec["tracking_expected"] == rec["tracking_predicted"]
            merge = pred.get("merge_into")
            merge_text = "없음" if not merge else f"문장 {merge.get('sentence_index')} · 항목 {merge.get('item_index', 0)}"
            intent_rows.append(f"""
            <tr class="{'ok' if ok else 'bad'}">
              <td><span class="pill">{esc(expected['kind'])}</span><br>{esc(expected['text'])}</td>
              <td>{'생성' if expected['create_tracking'] else '생성 안 함'}</td>
              <td>{esc(pred.get('decision'))} / {esc(pred.get('category'))}<br>
                  <small>{esc(pred.get('reason_code'))}</small></td>
              <td>{item_text(pred.get('items') or [])}</td>
              <td>{esc(merge_text)}<br><small>{esc(pred.get('context_note'))}</small></td>
              <td><strong>{'통과' if ok else '실패'}</strong></td>
            </tr>""")
        forbidden = "".join(f"<li>{esc(x)}</li>" for x in row.get("forbidden") or [])
        cards.append(f"""
        <section class="card">
          <h2>{esc(row['memo_id'])} · {esc(row['symbol'])}</h2>
          <pre>{esc(row['text'])}</pre>
          <table><thead><tr><th>기대 의도</th><th>기대 추적</th><th>기존 판정</th><th>생성 항목</th><th>병합</th><th>결과</th></tr></thead>
          <tbody>{''.join(intent_rows)}</tbody></table>
          <details><summary>금지 결과</summary><ul>{forbidden}</ul></details>
        </section>""")
    content = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>메모 의도 평가</title>
    <style>
    :root{{--bg:#f5f7fb;--card:#fff;--ink:#172033;--muted:#667085;--line:#dfe5ef;--ok:#e9f8ef;--bad:#fff0f0;--accent:#2457a6}}
    *{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,"Noto Sans KR",sans-serif}}
    main{{max-width:1280px;margin:36px auto;padding:0 22px}} h1{{margin-bottom:4px}} .sub{{color:var(--muted);margin-bottom:22px}}
    .stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:20px 0 28px}}
    .stat,.card{{background:var(--card);border:1px solid var(--line);border-radius:16px;box-shadow:0 2px 10px #1720330a}}
    .stat{{padding:16px}} .stat b{{display:block;font-size:24px;color:var(--accent)}} .card{{padding:20px;margin:18px 0;overflow:auto}}
    h2{{margin:0 0 10px}} pre{{white-space:pre-wrap;background:#f0f3f8;padding:14px;border-radius:10px;font:inherit}}
    table{{border-collapse:collapse;width:100%;min-width:980px}} th,td{{border-bottom:1px solid var(--line);padding:11px;text-align:left;vertical-align:top}}
    th{{background:#f8fafc}} tr.ok{{background:var(--ok)}} tr.bad{{background:var(--bad)}} .pill{{display:inline-block;padding:2px 8px;border-radius:999px;background:#e7eefb;color:#194788;font-weight:700}}
    small,details{{color:var(--muted)}} code{{color:#8b2c2c}} details{{margin-top:12px}}
    </style></head><body><main><h1>기존 코드 메모 의도 평가</h1>
    <div class="sub">새 테스트셋 18개 · 검색/카드/DB 쓰기 없이 메모 분석 단계만 실행</div>
    <div class="stats">
      <div class="stat"><b>{summary['memos']}</b>메모</div><div class="stat"><b>{summary['intents']}</b>의도</div>
      <div class="stat"><b>{summary['tracking_accuracy']*100:.1f}%</b>추적 여부 정확도</div>
      <div class="stat"><b>{summary['over_tracking']}</b>과잉 추적</div><div class="stat"><b>{summary['missed_tracking']}</b>추적 누락</div>
      <div class="stat"><b>{summary['price_accuracy']*100:.1f}%</b>가격 조건 정확도</div>
    </div>{''.join(cards)}</main></body></html>"""
    target = run_dir / "report.html"
    target.write_text(content, encoding="utf-8")
    return target


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    args = ap.parse_args()
    print(render(Path(args.run_dir)).resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
