# 코스피 전체 재무 DB 수집 기획안 (초안)

작성: 이민성 · 2026-10-29 · 상태: 결정 완료, 팀 공유 전

## 1. 목적과 범위

- 공시 무인 파이프라인(`run_all`)과 같은 대상(오늘 기준 코스피 상장 법인 전체, 약 800개사)의 재무 수치를 `financials`·`financials_fin`에 적재한다.
- 기간은 공시와 같은 정기보고서 10건이다(2024 1분기 ~ 2026 반기). 12월 결산이 아닌 회사는 회계연도 기준 분기로 맞춘다. 여기에 2024 보고서의 전기 값으로 2023년 4개 기간을 추가 호출 없이 덧붙인다(9절).
- 금융사는 같은 표에 섞지 않고, 업종별 지표를 `financials_fin`에 명시적인 컬럼으로 추가한다.
- 바이오·방산 같은 업종별 핵심 지표(R&D, 수주잔고, 임상)는 DB에 넣지 않고 공시 원문 검색으로 답한다(7절).

## 2. 확정한 결정

| # | 항목 | 결정 |
|---|---|---|
| 1 | 금융사 지표 범위 | 비율 + 업종별 핵심 금액 2~3개 (B안) |
| 2 | 컬럼 위치 | 금융 지표는 전부 `financials_fin`, `financials`는 공통 항목만 |
| 3 | `solvency_ratio` | `bis_ratio`로 이름 변경, 기존 코드도 같이 수정 |
| 4 | NULL 사유 | DB에 `null_reasons` jsonb 컬럼 추가 |
| 5 | 금융사 판별 | 업종코드 + 재무제표 계정으로 자동 판별, 애매하면 검토 CSV |
| 6 | 절차 | 이 문서로 팀 합의 → 마이그레이션은 이민성 PC에서 적용 |
| 7 | 표준 ID 없는 계정 | NULL + 검토 CSV (계정명으로 자동 채우지 않음) |
| 8 | 실행 구조 | 별도 명령 `run_financials_all` (`run_all`과 대상 목록·상태·실패 CSV 방식 공유) |
| 9 | 증권사 `revenue` | NULL(`not_applicable`), 영업수익은 `securities_operating_revenue`에만 |
| 10 | 세부 업종 | `stocks.fin_type` 컬럼 추가 |
| 11 | 비율 추출 시점 | 재무 API 금액 항목 먼저 적재, BIS·K-ICS·NCR은 `run_all` 완료 후 별도 실행 |
| 12 | 2023년 비교값 | 포함. 2024 보고서의 전기(`frmtrm`) 값으로 추가 호출 없이 채움 (9절 주의) |
| 13 | `bis_ratio` 이름 변경 | 진행. `eval/memo_personas` 3개 파일도 이번 작업에서 같이 수정, 담당 팀원에게 공유 |
| 14 | 업종별 본문 지표 | 지금은 안 함. 회사 간 비교나 조건 카드에 필요해지면 그때 검토 |

## 3. 지표와 DART 계정

2025 사업보고서 연결재무제표(`fnlttSinglAcntAll`)로 확인한 계정이다.

### 3.1 공통 (`financials`, 변경 없음)

매출, 영업이익, 지배주주 순이익, 자산·부채·자본, 유동자산·유동부채, 재고자산, 이자비용, 이익잉여금, EPS, BPS, 자본금, 자본잉여금.
금융사는 이 중 매출·유동 항목·재고자산이 원래 없다. 이 값들은 NULL로 두고 사유를 "해당 없음"으로 남긴다.

### 3.2 금융 (`financials_fin`)

| 업종 | 컬럼 | 출처 | 확인 결과 |
|---|---|---|---|
| 은행 | `net_interest_income` (기존) | 재무 API | — |
| 은행 | `fee_income` (기존) | 재무 API | `ifrs-full_FeeAndCommissionIncome` |
| 은행 | `loan_loss_provision` (기존) | 재무 API | — |
| 은행 | `loans` (신규) | 재무 API | `dart_LoansAtAmortisedCost` 기업은행·KB금융 있음 |
| 은행 | `deposits` (신규) | 재무 API | `ifrs-full_DepositsFromCustomers` 기업은행·KB금융 있음 |
| 은행 | `bis_ratio` (이름 변경) | 공시 본문 | 현재 KB금융만 `financials_bis`로 추출 |
| 보험 | `insurance_revenue` (신규) | 재무 API | `ifrs-full_InsuranceRevenue` 삼성생명·삼성화재·KB금융 있음 |
| 보험 | `kics_ratio` (신규) | 공시 본문 | 추출기 새로 필요 |
| 증권 | `securities_operating_revenue` (신규) | 재무 API | `ifrs-full_Revenue`(영업수익) 미래에셋증권 있음 |
| 증권 | `ncr_ratio` (신규) | 공시 본문 | 추출기 새로 필요 |
| 공통 | `null_reasons` (신규, jsonb) | 파이프라인 | 예: `{"kics_ratio": "해당 없음"}` |

