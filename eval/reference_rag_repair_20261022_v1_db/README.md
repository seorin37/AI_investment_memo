# 평가기준표 DB 정렬판 — rag_repair_20261022_v1 → 현재 DB 코퍼스

팀 평가기준표 `eval/reference_rag_repair_20261022_v1/`(원본, 수정하지 않음)의 근거 청크 번호를 현재 DB 청크
(파서 1.1·청커 1.1, 42,391청크, WO-017 재처리본)에 **내용 기준으로** 다시 매핑한 판이다. 질문·사실 그룹(그룹 간 AND,
그룹 안 동의 표현 OR)·판정 규칙은 원본 그대로이고, 근거 위치만 바뀌었다.

재생성:

```
PYTHONPATH=backend python -m pipelines.disclosures.eval_reference \
    --source eval/reference_rag_repair_20261022_v1 --out eval/reference_rag_repair_20261022_v1_db
```

DB 청크가 바뀌면(재청킹·재임베딩) 다시 생성해야 한다. `alignment_summary.json`의 `corpus`·`source_sha256`으로 확인한다.

## 파일

| 파일 | 내용 |
|---|---|
| `reference_annotations.jsonl` | 정렬된 기준표 (원본 필드 + 아래 필드) |
| `eval_scope.csv` | 질문별 채점 여부·제외 사유·검토 필요·그룹 상태·DB 근거 청크 (Excel용 UTF-8-SIG) |
| `alignment_report.csv` | 원본 근거 611개 각각의 매핑 결과 (`team_evidence` → `db_evidence`, 방법) |
| `alignment_summary.json` | 집계, 원본 해시, 코퍼스 버전 |

추가 필드: 질문 `eval_status`(scored/excluded)·`exclude_reason`·`needs_human_check`·`report_replacements`·
`team_repaired_chunk_ids`, 그룹 `alignment_status`·`team_valid_evidence_or`(원본 근거)·`unaligned_team_evidence`,
근거 `alignment`(content/numbers)·`team_rcept_no`·`team_chunk_index`·`team_excerpt`.

## 정렬 규칙

1. **content**: 같은 보고서에서 원본 발췌의 가운데 두 구간(헤더 제외, 공백·구두점 제거 40자, 15자 미만 발췌는 쓰지 않음)이
   모두 들어 있고 그룹의 사실 표현도 들어 있는 청크. 사실 표현은 원본 규칙대로 섹션 제목 포함 청크 전체에서 찾는다
   (헤더의 기업명·연도·보고서 종류는 제외).
2. **numbers**: 1이 없을 때. 표는 원본과 펼치는 방식이 달라(원본: 셀 순서, DB: `열이름: 값`) 1이 실패하므로 발췌의
   숫자(연도·날짜 제외, 숫자 단위 비교)로 찾는다. 점수 순으로 보며 아직 덮지 못한 발췌 숫자를 충분히 새로 덮는 청크만
   고르고, 고른 청크들이 발췌 숫자의 1/3 이상을 덮어야 인정한다 — 원본 청크 하나가 DB 청크 여러 개에 걸치면 모두 잡고,
   같은 숫자 일부만 가진 다른 표는 빠진다.
3. **보고서 교체**: 원본이 쓴 `20260324000835`(KB금융 2025 사업보고서 직전 정정본)는 DB에 없고, 같은 기간 최신 정정본
   `20260619000667`(WO-013)이 있다. 그 보고서에서 같은 문구로 근거를 찾았다(근거 26개).

## 결과 (2026-10-22)

- 질문: **채점 98 / 제외 2** (SK-15·SK-24 — 원본 판정 `not_disclosed_in_scope`)
- 사실 그룹 270: content 근거 있음 262 · numbers 근거만 6 · 원래 근거 없음 2
- 원본 근거 611: content 584 (그중 번호까지 같음 320) · numbers 23 · 못 옮김 4 (NV-25:199, KB-13:1511·455, KB-16:510 —
  모두 같은 그룹의 다른 근거로 충족)
- 원본 판정 `source_not_available`이던 KB-02·KB-11·KB-12·KB-22는 최신 정정본에서 근거를 찾아 채점 대상

## 사람 검토 필요 (`needs_human_check` 14문항)

- **보고서 교체**: KB-02, KB-11, KB-12, KB-22 — 직전 정정본 근거를 최신 정정본의 같은 문구로 옮김
- **numbers 근거 포함**: KB-04, KB-05, KB-07, KB-14, KB-19, KB-21, KB-23 — 표 근거라 숫자로 찾음
- **못 옮긴 원본 근거 있음**: NV-25, KB-13, KB-16
- **원본 근거 자체 확인 권고** (정렬은 원본을 그대로 옮겼다):
  - KB-04 F1 "총자본비율": 원본 대체 근거 `20251114003011:351`은 KB국민은행 표 → DB `:371`. 질문은 KB금융지주
  - KB-07 F1·F2: 원본 대체 근거 `20241114002984:372`·`:369`는 다른 표(대손충당금비율·적립율) → DB `:426`·`:420`
  - KB-05 F1 "지배기업 소유주": 원본 대체 근거 `20260515002888:474`(기타포괄손익 항목) → DB `:983`(이익잉여금 표)

원본의 `human_review_status`는 100문항 모두 `pending` 그대로다.
