"""AI 업데이트 생성 (추적 항목 → 후보 → LLM 관련성 판단 → 근거 검증 → 업데이트 초안).

가격 검사(price)·카드 코드 검사(checks)·근거 준비(evidence)·고정 문구(fixed)·즉답 분류(instant)·응답 파싱(judge)·판정 흐름(topic)은 DB·API 없이 동작한다.
DB 읽기는 candidates, 실험 실행은 experiment가 맡는다. LLM 호출은 호출자가 주입한다.
"""
