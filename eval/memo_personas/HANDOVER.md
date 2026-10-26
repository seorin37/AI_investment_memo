# 메모 1,000개 만들기 — 서린 실행 안내

상규가 3일 동안 자리를 비우는 사이에, 팀 DB가 있는 서린 PC에서 **명령어만 순서대로 실행해** 평가용 메모 1,000개를 만드는 방법입니다.
코드를 몰라도 됩니다. 화면에 ✅가 나오면 다음으로, ❌가 나오면 바로 아래 ↳ 안내대로 고친 뒤 같은 명령을 다시 실행하면 됩니다.

## 전체 순서 한눈에

| 순서 | 명령 | 걸리는 시간(예상) |
|---|---|---|
| 0 | 준비 (브랜치 받기, `.env` 3줄) | 10분 |
| 1 | `python -m eval.memo_personas.preflight` | 1분 |
| 2 | `python -m eval.memo_personas.export_evidence` | 1분 |
| 3 | `python -m eval.memo_personas.generate_memos --pilot` → `python -m eval.memo_personas.report` | 5~15분 |
| 4 | **summary.txt를 상규에게 카톡으로 보내고 OK 받기** | 상규 답장까지 |
| 5 | `python -m eval.memo_personas.generate_memos --all` → `python -m eval.memo_personas.report` | 1~2시간 (한도에 걸리면 다음 날 이어서) |
| 6 | 결과 폴더 두 개를 압축해서 상규에게 전달 | 5분 |

모든 명령은 **WSL2 터미널(Ubuntu)에서, 레포 맨 위 폴더(AI_investment_memo)에서** 실행합니다.

---

## 0. 준비 (처음 한 번)

### 0-1. 브랜치 받기와 환경 켜기
상규가 `feature/sanggue-next` 브랜치를 push했다고 알려 준 뒤에 합니다.

```bash
cd ~/AI_investment_memo        # 레포가 다른 곳에 있으면 그 경로
git fetch origin
git checkout feature/sanggue-next
git pull
conda activate ai_memo
```

`git status`에서 "Your branch is up to date"가 보이면 됩니다.

### 0-2. `.env`에 3줄 넣기
레포 맨 위 폴더의 `.env` 파일을 엽니다(없으면 `cp .env.example .env`로 먼저 만듭니다). 아래 3줄이 있어야 합니다. 이미 있는 줄은 그대로 두세요.

```
LLM_API_KEY=여기에_Gemini_API_키
LLM_MODEL=여기에_모델_이름
DATABASE_URL=postgresql+psycopg://사용자:비밀번호@localhost:포트/DB이름
```

- `LLM_API_KEY`, `LLM_MODEL`: 상규가 카톡으로 따로 알려 줍니다. 따옴표나 앞뒤 공백 없이 붙여 넣습니다.
- `DATABASE_URL`: 같은 `.env`의 `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_PORT`, `POSTGRES_DB` 값을 그대로 넣으면 됩니다.
- `.env`는 비밀번호가 들어 있으니 카톡·깃에 올리지 않습니다. 이 도구는 값을 화면에 절대 출력하지 않습니다.

### 0-3. (필요할 때만) 패키지 설치
1단계 preflight가 "필요한 패키지 ❌"라고 할 때만 실행합니다.

```bash
pip install -r eval/memo_personas/requirements.txt
```

### 0-4. 팀 DB 켜져 있는지
```bash
docker compose ps
```
`memos-db`가 `running`(또는 `Up`)이면 됩니다. 꺼져 있으면 `docker compose up -d`. **DB 볼륨을 지우거나 초기화하는 명령은 절대 실행하지 않습니다.**

---

## 1. 사전 점검 — preflight

```bash
python -m eval.memo_personas.preflight
```

정상이면 이렇게 끝납니다 (숫자·날짜는 실제 DB에 따라 다름):

```
✅ Python 버전 — 3.11.x
✅ 필요한 패키지 — requests, sqlalchemy, psycopg[binary], PyYAML, python-dotenv
✅ 페르소나 검증 — 100명 · 1,000슬롯 · 기업별 250
✅ .env LLM_API_KEY — 있음 (값은 표시하지 않음)
✅ .env LLM_MODEL — 있음 (값은 표시하지 않음)
✅ .env DATABASE_URL — 있음 (값은 표시하지 않음)
✅ DB 연결 — PostgreSQL 16.x, 읽기 전용으로 접속
✅ 필요한 테이블·컬럼 — 10개 테이블 확인
✅ 데이터 삼성전자(005930) — 주가 …건(…~…) · 공시 …건 · 공시 청크 …건 · 뉴스 …건 · 재무 …건
   (SK하이닉스·NAVER·KB금융·거시도 같은 형식)
✅ Gemini 테스트 호출 — 모델 … · 토큰 입력 … / 출력 … / thinking …

✅ 모두 준비됐습니다.
다음 명령: python -m eval.memo_personas.export_evidence
```

