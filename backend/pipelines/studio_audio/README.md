# AI 오디오 (내 종목 라디오) 시험 도구 — 2026-11-23

기간 안에 쌓인 **AI 업데이트 카드**를 두 진행자(A 메인 · B 해설)가 주고받는 라디오 대본으로 바꾸고, Fish Audio로 읽힌다.
지금은 시험용 CLI이고, 결과(`episode.json`)는 `studio_items.content`·프론트 `mockAudioEpisode`와 같은 모양이라 그대로 API에 옮길 수 있다.

```
메모 → (매일 실행) 업데이트 카드 ─┐
주가·지수·환율(prices_daily·market_indices·economic_observations) ─┤→ 브리프(collect) → LLM 대본(prompt) → 검사(schema.check)
                                                         │      └ 2번 실패하면 규칙 대본(fallback)
                                                         └→ 읽기 문장(speech: 숫자·날짜 → 한글) → Fish TTS 줄마다 → 이어 붙이기(tts) → episode.mp3
```

## 실행 순서
```bash
# 0) .env: OPENAI_API_KEY, FISH_API_KEY, FISH_VOICE_A, FISH_VOICE_B (선택: STUDIO_AUDIO_MODEL, FISH_TTS_MODEL)
# 1) 목소리 고르기
PYTHONPATH=backend python -m pipelines.studio_audio.voices --language ko
PYTHONPATH=backend python -m pipelines.studio_audio.voices --try <id1> --try <id2>      # results/studio_audio/voice_try/*.wav
# 2) 시험 데이터: 테스트 사용자 · 4종목 · 일주일 메모 7개 · 실제 파이프라인 카드 (공용 DB 자료를 쓰려면 --allow-shared-write)
PYTHONPATH=backend python -m pipelines.studio_audio.seed_week --allow-shared-write
# 3) 대본만 먼저 (TTS 비용 없음) → results/studio_audio/run_*/script.md, player.html
PYTHONPATH=backend python -m pipelines.studio_audio.run --email studio-audio-test@example.invalid --tts none
# 4) 대본이 괜찮으면 같은 대본으로 음성 (LLM 다시 안 부름)
PYTHONPATH=backend python -m pipelines.studio_audio.run --email studio-audio-test@example.invalid \
    --script results/studio_audio/run_<시각>/script.json --tts fish
# 5) 시험 데이터 지우기
PYTHONPATH=backend python -m pipelines.updates.db_cleanup results/studio_audio/seed_<시각> --e2e --execute --allow-shared-write
```
비용 없이 흐름만 볼 때: `run ... --llm none --tts fake` (규칙 대본 + 신호음).

## 대본 틀 (configs/studio_audio_prompt.md)
| 구간 | 줄 | 내용 |
|---|---|---|
| opening | 1~2 | 기간·종목 수·순서 |
| market | 1~2 | [증시]가 있을 때만. 코스피·코스닥·환율 종가와 등락률, 해석 없음 |
| stock × 소식 있는 종목 | 3~7 | A가 메모를 꺼냄 → B가 카드 사실(날짜·출처) → 메모와의 연결 한 줄 → (시세 한 줄) |
| no_news | 1 | 소식 없는 종목을 한 줄로 묶음 |
| closing | 1~2 | 마지막 줄 "판단은 메모와 원문을 직접 보고" |

- 종목 순서: 새 소식 있는 종목(보유 먼저, 카드 많은 순) → 없는 종목. 종목당 카드 최대 4장, 넘으면 "그 밖에 n건".
- 길이: 기본 35초 + 소식 종목 45초 + 추가 카드 15초 + 조용한 종목 6초 (최대 7분). 1분 ≈ 330자.
- 기간: 자료 날짜 기준. 카드 생성 시각이 [start+1일, end+2일)인 카드 (매일 06:30 실행이 전날 자료로 만든 카드).

## 검사 (schema.check) — 걸리면 고칠 점을 붙여 한 번 더, 그래도 안 되면 규칙 대본
- 구조: opening 처음·closing 끝, 소식 종목마다 stock 구간 하나, no_news 유무, 종목 이름 언급
- refs: 그 종목의 U번호만, 모든 카드를 한 번 이상 소개
- 숫자: 줄의 숫자는 그 종목 브리프에 있는 숫자 (소수는 반올림 값 인정) — 카드 숫자 검사(`pipelines.updates.checks`) 재사용
- 금지 표현: `configs/updates.yaml`의 금지 사전·시제 패턴 + 매수·매도 권유, 목표주가, 수혜, 급등락, 장중. 주체를 밝힌 전망 전달("○○은 ~로 전망했다고 보도했어요")은 허용
- 한 줄 90자, 같은 진행자 3줄 연속까지, 전체 글자 수 목표의 0.35~1.6배

## 읽기 문장 (speech.py)
화면 대본은 숫자 그대로, TTS에는 한글로: `180,500원 → 십팔만 오백 원`, `3.1% → 삼 점 일 퍼센트`, `11월 18일 → 십일월 십팔일`,
`4곳 → 네 곳`, `6월 → 유월`. 종목명·약어는 `configs/studio_audio.yaml`의 `pronounce`(예: SK하이닉스 → 에스케이하이닉스)로 바꾼다.
Fish가 이상하게 읽는 말이 있으면 여기에 더한다.

## TTS (tts.py)
- 줄마다 `POST /v1/tts`(헤더 `model`, `reference_id` = 진행자 목소리, wav) → 쉼(줄 0.3초·구간 0.7초)을 넣어 이어 붙임 → ffmpeg가 있으면 mp3.
- 줄마다 부르는 이유: 줄 시작 시각(플레이어 대본 따라가기·챕터)을 정확히 알 수 있고, 실패한 줄만 다시 부른다. 다중 화자 한 번 호출은 시각을 모른다.
- 캐시 `results/studio_audio/tts_cache/` (모델·목소리·문장 해시): 같은 대본을 다시 만들면 Fish 비용이 들지 않는다.

## 결과 폴더 `results/studio_audio/run_<시각>/`
`brief.txt`(LLM 입력) · `script.json` · `meta.json`(시도·검사 오류·토큰·거절된 대본) · `script.md`(화면/읽기 문장) · `episode.json` · `episode.mp3` · `player.html` · `summary.json`

## 본 백엔드로 옮길 때 (아직 안 함)
- `POST /api/v1/studio/audio` {period, symbols} → `studio_items`(kind=audio, status queued→generating→ready) → 백그라운드에서 collect→script→TTS →
  `audio_assets`(storage_path, duration_sec, provider=fish, voice, text_hash) · 크레딧 `audio` 5 (만들어졌을 때만, 소식 0건이면 만들지 않음)
- `GET /api/v1/studio/audio/{id}` → `content`, `GET .../file` → mp3. `user_settings.auto_audio`면 매일 실행 뒤 자동 생성.
