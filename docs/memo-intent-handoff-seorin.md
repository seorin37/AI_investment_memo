# 메모 질문 "한 번 답하기" 실험 전달 (민이 → 서린님, 2026-11-17 작성 · 11-19 갱신)

자세한 실험 기록: `docs/memo-intent-prototype-result.md`. 기획: 메인 체크아웃 `docs/memo-intent-redesign-proposal.md`.
코드 위치: 워크트리 `exp-disclosure` (브랜치 `exp/disclosure-retrieval`, 커밋 9개 **로컬에만 있음, 푸시 안 함**).
넘길 때는 최신 dev 위로 옮긴 새 브랜치로 드릴게요.

## 한 줄 요약
메모 속 **질문**("HBM이 뭐야?", "3분기 영업이익률 얼마야?")이 지금은 **추적 항목**으로 들어가서, 매일 "새 소식 카드"로 엉뚱하게 답하거나 답이 안 나왔어요.
→ 질문은 **한 번 답하기(ask)**로 따로 빼서, 다음 06:30 실행 때 카드와 함께 **한 번** 답하고 끝내는 구조를 시험했어요.
알림 단어("알려줘·나오면·계속·챙겨줘")가 있는 문장만 추적 항목이 돼요.
11-18부터 질문 답은 **공시·재무·주가·뉴스를 한 문단으로 이어 쓰고, 출처는 아래에 모아 보이는** 종합 답이에요.

## 바뀌는 흐름
```
메모 저장
 └ 메모 분석 (규칙 → LLM 1회)
     ├ 추적 항목 (알림 요청)  → 매일 06:30 새 소식 카드   (기존 그대로)
     └ 한 번 답하기 (질문)    → 다음 06:30에 한 번 답
           검색: 메모 원문 + 종목명으로 뉴스 + 공시(하이브리드, 질문 종류별 목차 가산점)
           관련성 판정 (terra) → 근거 묶기 (최대 8개, 관련 뉴스가 있으면 최소 3자리는 뉴스)
           + [재무·주가 표]: 코드가 DB에서 꺼내고 비율·증감률·주가 등락을 계산한 근거 한 건
           답 생성 (sol) → 코드 검사 → 검수 (terra, 답 본문만) → 막히면 이유를 주고 한 번 다시 쓰기
           ├ 답할 수 있으면 → 답 본문(최대 7문장·700자) + 출처 목록 + 코드 계산값
           └ 못 찾으면     → "물으신 내용은 지금 가진 공시·뉴스·재무 자료에서 확인되지 않았어요." (ask_no_answer)
```

답 모양 예시 (B2, M005 NAVER "네이버 클라우드 사업이 구체적으로 무엇을 하는지"):
> 공시에 따르면 네이버클라우드는 … '네이버 클라우드 플랫폼'을 제공하는 사업을 해요. … AI 분야에서는 HyperCLOVA X 기반의 AI 개발 도구 CLOVA Studio와 … Neurocloud for HyperCLOVA X를 제공해요. … 한국경제는 네이버클라우드가 네이버 AI팩토리 운영을 주도하기로 했다고 보도했어요. … 다만 전체 상품별 세부 기능과 이용 요금은 이번 자료로는 확인되지 않아요.
> 출처: [공시] 분기보고서 (2026.09) · [뉴스] 한국경제 · [뉴스] 매일경제

## 결과
### 메모 이해 (질문/추적 구분)
| 테스트 | 기존 | 바꾼 뒤 |
|---|---|---|
| 처음 18개 메모 (3회 반복) | 8/18 | **18/18** (3회 모두) |
| 지시문 예시와 안 겹치는 새 메모 14개 | 4/14 | **14/14** (2회) |
| 새 메모 30개 | — | **30/30** |
| 메모 100개 (`cases_v3_100.jsonl`) | 34/100 | **97/100** |

