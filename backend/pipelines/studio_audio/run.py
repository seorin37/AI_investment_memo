"""AI 오디오 한 편 만들기 (시험용 CLI, 2026-11-23). DB는 읽기만 한다. 결과는 results/studio_audio/run_<시각>/ 파일로.

    # 대본만 (LLM 비용만, TTS 없음) → 대본 확인부터
    PYTHONPATH=backend python -m pipelines.studio_audio.run --email studio-audio-test@example.invalid --tts none
    # 대본 + Fish Audio 음성
    PYTHONPATH=backend python -m pipelines.studio_audio.run --email studio-audio-test@example.invalid --tts fish
    # 비용 없이 흐름만: 규칙 대본 + 가짜 음성(신호음)
    PYTHONPATH=backend python -m pipelines.studio_audio.run --email ... --llm none --tts fake
    # 이미 만든 대본(script.json)으로 음성만 다시
    PYTHONPATH=backend python -m pipelines.studio_audio.run --email ... --script results/studio_audio/run_<시각>/script.json --tts fish

# 만들기 시트에 보일 값 (종목별 새 업데이트 수 [전날, 최근 3일, 최근 7일] · 직전 거래일)
    PYTHONPATH=backend python -m pipelines.studio_audio.run --email ... --options

고르기 (프론트 시트와 같다): --symbols 000660,005930 | --group 보유|관심 (기본: 내 종목 전체),
          --period 전날|"최근 3일"|"최근 7일" (기본 최근 7일, 끝은 어제) 또는 --end YYYY-MM-DD --days N, --no-market(증시 요약 끄기)
          업데이트 0건이어도 증시 요약을 켜면 만든다. 둘 다 없으면 만들지 않는다.
그 밖: --test-db(TEST_DATABASE_URL에서 읽기)
환경변수: OPENAI_API_KEY(또는 LLM_API_KEY), STUDIO_AUDIO_MODEL(없으면 LLM_MODEL), FISH_API_KEY, FISH_VOICE_A, FISH_VOICE_B,
          FISH_TTS_MODEL(없으면 configs/studio_audio.yaml tts.model)

결과 폴더: brief.txt(LLM에 준 입력) · brief.json · script.json(대본) · meta.json(시도·검사 오류·토큰) · lines.json(줄마다 화면·읽기 문장)
          · script.md(사람이 읽는 대본) · episode.json(화면 결과 = studio_items.content 모양) · episode.mp3/wav · player.html · summary.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

SEOUL = ZoneInfo("Asia/Seoul")


def _dump(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def script_md(content: dict, lines: list[dict]) -> str:
    out = [f"# {content['title']}", "", f"- 기간 {content['period']['start']} ~ {content['period']['end']} · 길이 "
           f"{content['dur'] // 60}:{content['dur'] % 60:02d} · 대본 {content['source']} · {content['prompt_version']}", ""]
    chapters = {t: name for t, name in content["chapters"]}
    for (t, sp, text), ln in zip(content["script"], lines):
        if t in chapters:
            out += ["", f"## {chapters.pop(t)} ({t // 60}:{t % 60:02d})"]
        refs = f"  `{', '.join(ln['refs'])}`" if ln["refs"] else ""
        out.append(f"- **{sp}** {text}{refs}")
        if ln["speech"] != text:
            out.append(f"  - 읽기: {ln['speech']}")
    out += ["", "## 출처"] + [f"- [{s['kind']}] {s['text']} {('· ' + s['memo']) if s['memo'] else ''}" for s in content["sources"]]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="AI 오디오 한 편 (시험용)")
    who = ap.add_mutually_exclusive_group(required=True)
    who.add_argument("--email")
    who.add_argument("--user-id", type=int)
    ap.add_argument("--period", choices=["전날", "최근 3일", "최근 7일"], help="시트의 기간 (끝은 어제). --end·--days보다 우선")
    ap.add_argument("--end", help="기간 마지막 날 (자료 날짜 기준, 기본: 어제)")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--symbols", help="이 종목만 (쉼표 구분). 기본: 사용자 보드 전체")
    ap.add_argument("--group", choices=["보유", "관심"], help="보유 종목 전체 | 관심 종목 전체")
    ap.add_argument("--no-market", action="store_true", help="직전 거래일 증시 요약을 넣지 않는다")
    ap.add_argument("--options", action="store_true", help="만들기 시트 값(종목별 기간별 새 업데이트 수)만 보여 준다")
    ap.add_argument("--llm", choices=["openai", "none"], default="openai", help="none: LLM 없이 규칙 대본")
    ap.add_argument("--tts", choices=["fish", "fake", "none"], default="none", help="none: 대본만 / fake: 신호음")
    ap.add_argument("--script", help="이 script.json을 그대로 쓴다 (LLM을 부르지 않음)")
    ap.add_argument("--test-db", action="store_true", help="TEST_DATABASE_URL에서 읽는다 (기본: READONLY_DATABASE_URL·DATABASE_URL)")
    ap.add_argument("--out-dir", help="결과 폴더 (기본: results/studio_audio)")
    args = ap.parse_args(argv)

    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    from app.studio_audio.collect import PERIODS, audio_options, collect_brief, period_range
    from app.studio_audio.episode import (NoUpdatesError, estimate_starts, flatten, lines_dict, text_hash, to_content,
                                          write_script)
    from app.studio_audio.llm import model_name, openai_call
    from app.studio_audio.prompt import build_user, config, target_chars
    from app.studio_audio.schema import check

    from ..common.config import REPO_ROOT, resolve_path
    from ..common.db import load_env, read_database_url
    from .player import render
    from .seed_week import sa_url

    load_env()
    cfg = config()
    now = datetime.now(SEOUL)
    if args.period:
        start, end = period_range(args.period, now)
    else:
        end = date.fromisoformat(args.end) if args.end else now.date() - timedelta(days=1)
        start = end - timedelta(days=args.days - 1)
    period_label = args.period or next((k for k, v in PERIODS.items() if v == args.days), f"{args.days}일")
    url = os.environ.get("TEST_DATABASE_URL", "") if args.test_db else read_database_url()
    if not url:
        raise SystemExit("TEST_DATABASE_URL이 없습니다")
    if args.options:
        engine = create_engine(sa_url(url), pool_pre_ping=True)
        with Session(engine) as db:
            db.execute(text("SET TRANSACTION READ ONLY"))
            uid = args.user_id or db.execute(text("SELECT id FROM users WHERE email = :e"), {"e": args.email}).scalar()
            if uid is None:
                raise SystemExit(f"사용자를 찾지 못했어요: {args.email}")
            opts = audio_options(db, int(uid), now)
            db.rollback()
        engine.dispose()
        print(json.dumps(opts, ensure_ascii=False, indent=1))
        return 0
    out = (Path(args.out_dir) if args.out_dir else REPO_ROOT / "results/studio_audio") / f"run_{now:%Y%m%d_%H%M%S}"
    out.mkdir(parents=True)

    # TTS 준비를 먼저 확인한다 (LLM 비용을 쓰고 나서 키가 없어 멈추지 않게)
    synth = None
    if args.tts == "fish":
        from app.studio_audio.tts import FishTTS
        synth = FishTTS(cfg["tts"], resolve_path("results/studio_audio/tts_cache"))
        problems = synth.check_ready()
        if problems:
            raise SystemExit("Fish Audio 준비가 안 됐어요: " + " / ".join(problems)
                             + "\n목소리 찾기: PYTHONPATH=backend python -m pipelines.studio_audio.voices --language ko")
    elif args.tts == "fake":
        from app.studio_audio.tts import FakeTTS
        synth = FakeTTS()

    engine = create_engine(sa_url(url), pool_pre_ping=True)
    with Session(engine) as db:
        db.execute(text("SET TRANSACTION READ ONLY"))
        uid = args.user_id or db.execute(text("SELECT id FROM users WHERE email = :e"), {"e": args.email}).scalar()
        if uid is None:
            raise SystemExit(f"사용자를 찾지 못했어요: {args.email}")
        symbols = [s.strip() for s in args.symbols.split(",")] if args.symbols else None
        if args.group:
            group = [o["stock_code"] for o in audio_options(db, int(uid), now)["stocks"] if o["hold"] == args.group]
            symbols = [c for c in (symbols or group) if c in group]
        if symbols is not None and not symbols:
            raise SystemExit("고른 종목이 없어요")
        brief = collect_brief(db, int(uid), start, end, symbols, max_cards_per_stock=cfg["brief"]["max_cards_per_stock"],
                              max_memos_per_stock=cfg["brief"]["max_memos_per_stock"], now=now,
                              include_market=not args.no_market)
        db.rollback()
    engine.dispose()
    if not brief.stocks:
        raise SystemExit("고른 종목이 내 종목 보드에 없어요")
    _dump(out / "brief.json", brief.to_dict())
    (out / "brief.txt").write_text(build_user(brief, cfg) + "\n", encoding="utf-8")
    n_cards = sum(len(s.cards) for s in brief.stocks)
    print(f"[1] 사용자 {uid} · 기간 {start} ~ {end} · 종목 {len(brief.stocks)}개 · 카드 {n_cards}장 "
          f"({', '.join(f'{s.name} {len(s.cards)}' for s in brief.stocks)}) · 증시 {len(brief.market)}줄 → {out / 'brief.txt'}")

    if args.script:
        script = json.loads(Path(args.script).read_text(encoding="utf-8"))
        meta = {"source": "file", "prompt": "-", "tries": 0, "errors": [], "usage": [], "checks": check(script, brief, cfg)}
    else:
        llm = (lambda msgs: openai_call(msgs, cfg)) if args.llm == "openai" else None
        try:
            script, meta = write_script(brief, llm, cfg)
        except NoUpdatesError as exc:
            print(f"오디오를 만들지 않았어요: {exc}")
            _dump(out / "summary.json", {"status": "no_updates", "user_id": uid, "start": str(start), "end": str(end)})
            return 0
        meta["model"] = model_name(cfg) if llm else None
    _dump(out / "script.json", script)
    _dump(out / "meta.json", meta)
    lines = flatten(script, cfg)
    chars = sum(len(ln.text) for ln in lines)
    print(f"[2] 대본 {meta['source']} · 시도 {meta['tries']} · {len(lines)}줄 · {chars}자 (목표 약 {target_chars(brief, cfg)}자)"
          + (f" · 검사 오류 {len(meta['errors'])}건 (meta.json)" if meta["errors"] else ""))
    for e in meta["errors"]:
        print(f"    {e[:300]}")

    audio_file, tts_info = None, {"provider": args.tts}
    if synth is not None:
        from app.studio_audio.tts import synthesize
        res = synthesize(lines, synth, cfg["tts"], out,
                         progress=lambda i, n: print(f"\r[3] 음성 합성 {i}/{n}", end="", flush=True))
        print()
        starts, duration = res["starts"], res["duration"]
        audio_file = Path(res["path"]).name
        voices = {sp: synth.voice(sp) for sp in ("A", "B")}
        tts_info = {"provider": synth.provider, "model": synth.model, "voices": voices, "path": res["path"], "mime": res["mime"],
                    "bytes": res["bytes"], "duration_sec": duration, "calls": synth.calls,
                    "text_hash": text_hash(lines, voices, synth.model), "speech_chars": sum(len(ln.speech) for ln in lines),
                    "speech_bytes": sum(len(ln.speech.encode('utf-8')) for ln in lines)}
        print(f"[3] {synth.provider} {synth.model} · 새 합성 {synth.calls['api']}줄 · 캐시 {synth.calls['cached']}줄 · "
              f"{duration:.1f}초 → {res['path']}")
    else:
        starts, duration = estimate_starts(lines, cfg)
        print(f"[3] 음성 없음 · 길이 어림 {duration:.0f}초")
    content = to_content(brief, script, lines, starts, duration, meta, cfg)
    content["audio"] = tts_info
    content["options"] = {"codes": [s.code for s in brief.stocks], "period": period_label, "market": not args.no_market}
    content["meta"] = f"오디오 · {len(brief.stocks)}종목 · {period_label} · {content['dur'] // 60}:{content['dur'] % 60:02d}"
    _dump(out / "episode.json", content)
    _dump(out / "lines.json", lines_dict(lines))
    (out / "script.md").write_text(script_md(content, lines_dict(lines)), encoding="utf-8")
    (out / "player.html").write_text(render(content, lines_dict(lines), audio_file), encoding="utf-8")
    summary = {"status": "ready", "user_id": uid, "start": str(start), "end": str(end), "stocks": len(brief.stocks), "cards": n_cards,
               "script_source": meta["source"], "tries": meta["tries"], "llm_usage": meta.get("usage"), "lines": len(lines),
               "chars": chars, "target_chars": target_chars(brief, cfg), "duration_sec": round(duration, 1), "tts": tts_info}
    _dump(out / "summary.json", summary)
    print(f"[4] 미리듣기: {out / 'player.html'} · 대본: {out / 'script.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
