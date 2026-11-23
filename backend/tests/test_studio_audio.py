"""AI 오디오: 읽기 문장 변환 · 대본 검사 · 재시도/대체 · TTS 조립 · 화면 결과 모양 (DB·LLM·Fish Audio 없이)."""
from __future__ import annotations

import copy
import io
import json
import struct
import wave
from datetime import date, datetime, time
from pathlib import Path

import pytest

from app.studio_audio.collect import card_window, day_label, period_range
from app.studio_audio.episode import NoUpdatesError, estimate_starts, flatten, text_hash, to_content, write_script
from app.studio_audio.fallback import fallback, josa
from app.studio_audio.prompt import FEWSHOT_ANSWER, FEWSHOT_BRIEF, build_user, config, messages, target_chars
from app.studio_audio.schema import AUDIO_SCHEMA, banned_hits, check
from app.studio_audio.speech import native, sino, to_speech
from app.studio_audio.tts import FakeTTS, FishTTS, TTSError, read_wav, synthesize
from pipelines.studio_audio.player import render
from pipelines.studio_audio.seed_week import SEOUL, card_time, memo_time, pg_dsn, sa_url

BRIEF = FEWSHOT_BRIEF
GOOD = FEWSHOT_ANSWER


def answer(**changes):
    a = copy.deepcopy(GOOD)
    for path, value in changes.items():
        seg, line, key = path.split("_")
        a["segments"][int(seg)]["lines"][int(line)][key] = value
    return a


# ───────── 읽기 문장
@pytest.mark.parametrize("n, want", [(0, "영"), (10, "십"), (11, "십일"), (180500, "십팔만 오백"), (10000, "만"),
                                     (100000000, "일억"), (2026, "이천이십육"), (1450, "천사백오십")])
def test_sino(n, want):
    assert sino(n) == want


def test_native():
    assert [native(n) for n in (1, 2, 3, 4, 20, 21, 35, 100)] == ["한", "두", "세", "네", "스무", "스물한", "서른다섯", "백"]


@pytest.mark.parametrize("text, want", [
    ("11월 18일 종가는 180,500원이었어요.", "십일월 십팔일 종가는 십팔만 오백 원이었어요."),
    ("전 거래일보다 +1.20% 올랐어요.", "전 거래일보다 플러스 일 점 이 퍼센트 올랐어요."),
    ("금액은 1조 2,000억 원이에요.", "금액은 일조 이천억 원이에요."),
    ("내 종목 4곳, 새 소식 3건이에요.", "내 종목 네 곳, 새 소식 세 건이에요."),
    ("6월 10일과 10월 1일", "유월 십일과 시월 일일"),
    ("3개월 동안 2배로", "삼 개월 동안 두 배로"),
    ("11.03~11.07", "십일월 삼일부터 십일월 칠일"),
    ("-3.1%p", "마이너스 삼 점 일 퍼센트포인트"),
    ("원/달러 1,450원대", "원 달러 천사백오십 원대"),
    # 숫자 뒤 조사는 읽는 소리에 맞춘다 (끝 0을 빼면 받침이 바뀐다)
    ("코스피는 2,510.40으로 마감했어요.", "코스피는 이천오백십 점 사로 마감했어요."),
    ("2,517로 마감", "이천오백십칠로 마감"),
    ("1.50은 2.0과 같아요", "일 점 오는 이와 같아요"),
    ("3을 더해요", "삼을 더해요"),
    ("180,500원이었어요", "십팔만 오백 원이었어요"),
    ("2로봇", "이로봇"),
])
def test_to_speech(text, want):
    assert to_speech(text) == want


def test_pronounce_words_before_numbers():
    words = config()["pronounce"]
    assert to_speech("SK하이닉스 HBM4 DART 공시", words) == "에스케이하이닉스 에이치비엠 포 다트 공시"
    assert not any(ch.isdigit() for ch in to_speech("코스피 2,650.35, 1,000원, 3분기 1위, 2026-11-18", words))


# ───────── 프롬프트·형식
def test_schema_is_strict_and_prompt_has_rules():
    s = AUDIO_SCHEMA["schema"]
    assert AUDIO_SCHEMA["strict"] and s["additionalProperties"] is False
    assert set(s["properties"]["segments"]["items"]["properties"]["kind"]["enum"]) == {"opening", "market", "stock", "no_news", "closing"}
    msgs = messages(BRIEF, fix=["숫자가 틀렸어요"])
    assert msgs[0]["role"] == "system" and "쓰면 안 되는 말" in msgs[0]["content"] and "refs" in msgs[0]["content"]
    assert msgs[-1]["content"].endswith("- 숫자가 틀렸어요")
    user = build_user(BRIEF)
    assert "[증시]" in user and "U1" in user and "[새 업데이트] 없음" in user and "길이 목표" in user