보험수익 계정은 `ifrs-full_InsuranceRevenue`로 통일한다. 삼성생명은 이 계정의 이름을 "일반보험서비스수익"이라고 붙였다. 삼성생명·KB금융의 `dart_OperatingIncomeInsurance`(보험서비스수익)는 이 값에 재보험수익을 더한 합계다(삼성생명 9.72조 + 0.17조 = 9.89조). 따라서 회사 간 비교가 되는 쪽은 IFRS17 표준 보험수익이다.

금융지주(KB금융 등)는 자회사에 은행·보험·증권이 섞여 있어, 계정이 있는 컬럼은 모두 채운다.

### 3.3 NULL 사유 코드

| 코드 | 뜻 |
|---|---|
| `not_applicable` | 업종상 해당 없음 (보험사의 재고자산 등) |
| `no_standard_id` | 값은 있지만 표준 계정 ID가 없음 (LG EPS 등) → 검토 CSV |
| `not_reported` | 해당 보고서에 계정 없음 |
| `no_xbrl` | 재무 API가 013 응답 (맥쿼리인프라 등) |
| `extract_failed` | 공시 본문 비율 추출 실패 |

## 4. 스키마 변경 (마이그레이션 0012 예정)

```sql
ALTER TABLE financials_fin RENAME COLUMN solvency_ratio TO bis_ratio;
ALTER TABLE financials_fin
  ADD COLUMN loans numeric(20,0),
  ADD COLUMN deposits numeric(20,0),
  ADD COLUMN insurance_revenue numeric(20,0),
  ADD COLUMN securities_operating_revenue numeric(20,0),
  ADD COLUMN kics_ratio numeric(8,2),
  ADD COLUMN ncr_ratio numeric(8,2),
  ADD COLUMN null_reasons jsonb NOT NULL DEFAULT '{}';
ALTER TABLE financials ADD COLUMN null_reasons jsonb NOT NULL DEFAULT '{}';
-- 금융 세부 업종
ALTER TABLE stocks ADD COLUMN fin_type text
  CHECK (fin_type IN ('bank', 'insurance', 'securities', 'holding', 'other'));
```

- 기존 컬럼 이름(`symbol`, `period_end`, `period_type`, `total_assets` 등)은 바꾸지 않는다.
- 적용: 이민성 PC에서 `alembic upgrade head` 1회. 다른 팀원은 적용하지 않는다.

`solvency_ratio` 이름 변경으로 같이 고칠 코드 (이번 작업에 포함):

- `backend/pipelines/disclosures/financials_bis.py`, `financials_pipeline.py`, `financials_loader.py`, `financials_validate.py`
- `backend/tests/test_financials_mapping.py`, `test_financials_bis_validate.py`
- `eval/memo_personas/export_evidence.py`, `devtools/fake_db.py`, `devtools/fake_data.py` (**다른 팀원 코드**)

## 5. 금융사 판별 규칙

DART 기업개황의 업종코드(KSIC)만으로는 구분이 안 된다. 지주회사 코드 64992에 KB금융·메리츠금융지주(금융)와 LG·SK(일반)가 같이 들어 있다.

1. 업종코드 641(은행) → `bank`, 651~653(보험) → `insurance`, 6612(증권) → `securities`
2. 64992(지주회사) → 연결재무제표에 `DepositsFromCustomers`나 `InsuranceRevenue`가 있으면 `holding`(금융), 없으면 일반
3. 그 밖의 64~66(카드·캐피탈 등) → `other`. 공통 컬럼과 기존 은행 컬럼 중 있는 것만 채움
4. 1~3의 결과가 계정과 맞지 않으면 검토 CSV에 남김 (예: 은행 코드인데 예수부채가 없음)

판별 결과는 `stocks.sector`(general/financial)와 `stocks.fin_type`에 반영한다.

## 6. 실행 구조 `run_financials_all`

