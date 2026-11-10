# AI 업데이트 단계 프로토타입 (`pipelines/updates`)

## 1. 이게 뭐 하는 코드인가
메모에서 폴백(`pipelines/tracking`)이 뽑은 **추적 항목**에 대해, 새 **공시·뉴스·주가**를 찾아 "메모와 왜 연결되는지"를 담은 **업데이트 카드**를 만든다.
메모를 만들거나 고치는 코드가 아니다. 메모 → 추적 항목 추출까지는 폴백이 하고, 이 코드는 그 다음 단계다.

## 2. 파이프라인에서의 위치
```
메모 작성 → [폴백] 추적 항목 추출 → ★이 코드: 후보 찾기 → LLM 카드 → 코드 검사 → 카드 초안★ → (아직 없음) DB 저장 → 화면 표시
```
| 단계 | 모듈 | 하는 일 |
|---|---|---|
| 후보 찾기 | `candidates.py` | 항목 임베딩(BGE-M3)과 가까운 뉴스·공시를 DB에서 SELECT (종목 필터 + 코사인 유사도) |
| 임계값 | `topic.py` | 유사도 `min_similarity` 미만은 버린다. 후보가 없으면 LLM을 부르지 않는다 |
| 근거 준비 | `evidence.py` | 공시 먼저(최대 2), 비슷한 뉴스는 하나로 묶어(최대 3) E1, E2… 번호를 붙인다 |
| LLM 카드 | `judge.py` | 항목 1개당 1회 호출. 시스템 프롬프트 `configs/update_judge_prompt.md`(팀 LLM 프롬프트 지침 v1.0 그대로) + 입력 템플릿. JSON 카드(제목·요약·이유·근거·확신도) |
| 코드 검사 | `checks.py` | 지침 3장: 형식(제목 20자·문장 60자·이유 80자·근거 3개), 출처 번호, 금지 표현(사전 + 시제 패턴, 회사 발언 전달 문장 제외), 숫자 일치, 확신도 0.7(update·answer에만), no_update 상태 검사 |
| 고정 문구 | `fixed.py` | 검사에 걸린 카드를 "새 공시가 올라왔어요" 같은 고정 카드로 대체 (설정으로 `drop` 가능) |
| 가격 | `price.py` | 종가와 조건가를 코드로 비교. 상태가 바뀌어 "가까워짐/도달"이 될 때만 카드 (LLM 없음) |
| 즉시 답변 | `instant.py` | 지침 2장: 규칙으로 분기(투자판단·예측→고정 문구, 현재가→코드 답, 단순 재무→코드 답(DB 조회 미구현)), 공시·뉴스 정리 질문은 `update_instant_prompt.md`로 LLM 답변 + 검사. 저장 위치는 미정 |
| 응답 유형 | `response.py`, `confirm.py`, `item_state.py` | 코드가 6개 유형(update_card·price_card·no_new_info·no_data·needs_confirmation·out_of_scope)을 정한다. 카드 실패는 no_new_info(reason에 이유), 확인 필요는 질문+선택지(52주·20거래일 고점·저점, 최근 종가), 범위 밖 문장은 내부 기록만. 항목 상태(마지막 확인 시각·유형)는 파일 저장소. `responses.jsonl` |
| 쓴 근거 건너뛰기 | `used_refs.py` | 항목별로 카드 문장이 쓴 근거 ref를 기록하고 다음 실행에서 후보에서 뺀다. 저장소 인터페이스 + 파일 구현(DB 테이블 없음). `experiment --used-refs <파일>`로만 켠다 |
| 결과 저장 | `results.py` | 결과를 DB가 아니라 `results/updates/run_<시각>/` 파일로 저장 |
| 임계값 보정 | `calibrate.py`, `autolabel.py`, `noise_floor.py` | 후보 O/X 표시(사람 또는 LLM)로 구간별 정밀도·재현율과 추천 임계값 계산, 다른 종목 자료로 하한선 계산 |
| 실험 | `experiment.py` | 위 전체를 4개 기업(005930·000660·035420·105560)으로 돌려 보고서를 만든다 |

## 3. 왜 이렇게 하나
- 모든 메모를 매일 LLM에 넣지 않는다. 임베딩 검색과 코드로 후보를 먼저 좁히고, 관련성이 있을 때만 LLM을 쓴다 (비용·크레딧).
- 업데이트는 **사실 중심**이다. 근거에 있는 숫자·표현만 쓰고, 매수/매도/예측/호재·악재 같은 표현은 코드가 막는다.
- **근거는 공시 중심 + 관련 뉴스**다. 공시 카드에는 관련 기사가 링크로 덧붙는다(`related_news`, LLM이 문장으로 쓰지 않은 기사, 유사도 `related_news_min_similarity` 이상).
- **주가는 근거로 쓰지 않는다.** 주가는 결과이므로 공시·뉴스 카드에 섞지 않고, 사용자가 정한 가격 조건이 있을 때만 별도 "가격 카드"로 낸다.