def test_target_chars_grows_with_cards():
    small = copy.deepcopy(BRIEF)
    small.stocks[0].cards = small.stocks[0].cards[:1]
    assert target_chars(BRIEF) > target_chars(small) > 0


# ───────── 검사
def test_fewshot_and_fallback_pass_checks():
    assert check(GOOD, BRIEF) == []
    assert check(fallback(BRIEF), BRIEF) == []


def test_check_finds_banned_and_forecast():
    errors = check(answer(**{"2_1_text": "1월 7일 공시는 호재예요. 금액은 3,200억 원이에요."}), BRIEF)
    assert any("호재" in e for e in errors)
    errors = check(answer(**{"2_5_text": "주가가 더 오를 것으로 보여요."}), BRIEF)
    assert any("전망·예측" in e or "주가 방향" in e for e in errors)


def test_attributed_forecast_and_buyback_fact_are_allowed():
    assert banned_hits("예시증권은 배당금이 500원으로 늘 수 있다고 전망했다고 보도했어요.") == []
    assert banned_hits("회사가 자기주식을 매수하기로 했어요.") == []
    assert banned_hits("지금 매수하세요.") != []


def test_check_wants_haeyo_style():
    errors = check(answer(**{"2_5_text": "1월 9일 예시경제 기사입니다. 예시증권은 주당 배당금이 500원으로 늘 수 있다고 전망했습니다."}), BRIEF)
    assert any("해요체" in e for e in errors)


def test_sample_brief_rules_script_passes():
    from pipelines.studio_audio.smoke import sample_brief
    b = sample_brief()
    assert [c.uid for s in b.stocks for c in s.cards] == ["U1", "U2", "U3"]
    assert check(fallback(b), b) == []


def test_check_finds_unknown_number():
    errors = check(answer(**{"2_1_text": "1월 7일 DART에 공시가 올라왔어요. 금액은 4,100억 원이에요."}), BRIEF)
    assert any("입력에 없는 숫자" in e and "4.1e+11" in e for e in errors)


def test_rounded_percent_is_allowed():
    a = answer(**{"1_0_text": "1월 9일 코스피는 2,510.4로 마감했어요. 기간 첫 거래일보다 1.6% 높아요."})
    assert check(a, BRIEF) == []


def test_check_structure_errors():
    a = copy.deepcopy(GOOD)
    a["segments"] = [g for g in a["segments"] if g["kind"] != "no_news"]
    assert any("no_news" in e for e in check(a, BRIEF))
    a = copy.deepcopy(GOOD)
    for line in a["segments"][2]["lines"]:
        line["refs"] = [r for r in line["refs"] if r != "U2"]
    assert any("U2" in e for e in check(a, BRIEF))
    a = answer(**{"4_1_text": "다음 방송에서 만나요."})
    assert any("판단" in e for e in check(a, BRIEF))
    a = copy.deepcopy(GOOD)
    for line in a["segments"][2]["lines"]:
        line["speaker"] = "B"
    assert any("이어서 말해요" in e for e in check(a, BRIEF))
    a = copy.deepcopy(GOOD)
    a["segments"][2]["lines"][1]["refs"] = ["U9"]
    assert any("참조" in e for e in check(a, BRIEF))


# ───────── 재시도·대체
def fake_llm(*answers):
    calls = []

    def llm(msgs):
        calls.append(msgs)
        a = answers[min(len(calls), len(answers)) - 1]
        if isinstance(a, Exception):
            raise a
        return {**json.loads(json.dumps(a)), "_usage": {"input": 10, "output": 5}}
    llm.calls = calls
    return llm


def test_retry_with_fix_then_llm():
    bad = answer(**{"2_1_text": "1월 7일 공시는 호재예요. 금액은 3,200억 원이에요."})
    llm = fake_llm(bad, GOOD)
    script, meta = write_script(BRIEF, llm)
    assert meta["source"] == "llm" and meta["tries"] == 2 and len(llm.calls) == 2
    assert "호재" in llm.calls[1][-1]["content"] and meta["usage"][0]["input"] == 10
    assert script["segments"][0]["kind"] == "opening"


def test_two_failures_use_rules_script():
    bad = answer(**{"2_1_text": "1월 7일 공시는 호재예요."})
    script, meta = write_script(BRIEF, fake_llm(bad, RuntimeError("timeout")))
    assert meta["source"] == "rules" and len(meta["errors"]) == 2 and check(script, BRIEF) == []


