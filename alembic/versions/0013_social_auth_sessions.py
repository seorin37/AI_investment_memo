"""Social OAuth transactions, one-time exchanges, and refresh sessions.

Revision ID: 0013_social_auth_sessions
Revises: 0012_financials_sector_columns
Create Date: 2026-11-04
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0013_social_auth_sessions"
down_revision: Union[str, Sequence[str], None] = "0012_financials_sector_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = """
CREATE TABLE oauth_transactions (
  state_hash text PRIMARY KEY,
  provider text NOT NULL CHECK (provider IN ('google', 'kakao', 'naver')),
  client_type text NOT NULL CHECK (client_type IN ('web', 'mobile')),
  return_to text NOT NULL,
  provider_redirect_uri text NOT NULL,
  provider_code_verifier text,
  oidc_nonce text,
  app_code_challenge text,
  expires_at timestamptz NOT NULL,
  consumed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (
    (client_type = 'mobile' AND app_code_challenge IS NOT NULL)
    OR (client_type = 'web' AND app_code_challenge IS NULL)
  )
);

CREATE TABLE auth_exchange_codes (
  code_hash text PRIMARY KEY,
  user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  code_challenge text NOT NULL,
  expires_at timestamptz NOT NULL,
  used_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE auth_sessions (
  id uuid PRIMARY KEY,
  family_id uuid NOT NULL,
  user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  refresh_token_hash text NOT NULL UNIQUE,
  user_agent_hash text,
  expires_at timestamptz NOT NULL,
  last_used_at timestamptz NOT NULL DEFAULT now(),
  revoked_at timestamptz,
  revoke_reason text,
  replaced_by uuid REFERENCES auth_sessions(id),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ix_auth_sessions_user_active
  ON auth_sessions (user_id, expires_at)
  WHERE revoked_at IS NULL;
CREATE INDEX ix_auth_sessions_family ON auth_sessions (family_id);
CREATE INDEX ix_oauth_transactions_expires_at ON oauth_transactions (expires_at);
CREATE INDEX ix_auth_exchange_codes_expires_at ON auth_exchange_codes (expires_at);

COMMENT ON TABLE auth_sessions IS
  'Refresh token rotation history. Token 원문은 저장하지 않고 HMAC 해시만 저장한다.';
COMMENT ON COLUMN auth_sessions.family_id IS
  '회전된 refresh token 계보. 폐기 토큰 재사용 시 전체 계보를 폐기한다.';
COMMENT ON TABLE auth_exchange_codes IS
  '모바일 OAuth callback용 단일 사용 PKCE 바인딩 교환 코드.';
"""


DOWNGRADE_SQL = """
DROP TABLE auth_sessions;
DROP TABLE auth_exchange_codes;
DROP TABLE oauth_transactions;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
