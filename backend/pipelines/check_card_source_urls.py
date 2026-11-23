"""AI 업데이트 카드(답변 포함)의 근거 뉴스에 원문 링크(url)가 있는지 센다 (읽기만 함).

실행: cd backend && PYTHONPATH=. python -m pipelines.check_card_source_urls
"""

from sqlalchemy import text

from app.db import SessionLocal

SQL = """
SELECT tu.type::text AS card_type, count(*) AS sources,
       count(na.url) AS with_url,
       count(*) FILTER (WHERE na.url LIKE 'http%') AS http_url
FROM update_sources us
JOIN tracking_updates tu ON tu.id = us.update_id
JOIN news_articles na ON na.id = us.news_id
GROUP BY 1 ORDER BY 1
"""


def main() -> None:
    db = SessionLocal()
    try:
        for r in db.execute(text(SQL)).mappings():
            print(f"{r['card_type']:<16} 근거 뉴스 {r['sources']:>5} · url 있음 {r['with_url']:>5} · http 링크 {r['http_url']:>5}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