def test_no_llm_uses_rules():
    _, meta = write_script(BRIEF, None)
    assert meta["source"] == "rules" and meta["tries"] == 0


def test_josa():
    assert josa("삼성전자", "은/는") == "삼성전자는" and josa("KB금융", "은/는") == "KB금융은" and josa("NAVER", "은/는") == "NAVER는"


# ───────── 화면 결과 모양 (frontend Studio.mock.ts mockAudioEpisode)
def test_content_shape_matches_frontend_mock():
    lines = flatten(GOOD)
    starts, dur = estimate_starts(lines)
    c = to_content(BRIEF, GOOD, lines, starts, dur, {"source": "llm", "prompt": "audio-v1"})
    for key in ("hosts", "dur", "chapters", "script", "sources", "market_source", "memo_link"):
        assert key in c
    assert c["hosts"] == ["진행자 A · 메인", "진행자 B · 해설"]
    assert [name for _, name in c["chapters"]] == ["오프닝", "1월 9일 증시 요약", "예시전자", "예시금융 · 새 소식 없음", "마무리"]
    assert all(len(row) == 3 and row[1] in ("A", "B") for row in c["script"])
    assert [s["kind"] for s in c["sources"]] == ["공시", "뉴스"] and c["sources"][0]["seek"] <= c["sources"][1]["seek"]
    assert c["memo_link"]["title"] == "신공장 투자 계속 보기" and c["memo_link"]["count"] == "공시 1건 · 뉴스 1건"
    assert c["market_source"] == "01.09 코스피 종가"
    assert starts == sorted(starts) and c["dur"] == round(dur)


def test_text_hash_changes_with_voice():
    lines = flatten(GOOD)
    assert text_hash(lines, {"A": "a", "B": "b"}, "s2") == text_hash(lines, {"A": "a", "B": "b"}, "s2")
    assert text_hash(lines, {"A": "a", "B": "c"}, "s2") != text_hash(lines, {"A": "a", "B": "b"}, "s2")


def test_player_escapes_script_tags():
    lines = flatten(GOOD)
    starts, dur = estimate_starts(lines)
    c = to_content(BRIEF, GOOD, lines, starts, dur, {"source": "llm"})
    c["title"] = "</script><b>x"
    page = render(c, [{"refs": [], "speech": "</script>"}], None)
    assert "</script><b>" not in page and page.count("</script>") == 1


# ───────── TTS 조립
def _wav(seconds: float, rate: int = 8000, streaming: bool = False) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x01\x00" * int(seconds * rate))
    data = buf.getvalue()
    if streaming:                                            # 스트리밍 응답처럼 data 크기를 최댓값으로
        i = data.find(b"data")
        data = data[:i + 4] + struct.pack("<I", 0xFFFFFFFF) + data[i + 8:]
    return data


def test_read_wav_tolerates_streaming_header():
    assert abs(read_wav(_wav(1.0, streaming=True)).seconds - 1.0) < 1e-6
    with pytest.raises(TTSError):
        read_wav(b"ID3 not a wav")


def test_synthesize_timings(tmp_path):
    lines = flatten(GOOD)
    cfg = {"lead": 0.3, "gap_line": 0.3, "gap_segment": 0.7}
    res = synthesize(lines, FakeTTS(cps=10, rate=8000), cfg, tmp_path)
    starts = res["starts"]
    assert starts[0] == 0.3 and starts == sorted(starts) and len(starts) == len(lines)
    dur = lambda ln: max(0.4, len(ln.speech) / 10)
    line_gap = starts[1] - starts[0] - dur(lines[0])
    assert lines[1].seg == lines[0].seg and abs(line_gap - 0.3) < 0.01       # 같은 구간 안은 0.3초
    k = next(i for i in range(1, len(lines)) if lines[i].seg != lines[i - 1].seg)
    seg_gap = starts[k] - starts[k - 1] - dur(lines[k - 1])
    assert abs(seg_gap - 0.7) < 0.01                         # 구간(오프닝 → 증시)이 바뀌면 0.7초
    with wave.open(res["wav"]) as w:
        assert abs(w.getnframes() / w.getframerate() - res["duration"]) < 0.01


class _Resp:
    def __init__(self, status, content=b"", text=""):
        self.status_code, self.content, self.text = status, content, text


