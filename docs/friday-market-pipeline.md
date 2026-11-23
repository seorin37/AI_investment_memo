# 금요일 시장데이터 운영 파이프라인

## 확정 흐름

1. 금요일 20:00 기존 KIS Capture가 현재가 응답과 EPS/BPS 원본을 파일로 고정한다.
2. 토요일 08:00 `collect_friday_market_data.py saturday-auto`가 직전 금요일 KRX 응답을 한 번 받아 원문과 SHA-256을 보존한다. 종목 집합과 가격을 검증한 뒤 `prices_daily`에는 `KRX_OPEN_API` 원시 행을, `stock_fundamentals_snapshot`에는 KIS 원본 PER/PBR 및 EPS/BPS와 확정 종가 기반 `analysis_per`/`analysis_pbr`을 한 트랜잭션으로 저장한다.
3. 월요일 08:00 `collect_friday_market_data.py monday-auto`가 토요일 원본 SHA와 DB 행을 먼저 확인한다. KIS 원시 행은 KRX 검증에만 쓰고, `FID_ORG_ADJ_PRC=0` 수정 행만 `adjusted_prices_daily`에 `source=KIS`로 저장한다.

금요일 상태 파일은 `logs/market/friday_finality_v1/<거래일>/`에 보존한다. 기존 평일 Finalize 마커와 이름·경로를 공유하지 않는다.

## 실패와 재개

- DB 장애 전에 KRX 원본을 받았다면 복구 실행은 그 원본과 SHA를 재사용하며 KRX를 다시 호출하지 않는다.
- DB 행이 이미 있으면 모든 핵심 값과 공급원이 같을 때만 완료로 인정한다. 값이나 공급원이 다르면 덮어쓰지 않고 충돌로 중단한다.
- 월요일은 성공 종목별 응답과 SHA를 체크포인트로 남긴다. 재실행은 완료 종목의 파일과 DB 상태를 확인하고 실패 종목만 조회한다.
- 자동 타이머는 `Persistent=false`다. 지연 복구는 과거의 실제 금요일 거래일을 명시해야 한다.

```bash
PYTHONPATH=backend .venv/bin/python scripts/collect_friday_market_data.py \
  saturday-recovery --trade-date YYYY-MM-DD

PYTHONPATH=backend .venv/bin/python scripts/collect_friday_market_data.py \
  monday-recovery --trade-date YYYY-MM-DD
```

두 명령 모두 `FRIDAY_MARKET_PIPELINE_ENABLED=true`와 공통 advisory lock이 필요하다.

## 배포 순서

운영 DB와 systemd는 별도 승인 후 다음 순서로 적용한다.

```bash
# 1. 백업 및 migration SQL 검토 후
PYTHONPATH=backend .venv/bin/alembic upgrade 0024_friday_fundamental_ratios

# 2. 코드 단위·회귀 테스트
PYTHONPATH=backend .venv/bin/python -m pytest -q \
  backend/tests/test_friday_market_pipeline.py \
  backend/tests/test_kis_fundamentals_staging.py \
  backend/tests/test_daily_refresh.py

# 3. unit 계획만 확인(아무것도 설치하지 않음)
bash scripts/install_friday_market_pipeline_timer.sh

# 4. 승인 후에만 설치
bash scripts/install_friday_market_pipeline_timer.sh --apply
```

설치되는 타이머는 토요일·월요일 08:00이며 둘 다 `Persistent=false`다. 월요일 서비스 timeout은 55분이지만 코드가 08:45 이후 새 요청을 시작하지 않는다. 기존 Capture, 평일 Finalize, Morning timer는 설치 스크립트가 변경하지 않는다.

## 상장폐지와 무거래 종목

- 검토된 `configs/kis_symbol_status.json`의 종료 상태만 상장폐지 예외 근거로 사용한다.
- 종료 효력일부터 새 가격행을 만들지 않으며 0원 센티널을 가격으로 저장하지 않는다.
- 거래량 0일 때 KRX O/H/L=0은 원시 테이블에 그대로 보존한다.
- 월요일 검증에서는 KRX O/H/L=0, KIS O/H/L=종가 차이를 종가·거래량·날짜·종목 및 KIS 원시/수정 행이 모두 일치할 때만 표현 차이로 허용한다.
