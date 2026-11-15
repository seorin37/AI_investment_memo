# 재무 결산월 오판 수정 (2026-11-13)

`financials`의 결산월이 공시 목록과 다른 회사가 있었다. 분기 단독 테이블(0016) 점검 중에 8곳이 드러났고, 전체를 다시 보니 23곳이다.

## 원인

`run_financials_all.fy_end_month()`는 DART 기업개황(company.json)의 `acc_mt`만 믿었다. 대상 기간과 보고서 코드(q1·half·q3·annual → 11013·11012·11014·11011)를 모두 이 값으로 정했다.

| 유형 | 회사 | acc_mt가 틀린 이유 | 잘못 저장된 결과 |
|---|---|---|---|
| 결산월 변경 | 001080 MH머트리얼즈 | 결산월을 12월 → 6월로 바꿨는데 acc_mt는 12. 공시는 사업보고서 2024.06·2025.06·2026.06 | 2024-06-30을 half로 저장. 값은 `2024_11012` 응답, 즉 2024.12 반기보고서(제73기)라서 모든 기간이 3~6개월 어긋남 |
| 6개월 결산 리츠 (18곳) | 334890·338100·357120·357250·400760·404990 외 12곳 (088260·293940·330590·348950·350520·357430·365550·377190·396690·432320·451800·481850) | 사업보고서가 6개월마다(예: 5·11월), 그 사이에 반기보고서가 나옴. acc_mt는 둘 중 하나만 표시 | 반기보고서(3개월치)가 3개월 앞선 날짜의 half로, 6개월치 사업보고서가 annual로 들어감 |
| 3개월 결산 리츠 (4곳) | 0030R0·395400·417310·448730 | 사업보고서가 3개월마다 | 1년에 annual 한 건만 들어가고 나머지는 빈칸 |

확인 근거:
- 공시 목록(`data/raw/dart/reports.json`)
- 재무 원본 캐시의 `rcept_no`
- 주식 총수 캐시의 `rcept_no`

예를 들어 400760의 `2024_11012` 응답은 rcept 20241114001843, 곧 2024.09 반기보고서다. 그런데 2024-06-30 half로 저장돼 있었다.

추가로 확인한 점:
- **DART 재무 API(fnlttSinglAcntAll)는 사업연도·보고서 코드마다 한 건만 돌려준다.** 6·3개월 결산 리츠는 같은 해의 사업보고서 2건 중 나중 것만 받을 수 있다. 그래서 결산월을 맞춰도 보고서의 절반은 구조적으로 받을 수 없다.
- **주식 총수 API(stockTotqySttus)는 재무 API와 보고서를 다르게 고른다.** MH머트리얼즈의 `2024_11013`은 2024.03 보고서이고 `2024_11014`는 2024.09 보고서로, 재무 API와 반대다. DART 기업개황의 옛 결산월(12월)을 따르는 것으로 보인다.

## 수정 (`run_financials_all.py`)

1. **결산월 판정 `fiscal_basis()`**: 공시 목록을 우선한다. 공시 목록은 DB `disclosures`와 `reports.json`을 합친 것이다.
   - run_all의 `select_window_candidates`와 같은 규칙을 쓴다. 가장 최근 사업보고서의 기간 월, 없으면 반기보고서 월 + 6, 목록이 비면 acc_mt.
   - 결산 주기는 `dart.fiscal_cycle`(12·6·3)로 정한다.
   - acc_mt와 다르면 state에 `fiscal_note`, summary에 `fiscal_notes`를 남긴다.
2. **6·3개월 결산 리츠는 재무를 저장하지 않는다**(사용자 결정 2026-11-13).
   - state에 `status: done`, `excluded: fiscal_cycle_6|3`을 남긴다. summary에는 `excluded`로 나온다.
   - financials에 행이 없으므로 분기 테이블에도 자동으로 빠진다. 기업 페이지에서 이 리츠들의 재무는 빈칸이 된다.
3. **응답 교차 검증**: 재무 API 응답의 `rcept_no`가 공시 목록상 다른 기간이면 그 기간을 버리고 failed.csv(검증)에 남긴다.
   - 전체 캐시로 대조한 결과: 일치 7,961건, 불일치 0건, 목록에 없는 접수번호 7건(정정 전 원본 등, 통과시킴).