def test_fish_request_cache_and_errors(tmp_path, monkeypatch):
    monkeypatch.delenv("FISH_VOICE_A", raising=False)
    monkeypatch.delenv("FISH_VOICE_B", raising=False)
    monkeypatch.delenv("FISH_TTS_MODEL", raising=False)
    monkeypatch.delenv("FISH_API_KEY", raising=False)       # 다른 테스트가 .env를 읽어 두면 '키 없음' 확인이 실제 키를 집는다
    sent = []

    def post(url, headers, json, timeout):
        sent.append((url, headers, json))
        return _Resp(200, _wav(0.5, streaming=True))
    cfg = {**config()["tts"], "voices": {"A": {"id": "voice-a"}, "B": {"id": "voice-b"}}}
    tts = FishTTS(cfg, tmp_path, api_key="k", post=post)
    assert tts.check_ready() == []
    tts("안녕하세요", "B")
    tts("안녕하세요", "B")
    assert len(sent) == 1 and tts.calls == {"api": 1, "cached": 1, "chars": 5}
    url, headers, body = sent[0]
    assert url.endswith("/v1/tts") and headers["model"] == cfg["model"] and headers["Authorization"] == "Bearer k"
    assert body["reference_id"] == "voice-b" and body["format"] == "wav" and body["prosody"]["speed"] == 1.0

    calls = []

    def denied(url, headers, json, timeout):
        calls.append(1)
        return _Resp(402, text="no credit")
    with pytest.raises(TTSError, match="402"):
        FishTTS(cfg, tmp_path / "x", api_key="k", post=denied)("다른 문장", "A")
    assert len(calls) == 1                                   # 크레딧 부족은 다시 부르지 않는다
    missing = FishTTS({**cfg, "voices": {"A": {"id": "same"}, "B": {"id": "same"}}}, tmp_path, api_key="")
    assert len(missing.check_ready()) == 2


# ───────── 기간·시험 데이터 날짜
def test_card_window_is_next_morning_runs():
    lo, hi = card_window(date(2026, 11, 16), date(2026, 11, 22))
    assert lo.date() == date(2026, 11, 17) and hi.date() == date(2026, 11, 24)
    assert day_label("2026-11-18") == "11월 18일(수)"


def test_seed_card_time():
    start = date(2026, 11, 16)
    now = datetime(2026, 11, 23, 10, 0, tzinfo=SEOUL)
    memo = memo_time(start, 0)
    assert memo == datetime(2026, 11, 16, 21, 0, tzinfo=SEOUL)
    assert card_time(date(2026, 11, 18), memo, now) == datetime(2026, 11, 19, 6, 30, tzinfo=SEOUL)
    assert card_time(date(2026, 11, 10), memo, now) == datetime(2026, 11, 17, 6, 30, tzinfo=SEOUL)   # 메모보다 앞서지 않게
    assert card_time(date(2026, 11, 23), memo, now) == now                                         # 지금보다 늦지 않게
    assert card_time(None, memo_time(start, 3), now).date() == date(2026, 11, 20)


def test_db_url_helpers():
    assert sa_url("postgresql://u@h:5433/x_test") == "postgresql+psycopg://u@h:5433/x_test"
    assert pg_dsn("postgresql+psycopg://u@h:5433/x_test") == "postgresql://u@h:5433/x_test"


# ───────── 고르기 (만들기 시트: 종목 · 기간 · 증시 요약)
def test_period_range_ends_yesterday():
    now = datetime(2026, 11, 23, 10, 0, tzinfo=SEOUL)
    assert period_range("전날", now) == (date(2026, 11, 22), date(2026, 11, 22))
    assert period_range("최근 3일", now) == (date(2026, 11, 20), date(2026, 11, 22))
    assert period_range("최근 7일", now) == (date(2026, 11, 16), date(2026, 11, 22))
    with pytest.raises(ValueError):
        period_range("최근 30일", now)


def test_market_only_episode_when_no_updates():
    quiet = copy.deepcopy(BRIEF)
    for st in quiet.stocks:
        st.cards = []
    script, meta = write_script(quiet, None)                 # 업데이트 0건이어도 증시 요약이 있으면 만든다 (프론트 시트 규칙)
    assert [g["kind"] for g in script["segments"]] == ["opening", "market", "no_news", "closing"]
    assert check(script, quiet) == []
    quiet.market = []
    with pytest.raises(NoUpdatesError):                      # 업데이트 0건 + 증시 요약 끔 → 만들지 않음
        write_script(quiet, None)


def test_market_off_and_single_day():
    b = copy.deepcopy(BRIEF)
    b.market, b.start = [], b.end
    assert "[증시]" not in build_user(b) and "하루" in build_user(b)
    script = fallback(b)
    assert "market" not in [g["kind"] for g in script["segments"]]
    assert script["segments"][0]["lines"][0]["text"].startswith("1월 11일,")
    assert any("market" in e for e in check(GOOD, b))         # 증시를 껐는데 market 구간을 쓰면 걸린다
