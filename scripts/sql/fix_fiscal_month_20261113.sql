-- 결산월 오판 정리 (2026-11-13, docs/financials-fiscal-month-fix.md)
-- MH머트리얼즈(결산월 12→6월 변경)와 6·3개월 결산 리츠 22곳의 재무·분기 행을 지운다.
-- 이 SQL 뒤에 run_financials_all --symbols ... --force 로 다시 적재한다 (리츠는 저장 제외라 다시 생기지 않음).
-- 결산월 수정 코드가 정기보고서 자동 수집 체크아웃에 반영된 뒤에 실행할 것 (아니면 새벽 수집이 옛 기간으로 다시 쓴다).
BEGIN;
CREATE TEMP TABLE fix_symbols (symbol character(6) PRIMARY KEY) ON COMMIT DROP;
INSERT INTO fix_symbols VALUES
  ('001080'),
  ('0030R0'), ('088260'), ('293940'), ('330590'), ('334890'), ('338100'), ('348950'), ('350520'),
  ('357120'), ('357250'), ('357430'), ('365550'), ('377190'), ('395400'), ('396690'), ('400760'),
  ('404990'), ('417310'), ('432320'), ('448730'), ('451800'), ('481850');
DELETE FROM financials_fin_quarterly WHERE symbol IN (SELECT symbol FROM fix_symbols);
DELETE FROM financials_quarterly     WHERE symbol IN (SELECT symbol FROM fix_symbols);
DELETE FROM financials_fin           WHERE symbol IN (SELECT symbol FROM fix_symbols);
DELETE FROM financials               WHERE symbol IN (SELECT symbol FROM fix_symbols);
COMMIT;