4. **주식 총수 `pick_shares()`**: 기본 파일이 다른 기간 보고서면 같은 종목 캐시 중 대상 기간 파일을 쓰고, 없으면 쓰지 않는다.
5. **새 옵션**:
   - `--force`: done 상태 기업도 다시 처리한다.
   - `--through YYYY-MM-DD`: 대상 기간 끝을 늘리고 개수 제한 없이 받는다(정기 수집과 같은 방식).
6. **`run_periodic_updates`**: 새벽 정기 수집의 재무 단계도 같은 `fiscal_basis`를 쓴다. 제외 리츠는 대기 목록에서 빼고, summary `financials.excluded`에 남긴다.

결산월이 바뀌는 회사는 전체 829곳 중 001080 한 곳뿐이다. 12개월 결산 회사의 기간·보고서 코드는 그대로다.

테스트: `backend/tests/test_run_financials_all.py`에 FiscalBasisTest·PickSharesTest·ProcessCompanyFiscalTest를 추가했다.

## 테스트 DB 확인 (127.0.0.1:5433, 2026-11-13)

`scripts/sql/fix_fiscal_month_20261113.sql`로 23곳을 지웠다. 그다음 아래 명령으로 다시 적재했다.

```
run_financials_all --symbols <23곳> --force --through 2026-09-30
```

- MH머트리얼즈: 대상 11개 기간이 모두 공시 목록의 기간 구분과 같다. 2024-03-31 q3, 2024-06-30 annual, 2024-09-30 q1, 2024-12-31 half … 2026-09-30 q1. 전기 4행(2023)이 함께 들어간다.
  - 2026-06-30 annual부터 연결(consolidated)로 바뀐다. 그래서 그해 Q4 단독값은 `fs_div_mismatch`로 NULL이다. 정상 동작이다.
- 리츠 22곳: financials·financials_fin·분기 행 0건.
- `run_financials_quarterly --check`: 합계 불일치 0건(일반 264행, 금융 145행).

## 중앙 DB 반영 (사용자가 실행)

**먼저 할 일**: 이 수정을 새벽 정기 수집이 도는 체크아웃(`C:\projects\AI_investment_memo`)에 반영한다. 반영하지 않으면 다음 공시 때 옛 코드가 MH머트리얼즈·리츠 행을 다시 잘못 쓴다. 02:00 수집이 끝난 뒤에 실행한다.

0) 지금 상태 확인 (읽기 전용). 2026-11-13 기준 financials 154, financials_fin 9, financials_quarterly 154, financials_fin_quarterly 9행이다.

```sql
SELECT 'financials' t, count(*) FROM financials WHERE symbol IN ('001080','0030R0','088260','293940','330590','334890','338100','348950','350520','357120','357250','357430','365550','377190','395400','396690','400760','404990','417310','432320','448730','451800','481850')
UNION ALL SELECT 'financials_fin', count(*) FROM financials_fin WHERE symbol IN ('0030R0','481850');
```

1) 잘못된 행 삭제 (한 트랜잭션). 23곳의 financials·financials_fin·두 분기 테이블 행을 지운다.

```bash
psql "postgresql://<계정>@192.168.0.105:15432/<DB>" -f scripts/sql/fix_fiscal_month_20261113.sql
```

2) 다시 적재 (저장소 루트, .env가 중앙 DB). 리츠는 excluded로 끝나 행이 생기지 않는다. DART 호출은 캐시 덕분에 1~2회뿐이다.

```bash
PYTHONPATH=backend python -m pipelines.disclosures.run_financials_all --symbols 001080,0030R0,088260,293940,330590,334890,338100,348950,350520,357120,357250,357430,365550,377190,395400,396690,400760,404990,417310,432320,448730,451800,481850 --force --through 2026-09-30
```

3) 검증

```bash
PYTHONPATH=backend python -m pipelines.disclosures.run_financials_quarterly --check
```

- `sums_mismatched`가 0이어야 한다.
- financials에는 001080만 15행이어야 한다(기간 11 + 전기 4). 나머지 22곳은 0행이다.
- `data/run_financials/summary.json`의 `excluded`가 22곳이어야 한다.

참고: MH머트리얼즈 2026.09 1분기의 옛 캐시 `001080_2026_11013_{CFS,OFS}.json`은 공시 전에 받은 013(자료 없음)이었다. 이 캐시는 테스트 중에 치웠고(공유 data 폴더), CFS를 다시 받아 두었다. 따라서 2)에서 추가 작업은 없다.