```
PYTHONPATH=backend python -m pipelines.disclosures.run_financials_all [--status]
```

- 대상 목록: `run_all`의 `data/run_all/universe.json`을 그대로 사용한다.
- 단계: 판별 → 수집(재무 API, 주식총수) → 적재 → 비율 추출(공시 청크가 있는 회사만) → 검증
- 기간: `select_window_candidates`의 결산월 판정을 재사용한다. 현재 `REPRT_CODES`는 3·6·9·12월 고정이라 비12월 결산사에서 틀리므로 회계연도 기준으로 고친다.
- 공통: 묶음 단위 재개(`state.json`), DART 020이면 00:05 KST까지 대기, 실패는 `failed_reports.csv`와 같은 형식으로 저장
- 산출물: `data/run_financials/` (`.gitignore` 추가)
- 호출량: 회사당 기간별 재무 1~2회 + 주식총수 1회 → 약 800 × 10 × 2.5 = **약 2만 회**. 일일 한도(2만)와 `run_all`이 같은 키를 쓰므로 2~3일로 잡는다.

## 7. 다른 업종(바이오·방산 등)은?

재무제표 구조가 다른 업종은 금융뿐이다. 2025 사업보고서로 확인한 결과는 아래와 같다.

| 회사 | 매출 | 영업이익 | 재고자산 | 연구개발비 계정 |
|---|---|---|---|---|
| 삼성바이오로직스 | O | O | O | 없음 |
| 셀트리온 | O | O | O | 없음 |
| 한화에어로스페이스 | O | O | O | O (`ResearchAndDevelopmentExpense`) |
| 현대로템 | O | O | O | 없음 |

- 바이오·방산도 일반 제조업과 같은 표준 계정을 써서 공통 컬럼이 모두 채워진다. 적자 기업은 음수로 들어가므로 따로 처리할 것이 없다.
- 다만 업종별 핵심 지표는 재무 API로 일관되게 얻을 수 없다.
  - 연구개발비는 손익계산서에 따로 표시한 회사만 나온다. 나머지는 판관비 주석이나 "연구개발활동" 본문에 있다.
  - 수주잔고는 계정이 아예 없고 "사업의 내용" 본문에만 있다. 계약부채는 수주잔고가 아니다.
  - 임상 파이프라인도 본문에만 있다.
- 이 지표들은 `run_all`이 적재하는 공시 원문 청크에 들어 있으므로, 당분간 **LLM이 공시 원문 검색으로 답한다** (평가셋 SS-19 연구개발비 비교, SS-22 HBM 연구개발 실적이 이미 이 방식).
- 공시 검색으로 어려운 쓰임은 여러 회사 비교·정렬, 추이 차트, 조건 카드다. 이런 기능이 필요해지면 그때 본문 추출 → DB 적재를 검토한다.
- 구조 예외는 금융 외에 리츠·인프라펀드가 있다. 별도재무제표만 있거나(롯데리츠), 재무 API가 013으로 응답한다(맥쿼리인프라). 이런 경우는 NULL 사유(`no_xbrl`)로 처리한다.

## 8. 검증

- 판별: 기업은행·삼성생명·미래에셋증권·KB금융·메리츠금융지주가 금융, LG·SK가 일반으로 판별되는지 확인
- 금액: 3절 확인값과 적재값 일치
- NULL: 모든 NULL 칸에 `null_reasons` 코드가 있는지 확인 (사유 없는 NULL 0건)
- 기존 4개사: 이번 변경 전후로 공통 컬럼 값이 같은지 확인

## 9. 주의할 점

- **2023년 비교값의 범위**: 분기보고서의 전기 값은 손익 항목은 전년 같은 분기지만, 재무상태표 항목은 전년 같은 분기가 아니라 직전 사업연도 말이다. 따라서
  - 2023 사업연도(연간): 손익·재무상태표 모두 채움 (2024 사업보고서 전기 값)
  - 2023 1분기·반기·3분기: 손익 항목만 채우고 재무상태표 항목은 NULL(`not_reported`)
  - 같은 기간이 2023 보고서에서 직접 수집된 값과 겹치면 직접 수집한 값을 우선한다 (현재 범위에는 2023 보고서가 없어 겹치지 않음)
- **`bis_ratio` 이름 변경**: 마이그레이션 적용과 코드 수정을 같은 커밋 묶음으로 올리고, 적용 전에 `eval/memo_personas` 담당 팀원에게 알린다.
