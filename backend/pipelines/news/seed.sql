-- 뉴스 파트 시드: news_feeds에 전체뉴스 RSS 4개를 넣는다.
-- news_sources(sedaily, mk, hankyung, yonhap)와 stocks(시범 종목 4개)는 DB에 이미 있어서 넣지 않는다.
-- news_feeds에는 (source_id, section) UNIQUE가 없어서 ON CONFLICT 대신 NOT EXISTS로 중복을 막는다. 여러 번 실행해도 된다.
INSERT INTO news_feeds (source_id, section, feed_url)
SELECT s.id, '전체뉴스', v.url
FROM news_sources s
JOIN (VALUES
  ('sedaily',  'https://www.sedaily.com/rss/newsall'),
  ('hankyung', 'https://www.hankyung.com/feed/all-news'),
  ('yonhap',   'https://www.yna.co.kr/rss/news.xml'),
  ('mk',       'https://www.mk.co.kr/rss/40300001/')
) AS v(code, url) ON s.code = v.code
WHERE NOT EXISTS (
  SELECT 1 FROM news_feeds f WHERE f.source_id = s.id AND f.section = '전체뉴스'
);
