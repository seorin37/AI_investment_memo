# AI Investment Memo (memo's)

국내 주식 투자 분석을 위한 데이터 수집·가공·저장 프로젝트입니다.

PostgreSQL과 pgvector를 기반으로 주가, 시장지수, 거시경제지표, 뉴스, DART 공시 및 재무제표 데이터를 관리합니다.

## 1. 개발 환경

- Python 3.11
- Conda 환경: `ai_memo`
- PostgreSQL 16 + pgvector (Docker)
- SQLAlchemy / Alembic
- BGE-M3 (FlagEmbedding)
- GPU 임베딩 지원 (CUDA)

### 환경 설치

```bash
conda env create -f environment.yml
conda activate ai_memo
```

현재 통합 테스트에서 사용한 주요 버전:

| 패키지 | 버전 |
|---|---|
| FlagEmbedding | 1.4.2 |
| transformers | 4.51.3 |
| PyTorch | 2.5.1+cu121 |
| exchange-calendars | 4.13.2 |
| Python | 3.11 |

PyTorch의 CUDA 빌드는 `environment.yml`에서 별도로 고정하지 않았습니다.

GPU 환경에서는 NVIDIA 드라이버와 CUDA 호환성을 확인하고, PyTorch 공식 설치 안내에 따라 적절한 빌드를 설치해야 합니다.

설치 후 확인:

```bash
python -m pip check
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

## 2. 환경변수

저장소 루트의 `.env`에 DB 연결 및 외부 API 인증 정보를 설정합니다.

주요 환경변수:

- `DATABASE_URL`: SQLAlchemy DB 연결 URL
- `POSTGRES_USER`: PostgreSQL 사용자
- `POSTGRES_PASSWORD`: PostgreSQL 비밀번호
- `POSTGRES_DB`: 기본 DB 이름
- `POSTGRES_PORT`: 호스트 연결 포트
- `DART_API_KEY`: OpenDART API 키

뉴스 및 경제지표 파이프라인의 추가 API 인증 변수는 해당 모듈의 설정을 확인합니다.

`.env`와 API 키, 비밀번호는 Git에 커밋하지 않습니다.

## 3. PostgreSQL 실행

Docker Compose 설정은 `docker-compose.yml`을 사용합니다.

```bash
docker compose up -d
docker compose ps
```

DB 컨테이너 이름은 `memos-db`입니다.

최초 DB 생성 및 마이그레이션 적용:

```bash
alembic upgrade head
alembic current
alembic heads
```

주의: Alembic 명령은 현재 `DATABASE_URL`이 가리키는 DB에 적용됩니다. 실행 전에 DB 연결 대상을 반드시 확인해야 합니다.

기존 DB의 Docker 볼륨을 삭제하거나 초기화하지 마세요.

## 4. 데이터 파이프라인

모든 명령은 저장소 루트에서 실행합니다.

### 마켓 데이터

위치:

`backend/pipelines/market/`

주요 데이터:

- 국내 개별 종목 OHLCV
- KOSPI / KOSDAQ 지수
- KRX 금 가격

`pipeline.py`에는 백필 함수들이 정의되어 있습니다.

**주의:** `python backend/pipelines/market/pipeline.py`를 직접 실행하면 코드에 지정된 2020~2026년 과거 데이터 수집이 시작됩니다.

테스트할 때는 Python에서 백필 함수를 명시적인 날짜 범위와 종목 목록으로 호출합니다.

### 경제지표

위치:

`backend/pipelines/economic/`

주요 함수:

- `backfill_ecos()`
- `backfill_fred()`

ECOS 및 FRED API를 이용해 경제지표를 수집합니다.

경제 파이프라인은 호출할 기간과 상태 저장 경로를 지정해 Python에서 실행합니다.

### 뉴스

위치:

`backend/pipelines/news/`

일반 실행 명령:

```bash
PYTHONPATH=backend python -m pipelines.news.pipeline hourly
```

```bash
PYTHONPATH=backend python -m pipelines.news.pipeline daily
```

주요 옵션:

- `--variant hybrid`: Dense + Sparse 임베딩
- `--variant dense`: Dense 임베딩
- `--skip-embed`: 임베딩 생략
- `--skip-naver`: 네이버 API 수집 생략
- `--embed`: hourly에서 임베딩 실행
- `--loop 1800`: 1,800초 간격 반복 실행

뉴스 파이프라인은 기사 저장, 종목 태깅, BGE-M3 임베딩을 처리합니다.

`daily` 실행은 기사 보존 정책에 따라 정리 작업이 수행될 수 있으므로 운영 DB에서 실행하기 전에 옵션을 확인해야 합니다.

### DART 정기보고서

위치:

`backend/pipelines/disclosures/`

Dense 모드:

```bash
PYTHONPATH=backend python -m pipelines.disclosures.run_dense \
  --config configs/common.yaml \
  --mode-config configs/dense.yaml \
  --symbols 005930 \
  --limit 1