- ⚠️(노란 경고)는 진행해도 됩니다. 예: 어떤 기업의 뉴스가 0건이면 메모 생성 때 다른 근거로 자동 조정됩니다.
- ❌가 있으면 맨 아래 'preflight ❌ 해결표'를 보고 고친 뒤 같은 명령을 다시 실행합니다.
- Gemini 테스트 호출은 하루 한도에서 1회를 씁니다.

## 2. 근거 자료 내보내기 — export_evidence

```bash
python -m eval.memo_personas.export_evidence
```

DB를 **읽기만** 합니다(쓰기·삭제 없음). 정상 예시:

```
✅ 삼성전자 (005930) — 기준일 2026-10-.. · 공시 8건, 뉴스 15건, 주가·거래 6건, 재무 6건
✅ SK하이닉스 (000660) — …
✅ NAVER (035420) — …
✅ KB금융 (105560) — …
✅ 거시 — 5개 지표 (기준 2026-10-..)

저장 완료 → data/evidence_packs/ (기업 4개 JSON, macro.json, coverage.md)
다음 단계: python -m eval.memo_personas.generate_memos --pilot
```

⚠️ 줄이 나오면 그대로 진행합니다(근거가 모자란 유형은 자동으로 다른 유형으로 옮겨집니다). 
**이 단계는 파일럿 전에 한 번만** 실행합니다. 파일럿 뒤에 다시 실행하면 근거가 바뀌어 4단계에서 멈춥니다(아래 문제 해결표 참고).

## 3. 파일럿 10명(100개) — generate_memos --pilot, report

```bash
python -m eval.memo_personas.generate_memos --pilot
```

정상 예시:

```
✅ 슬롯 설계 저장 — 1000슬롯 · 추적형 850 · 폴백·혼합 150 · 복합 33% · 자료 부족 10%
파일럿 10명 중 완료 0명 · 이번에 할 사람 10명 · 모델 …
✅ [1/10] P040 — 완료 · 시도 1회 · 토큰 … · 25초
…
✅ [10/10] P082 — 완료 · 시도 1회 · 토큰 … · 31초

파일럿: 완료 10/10명, 실패 0명 · 전체 누적 100개 메모 → …/results/memo_personas/memos/memos.jsonl
다음 단계: python -m eval.memo_personas.report → summary.txt를 상규에게 카톡으로 보내고 확인받은 뒤 --all 실행
```

- `↻ … 다시 생성` 줄은 자동 검사에 걸려 그 사람만 다시 만드는 중이라는 뜻입니다. 기다리면 됩니다.
- `⏳ … 429 … 기다렸다 다시 시도`는 분당 한도에 걸려 잠깐 쉬는 중입니다. 기다리면 됩니다.

이어서 보고서를 만듭니다.

```bash
python -m eval.memo_personas.report
```

화면에 20줄 요약이 나오고 `results/memo_personas/memos/summary.txt`에 저장됩니다.

## 4. 상규에게 확인받기 (꼭!)

`results/memo_personas/memos/summary.txt` 내용을 **그대로 복사해서 상규에게 카톡**으로 보냅니다.
여유가 되면 같은 폴더의 `review.md`도 파일로 보내 주세요.
**상규가 "OK, --all 돌려도 돼"라고 답하기 전에는 5단계를 실행하지 않습니다.** 고칠 점이 있으면 상규가 방법을 알려 줍니다.

## 5. 나머지 90명 — generate_memos --all, report

```bash
python -m eval.memo_personas.generate_memos --all
```

- 파일럿에서 끝난 10명은 건너뛰고 나머지를 만듭니다. 기본 설정은 분당 5회라 **1~2시간** 걸립니다. 터미널을 켜 둔 채 기다리면 됩니다.
- 끝나면 `전체: 완료 100/100명, 실패 0명`이 보입니다. 실패한 사람이 있으면 **같은 명령을 한 번 더** 실행하면 실패한 사람만 다시 시도합니다.

끝나면 보고서를 다시 만듭니다.

```bash
python -m eval.memo_personas.report
```

## 6. 결과 파일 위치와 전달

| 폴더 | 내용 |
|---|---|
| `results/memo_personas/memos/` | `memos.jsonl`(메모 1,000개), `review.md`, `summary.txt`, `failed.jsonl`, `usage.jsonl`(토큰), `slot_design.json`, `persons/`(사람별 저장본) |
| `data/evidence_packs/` | 근거 자료 (`005930.json` 등 기업 4개, `macro.json`, `coverage.md`) |

두 폴더를 압축해서 상규에게 보내 주세요(카톡 파일 전송 또는 팀 드라이브). 레포 맨 위 폴더에서:

