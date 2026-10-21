"""Harden schema rules confirmed after the full v1.2 review.

Revision ID: 0005
Revises: 0004
"""

from alembic import op
from sqlalchemy import text

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # Run every data-safety preflight before the non-transactional enum change.
    duplicate_email = bind.execute(
        text(
            """
            SELECT lower(email)
            FROM users
            WHERE email IS NOT NULL
            GROUP BY lower(email)
            HAVING count(*) > 1
            LIMIT 1
            """
        )
    ).scalar()
    if duplicate_email is not None:
        raise RuntimeError(
            "Cannot create case-insensitive email uniqueness: "
            f"duplicate email {duplicate_email!r} exists"
        )

    mismatched_revision = bind.execute(
        text(
            """
            SELECT tu.id
            FROM tracking_updates AS tu
            JOIN tracking_items AS ti ON ti.id = tu.tracking_item_id
            JOIN memo_revisions AS mr ON mr.id = tu.memo_revision_id
            WHERE tu.memo_revision_id IS NOT NULL
              AND mr.memo_id <> ti.memo_id
            LIMIT 1
            """
        )
    ).scalar()
    if mismatched_revision is not None:
        raise RuntimeError(
            "Cannot enforce memo revision ownership: tracking update "
            f"{mismatched_revision} references another memo"
        )

    conflicting_trade_value = bind.execute(
        text(
            """
            SELECT symbol
            FROM prices_daily
            WHERE trade_value IS NOT NULL
              AND trading_value IS NOT NULL
              AND trade_value <> trading_value
            LIMIT 1
            """
        )
    ).scalar()
    if conflicting_trade_value is not None:
        raise RuntimeError(
            "Cannot merge trade_value and trading_value: conflicting values "
            f"exist for symbol {conflicting_trade_value!r}"
        )

    # PostgreSQL requires enum changes outside the main migration transaction.
    # Do this after preflight so all following schema/data changes remain atomic.
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE update_type ADD VALUE IF NOT EXISTS 'price_condition'"
        )

    # Email is optional for social-only accounts, but non-null emails are unique
    # after case folding.

    op.execute("ALTER TABLE users ALTER COLUMN email DROP NOT NULL")
    op.execute("ALTER TABLE users DROP CONSTRAINT users_email_key")
    op.execute(
        "CREATE UNIQUE INDEX ux_users_email_lower "
        "ON users (lower(email)) WHERE email IS NOT NULL"
    )
    op.execute(
        "COMMENT ON COLUMN users.email IS "
        "'일반 이메일 가입은 필수. 이메일 없는 소셜 계정은 NULL 허용하며, 값이 있으면 대소문자 무시 고유'"
    )

    # Financial values store year-to-date cumulative amounts. The application
    # derives standalone quarter values and prefers consolidated statements.
    op.execute("ALTER TABLE financials ADD COLUMN capital_surplus numeric(20,0)")
    op.execute(
        "COMMENT ON TABLE financials IS "
        "'DART 재무 원천값. 손익은 연초부터 누적값으로 저장하고 분기 단독값은 코드로 계산한다. "
        "연결재무제표가 있으면 연결만, 없으면 별도만 저장한다. 2024년 이후가 기본 수집 범위이며 "
        "전년 비교 계산에 필요한 2023년 대응 기간 값은 허용한다'"
    )
    op.execute(
        "COMMENT ON COLUMN financials.fs_div IS "
        "'consolidated(연결) / separate(별도). 연결이 있으면 연결만, 없으면 별도만 저장'"
    )
    op.execute(
        "COMMENT ON COLUMN financials.capital_surplus IS "
        "'자본잉여금. 유보율 계산에 사용'"
    )
    op.execute(
        "COMMENT ON COLUMN financials.capital_stock IS "
        "'자본금. 유보율 = (자본잉여금 + 이익잉여금) / 자본금 * 100'"
    )
    op.execute(
        "COMMENT ON COLUMN financials.retained_earnings IS "
        "'이익잉여금. 유보율 계산에 사용'"
    )

    # Give memo snapshots a stable per-memo sequence. Existing snapshots retain
    # their chronological order; memos without a snapshot receive the current
    # document as revision 1.
    op.execute("ALTER TABLE memo_revisions ADD COLUMN revision_no integer")
    op.execute(
        """
        WITH ranked AS (
          SELECT id,
                 row_number() OVER (
                   PARTITION BY memo_id ORDER BY created_at, id
                 ) AS revision_no
          FROM memo_revisions
        )
        UPDATE memo_revisions AS mr
        SET revision_no = ranked.revision_no
        FROM ranked
        WHERE mr.id = ranked.id
        """
    )
    op.execute(
        """
        INSERT INTO memo_revisions (memo_id, title, content, revision_no, created_at)
        SELECT m.id, m.title, m.content, 1, m.created_at
        FROM memos AS m
        WHERE NOT EXISTS (
          SELECT 1 FROM memo_revisions AS mr WHERE mr.memo_id = m.id
        )
        """
    )
    op.execute(
        """
        INSERT INTO memo_revisions (memo_id, title, content, revision_no, created_at)
        SELECT m.id,
               m.title,
               m.content,
               latest.revision_no + 1,
               m.updated_at
        FROM memos AS m
        JOIN LATERAL (
          SELECT mr.revision_no, mr.title, mr.content
          FROM memo_revisions AS mr
          WHERE mr.memo_id = m.id
          ORDER BY mr.revision_no DESC
          LIMIT 1
        ) AS latest ON true
        WHERE latest.title IS DISTINCT FROM m.title
           OR latest.content IS DISTINCT FROM m.content
        """
    )
    op.execute("ALTER TABLE memo_revisions ALTER COLUMN revision_no SET NOT NULL")
    op.execute(
        "ALTER TABLE memo_revisions ADD CONSTRAINT ck_memo_revisions_revision_no "
        "CHECK (revision_no > 0)"
    )
    op.execute(
        "ALTER TABLE memo_revisions ADD CONSTRAINT uq_memo_revisions_memo_revision "
        "UNIQUE (memo_id, revision_no)"
    )
    op.execute(
        "COMMENT ON COLUMN memo_revisions.revision_no IS "
        "'메모별 버전 번호. 최초 작성본은 1이고 제목 또는 본문 변경 시 증가'"
    )

    op.execute(
        """
        CREATE FUNCTION capture_memo_revision() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
          next_revision integer;
        BEGIN
          IF TG_OP = 'INSERT' THEN
            IF NOT EXISTS (
              SELECT 1 FROM memo_revisions WHERE memo_id = NEW.id
            ) THEN
              INSERT INTO memo_revisions (
                memo_id, title, content, revision_no, created_at
              ) VALUES (
                NEW.id, NEW.title, NEW.content, 1, NEW.created_at
              );
            END IF;
          ELSIF OLD.title IS DISTINCT FROM NEW.title
             OR OLD.content IS DISTINCT FROM NEW.content THEN
            SELECT COALESCE(max(revision_no), 0) + 1
            INTO next_revision
            FROM memo_revisions
            WHERE memo_id = NEW.id;

            INSERT INTO memo_revisions (
              memo_id, title, content, revision_no, created_at
            ) VALUES (
              NEW.id, NEW.title, NEW.content, next_revision, NEW.updated_at
            );
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_capture_memo_revision
        AFTER INSERT OR UPDATE OF title, content ON memos
        FOR EACH ROW EXECUTE FUNCTION capture_memo_revision()
        """
    )

    # Every existing update receives the latest snapshot of the memo belonging
    # to its tracking item.
    op.execute(
        """
        UPDATE tracking_updates AS tu
        SET memo_revision_id = latest.id
        FROM tracking_items AS ti
        JOIN LATERAL (
          SELECT mr.id
          FROM memo_revisions AS mr
          WHERE mr.memo_id = ti.memo_id
          ORDER BY mr.revision_no DESC
          LIMIT 1
        ) AS latest ON true
        WHERE ti.id = tu.tracking_item_id
          AND tu.memo_revision_id IS NULL
        """
    )
    op.execute(
        "ALTER TABLE tracking_updates "
        "DROP CONSTRAINT tracking_updates_memo_revision_id_fkey"
    )
    op.execute(
        "ALTER TABLE tracking_updates ALTER COLUMN memo_revision_id SET NOT NULL"
    )
    op.execute(
        "ALTER TABLE tracking_updates "
        "ADD CONSTRAINT tracking_updates_memo_revision_id_fkey "
        "FOREIGN KEY (memo_revision_id) REFERENCES memo_revisions(id) "
        "DEFERRABLE INITIALLY DEFERRED"
    )

    # A dedicated update type distinguishes user conditions from ordinary
    # market price events.
    op.execute(
        "ALTER TABLE tracking_updates ADD COLUMN observed_trade_date date"
    )
    op.execute(
        "ALTER TABLE tracking_updates "
        "ADD CONSTRAINT ck_tracking_updates_price_condition_fields CHECK ("
        "  (type = 'price_condition' AND observed_trade_date IS NOT NULL "
        "    AND price_state IS NOT NULL AND observed_value IS NOT NULL "
        "    AND tracking_revision_id IS NOT NULL) "
        "  OR (type <> 'price_condition' AND observed_trade_date IS NULL)"
        ")"
    )
    op.execute(
        "CREATE UNIQUE INDEX ux_tracking_updates_price_condition_daily "
        "ON tracking_updates (tracking_item_id, tracking_revision_id, observed_trade_date) "
        "WHERE type = 'price_condition'"
    )
    op.execute(
        "COMMENT ON COLUMN tracking_updates.observed_trade_date IS "
        "'사용자 가격 조건을 전일 종가로 판정한 기준 거래일. price_condition 업데이트에만 사용'"
    )

    op.execute(
        """
        CREATE FUNCTION validate_tracking_update_revision() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
          expected_memo_id bigint;
          latest_memo_revision_id bigint;
          linked_memo_id bigint;
          linked_tracking_type tracking_type;
        BEGIN
          SELECT memo_id INTO expected_memo_id
          FROM tracking_items
          WHERE id = NEW.tracking_item_id;

          IF expected_memo_id IS NULL THEN
            RAISE EXCEPTION 'tracking item % does not exist', NEW.tracking_item_id;
          END IF;

          IF NEW.memo_revision_id IS NULL THEN
            SELECT id INTO latest_memo_revision_id
            FROM memo_revisions
            WHERE memo_id = expected_memo_id
            ORDER BY revision_no DESC
            LIMIT 1;
            NEW.memo_revision_id := latest_memo_revision_id;
          END IF;

          SELECT memo_id INTO linked_memo_id
          FROM memo_revisions
          WHERE id = NEW.memo_revision_id;

          IF linked_memo_id IS DISTINCT FROM expected_memo_id THEN
            RAISE EXCEPTION
              'memo revision % does not belong to tracking item %',
              NEW.memo_revision_id, NEW.tracking_item_id;
          END IF;

          IF NEW.type = 'price_condition' THEN
            IF EXISTS (
              SELECT 1 FROM update_sources WHERE update_id = NEW.id
            ) THEN
              RAISE EXCEPTION
                'price condition updates do not use update_sources';
            END IF;

            SELECT type INTO linked_tracking_type
            FROM tracking_item_revisions
            WHERE id = NEW.tracking_revision_id
              AND tracking_item_id = NEW.tracking_item_id;

            IF linked_tracking_type IS NULL
               OR linked_tracking_type NOT IN ('price_below', 'price_above') THEN
              RAISE EXCEPTION
                'price condition update requires a price tracking revision';
            END IF;
          END IF;

          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_validate_tracking_update_revision
        BEFORE INSERT OR UPDATE OF tracking_item_id, tracking_revision_id,
          memo_revision_id, type
        ON tracking_updates
        FOR EACH ROW EXECUTE FUNCTION validate_tracking_update_revision()
        """
    )
    op.execute(
        """
        CREATE FUNCTION reject_price_condition_source() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          IF EXISTS (
            SELECT 1
            FROM tracking_updates
            WHERE id = NEW.update_id AND type = 'price_condition'
          ) THEN
            RAISE EXCEPTION
              'price condition updates do not use update_sources';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_reject_price_condition_source
        BEFORE INSERT OR UPDATE OF update_id ON update_sources
        FOR EACH ROW EXECUTE FUNCTION reject_price_condition_source()
        """
    )

    # Both columns represented KRX ACC_TRDVAL. Preflight has already verified
    # that merging cannot overwrite a different non-null value.
    op.execute(
        "UPDATE prices_daily "
        "SET trade_value = COALESCE(trade_value, trading_value) "
        "WHERE trading_value IS NOT NULL"
    )
    op.execute("ALTER TABLE prices_daily DROP COLUMN trading_value")
    op.execute(
        "COMMENT ON COLUMN prices_daily.trade_value IS "
        "'거래대금(원). KRX 일별매매정보 ACC_TRDVAL'"
    )


