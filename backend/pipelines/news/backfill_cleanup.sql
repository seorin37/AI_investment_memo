-- 과거 뉴스 백필 행 정리 (backfill_list로 넣은 2026-10-28 이전 발행 한국경제·매일경제 기사)
--
-- 이 파일을 그대로 실행하면 건수만 보여 준다 (읽기만). 지우는 문장은 맨 아래에 주석으로만 두었다.
--   psql "$DATABASE_URL" -f backend/pipelines/news/backfill_cleanup.sql
--
-- 대상: news_sources.code IN ('hankyung','mk') AND published_at < 2026-10-28 00:00 KST.
--   실시간 수집(RSS)은 2026-10-28부터라 그 이전 한경·매경 기사는 모두 백필 행이다
--   (2026-11-12 백필 전 확인: 한경 최초 10-28 15:44, 매경 최초 10-28 11:29, 10-28 이전 0건).
--   11-11·11-12 공백 채우기(--allow-recent)로 넣은 기사는 실시간 구간이라 이 대상에 들어가지 않는다.
--   그 기사는 section이 '전체뉴스'가 아니고(백필은 매체 섹션, RSS는 '전체뉴스' 또는 NULL) 아래 [참고] 쿼리로 볼 수 있다.
--
-- 함께 지워지는 것 (FK): news_article_bodies → news_chunks, news_embedding_variants, news_article_leads,
--   news_cluster_members (ON DELETE CASCADE), news_clusters.representative_news_id (SET NULL).
-- 먼저 지워야 하는 것 (NO ACTION): news_stocks. tracking_matches·update_sources가 참조하는 기사는 메모 근거라 지우지 않는다.

WITH target AS (
  SELECT a.id
  FROM news_articles a JOIN news_sources s ON s.id = a.source_id
  WHERE s.code IN ('hankyung', 'mk') AND a.published_at < TIMESTAMPTZ '2026-10-28 00:00:00+09'
)
SELECT 'news_articles (대상 기사)' AS 항목, count(*) AS 건수 FROM target
UNION ALL SELECT '  ㄴ 메모 근거라 남길 기사 (tracking_matches·update_sources 참조)', count(*) FROM target t
  WHERE EXISTS (SELECT 1 FROM tracking_matches m WHERE m.news_id = t.id)
     OR EXISTS (SELECT 1 FROM update_sources u WHERE u.news_id = t.id)
UNION ALL SELECT 'news_article_bodies (원문)', count(*) FROM news_article_bodies b JOIN target t ON t.id = b.news_id
UNION ALL SELECT 'news_chunks (청크·임베딩)', count(*) FROM news_chunks c JOIN target t ON t.id = c.news_id
UNION ALL SELECT 'news_embedding_variants (제목+요약 임베딩)', count(*) FROM news_embedding_variants v JOIN target t ON t.id = v.news_id
UNION ALL SELECT 'news_stocks (종목 태그)', count(*) FROM news_stocks k JOIN target t ON t.id = k.news_id
UNION ALL SELECT 'news_article_leads (리드)', count(*) FROM news_article_leads l JOIN target t ON t.id = l.news_id
UNION ALL SELECT 'news_cluster_members (묶음)', count(*) FROM news_cluster_members cm JOIN target t ON t.id = cm.news_id
UNION ALL SELECT 'news_clusters (대표 기사가 대상인 묶음, 대표만 비워짐)', count(*) FROM news_clusters cl JOIN target t ON t.id = cl.representative_news_id;

-- [참고] 11-11·11-12 공백 채우기로 들어온 한경·매경 기사 (RSS 섹션 '전체뉴스'가 아닌 것)
-- SELECT s.code, (a.published_at AT TIME ZONE 'Asia/Seoul')::date AS 발행일, count(*)
-- FROM news_articles a JOIN news_sources s ON s.id = a.source_id
-- WHERE s.code IN ('hankyung', 'mk') AND a.published_at >= TIMESTAMPTZ '2026-11-11 00:00:00+09'
--   AND a.published_at < TIMESTAMPTZ '2026-11-13 00:00:00+09' AND a.section IS DISTINCT FROM '전체뉴스'
--   AND a.section IS NOT NULL
-- GROUP BY 1, 2 ORDER BY 1, 2;

-- ---------------------------------------------------------------- 실제 삭제 (실행하지 않음, 필요할 때 주석을 풀어 한 트랜잭션으로)
-- BEGIN;
-- CREATE TEMP TABLE backfill_target ON COMMIT DROP AS
--   SELECT a.id FROM news_articles a JOIN news_sources s ON s.id = a.source_id
--   WHERE s.code IN ('hankyung', 'mk') AND a.published_at < TIMESTAMPTZ '2026-10-28 00:00:00+09'
--     AND NOT EXISTS (SELECT 1 FROM tracking_matches m WHERE m.news_id = a.id)
--     AND NOT EXISTS (SELECT 1 FROM update_sources u WHERE u.news_id = a.id);
-- DELETE FROM news_stocks WHERE news_id IN (SELECT id FROM backfill_target);
-- DELETE FROM news_articles WHERE id IN (SELECT id FROM backfill_target);   -- 원문·청크·임베딩·리드·묶음은 CASCADE
-- COMMIT;
-- 원문 jsonl(data/news_raw/<날짜>.jsonl)과 진행 기록(data/news_backfill/progress.json)도 함께 지워야 다시 백필할 수 있다.
