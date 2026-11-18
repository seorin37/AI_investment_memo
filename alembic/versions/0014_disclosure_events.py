"""수시공시(주요사항·거래소·기타 공시)에서 뽑은 항목값.

Revision ID: 0014_disclosure_events
Revises: 0013_social_auth_sessions
Create Date: 2026-11-04

- 공시 자체는 기존 disclosures에 kind = major(주요사항보고서) / other(거래소·기타 공시), period_end = NULL로 넣는다.
- 본문은 기존 disclosure_chunks에 넣는다 (즉시 답변·업데이트 후보 검색이 그대로 찾는다).
- disclosure_events에는 규칙으로 뽑은 값(fields)과 원문 표의 항목-값 전체(pairs)를 둔다. LLM이 만든 값은 없다.
- 정정공시는 원본을 지우지 않고 corrects로 원본 접수번호를 가리킨다. 화면에는 다른 행이 corrects로
  가리키지 않는(= 최신) 행만 보여 준다.
- disclosures.created_at 인덱스: "마지막 확인 이후 DB에 들어온 공시" 조회용.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0014_disclosure_events"
down_revision: Union[str, Sequence[str], None] = "0013_social_auth_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = """
CREATE TABLE disclosure_events (
  rcept_no text PRIMARY KEY REFERENCES disclosures(rcept_no) ON DELETE CASCADE,
  event_type text NOT NULL,
  topic text NOT NULL CHECK (topic IN ('earnings', 'shareholder_return', 'business', 'capital', 'risk', 'schedule')),
  base_title text NOT NULL,
  is_correction boolean NOT NULL DEFAULT false,
  is_subsidiary boolean NOT NULL DEFAULT false,
  corrects text REFERENCES disclosures(rcept_no) ON DELETE SET NULL,
  fields jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(fields) = 'object'),
  pairs jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(pairs) = 'array'),
  correction jsonb CHECK (correction IS NULL OR jsonb_typeof(correction) = 'object'),
  parse_status text NOT NULL CHECK (parse_status IN ('ok', 'partial', 'failed')),
  parse_issues jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(parse_issues) = 'array'),
  doc_format text,
  parser_version text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (corrects IS NULL OR corrects <> rcept_no)
);

CREATE INDEX ix_disclosure_events_type ON disclosure_events (event_type);
CREATE INDEX ix_disclosure_events_topic ON disclosure_events (topic);
CREATE INDEX ix_disclosure_events_corrects ON disclosure_events (corrects) WHERE corrects IS NOT NULL;
CREATE INDEX ix_disclosures_created_at ON disclosures (created_at);

COMMENT ON TABLE disclosure_events IS
  '수시공시 항목값. 1행 = disclosures 1행(kind major/other). 값은 원문 표에서 규칙으로 뽑는다(LLM 없음).';
COMMENT ON COLUMN disclosure_events.event_type IS
  'configs/disclosure_events.yaml의 종류: prelim_earnings, dividend, treasury_buy, supply_contract …';
COMMENT ON COLUMN disclosure_events.fields IS
  '종류별 필드. 금액은 원 단위 정수, 날짜는 YYYY-MM-DD, 해당 없음은 null.';
COMMENT ON COLUMN disclosure_events.pairs IS
  '원문 표의 [{path, value, acode, table}] 전체. 규칙이 놓친 항목 대비.';
COMMENT ON COLUMN disclosure_events.corrects IS
  '정정공시면 원본 공시의 접수번호. 원본이 DB에 없으면 NULL이고 correction.original_date만 남는다.';
COMMENT ON COLUMN disclosure_events.parse_status IS
  'ok: 필수 필드 모두 있음, partial: 일부 없음(원문에 값이 없는 경우 포함), failed: 원문 파싱 실패';
"""

DOWNGRADE_SQL = """
DROP INDEX ix_disclosures_created_at;
DROP TABLE disclosure_events;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