def downgrade() -> None:
    bind = op.get_bind()

    price_condition_count = bind.execute(
        text(
            "SELECT count(*) FROM tracking_updates "
            "WHERE type = 'price_condition'"
        )
    ).scalar_one()
    if price_condition_count:
        raise RuntimeError(
            "Cannot downgrade 0005 while price_condition updates exist"
        )

    null_email_count = bind.execute(
        text("SELECT count(*) FROM users WHERE email IS NULL")
    ).scalar_one()
    if null_email_count:
        raise RuntimeError("Cannot downgrade 0005 while users.email contains NULL")

    op.execute("ALTER TABLE prices_daily ADD COLUMN trading_value numeric(20,0)")
    op.execute(
        "UPDATE prices_daily SET trading_value = trade_value "
        "WHERE trade_value IS NOT NULL"
    )
    op.execute(
        "COMMENT ON COLUMN prices_daily.trading_value IS "
        "'거래대금(원). KRX 일별 시세 값'"
    )

    op.execute(
        "DROP TRIGGER trg_reject_price_condition_source ON update_sources"
    )
    op.execute("DROP FUNCTION reject_price_condition_source()")
    op.execute(
        "DROP TRIGGER trg_validate_tracking_update_revision ON tracking_updates"
    )
    op.execute("DROP FUNCTION validate_tracking_update_revision()")
    op.execute("DROP INDEX ux_tracking_updates_price_condition_daily")
    op.execute(
        "ALTER TABLE tracking_updates "
        "DROP CONSTRAINT ck_tracking_updates_price_condition_fields"
    )
    op.execute("ALTER TABLE tracking_updates DROP COLUMN observed_trade_date")

    op.execute("ALTER TYPE update_type RENAME TO update_type_0005")
    op.execute("CREATE TYPE update_type AS ENUM ('news', 'disclosure', 'price')")
    op.execute(
        "ALTER TABLE tracking_updates ALTER COLUMN type TYPE update_type "
        "USING type::text::update_type"
    )
    op.execute(
        "ALTER TABLE persona_samples ALTER COLUMN expected_source TYPE update_type "
        "USING expected_source::text::update_type"
    )
    op.execute("DROP TYPE update_type_0005")

    op.execute(
        "ALTER TABLE tracking_updates "
        "DROP CONSTRAINT tracking_updates_memo_revision_id_fkey"
    )
    op.execute(
        "ALTER TABLE tracking_updates ALTER COLUMN memo_revision_id DROP NOT NULL"
    )
    op.execute(
        "ALTER TABLE tracking_updates "
        "ADD CONSTRAINT tracking_updates_memo_revision_id_fkey "
        "FOREIGN KEY (memo_revision_id) REFERENCES memo_revisions(id) "
        "ON DELETE SET NULL"
    )
    op.execute("DROP TRIGGER trg_capture_memo_revision ON memos")
    op.execute("DROP FUNCTION capture_memo_revision()")
    op.execute(
        "ALTER TABLE memo_revisions "
        "DROP CONSTRAINT uq_memo_revisions_memo_revision"
    )
    op.execute(
        "ALTER TABLE memo_revisions "
        "DROP CONSTRAINT ck_memo_revisions_revision_no"
    )
    op.execute("ALTER TABLE memo_revisions DROP COLUMN revision_no")

    op.execute("ALTER TABLE financials DROP COLUMN capital_surplus")
    op.execute(
        "COMMENT ON TABLE financials IS "
        "'DART 재무 원천값(2024~현재). 증가율, 영업이익률, ROE, 부채비율 등은 저장하지 않고 계산'"
    )
    op.execute(
        "COMMENT ON COLUMN financials.fs_div IS "
        "'consolidated(연결) / separate(별도). 화면은 연결 기준'"
    )
    op.execute(
        "COMMENT ON COLUMN financials.capital_stock IS "
        "'자본금. 유보율 = 이익잉여금 / 자본금 계산용'"
    )
    op.execute("COMMENT ON COLUMN financials.retained_earnings IS NULL")

    op.execute("DROP INDEX ux_users_email_lower")
    op.execute("ALTER TABLE users ALTER COLUMN email SET NOT NULL")
    op.execute("ALTER TABLE users ADD CONSTRAINT users_email_key UNIQUE (email)")
    op.execute("COMMENT ON COLUMN users.email IS NULL")