### 메모 100개 전체 (메모 분석 → 답까지, 같은 100개)
| 실행 | 질문 답 (64개 중) | 알림 카드 (38개 중) | 검수에서 버려짐 | 뉴스 쓴 카드 | 비용 |
|---|---|---|---|---|---|
| 기존 코드 (운영 설정) | 24 | 6 | — | — | $0.87 |
| A 11-17 최종 (비용 절감 설정) | 41 | 14 | 6 | 1 | $2.52 |
| B 11-18 종합 답 형식 | 34 | 10 | 14 | 0 | $2.67 |
| B2 + 검수 수정 | 47 | 13 | 0 | 3 | $2.79 |
| **B3 B2 + 뉴스-종목 태그 반영 (11-19)** | **51** | **16** | **1** | **20** | **$3.42** |

- A → B: 답이 길어지면서(facts 최대 8 + 본문 7문장) 검수할 문장이 10~13개로 늘어, 한 문장만 막혀도 카드 전체가 버려졌어요.
  막힌 문장은 대부분 본문에서 풀어 쓰다 조건이 빠진 경우("석유화학 부문" → 회사 전체, "플랫폼 **또는** 기술" → "플랫폼**과** 기술", 근거에 없는 "당일 출시")였어요.
- B → B2: 검수 기준은 그대로 두고 ① 질문 답은 화면에 보이는 본문만 검수(숨긴 facts는 같은 내용이라 두 번 검수하지 않음) ② 검수에서 막히면 막힌 문장과 이유를 주고 한 번만 다시 쓰기. 새로 카드가 나온 항목 19, 사라진 항목 3(LLM 무답 2·코드 검사 1, 검수와 무관한 실행 흔들림).
- B2 → B3 (코드·설정 같음, 중앙 DB `news_stocks`만 4개사 → 489개사): 근거에 뉴스가 들어간 항목 6 → 47 (95개 중), 뉴스를 출처로 쓴 카드 3 → 20.
  새로 답한 질문 M023·M027·M029·M033·M035·M041·M066·M072·M096 등, 새 알림 카드 M014·M030·M056. 빠진 질문 5개: 예측 문장 M009, 범위 표현 M019, 형식 M068, 검수 M077, LLM 무답 M001 (뉴스에 전망 기사가 섞인 것 + 실행 흔들림).
  비용 +23%는 근거에 뉴스 본문이 더 들어가서예요.
  예: "삼성화재 K-ICS 비율이 뭐야?" → 서울경제 기사로 뜻(가용자본 ÷ 요구자본)을 설명하고 반기보고서 2026년 6월말 연결 기준 282.78%를 붙여, 출처에 기사·공시를 함께 보여 줘요.
- 비교 화면: `eval/memo_intent_eval_v1/compare_html.py` (두 실행을 메모별로 나란히, "결과가 다른 메모만" 거르기).

### 답의 질 예시
- "SK하이닉스 3분기 영업이익률 얼마야?" → "2026년 3분기 잠정, 연결 기준 영업이익률 79.7%" (전엔 답 없음)
- "기아랑 현대차 영업이익률 같은 분기로 비교" → 2026년 2분기 연결 기아 8.0%·현대차 5.8% (전엔 답 없음)
- "KB금융 3분기 순이익 전년 대비 얼마나 늘었어?" → 연결 지배주주 순이익 1조 7,588억원, 전년 같은 분기 대비 +4.3% (재무 표 값. 11-17 초기엔 잠정실적의 전체 순이익을 써서 +15.6%로 틀렸던 것을 지배주주 순이익으로 바로잡음)
- "NAVER 주가 왜 빠졌어?" → 매일경제의 하락 원인 기사 + 3분기 영업이익 −20.9% + 1주 −11.9%를 한 문단으로, 기사 사이 인과는 기사가 말한 것만
- 모르는 부분은 "다만 ~는 이번 자료로는 확인되지 않아요"로 끝맺음

## 바뀐 파일과 운영 영향
**운영에 바로 영향 (버그 수정)**
| 파일 | 내용 |
|---|---|
| `backend/pipelines/tracking/segment.py` | "유상증**자** 한다던데", "미국 해**군** MRO"를 "~하자/~하군" 문장 끝으로 보고 자르던 것 수정 (증자·감자·출자·융자·해군·육군·공군·장군) |
| `backend/pipelines/tracking/price.py` | "65,000원 아래로 **내려오면**"을 가격 조건으로 인식 (내려오·올라오·빠지) |

