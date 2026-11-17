# 메모 질문 "한 번 답하기" 실험 전달 (민이 → 서린님, 2026-11-17)

자세한 실험 기록: `docs/memo-intent-prototype-result.md`. 기획: 메인 체크아웃 `docs/memo-intent-redesign-proposal.md`.
코드 위치: 워크트리 `exp-disclosure` (브랜치 `exp/disclosure-retrieval`, **아직 커밋·푸시 안 함**).

## 한 줄 요약
메모 속 **질문**("HBM이 뭐야?", "3분기 영업이익률 얼마야?")이 지금은 **추적 항목**으로 들어가서, 매일 "새 소식 카드"로 엉뚱하게 답하거나 답이 안 나왔어요.
→ 질문은 **한 번 답하기(ask)**로 따로 빼서, 다음 06:30 실행 때 카드와 함께 **한 번** 답하고 끝내는 구조를 시험했어요.
알림 단어("알려줘·나오면·계속·챙겨줘")가 있는 문장만 추적 항목이 돼요.

## 바뀌는 흐름
```
메모 저장
 └ 메모 분석 (규칙 → LLM 1회)
     ├ 추적 항목 (알림 요청)  → 매일 06:30 새 소식 카드   (기존 그대로)
     └ 한 번 답하기 (질문)    → 다음 06:30에 한 번 답
           근거: 뉴스 + 공시(하이브리드) + [재무 표](코드가 DB에서 꺼내고 비율 계산)
           ├ 답할 수 있으면 → 답 카드 (질문 전용 지시문, 기존 코드 검사·검수 그대로)
           └ 못 찾으면     → "물으신 내용은 지금 가진 공시·뉴스·재무 자료에서 확인되지 않았어요." (ask_no_answer)
```

## 결과
| 단계 | 테스트 | 기존 | 바꾼 뒤 |
|---|---|---|---|
| 메모 이해 (질문/추적 구분) | 처음 18개 메모 (3회 반복) | 8/18 | **18/18** (3회 모두) |
| 〃 | 지시문 예시와 안 겹치는 새 메모 14개 | 4/14 | **14/14** (2회) |
| 〃 | 새 메모 30개 (의도 42개) | — | **30/30** |
| 질문에 답이 나옴 | 30개 메모 속 질문 24개 | 10 (기존 카드 지시문으로 답하게 했을 때) | **12** + 나머지는 "자료 없음" 답 |

답의 질 예시 (30개 실행):
- "SK하이닉스 3분기 영업이익률 얼마야?" → "2026년 3분기 잠정, 연결 기준 영업이익률 79.7%" (전엔 답 없음)
- "기아랑 현대차 영업이익률 같은 분기로 비교" → 2026년 2분기 연결 기아 8.0%·현대차 5.8% (전엔 답 없음)
- "신한이랑 KB 순이익 증가율 비교" → 3분기 잠정 연결 전년 같은 분기 대비 신한 +10.9%·KB +15.6% (전엔 신한만)
- "자사주 소각이 왜 좋아?" → 전엔 소각 수량만 → 기사 속 설명(발행주식 수에서 빠짐, 배당 총액이 같으면 주당배당금 ↑ 조건부)
- 모르는 부분은 "이번 자료에서 확인되지 않아요"라고 밝힘

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
| `configs/ask_answer_prompt.md` (새) | 질문 전용 답변 지시문 ("새 소식인가" → "근거로 답할 수 있나") | `topic.prompt_path_ask` |
| `configs/ask_relevance_prompt.md` (새) | 질문 전용 관련성 판정 (용어 설명·사업 설명·지난 실적도 O) | `relevance.prompt_ask` |
| `updates/fin_table.py` (새) | [재무 표] 근거: 최근 6분기 + 최신 잠정실적 + 재무상태, 비율은 코드 계산, 질문에 나온 다른 회사 표도 | `topic.ask_fin_table` |
| `updates/topic.py`, `experiment.py`, `judge.py` | ask 항목이면 위 지시문·재무 표 사용, '최신 강한 후보에서 멈추기' 끔 | `item.category == "ask"` |
| `updates/response.py` | ask인데 답을 못 만들면 `ask_no_answer`(보임). 호출 실패 등 시스템 실패는 기존처럼 숨기고 재시도 | 위와 같음 |
| `updates/disclosure_search.py` (새), `evidence.py`, `checks.py`, `relevance.py`, `models.py` | (Codex 실험) 공시 하이브리드 검색, 공시도 관련성 판정, 잠정실적 연결/별도 표시 검사 | `disclosure.search: hybrid`, `relevance.include_disclosures`, `topic.require_financial_basis` |

실험 설정 전체: `configs/updates_exp.yaml` (운영 `configs/updates.yaml`은 손대지 않음). 관련 테스트 349 passed (3 skipped).

## 서린님께 부탁·같이 정할 것
1. **ask 저장과 매일 실행 연결** (아직 없음): 지금 `questions`는 분석 결과에만 있고 메모 저장 API(`board/service.py`)가 저장·반환하지 않아요.
   - 저장 칸(tracking_items에 `kind=ask`로 넣을지, 따로 테이블) · `daily.py`가 ask를 한 번만 처리하고 끝내기 · 요금제 한도에서 ask를 셀지.
2. **화면**: 답 카드와 "자료 없음" 답을 추적 카드와 같은 자리에 보일지, 질문 답임을 표시할지. 응답 유형 이름 `ask_no_answer`.
3. **기존 카드와 비교**: 서린님 카드 파이프라인(운영 설정)과 같은 메모로 나란히 보기. 결과 폴더의 `report.md`에 메모별 원문·분석·답이 있어요.
4. **아직 못 푸는 질문** (지시문 밖 문제):
   - 뉴스가 약 한 달치뿐이라 배경 질문("46시리즈가 뭐야", "인도 IPO 자금 용도")의 기사가 없음
   - 질문 문장 그대로 공시를 검색해 사업보고서의 엉뚱한 절이 걸림 (질문 → 검색어 바꾸기 없음)
   - 공시에 정보 자체가 없음 (부문별 손익, 방산 매출 인식 "보안상 미기재")
   - 뜻 질문을 LLM 일반 지식으로 답할지는 미정 (지금은 근거 밖 지식 금지 원칙 유지)
   - 실행마다 답/무답이 바뀌는 질문이 몇 개 있음 (검수 호출·숫자 검사 실패)

## 돌려 보는 법
```bash
cd .claude/worktrees/exp-disclosure
# 메모 분석 + 채점만 (카드 생성 안 함, 빠름)
PYTHONPATH=backend python eval/memo_intent_eval_v1/run_service.py --cases eval/memo_intent_eval_v1/cases_v2_30.jsonl \
  --prompt configs/tracking_judge_prompt_intent.md --skip-cards --out-dir results/intent_try
# 메모 분석 → 근거 검색 → 답까지 (30개 약 10분, DB 읽기만)
PYTHONPATH=backend python eval/memo_intent_eval_v1/run_service.py --cases eval/memo_intent_eval_v1/cases_v2_30.jsonl \
  --prompt configs/tracking_judge_prompt_intent.md --config configs/updates_exp.yaml --answer-asks --out-dir results/intent_try
```
`--answer-asks`는 ask를 같은 근거 검색·카드 생성에 태우는 실험용 연결이에요 (운영 daily에는 아직 없음).
테스트 메모: `eval/memo_intent_eval_v1/cases.jsonl`(18), `cases_holdout.jsonl`(14), `cases_v2_30.jsonl`(30).