## 4. 예상 결과물
`PYTHONPATH=backend python -m pipelines.updates.experiment --llm none|openai` 를 실행하면 `results/updates/run_<시각>/` 에 다음이 생긴다.

| 파일 | 내용 |
|---|---|
| `cards.jsonl` | 카드 초안 한 줄에 한 건. 종류(공시/뉴스/가격), 제목, 요약, 이유, `sources`(근거 ref + 근거 문장), `related_news`, 가격 상태, 기준일, 출처 구분(llm/fixed). 나중에 DB에 넣을 내용과 같은 모양 |
| `report.md` | 항목별 후보 표(유사도·날짜·제목), LLM 카드, 검사 실패 코드, 최종 카드 |
| `candidates.csv` | 후보 전체(임계값 아래 포함) + 비어 있는 `관련(O/X)` 열. 표시해서 `calibrate`에 넣는다 |
| `summary.json` | 항목 수, 유사도 분포, 처리 결과 집계, 검사 실패 코드, LLM 호출·토큰 사용량 |

카드 한 건의 모양 (값은 예시):
```json
{"update_type": "disclosure", "title": "HBM 매출 8.0% 증가",
 "summary": "HBM 매출이 전 분기보다 8.0% 늘었어요.",
 "reason": "메모에 쓰신 'HBM 실적'과 관련된 공시예요",
 "sources": [{"ref": "disc:<접수번호>#0", "quote": "HBM 매출이 전 분기 대비 8.0% 증가했다"}],
 "related_news": [{"ref": "news:123", "title": "SK하이닉스 HBM 출하 확대"}],
 "origin": "llm"}
```
가격 카드는 `update_type: price_condition`, `price_state: near|reached`, `observed_trade_date`, `details`(남은 값·%)이고 `sources`는 비어 있다.

## 5. DB·Alembic·SQL을 건드리지 않는 방식
- DB 접속은 `get_read_dsn()`(`READONLY_DATABASE_URL`, 없으면 `DATABASE_URL`)이고, 연결 후 `conn.read_only = True` 로 읽기 전용 세션을 건다. SELECT만 쓴다.
- `INSERT/UPDATE/DELETE`, `commit`, `get_dsn`/`get_engine`(쓰기용) 호출이 패키지에 없는지 테스트(`ReadOnlyGuardTest`)가 소스를 검사한다.
- `alembic/`, `alembic/sql/`, `db/` 는 한 글자도 수정하지 않았다. 새 테이블·컬럼·마이그레이션도 만들지 않았다.
- 결과 파일은 `results/` 아래에만 쓴다. (`.gitignore`에 `results/`를 추가할지는 팀 결정)
- 외부로 나가는 건 `--llm openai`일 때의 OpenAI API 호출뿐이다 (토큰 비용 발생). `--llm none`은 비용이 없다.

## 6. 아직 없는 것 / 확인되지 않은 것
- 카드를 DB(`tracking_updates`, `update_sources`)에 쓰는 코드, 하루 한 번 도는 실행기, 크레딧 장부·차감
- 재무 근거, "공시와 숫자가 다르면 공시 우선" 로직, 뉴스 묶음 기준의 정식 값(지금은 제목 글자 유사도 임시값)
- 즉답 결과를 저장할 테이블 (팀 질문 Q3)
- 실제 DB·OpenAI에 대한 실행: 후보 검색 SQL, 가격 조회 SQL, `experiment` CLI는 이 환경에서 돌려 보지 못했다. 테스트는 가짜 LLM·가짜 후보로만 통과했다.
- 임계값(`min_similarity` 0.5, `related_news_min_similarity` 0.6, `near_pct` 3.0)은 모두 임시값이다. 첫 실험의 유사도 분포를 보고 정한다.