```

Hybrid 모드:

```bash
PYTHONPATH=backend python -m pipelines.disclosures.run_hybrid \
  --config configs/common.yaml \
  --mode-config configs/hybrid.yaml \
  --symbols 005930 \
  --limit 1
```

처리 단계:

`collect → parse → chunk → load → embed → validate`

`--steps`를 이용해 필요한 단계만 실행할 수 있습니다.

예:

```bash
PYTHONPATH=backend python -m pipelines.disclosures.run_dense \
  --config configs/common.yaml \
  --mode-config configs/dense.yaml \
  --symbols 005930 \
  --limit 1 \
  --steps collect,parse,chunk,load
```

`--limit 1`은 처리 문서 상한이며, DART 목록 조회나 원문 다운로드 횟수를 반드시 1회로 제한하는 것은 아닙니다.

### DART 재무 데이터

위치:

`backend/pipelines/disclosures/`

```bash
PYTHONPATH=backend python -m pipelines.disclosures.run_financials \
  --config configs/common.yaml \
  --mapping configs/financials_mapping.yaml \
  --symbols 005930 \
  --steps collect,load,validate
```

처리 단계:

`collect → load → bis → validate`

`bis`는 금융기업의 총자본비율 후처리 단계입니다.

재무 파이프라인에는 별도 기간 제한 CLI 옵션이 없으므로, 테스트할 때는 전용 YAML 설정에서 대상 기간을 제한해야 합니다.

## 5. 테스트 실행

공시 및 재무 단위 테스트 예시:

```bash
PYTHONPATH=backend python -m pytest -q \
  backend/tests/test_disclosure_chunker.py \
  backend/tests/test_disclosure_parser.py \
  backend/tests/test_disclosure_embedder.py \
  backend/tests/test_financials_mapping.py
```

일부 테스트는 실제 DB에 접근해 쓰기 작업을 수행합니다.

따라서 DB 테스트는 운영 DB가 아닌 독립 테스트 DB를 대상으로 실행해야 합니다.

### 테스트 DB 사용 원칙

통합 테스트에서는 별도 DB `memos_integration_test`를 사용했습니다.

테스트를 실행하기 전에 다음 사항을 확인합니다.

1. `DATABASE_URL`이 테스트 DB를 가리키는지 확인
2. 테스트 DB에 Alembic 최신 마이그레이션 적용
3. 테스트용 설정으로 파일 산출물 경로 분리
4. 운영 DB의 테이블·데이터 및 Docker 볼륨을 임의로 초기화하지 않기

로컬 통합 테스트용 `configs/integration_test.yaml`은 팀 공통 운영 설정과 분리해서 관리합니다.

## 6. 통합 검증 기록 (2026-10-23)

`dev2` 통합 테스트 환경에서 다음 항목을 확인했습니다.

| 구분 | 검증 결과 |
|---|---|
| KRX 개별 종목 주가 | 수집·적재 성공 |
| KOSPI / KOSDAQ 지수 | 수집·적재 성공 |
| KRX 금 가격 | 수집·적재 성공 |
| ECOS / FRED | 수집·적재 성공 |
| 뉴스 | 기사 저장·종목 태깅 성공 |
| 뉴스 BGE-M3 | Hybrid 임베딩 1건 성공 |
| DART 공시 | 삼성전자 보고서 1건, 청크 622개 적재 |
| 공시 BGE-M3 | Dense 임베딩 2개 성공 |
| DART 재무 | 삼성전자 2024년 1분기 적재 성공 |
| 재무 검증 | 10개 통과, 경고 1개 |
| 선택된 공시·재무 테스트 | 68개 통과 |

이 결과는 제한된 범위의 통합 테스트이며, 모든 종목·기간·운영 시나리오의 검증 완료를 의미하지는 않습니다.

## 7. 후속 점검 사항

- 공시 `embed_pending()`의 전체 배치 적재 및 재시작 테스트
- 운영 환경별 CUDA PyTorch 설치 절차 확인
- 파이프라인별 실행 의존성 및 환경변수 정리
- 마켓 대량 백필을 방지하는 안전한 CLI 구성
- 뉴스 수집·보존 정책과 반복 실행 설정 검토
- DART 원문 수집 시 `--limit` 적용 범위 개선 검토
- 다양한 종목과 기간에 대한 데이터 품질 검증