**실험 설정을 켤 때만 동작 (끄면 지금과 같음)**
| 파일 | 내용 | 켜는 법 |
|---|---|---|
| `configs/tracking_judge_prompt_intent.md` (새) | 메모 분석 지시문: 질문은 `ask`, 알림 단어 있을 때만 items | 환경변수 `TRACKING_PROMPT_PATH` |
| `tracking/llm.py`, `tracking/judge.py`, `app/board/analysis.py` | LLM 응답의 `ask` 읽기 → `Judgment.asks` → `AnalysisResult.questions` | 위와 같음 (없으면 빈 목록) |
| `configs/ask_answer_prompt.md` (새) | 질문 전용 답변 지시문. 11-18: 근거 종류를 나누지 않고 한 문단으로 종합, `explanation`이 보이는 답·`facts`는 숨긴 검증용, 첫 문장에 답 | `topic.prompt_path_ask` |
| `configs/ask_relevance_prompt.md` (새) | 질문 전용 관련성 판정 (용어 설명·사업 설명·지난 실적도 O) | `relevance.prompt_ask` |
| `updates/fin_table.py` (새) | [재무·주가 표] 근거: 최근 6분기 + 최신 잠정실적 + 3개년 연간 + 재무상태 + `financial_metrics`(0017) 비율 + 사건 비율(0018) 줄 + **주가 줄**(종가·1주/1개월 등락·52주 고저·시가총액). 금융사는 이익률·이자보상배율 뺌 | `topic.ask_fin_table` |
| `updates/calc.py` (새) | 즉석 계산: LLM은 두 값과 근거 번호만 고르고, 코드가 근거와 대조해 계산 (백만원·십억원 단위, 단위 의심 범위 검사) | ask 카드의 `calc` |
| `updates/topic.py` | ask면 위 지시문·재무 표·계산 사용, '최신 강한 후보에서 멈추기' 끔, `ask_overrides`(질문만 facts 8·본문 7문장·700자·본문만 검수), **출처 목록** `source_list`, **검수 실패 다시 쓰기** `verify_retry` | `item.category == "ask"`, `topic.verify_retry` |
| `updates/evidence.py` | `min_news`: 관련 뉴스가 있으면 근거 중 최소 N자리는 뉴스 (공시 청크가 근거를 다 채워 뉴스가 0건이 되던 문제) | `topic.min_news` |
| `updates/models.py`, `results.py` | `TrackingItem.query_text`(ask는 메모 원문+종목명으로 검색), `UpdateDraft.calculations`·`source_list` → `cards.jsonl` | ask일 때만 채워짐 |
| `updates/response.py` | ask인데 답을 못 만들면 `ask_no_answer`(보임). 호출 실패 등 시스템 실패는 기존처럼 숨기고 재시도 | 위와 같음 |
| `updates/disclosure_search.py` (새), `relevance.py`, `checks.py`, `experiment.py` | 공시 하이브리드 검색(dense+sparse 0.6/0.4) + 질문 종류별 목차 가산점, 공시도 관련성 판정, 잠정실적 연결/별도 표시 검사, 검수만 다른 모델로 보내기 | `disclosure.search: hybrid`, `relevance.include_disclosures`, `topic.require_financial_basis`, `topic.verify_model` |

실험 설정 전체: `configs/updates_exp.yaml` (운영 `configs/updates.yaml`은 손대지 않음).
비용 설정: 관련성 판정·검수는 `gpt-6.1-terra`, 답 생성은 `gpt-6.1-sol`, 근거 상한 8, 판정 입력 600자.
테스트: 업데이트 관련 243 passed (`test_card_v2`·`test_updates`·`test_evidence_min_news`·`test_verify_retry`).

## 서린님께 부탁·같이 정할 것
1. **뉴스-종목 태그 (11-19 반영 확인, 감사합니다)**: `news_stocks` 4개사·기사 4,117건 → 489개사·기사 10,290건 (청크 있는 기사 9,957건). 테스트 100개의 56개 회사 모두 연결됐고, 결과는 위 B3예요.
   다만 대형사인데 태그 기사가 너무 적은 곳이 있어요: POSCO홀딩스(005490) 2건, S-Oil(010950) 3건, 삼성에스디에스(018260) 6건, 신한지주(055550) 8건. "포스코"·"에쓰오일"처럼 줄여 쓰는 이름(별칭)이 빠졌는지 봐 주시면 좋겠어요.