```bash
python -m zipfile -c memos_result.zip results/memo_personas/memos data/evidence_packs
```

만들어진 `memos_result.zip`을 보내면 됩니다.

git commit·push는 하지 않아도 됩니다. 상규가 돌아와서 확인한 뒤 커밋합니다.

---

## 중단되거나 오류가 났을 때

| 화면에 나온 말 | 뜻 | 할 일 |
|---|---|---|
| `⚠️ 중간에 멈췄습니다` (Ctrl+C, 창 닫힘, PC 꺼짐 포함) | 그 사람까지만 저장됨 | **같은 명령을 다시 실행**. 완료한 사람은 건너뜁니다 |
| `⚠️ … 일일 … 한도 …` / `내일 같은 명령을 다시 실행하세요` | 오늘 쓸 수 있는 Gemini 요청을 다 씀 | **내일 같은 명령을 다시 실행** |
| `⚠️ … 여러 번 기다려도 풀리지 않았습니다` | 분당 한도(429)가 계속 걸림 | 10분쯤 뒤 같은 명령 다시 실행 |
| `❌ Gemini 인증 실패 (HTTP 401/403)` | API 키가 틀림 | `.env`의 `LLM_API_KEY` 다시 확인(상규에게 다시 받기) |
| `❌ Gemini 모델을 찾을 수 없음 (HTTP 404)` | 모델 이름이 틀림 | `.env`의 `LLM_MODEL` 오타·공백 확인 |
| `↻ … 응답이 중간에 끊김 (finishReason=MAX_TOKENS)`가 반복 | 응답이 너무 길어 잘림 | `eval/memo_personas/config.yaml`의 `max_output_tokens: 16384`를 `32768`로 바꾸고 다시 실행 |
| `❌ 처음 생성할 때와 입력이 달라졌습니다` | 파일럿 뒤에 export_evidence를 다시 돌렸거나 설정이 바뀜 | 상규에게 화면을 보내 주세요. 급하면 안내대로 `results/memo_personas/memos` 폴더 이름을 `memos_old`로 바꾸고 3단계부터 다시 |
| `❌ 근거 자료가 없습니다` | 2단계를 아직 안 함 | `python -m eval.memo_personas.export_evidence` |
| `실패 N명 … failed.jsonl` | 자동 검사를 3번 다 통과 못한 사람 | 같은 명령을 한 번 더 실행. 그래도 남으면 `failed.jsonl`을 상규에게 전달 |
| 그 밖의 빨간 오류(Traceback) | 예상하지 못한 오류 | 화면 전체를 캡처해서 상규에게 보내 주세요 |

## preflight ❌ 해결표

| ❌ 항목 | 흔한 원인 | 해결 |
|---|---|---|
| Python 버전 | conda 환경이 안 켜짐 | `conda activate ai_memo` 후 다시 실행 |
| 필요한 패키지 | 환경에 일부 패키지가 없음 | `pip install -r eval/memo_personas/requirements.txt` |
| 페르소나 파일 / 페르소나 검증 | 브랜치를 못 받았거나 파일이 바뀜 | `git checkout feature/sanggue-next && git pull`, 그래도 안 되면 `git checkout -- results/memo_personas/personas_100` |
| .env 파일 | `.env`가 없음 | `cp .env.example .env` 후 0-2의 3줄 채우기 |
| .env LLM_API_KEY / LLM_MODEL / DATABASE_URL | 그 줄이 없거나 비어 있음 | 0-2 참고. `키=값` 형식, 따옴표·공백 없이 |
| DB 연결 | DB가 꺼짐, 포트·비밀번호·DB 이름 틀림 | `docker compose ps`로 memos-db 확인, 꺼져 있으면 `docker compose up -d`. 안내에 나온 대로 `DATABASE_URL`의 해당 부분 확인 |
| 필요한 테이블·컬럼 | 팀 DB에 최신 마이그레이션이 안 됨 | DB 담당자에게 `alembic current` 확인 요청 (직접 `alembic upgrade`는 담당자와 상의 후) |
| 데이터 ○○ (주가 0건) | 그 기업 주가가 DB에 없음 | 진행 불가. 화면을 상규에게 보내 주세요 |
| Gemini 테스트 호출 | 키·모델 이름·한도 | ↳ 안내대로. 429면 1~2분 뒤 다시, 일일 한도면 내일 |

## 하지 말아야 할 것
- `config.yaml`의 `mock: false`를 `true`로 바꾸지 않습니다(테스트용 가짜 응답이 됩니다).
- `results/memo_personas/memos/` 안의 파일을 직접 고치거나 지우지 않습니다(이어서 하기에 필요합니다).
- `.env` 내용을 카톡·깃에 올리지 않습니다.
- DB를 지우거나 초기화하는 명령(`docker compose down -v` 등)을 실행하지 않습니다.
