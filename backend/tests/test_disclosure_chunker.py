import unittest

from pipelines.disclosures import chunker, parser
from pipelines.disclosures.parser import Block
from tests.disclosure_fixtures import EXCLUDE_PATTERNS, SAMPLE_XML, FakeTokens


SETTINGS = chunker.ChunkSettings(target_tokens=60, overlap_tokens=10, max_tokens=80)


def words(prefix, count):
    return " ".join(f"{prefix}{i}" for i in range(count))


def run(blocks, settings=SETTINGS):
    return chunker.chunk_blocks("R1", blocks, "삼성전자", "2026-06-30", FakeTokens(), settings)


class ChunkerTest(unittest.TestCase):
    def test_header_and_period_labels(self):
        self.assertEqual(chunker.chunk_header("KB금융", "2025-12-31", "A > B"), "[KB금융 2025 사업보고서 | A > B]\n")
        self.assertEqual(chunker.period_label("2024-03-31"), "1분기")
        self.assertEqual(chunker.period_label("2024-09-30"), "3분기")
        self.assertEqual(chunker.period_label("2024-06-30"), "반기")

    def test_deterministic_index_hash_and_fingerprint(self):
        doc = parser.parse_xml(SAMPLE_XML.encode("utf-8"), "R1", EXCLUDE_PATTERNS)
        first = chunker.chunk_blocks("R1", doc.blocks, "삼성전자", "2026-06-30", FakeTokens(), SETTINGS)
        second = chunker.chunk_blocks("R1", doc.blocks, "삼성전자", "2026-06-30", FakeTokens(), SETTINGS)
        self.assertEqual([c.to_dict() for c in first], [c.to_dict() for c in second])
        self.assertEqual([c.chunk_index for c in first], list(range(len(first))))
        for chunk in first:
            self.assertEqual(chunk.chunk_hash, chunker.sha256_text(chunk.chunk_text))
            self.assertTrue(chunk.chunk_text.startswith(f"[삼성전자 2026 반기 | {chunk.section}]\n"))
        fingerprint = chunker.doc_fingerprint([c.chunk_hash for c in first])
        self.assertEqual(fingerprint, chunker.sha256_text("".join(c.chunk_hash for c in first)))
        self.assertEqual(len(fingerprint), 64)

    def test_text_respects_max_tokens_and_overlaps(self):
        sentences = [words(f"s{n}w", 9) + "." for n in range(30)]
        chunks = run([Block(section=["A"], block_type="text", text=" ".join(sentences))])
        self.assertGreater(len(chunks), 3)
        for chunk in chunks:
            self.assertLessEqual(chunk.token_count, SETTINGS.max_tokens)
            self.assertEqual(chunk.token_count, FakeTokens().count(chunk.chunk_text))
        # 다음 청크는 직전 청크의 마지막 문장(오버랩 10토큰 이내)으로 시작한다
        first_body = chunks[0].chunk_text.split("\n", 1)[1]
        second_body = chunks[1].chunk_text.split("\n", 1)[1]
        last_sentence = first_body.split(". ")[-1]
        self.assertTrue(second_body.startswith(last_sentence.rstrip(".")))

    def test_long_sentence_is_hard_split_without_losing_words(self):
        text = words("w", 200)
        chunks = run([Block(section=["A"], block_type="text", text=text)])
        self.assertTrue(all(c.token_count <= SETTINGS.max_tokens for c in chunks))
        joined = " ".join(c.chunk_text.split("\n", 1)[1] for c in chunks)
        for token in ("w0", "w100", "w199"):
            self.assertIn(token, joined)

    def test_large_table_split_on_rows_repeats_caption_unit_header(self):
        rows = [f"구분: 행{i} | 금액: {i}" for i in range(40)]
        block = Block(section=["T"], block_type="table", caption="표 제목", unit="(단위 : 백만원)", header=["구분", "금액"], rows=rows)
        chunks = run([block])
        self.assertGreater(len(chunks), 1)
        seen = []
        for chunk in chunks:
            body = chunk.chunk_text.split("\n")[1:]
            self.assertEqual(body[:3], ["[표] 표 제목", "(단위 : 백만원)", "열: 구분 | 금액"])
            self.assertLessEqual(chunk.token_count, SETTINGS.max_tokens)
            self.assertEqual(chunk.block_type, "table")
            seen.extend(body[3:])
        self.assertEqual(seen, rows)  # 행 경계에서만 나뉘고 누락·중복 없음

    def test_huge_table_prefix_does_not_explode_into_tiny_chunks(self):
        header = [f"열{i}" for i in range(40)]  # `열:` 줄만 40토큰 이상
        rows = [" | ".join(f"열{i}: {r}" for i in range(3)) for r in range(30)]
        block = Block(section=["T"], block_type="table", caption=words("제목", 30), unit="(단위 : 원)", header=header, rows=rows)
        chunks = run([block])
        self.assertLess(len(chunks), len(rows))  # 행마다 한 청크로 쪼개지지 않는다
        for chunk in chunks:
            self.assertLessEqual(chunk.token_count, SETTINGS.max_tokens)
            self.assertIn("(단위 : 원)", chunk.chunk_text)
            self.assertNotIn("열: 열0", chunk.chunk_text)
        joined = "\n".join(chunks_body for c in chunks for chunks_body in c.chunk_text.split("\n"))
        for row in rows:
            self.assertIn(row, joined)

    def test_small_tables_in_same_section_are_merged(self):
        small = lambda n: Block(section=["T"], block_type="table", rows=[f"a: {n}"])
        chunks = run([small(1), small(2), Block(section=["U"], block_type="table", rows=["a: 3"])])
        self.assertEqual(len(chunks), 2)
        self.assertIn("a: 1", chunks[0].chunk_text)
        self.assertIn("a: 2", chunks[0].chunk_text)

    def test_manifest_row_fields(self):
        chunk = run([Block(section=["A"], block_type="text", text="한 문장.")])[0]
        self.assertEqual(
            set(chunk.manifest_row()),
            {"rcept_no", "chunk_index", "section", "token_count", "chunk_hash", "block_type", "parser_version", "chunker_version"},
        )


if __name__ == "__main__":
    unittest.main()
