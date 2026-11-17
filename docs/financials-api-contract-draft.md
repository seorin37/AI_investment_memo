# 기업정보 페이지 재무 API 계약 초안 (API·프론트 담당 전달용)

작성: 이민성 · 2026-11-16 · 근거: docs/company-page-data-gaps-plan.md (결정 기록)

데이터 파이프라인(0016·0017)은 준비됐다. 이 문서는 API가 어느 테이블을 어떻게 읽어 화면에 내려 줄지에 대한 제안이다. 계산은 이미 DB에 저장돼 있으니 **API는 읽기만** 한다.

## 1. 테이블

| 테이블 | 한 행 | 쓰는 곳 |
|---|---|---|
| `financials_quarterly` | 회사 × 분기(period_end). 분기 단독 매출·영업이익·순이익 | 실적 차트 6분기 |
| `financials_fin_quarterly` | 금융사 분기 단독 순이자이익·수수료이익·보험수익·증권 영업수익 | (화면 미사용, 저장만) |
| `financial_metrics` | 회사 × 보고 기간(financials와 같은 period_end) | 수익성 차트(분기 이익률·ROE), 건전성 레이더 |
| `financials` | 원본 누적값·잔액 | 기준 문구(fs_div), 필요 시 원본 |
| `stocks` | sector('general'·'financial'), fin_type, description | 개요, 업종 분기 |

공통:
- `null_reasons` jsonb: 값이 NULL인 컬럼의 사유 코드. 화면 표시는 하지 않고 디버깅·추후 안내용으로 내려 준다.
- 기간 키는 `period_end`(분기 말일)다. 결산월이 12월이 아닌 회사도 있으니 화면 라벨은 period_end로 만든다(예: '2026.09').

## 2. `GET /stocks/{code}/financials` 제안

```jsonc
{
  "code": "005930",
  "sector": "general",            // 'general' | 'financial'
  "fin_type": null,               // 금융사: bank | insurance | securities | holding | other
  "basis": "2026년 09월 기준 · 연결재무제표",   // fs_div(consolidated|separate) + 최신 period_end
  "quarters": [                   // 최근 6분기 + 전년 동기 비교용 4분기 (오래된 순)
    {
      "period_end": "2026-09-30",
      "revenue": 79100000000000,          // financials_quarterly. 금융사는 null (화면에서 매출 항목 뺌)
      "operating_income": 12000000000000,
      "net_income": 9800000000000,
      "operating_margin": 15.17,          // financial_metrics (%). 금융사는 내려 보내지 않음
      "net_margin": 12.39,
      "roe": 10.14                        // TTM 기준 (%)
    }
  ],
  "stability": {                  // 최신 보고 기간의 financial_metrics
    "as_of": "2026-09-30",
    "debt_ratio": 29.94,
    "current_ratio": 232.76,      // 금융사 null
    "quick_ratio": 183.30,        // 금융사 null
    "interest_coverage": 92.82,   // 금융사는 내려 보내지 않음 (값은 DB에 있음)
    "interest_coverage_basis": "cf_paid",   // income_statement | cf_adjustment | cf_paid
    "reserve_ratio": 45296.17
  },
  "null_reasons": { "stability.reserve_ratio": "source_null" }
}
```

### 규칙
1. **모든 숫자 필드는 `number | null`이다. null이면 화면에서 그 항목을 뺀다**(기획 파트 2026-11-16). 레이더는 남은 축만 그린다.
2. **금융사(`sector='financial'`)** 화면에서 빼는 항목은 null로 내려 보낸다(DB 값이 있어도): `revenue`, `operating_margin`, `net_margin`, `current_ratio`, `quick_ratio`, `interest_coverage`. 남는 항목은 영업이익·순이익·ROE·부채비율·유보율이다.
3. `interest_coverage_basis = 'cf_paid'`면 화면에 "현금 이자지급 기준" 각주를 단다. 대부분의 일반 기업(테스트 표본 14곳 중 9곳)이 여기에 해당한다.
4. 전년 동기 대비 증감률은 API에서 계산한다: (이번 분기 - 1년 전 같은 분기) / |1년 전 분기| × 100. 1년 전 분기가 없거나 0이면 null.
5. 비율 공식은 DB(financial_metrics 컬럼 주석, `backend/pipelines/disclosures/financial_metrics.py` 맨 위 표)가 기준이다. API에서 다시 계산하지 않는다.

### 쿼리 예시
```sql
-- 최근 10분기 (6분기 표시 + 전년 동기 4분기)
SELECT q.period_end, q.revenue, q.operating_income, q.net_income, m.operating_margin, m.net_margin, m.roe
FROM financials_quarterly q LEFT JOIN financial_metrics m USING (symbol, period_end)
WHERE q.symbol = :code ORDER BY q.period_end DESC LIMIT 10;

-- 건전성: 최신 보고 기간
SELECT * FROM financial_metrics WHERE symbol = :code ORDER BY period_end DESC LIMIT 1;
```

## 3. 프론트 변경 필요 사항
- `frontend/src/types/models.ts`: `AnnualFinancial` → 분기 단위로 바꾸고 모든 숫자 필드를 `number | null`로 바꾼다. `Stability`도 nullable로 바꾸고 `interest_coverage_basis`를 추가한다.
- `CompanyInfo.tsx`: null 항목을 걸러 레이더 축·수익성 선·실적 막대를 그린다. 항목이 빠졌을 때의 레이아웃은 프론트 담당이 정한다.
- `frontend/docs/API_CONTRACT.md` 91행 "연간 7개년"을 "최근 6분기(+ 비교 4분기)"로 고친다.

## 4. `GET /stocks/{code}/profile`
- `overview` = `stocks.description` (825곳 적재 완료). 우선주 111곳은 본주 개요 복사 예정이다. 그 전까지 null이면 "기업 개요를 준비 중이에요."로 표시한다.
