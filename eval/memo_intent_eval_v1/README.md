# memo_intent_eval_v1

메모 원문에서 사용자의 의도가 보존되는지 확인하는 신규 평가셋이다. 기존 `memo_eval_v0`의 정규화된
추적 항목을 재사용하지 않았고, 검색·카드 생성 전에 메모 분석 단계만 먼저 평가하도록 만들었다.

## 목적

- 개념 질문(`definition`)과 새 소식 추적(`tracking`)을 분리한다.
- 원인 질문(`causal`)을 단순 주제 관련 소식으로 바꾸지 않는다.
- 가격 조건, 비교, 비추적 문장과 확인 필요 문장을 구분한다.
- 여러 문장을 합칠 때 원문 의도를 잃지 않는다.

## 파일

- `cases.jsonl`: 18개 메모. 한 줄이 한 메모다.

## 주요 필드

- `expected_intents[].kind`: `definition`, `causal`, `tracking`, `price_condition`, `comparison`,
  `non_tracking`, `clarification` 중 하나
- `create_tracking`: 이 의도에서 매일 업데이트용 추적 항목을 만들어야 하는지
- `tracking`: 만들어야 할 항목의 최소 조건. 완전한 문구 일치 대신 타입·필수 의미·핵심어를 검사한다.
- `answer_requirements`: 답변이나 카드가 생성되려면 근거가 충족해야 할 조건
- `forbidden`: 잘못 생성하면 안 되는 항목 또는 카드의 특징
- `merge_policy`: 문장 간 병합 정책. 병합하더라도 `preserve_intents`를 잃으면 실패다.

## 권장 평가 순서

1. `cases.jsonl`의 `text`만 실제 메모 분석 코드에 입력한다.
2. 생성된 문장 판정과 추적 항목을 `expected_intents`와 비교한다.
3. `create_tracking=false` 의도에서 항목이 생기면 과잉 추적으로 센다.
4. 병합 후 `preserve_intents`가 사라지면 의도 손실로 센다.
5. 메모 분석을 통과한 사례만 검색·카드 단계로 보낸다.

카드 수는 성공 지표로 사용하지 않는다. 우선순위는 의도 보존, 잘못된 추적 항목 생성률,
질문에 직접 답한 비율, 근거 정확성, 비용 순이다.