## 7. 임계값 정하는 순서 (사람 표시를 최소화하는 방법)
임계값은 **처음 한 번만** 정하면 된다. 정한 숫자를 `configs/updates.yaml`에 적어 두면 서비스는 매번 그 숫자로 거른다. 임베딩 모델·데이터 양·종목 범위가 크게 바뀔 때만 다시 한다.
```bash
# 1) 후보 전체를 뽑는다 (비용 없음). 표본은 후보 100건 이상(주제 항목 10개 이상)
PYTHONPATH=backend python -m pipelines.updates.experiment --llm none --limit 30
# 2) LLM이 후보마다 O/X를 자동 표시한다 (OpenAI 호출: 항목 수만큼). 사람 표시 열은 그대로, 'LLM관련(O/X)' 열이 채워진 candidates_auto_<모델>.csv가 생긴다 (모델: LABELER_MODEL, 없으면 LLM_MODEL)
PYTHONPATH=backend python -m pipelines.updates.autolabel --labels results/updates/run_*/candidates.csv
# 3) (선택, 권장) 사람이 candidates_auto_<모델>.csv의 '관련(O/X)' 열에 30~50건만 표시한다 → LLM 표시와의 일치율이 나온다
# 4) 다른 종목 자료로 하한선을 구한다 (비용 없음, DB 읽기 전용)
PYTHONPATH=backend python -m pipelines.updates.noise_floor --limit 30
# 5) 합쳐서 계산한다
PYTHONPATH=backend python -m pipelines.updates.calibrate --labels results/updates/run_*/candidates_auto_<모델>.csv \
    --noise-floor results/updates/run_*/noise_floor.json --min-precision 0.8
```
- 표시 우선순위(`--source merged`, 기본): 사람 표시가 있으면 사람, 없으면 LLM. `human`/`llm`으로 하나만 쓸 수도 있다.
- 결과: `calibration.md` — 구간별 정답률, 임계값별 통과량·정밀도·재현율, 사람·LLM 일치율, 추천값, `updates.yaml`에 넣을 줄.
- 추천 기준: **정밀도 우선**. 통과한 후보 중 관련 있는 비율이 `--min-precision`(기본 80%) 이상이 되는 가장 낮은 임계값. 거기에 noise floor(다른 종목 자료 유사도의 p95)가 더 높으면 그 값을 쓴다. 엉뚱한 근거를 내느니 기준을 넘는 후보가 없으면 카드를 만들지 않는다. 목표를 만족하는 값이 없으면 그 종류는 사용하지 않는 쪽(0.99)을 권한다.
- 뉴스와 공시는 분포가 다르므로 종류별로도 계산한다(각 20건·관련 3건 이상일 때). `min_similarity_news`, `min_similarity_disclosure`로 따로 적용한다.
- 한계:
  - LLM 표시는 정답이 아니다. 같은 계열 모델이 서비스 단계에서도 판정하므로 편향이 겹칠 수 있다. 3)의 일치율로 확인한다.
  - noise floor는 같은 종목 안의 관련 없는 자료를 못 거르고, 재현율은 알 수 없다. 업종이 다른 종목만 쓰는 게 기본이다 (stocks.sector는 general/financial 두 가지뿐이라 거칠다).
  - 표시한 후보는 검색 상위 k건 안에서만 정해진다. 검색에서 빠진 자료는 알 수 없다.
  - `autolabel`, `noise_floor`의 DB·OpenAI 실행은 아직 실제 환경에서 돌려 보지 못했다 (테스트는 가짜 호출로만).

## 8. 팀 LLM 프롬프트 지침 v1.0 반영 내용 (2026-10-27)
- `configs/update_judge_prompt.md`, `configs/update_instant_prompt.md`는 지침서의 시스템 프롬프트를 그대로 옮겼다. 지침이 바뀌면 이 파일만 교체한다.
- 입력 템플릿(추적 항목, 이미 보여 준 내용, 메모 문장, 새 근거)은 `judge.py`의 `INPUT_TEMPLATE`이다. 근거 번호는 E1, E2…
- 이미 보여 준 출처(`TrackingItem.already_shown_ids`)로만 이루어진 근거는 LLM을 부르지 않고 `already_shown`으로 처리한다 (크레딧 절약·중복 방지). 이전 카드 요약·식별값은 프롬프트로 전달한다.
- `no_update`는 6개 키가 모두 있고 title·reason이 비며 summary·evidence가 빈 배열이어야 한다. 아니면 형식 실패로 본다.
- 금지 표현 사전은 지침 3-3 초기 사전 21개다. "매수"·"매도" 단독은 넣지 않았다 (자기주식 매수 같은 공시 사실을 막기 때문). 시제 패턴(`topic.banned_patterns`)은 예측·단정 표현을 막되, "~라고 밝혔어요"처럼 회사 발언을 전달하는 문장에는 적용하지 않는다.
- 구현하지 않은 것: 검사 10(뉴스·공시 충돌 시 공시 사용 확인), 검사 11(연결·별도 섞임 확인), 재무 근거([재무]) 카드와 재무 고정 문구. 근거 DB에 연결/별도 구분이 없어 입력 템플릿에서도 그 줄을 뺐다.
- `--response-schema`는 OpenAI Structured Outputs(`json_schema`, strict)로 보낸다. `judge.py`의 스키마를 `openai_schema.to_json_schema`가 변환하며 `maxItems` 같은 길이 제한은 뺀다 (실제 API 수용 여부 미확인). 길이·형식은 코드가 검사한다. 기본은 꺼 둔다.
- 지침 5장의 미정 값(near 비율, 조건가 도달 후 처리, 즉시 답변 저장 구조, 뉴스 묶음 기준, 계산 지표 포함 여부)은 여전히 임시값이다.