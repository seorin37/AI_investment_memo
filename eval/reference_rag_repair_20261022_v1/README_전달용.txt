공시 RAG 새 평가기준표 전달본
버전: rag_repair_20261022_v1
작성일: 2026-10-22

우선 확인할 파일
1. reference_review.csv: Excel 검토용 100문항 평가기준표(UTF-8-SIG)
2. reference_annotations.jsonl: 프로그램 평가용 상세 기준
3. gold_change_log.csv: 기존 gold와 새 근거 위치 비교
4. unresolved_items.csv: 미공시·최신 원문 미제공·추출 누락 추적
5. reference_table_report.md: 결과와 사용법
6. reference_validation.json: 자동 무결성 검증 결과
7. reference_manifest.json: 입력·산출물 해시 및 실행 범위

판정 현황
- 공식 원문 근거 확인: 94개
- 평가 범위 내 미공시: 2개(SK-15, SK-24)
- 최신 정정본 원문 미제공: 4개(KB-02, KB-11, KB-12, KB-22)
- 사람 승인 상태: 100개 pending

이 전달본 작성 과정에서 재임베딩, DB 수정, 검색 실행 및 검색 성능 재평가는 수행하지 않았습니다.
