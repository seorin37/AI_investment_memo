# 금융사 건전성 비율 (BIS · K-ICS · NCR)

`financials_fin`의 `bis_ratio` · `kics_ratio` · `ncr_ratio`를 정기보고서 본문(`disclosure_chunks`)에서 뽑아 채운다.
재무제표 API에는 이 비율이 없어서 `run_financials_all`과 따로 돈다.

- 추출: `backend/pipelines/disclosures/financials_ratios.py`
- 실행: `backend/pipelines/disclosures/run_financial_ratios.py`
- 테스트: `backend/tests/test_financial_ratios.py` (실제 보고서 조각, DB 없음)

## 1. 어떤 회사에 어떤 비율

| stocks.fin_type | 채우는 컬럼 | 보고서 행 이름 예 |
|---|---|---|
| bank, holding | bis_ratio (BIS 총자본비율) | `총자본비율(A/B)`, `BIS자기자본비율(A/B)`, `BIS기준 자기자본비율`, `BIS기준 총 자기자본비율` |
| insurance | kics_ratio (지급여력비율, 경과조치 적용 후) | `지급여력비율(A/B)` |
| securities | ncr_ratio (순자본비율) | `순자본비율[(A-B)/C]`, `순자본비율(C/D)` |

- 나머지 두 비율, `other` 업종은 세 비율 모두 `null_reasons = not_applicable`.
- 은행이 없는 금융지주도 bis_ratio는 `not_applicable`이다 (`financials_ratios.NOT_APPLICABLE_SYMBOLS`).
  - 한국금융지주: 보고서의 BIS는 한국투자저축은행 값이다.
  - 메리츠금융지주: 보고서의 총자본비율은 금융지주 업계 통계다.
- 단위는 % 그대로 쓴다 (NCR은 1,000%를 넘는 일이 흔하다).

## 2. 표·열 고르는 규칙

1. **행**: 비율 이름으로 시작하는 표 행만 쓴다. 아래는 쓰지 않는다.
   - 문장 속 언급, 제도 설명(`총자본비율 8.0% 이상`)
   - 다른 표의 셀 값(`지표명: BIS기준 자기자본비율`)
   - 다른 말에 붙은 이름(`기본자본 지급여력비율`, `조정자기자본비율`)
   - 경과조치 전 행, RBC 행, 보통주·기본자본비율 행
2. **열**: 표의 **첫 번째 값 열**만 쓰고, 그 열 머리가 보고서 기간과 맞아야 한다.
   - 기간 종류(1분기·반기·3분기·연간)와 연도를 본다. `제77기 반기`, `2026년 6월 말`, `FY2026 2Q`, `2026.06`, `'26년2분기말` 모두 알아본다.
   - `제N기` 표는 첫 열의 N이 표 안에서 가장 커야 한다.
   - 3월 결산 회사(신영증권)는 financials_fin.period_type(1분기 등)으로 맞추고 연도는 ±1년을 허용한다.
   - 열 머리가 기간이 아니면 표 제목의 기준일(`기준일 : 2026.06.30`)을 본다.
3. **섹션 순위**: `재무건전성 등 기타 참고사항` → `이사의 경영진단` → 나머지 순서다.
   - 재무제표 주석(0.1478 같은 소수 표기), 임원 보수, 감사 섹션은 쓰지 않는다.
   - 정정 공시의 `정정 전·후` 대조 청크도 쓰지 않는다.
4. **같은 순위 안**: 보고서 앞쪽 표를 쓴다. 지주·연결 표가 자회사·지배회사(별도) 표보다 앞에 온다.
   - 다른 후보 값은 `alternatives`에 남긴다.
5. **corroborated**: 같은 값이 보고서의 다른 곳(다른 표·본문 문장)에도 나오면 표시한다.
6. **provisional**: 표 뒤 주석에 `잠정`이 있으면 표시한다. 값은 그대로 쓰고, 정정 공시가 수집되면 다시 실행해 바뀐다.
7. **범위 밖이면 NULL + `needs_review`**: BIS 1~60, K-ICS 10~3,000, NCR 10~99,999.
8. **못 찾으면 NULL + `extract_failed`**: 정기보고서 본문이 수집되지 않은 기간도 같다 (사유: `정기보고서 본문 미수집`).
9. 이미 저장된 값은 NULL로 덮지 않는다. 바뀐 것이 없는 행은 UPDATE하지 않는다.

## 3. 실행

```bash
PYTHONPATH=backend python -m pipelines.disclosures.run_financial_ratios --dry-run   # 읽기 전용, 결과 파일만
PYTHONPATH=backend python -m pipelines.disclosures.run_financial_ratios             # financials_fin UPDATE
```

결과는 `data/financials_ratios/`에 남는다 (git 제외).

- `results.json`: 행별 값과 출처(rcept_no, 청크 번호, 행 이름, 열 머리, 잠정 여부, 다른 후보 값)
- `review.csv`: 검토할 것
  - 추출 실패
  - uncorroborated 값
  - 직전 분기 대비 큰 변동: BIS ±3%p, K-ICS ±60%p, NCR ±50%
- `summary.json`: 컬럼별 값·사유 건수

새 정기보고서가 수집된 뒤 다시 실행하면 새 기간이 채워지고, 잠정치는 정정본 값으로 바뀐다.

## 4. 2026-11-06 중앙 DB dry-run 결과

financials_fin 780행 중 값이 채워진 것은 다음과 같다.

| 컬럼 | 값 |
|---|---|
| bis_ratio | 103 |
| kics_ratio | 106 |
| ncr_ratio | 165 |

- 본문이 있는 보고서는 모두 값을 찾았다.
- NULL 164건은 모두 `정기보고서 본문 미수집`이다.
  - 2023년 152건: 본문 수집이 최근 10개 보고서까지라서 빠졌다.
  - 하나금융지주 2025~, 유안타증권 2025-06~: 본문 수집이 빠져 있다. 별도 확인이 필요하다.
- 사업보고서 값 75건은 모두 다음 해 보고서의 전기 열 값과 일치했다.
- 큰 변동 2건은 실제 변동이다.
  - 대신증권 2026 반기 NCR 385.0 → 682.1: 본문에도 682.1% 기재.
  - 케이뱅크 2026 1분기 BIS 14.52 → 21.47: 상장 자본 확충.

남은 일:
- 다올투자증권은 fin_type이 `other`라 비율을 채우지 않는다. 증권사이므로 `securities`로 분류를 고치면 NCR이 채워진다.
- 기존 `financials_pipeline`의 `bis` 단계(KB금융 4개사 파이프라인)는 그대로 두었다.
