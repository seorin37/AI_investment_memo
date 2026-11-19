"""두 방식 메모 단위 비교 화면 (preview_compare --methods, method_compare 결과 폴더). 파일만 읽는다. 2026-11-19."""

import json
import tempfile
import unittest
from pathlib import Path

from pipelines.updates.preview_compare import build_methods


def _w(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')


EV = 'E1 [뉴스]\n- 제목: 카카오 개편\n- 언론사: 한국경제\n- 게시 일자: 2026-11-10\n- 제공 요약: 카카오는 기능을 추가했다.'


class MethodsPageTest(unittest.TestCase):
    def _dir(self, tmp: Path) -> Path:
        _w(tmp / 'dataset.jsonl', [{'memo_id': 'K03', 'symbol': '035720', 'company': '카카오', 'text': '카톡 개편 반응 궁금',
                                    'set': '코스피'},
                                   {'memo_id': 'K10', 'symbol': '004370', 'company': '농심', 'text': '그냥 라면 좋아서 삼',
                                    'set': '코스피'}])
        (tmp / 'meta.json').write_text(json.dumps({'as_of': '2026-11-19T14:27', 'sets': {'코스피': 2}}), encoding='utf-8')
        for m, cat in (('seorin', ''), ('minyi', 'ask')):
            _w(tmp / m / 'gold.jsonl', [{'memo_id': 'K03', 'symbol': '035720', 'text': '카톡 개편 반응 궁금', 'sentences': [
                {'sentence_index': 0, 'text': '카톡 개편 반응 궁금', 'items': [{'type': 'topic', 'description': '카톡 개편 반응',
                                                                           'category': cat}]}]},
                                        {'memo_id': 'K10', 'symbol': '004370', 'text': '그냥 라면 좋아서 삼', 'sentences': []}])
            _w(tmp / m / 'analysis.jsonl', [{'memo_id': 'K03', 'usd': 0.01, 'items': [{}], 'asks': [], 'responses': [],
                                             'sentences': []},
                                            {'memo_id': 'K10', 'usd': 0.0, 'items': [], 'asks': [],
                                             'responses': [{'type': 'out_of_scope', 'scope': 'memo', 'reason': '감상'}],
                                             'sentences': [{'text': '그냥 라면 좋아서 삼', 'decision': 'out_of_scope', 'reason': 'X'}]}])
            run = tmp / m / 'cards' / 'run_1'
            run.mkdir(parents=True)
            if m == 'seorin':
                _w(run / 'cards.jsonl', [{'item_id': 'K03:0:0', 'card_schema': 'v2', 'update_type': 'news',
                                          'headline': '카카오, 카톡 의견 접수 기능 추가', 'when': '2026-11-10',
                                          'facts': [{'text': '카카오는 기능을 추가했어요.', 'ref': 'news:1'}],
                                          'memo_link': '메모의 개편 반응과 연결돼요.', 'sources': [{'ref': 'news:1'}]}])
                _w(run / 'outcomes.jsonl', [{'item_id': 'K03:0:0', 'kind': 'update', 'checks': []}])
                _w(run / 'responses.jsonl', [{'item_id': 'K03:0:0', 'type': 'update_card', 'reason': 'card'}])
            else:
                _w(run / 'cards.jsonl', [])
                bad = {'headline': '카카오 개편', 'facts': [{'text': '기능을 추가할 것이라고 밝혔어요.', 'evidence_id': 'E1'}],
                       'memo_link': '연결돼요.'}
                _w(run / 'outcomes.jsonl', [{'item_id': 'K03:0:0', 'kind': 'no_update', 'fail_codes': ['ATTRIBUTION'],
                                             'checks': [{'stage': 'card', 'card': bad, 'codes': ['ATTRIBUTION']},
                                                        {'stage': 'format_retry', 'card': bad, 'codes': ['ATTRIBUTION']}]}])
                _w(run / 'responses.jsonl', [{'item_id': 'K03:0:0', 'type': 'ask_no_answer', 'reason': 'check_failed',
                                              'message': '물으신 내용은 확인되지 않았어요.'}])
            _w(run / 'llm_io.jsonl', [{'stage': 'card', 'item_id': 'K03:0:0', 'prompt': '# 새 근거\n' + EV + '\n\n# 출력'}])
            (run / 'refs.json').write_text(json.dumps({'news:1': {'kind': 'news', 'title': '카카오 개편', 'source': '한국경제',
                                                                  'date': '2026-11-10'}}), encoding='utf-8')
            _w(tmp / m / 'cwd/results/updates/usage_log.jsonl', [{'total': {'usd': 0.05}}])
        return tmp

    def test_page(self):
        with tempfile.TemporaryDirectory() as t:
            page = build_methods(self._dir(Path(t)))
        self.assertEqual(page.count('class="memo-row"'), 2)
        self.assertIn('카카오, 카톡 의견 접수 기능 추가', page)                 # 서린 알림 카드
        self.assertIn('한 번 답하기', page)                                     # 팀원 항목 구분
        self.assertIn('자료 없음 답', page)
        self.assertIn('두 방식 같은 근거 1건', page)                            # 같은 근거는 하나만
        self.assertIn('data-diff="1"', page)                                  # K03은 결과가 다르다
        self.assertIn('data-diff="0"', page)                                  # K10은 둘 다 카드 없음
        self.assertIn('범위 밖 안내', page)
        self.assertIn('고른 결과 CSV 내려받기', page)
        self.assertIn('$0.01 + $0.05', page)

    def test_check_failure_shows_hit_sentence(self):
        with tempfile.TemporaryDirectory() as t:
            d = self._dir(Path(t))
            out = d / 'minyi/cards/run_1/outcomes.jsonl'
            o = json.loads(out.read_text(encoding='utf-8'))
            _w(out, [o])
            (d / 'minyi/cards/run_1/responses.jsonl').write_text(json.dumps(
                {'item_id': 'K03:0:0', 'type': 'no_new_info', 'reason': 'check_failed'}, ensure_ascii=False), encoding='utf-8')
            page = build_methods(d)
        self.assertIn('검사 실패', page)
        self.assertIn('형식 재요청 뒤에도', page)
        self.assertIn('기능을 추가할 것이라고 밝혔어요. <span class="code">← ATTRIBUTION', page)


if __name__ == '__main__':
    unittest.main()
