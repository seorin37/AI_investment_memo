#!/usr/bin/env bash
# 테스트 DB(.env.test의 TEST_DATABASE_URL)로만 명령을 실행한다.
#   scripts/with_test_db.sh alembic upgrade head
#   scripts/with_test_db.sh python -m backend.pipelines.news.pipeline hourly --cluster
# 이 명령 안에서만 DATABASE_URL·READONLY_DATABASE_URL·ALEMBIC_DATABASE_URL을 테스트 DB로 덮어쓴다.
# 코드는 load_dotenv 기본값(기존 환경변수 유지)을 쓰므로 .env의 중앙 DB 주소보다 이 값이 우선한다.
# 접속 주소가 127.0.0.1:5433(테스트 DB 컨테이너)이 아니면 실행하지 않는다. 비밀번호는 출력하지 않는다.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
env_file="${TEST_ENV_FILE:-$repo_root/.env.test}"
allowed_host="127.0.0.1"
allowed_port="5433"

if [[ $# -eq 0 ]]; then
  echo "사용법: scripts/with_test_db.sh <명령> [인자...]" >&2
  exit 2
fi
if [[ ! -f "$env_file" ]]; then
  echo "$env_file 이 없습니다. TEST_DATABASE_URL=... 한 줄을 넣어 만드세요." >&2
  exit 1
fi

url="$(grep -E '^TEST_DATABASE_URL=' "$env_file" | tail -n 1 | cut -d= -f2- || true)"
url="${url%$'\r'}"
url="${url#\"}"; url="${url%\"}"
if [[ -z "$url" ]]; then
  echo "$env_file 에 TEST_DATABASE_URL이 없습니다." >&2
  exit 1
fi

# 주소를 scheme / host / port로 나눠 테스트 DB인지 확인한다 (비밀번호는 다루지 않음).
if [[ ! "$url" =~ ^(postgres(ql)?)(\+[a-z0-9]+)?://[^@/]+@([^:/]+):([0-9]+)/[^/?]+ ]]; then
  echo "TEST_DATABASE_URL 형식을 알 수 없습니다 (postgresql://계정:비밀번호@호스트:포트/DB)." >&2
  exit 1
fi
host="${BASH_REMATCH[4]}"
port="${BASH_REMATCH[5]}"
if [[ "$host" != "$allowed_host" || "$port" != "$allowed_port" ]]; then
  echo "테스트 DB가 아닙니다 (${host}:${port}). ${allowed_host}:${allowed_port}만 허용합니다." >&2
  exit 1
fi

# SQLAlchemy(alembic)가 psycopg(v3)를 쓰도록 드라이버를 명시한다. psycopg 코드 쪽은 get_dsn()이 접미사를 뗀다.
sa_url="$(printf '%s' "$url" | sed -E 's#^postgres(ql)?(\+[a-z0-9]+)?://#postgresql+psycopg://#')"

export DATABASE_URL="$sa_url"
export READONLY_DATABASE_URL="$sa_url"
export ALEMBIC_DATABASE_URL="$sa_url"
unset POSTGRES_HOST POSTGRES_PORT POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB

echo "[with_test_db] 테스트 DB ${host}:${port} 로 실행: $*" >&2
cd "$repo_root"
exec "$@"
