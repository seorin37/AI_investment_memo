"""검증 호출(verify_call)이 결함 있는 카드 문장을 걸러내는지 시험한다.

    PYTHONPATH=backend python scripts/probe_verify.py --dry-run     # 프롬프트 한 개만 출력, LLM 호출 없음
    PYTHONPATH=backend python scripts/probe_verify.py --run         # LLM 호출 (사례 수만큼, 약 15회)

가상 회사("가상전자")의 근거 2개(뉴스 1, 공시 1)에 대해, 정상 문장(control)과 일부러 결함을 넣은 문장(defect)을
검증 프롬프트(judge.build_verify_prompt)에 넣고 문장별 supported 판정이 기대와 맞는지 센다.

- 걸러냄(catch): 결함 문장을 supported=false로 판정
- 오탐(false reject): 정상 문장을 supported=false로 판정
- 파싱 실패: 검증 응답을 읽지 못함 (카드를 내보내지 않는 쪽으로 처리되는 경우)

DB·중앙 DB는 쓰지 않는다. LLM 키는 .env의 LLM_API_KEY를 쓴다 (experiment와 같은 호출기).
결과는 logs/probe_verify_<시각>.json에 저장한다.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from pipelines.updates.judge import build_verify_prompt, parse_verify
from pipelines.updates.models import Candidate, Card, Evidence

NEWS_TITLE = "가상전자, 차세대 메모리 양산 일정 공개"
NEWS_TEXT = ("가상전자는 내년 상반기 차세대 메모리 양산에 들어가고 하반기에 증산한다고 밝혔다. "
             "회사는 올해 3분기 매출이 12조원이라고 밝혔다.")
DISC_TITLE = "반기보고서 (2026.06)"
DISC_TEXT = ("당반기 연결 매출액은 45,300억원으로 전년 동기 대비 8.0% 증가하였다. 영업이익은 2,100억원이다. "
             "환율 5% 변동 시 USD 관련 당기손익 영향은 4,350억원이다.")

# (id, 구분, 문장들, 기대 supported)
CASES = [
    ("C1", "control", ["가상전자는 내년 상반기에 차세대 메모리 양산을 시작한다고 밝혔어요. [E1]"], [True]),
    ("C2", "control", ["당반기 연결 매출액은 45,300억원이고 전년 동기 대비 8.0% 증가했어요. [E2]"], [True]),
    ("C3", "control", ["회사는 하반기에 증산한다고 밝혔어요. [E1]"], [True]),
    ("C4", "control", ["회사는 올해 3분기 매출이 12조원이라고 밝혔어요. [E1]"], [True]),
    ("D1 지어낸 인용", "defect", ["가상전자 대표는 '올해 안에 수율 90%를 달성하겠다'고 말했어요. [E1]"], [False]),
    ("D2 숫자 변조", "defect", ["당반기 연결 매출액은 45,300억원이고 전년 동기 대비 18.0% 증가했어요. [E2]"], [False]),
    ("D3 단위 누락", "defect", ["영업이익은 2,100이에요. [E2]"], [False]),
    ("D4 근거 밖 단정", "defect", ["가상전자는 메모리 시장 1위를 확정했어요. [E1]"], [False]),
    ("D5 주체 바꿈", "defect", ["경쟁사가 내년 상반기 양산에 들어간다고 밝혔어요. [E1]"], [False]),
    ("D6 전망 문장", "defect", ["내년 하반기 증산으로 실적이 크게 늘어날 전망이에요. [E1]"], [False]),
    ("D7 범위 확대", "defect", ["가상전자의 올해 매출이 12조원으로 사상 최대예요. [E1]"], [False]),
    ("D8 시점 이동", "defect", ["가상전자는 올해 하반기에 양산을 시작해요. [E1]"], [False]),
    ("D9 방향 뒤집기", "defect", ["당반기 연결 매출액이 전년 동기 대비 8.0% 감소했어요. [E2]"], [False]),
    ("M1 섞임(마지막만 결함)", "mixed",
     ["가상전자는 내년 상반기에 양산에 들어간다고 밝혔어요. [E1]",
      "당반기 연결 영업이익은 2,100억원이에요. [E2]",
      "가상전자는 해외 공장 증설도 발표했어요. [E1]"], [True, True, False]),
]


def make_evidence() -> list[Evidence]:
    news = Candidate(ref="news:0", kind="news", symbol="000000", date="2026-11-01", title=NEWS_TITLE,
                     text=NEWS_TEXT, url=None, source="가상일보", similarity=0.6)
    disc = Candidate(ref="disc:0#0", kind="disclosure", symbol="000000", date="2026-08-14", title=DISC_TITLE,
                     text=DISC_TEXT, url=None, source="DART", similarity=0.6)
    return [Evidence("E1", news, NEWS_TEXT), Evidence("E2", disc, DISC_TEXT)]


def run(call, evidence, repeat: int = 1) -> list[dict]:
    rows = []
    for case_id, kind, sentences, expected in CASES:
        card = Card("update", "시험 카드", list(sentences), "", [], 0.9)
        prompt = build_verify_prompt(card, evidence)
        for k in range(repeat):
            raw = call(prompt)
            flags = parse_verify(raw, len(sentences))
            rows.append({"case": case_id, "kind": kind, "try": k + 1, "sentences": sentences,
                         "expected": expected, "got": flags, "raw": raw})
    return rows


def summarize(rows: list[dict]) -> dict:
    caught = missed = false_reject = ok = parse_fail = 0
    for r in rows:
        if r["got"] is None:
            parse_fail += 1
            continue
        for exp, got in zip(r["expected"], r["got"]):
            if exp is False:
                caught, missed = caught + (not got), missed + bool(got)
            else:
                false_reject, ok = false_reject + (not got), ok + bool(got)
    return {"caught": caught, "missed": missed, "false_reject": false_reject, "ok": ok, "parse_fail": parse_fail}


def main(argv: list[str] | None = None, call=None) -> int:
    ap = argparse.ArgumentParser(description="verify_call 시험 (결함 문장을 걸러내는지)")
    ap.add_argument("--dry-run", action="store_true", help="프롬프트 하나만 출력, LLM 호출 없음")
    ap.add_argument("--run", action="store_true", help="LLM을 호출해 시험")
    ap.add_argument("--repeat", type=int, default=1, help="사례마다 반복 횟수 (흔들림 확인용)")
    ap.add_argument("--out-dir", default="logs")
    args = ap.parse_args(argv)
    evidence = make_evidence()

    if args.dry_run or not args.run:
        card = Card("update", "시험 카드", list(CASES[0][2]), "", [], 0.9)
        print(build_verify_prompt(card, evidence))
        print(f"\n(사례 {len(CASES)}개, --run 으로 실행하면 LLM을 약 {len(CASES) * args.repeat}회 호출합니다)", file=sys.stderr)
        return 0

    client = None
    if call is None:
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
        from pipelines.tracking.openai_client import OpenAIClient
        client = call = OpenAIClient.from_env()

    rows = run(call, evidence, args.repeat)
    stat = summarize(rows)
    for r in rows:
        mark = "-" if r["got"] is None else ("OK" if r["got"] == r["expected"] else "XX")
        print(f"{mark:>2} {r['case']:<24} 기대 {r['expected']} / 판정 {r['got']}")
    n_def = sum(1 for r in rows for e in r["expected"] if e is False and r["got"] is not None)
    n_ctl = sum(1 for r in rows for e in r["expected"] if e is True and r["got"] is not None)
    print(f"\n결함 문장 {n_def}개 중 걸러냄 {stat['caught']} / 놓침 {stat['missed']}")
    print(f"정상 문장 {n_ctl}개 중 통과 {stat['ok']} / 오탐 {stat['false_reject']}")
    print(f"파싱 실패 {stat['parse_fail']}건")
    if client is not None and getattr(client, "calls", None):
        pt = sum(c.prompt_tokens or 0 for c in client.calls)
        ot = sum(c.output_tokens or 0 for c in client.calls)
        print(f"LLM 호출 {len(client.calls)}회, 입력 토큰 {pt}, 출력 토큰 {ot}")

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"probe_verify_{time.strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps({"summary": stat, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"결과: {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())