2. **ask 저장과 매일 실행 연결** (아직 없음): 지금 `questions`는 분석 결과에만 있고 메모 저장 API(`board/service.py`)가 저장·반환하지 않아요.
   - 저장 칸(tracking_items에 `kind=ask`로 넣을지, 따로 테이블) · `daily.py`가 ask를 한 번만 처리하고 끝내기 · 요금제 한도에서 ask를 셀지.
3. **화면**: 답 본문 + 출처 목록(`source_list`: 종류·제목·매체·날짜·링크) + 코드 계산값. 추적 카드와 같은 자리에 보일지, 질문 답임을 표시할지. 응답 유형 이름 `ask_no_answer`.
4. **비용**: 메모 100개 ≈ $2.8 (메모당 약 $0.03). 검수 다시 쓰기는 한 번에 약 $0.02 (100개에 5번). 다시 쓰기를 terra로 보내면 조금 더 줄일 수 있어요.
5. **실행 시간**: 100개를 한 프로세스로 돌리면 30~40분이 대부분 LLM 응답 대기예요. 메모 단위로 4개 나눠 동시에 돌리면 약 11분 (같은 메모 항목끼리 카드 합치는 처리가 있어 메모 단위로 나눠야 함). 단, 프로세스마다 검색 모델(BGE-M3)을 GPU에 올려서 6GB GPU에 다른 앱이 떠 있으면 4개 동시엔 메모리가 차서 멈춰요 (11-19 B3 첫 실행이 2시간 48분 멈춤) → 2개씩 약 25분. 운영 06:30도 메모가 많아지면 같은 방식이 필요해요.
6. **공용 코드 확인** (11-17 전달드린 것): `checks.numbers`가 "백만원" 붙은 숫자·"천명" 표 머리를 못 읽어 맞는 문장을 NUMBER로 막는 경우.
7. **아직 못 푸는 질문** (지시문 밖 문제):
   - 공시에 정보 자체가 없음 (부문별 손익, 방산 매출 인식 "보안상 미기재")
   - 뜻 질문을 LLM 일반 지식으로 답할지는 미정 (지금은 근거 밖 지식 금지 원칙 유지)
   - sol은 temperature를 못 정해 실행마다 답/무답이 몇 개씩 바뀜 (100개에서 2~3개)
   - 뉴스 본문 미수집 9%: [포토]·[표]류 약 4,060건(괜찮음), **10-30·31 이틀 수집 공백 약 2,310건**(다시 수집 필요, 수집 담당께 전달)

## 돌려 보는 법
```bash
cd .claude/worktrees/exp-disclosure
set -a; . ./.env; set +a
# 메모 분석 + 채점만 (카드 생성 안 함, 빠름)
PYTHONPATH=backend python eval/memo_intent_eval_v1/run_service.py --cases eval/memo_intent_eval_v1/cases_v2_30.jsonl \
  --prompt configs/tracking_judge_prompt_intent.md --skip-cards --out-dir results/intent_try
# 메모 분석 → 근거 검색 → 답까지 (DB 읽기만)
PYTHONPATH=backend python eval/memo_intent_eval_v1/run_service.py --cases eval/memo_intent_eval_v1/cases_v3_100.jsonl \
  --prompt configs/tracking_judge_prompt_intent.md --config configs/updates_exp.yaml --answer-asks --out-dir results/intent_try
# 두 실행 나란히
python eval/memo_intent_eval_v1/compare_html.py --cases eval/memo_intent_eval_v1/cases_v3_100.jsonl \
  --a <실행1>/run_<시각> --b <실행2>/run_<시각> --out compare.html
```
`--answer-asks`는 ask를 같은 근거 검색·카드 생성에 태우는 실험용 연결이에요 (운영 daily에는 아직 없음).
테스트 메모: `cases.jsonl`(18), `cases_holdout.jsonl`(14), `cases_v2_30.jsonl`(30), `cases_v3_100.jsonl`(100), `cases_integrated4.jsonl`(종합 답 4개).
결과 폴더: `report.md`(메모별 원문·분석·답), `cards/run_*/llm_io.jsonl`(LLM 입력·출력, stage: relevance·card·verify·format_retry).
