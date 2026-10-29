# KIS 개별 종목 마켓데이터 정책

## 공급원 경계

- 파일럿 4종목의 원시 OHLCV·거래대금은 KIS
  `inquire-daily-itemchartprice`의 KRX 시장(`J`),
  `FID_ORG_ADJ_PRC=1`을 사용한다.
- 수정 OHLCV는 같은 API의 `FID_ORG_ADJ_PRC=0`을 사용한다.
- PER·PBR·EPS·BPS, 52주 고저가·달성일, 현재 시가총액과 상장주식수는
  KIS `inquire-price` 응답을 그대로 스냅샷으로 보존한다.
- KRX Open API는 종목 기본정보, KOSPI/KOSDAQ 지수와 금에 계속 사용한다.
- ECOS·FRED·DART 공급원은 변경하지 않는다.

`prices_daily.source`는 OHLCV 공급원을 뜻한다. 기존 KRX 행은
`KRX_OPEN_API`, 신규 KIS 행은 `KIS`다. 과거 KRX의 시가총액·상장주식수를
KIS OHLCV 갱신 과정에서 지우지 않으며, 그 출처는
`market_metadata_source`로 별도 구분한다.

과거 일별 시가총액·상장주식수는 KRX KOSPI 일별매매정보를 거래일당 한 번
호출해 파일럿 종목의 `MKTCAP`, `LIST_SHRS`만 추출한다. KRX OHLCV는 읽거나
저장하지 않는다. `source='KIS'` 가격 행이 이미 있을 때만 해당 메타데이터를
UPDATE하며, 가격 행이 없는 키는 NOT NULL OHLCV 제약 때문에 단독 INSERT하지
않고 보류 목록으로 남겨 다음 실행에서 다시 결합한다.

## 과거 시가총액·상장주식수

KIS 기간별 일봉의 `output2`에는 과거 일별 시가총액과 상장주식수가 없다.
따라서 KIS 신규 일봉에 이를 추정하거나 현재값으로 소급 채우지 않는다. 과거
일별 값은 위 KRX 메타데이터 단계로 결합하고, `inquire-price`가 반환한 최신
값은 `stock_fundamentals_snapshot`에도 별도 저장한다.

## 확정 가격과 투자지표

서비스 가격은 `prices_daily` 또는 `adjusted_prices_daily`의 최신 확정 일봉을
사용한다. `inquire-price` 자체에는 가격 기준 거래일이 없으므로, 현재가
`stck_prpr`가 별도로 조회한 최신 확정 KIS 원시 종가와 정확히 일치할 때만
스냅샷을 저장한다. 이전 거래일을 기준으로 수집하면서 당일 누적거래량이 이미
발생했다면 장중 스냅샷으로 보고 저장을 보류한다. 같은 스냅샷의 `final_close`와
`basis_trade_date`가 확정 일봉 기준이다.

KIS가 0으로 반환한 PER/PBR과 미제공(NULL)은 구분한다. EPS/BPS는 적자·자본
상태를 보존하기 위해 음수를 허용한다. API가 제공하지 않은 값은 생성하지 않는다.

## 수정주가 재동기화

일일 실행은 최근 35일을 다시 조회한다. 기업행동이 과거 값 전체를 소급 변경할
수 있으므로 지정 요일마다 파일럿 종목 하나를 순환하여 2020-01-01 이후 수정
일봉을 전체 재동기화한다. 원시 일봉은 이 전체 재동기화 대상이 아니다.

종목 하나의 원시·수정 응답이 모두 정상화된 뒤에만 UPSERT한다. 빈 응답, 잘못된
OHLC, API 오류가 있으면 해당 종목의 기존 정상 데이터를 유지하고 다른 종목은
계속 처리한다.

## 운영 활성화 순서

1. `0011_kis_market_data` migration 검토·적용
2. `scripts/collect_kis_market_data.py`로 파일럿 백필
3. 중복·결측·OHLCV·2018년 삼성전자 분할 검증
4. `.env`에서 `DAILY_REFRESH_KIS_ENABLED=true` 설정

기본값은 false다. 활성화 상태에서도 코드가 0011 컬럼과 테이블을 찾지 못하면
외부 KIS 호출 전에 실패하므로 기존 KRX 지수·금·ECOS·FRED 단계는 계속된다.
