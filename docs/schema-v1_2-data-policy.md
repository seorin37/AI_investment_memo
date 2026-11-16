# Schema v1.2 데이터 처리 정책 (`0005`)

## 인증

- 일반 이메일 회원가입은 이메일과 비밀번호를 필수로 받는다.
- 카카오·네이버·구글 소셜 가입은 이메일이 없어도 허용한다.
- 사용자는 `users.id`로 식별하고, 소셜 계정은 `(provider, provider_uid)`로 식별한다.
- 이메일이 있으면 소문자 변환 기준으로 중복을 허용하지 않는다. 로그인·가입 코드도 비교 전에 이메일을 정규화해야 한다.

## 재무 데이터

- 연결재무제표가 있으면 연결만 저장한다.
- 연결재무제표가 없으면 별도재무제표만 저장한다.
- 실제 선택 결과는 `financials.fs_div`에 `consolidated` 또는 `separate`로 기록한다.
- 손익 항목은 연초부터 보고기간 말까지의 누적값을 저장한다(`financials`·`financials_fin`, 원본 그대로 보존).
- 분기 단독값은 같은 회계연도(결산월 기준)의 누적값 차이로 계산해 `financials_quarterly`·`financials_fin_quarterly`(0016)에 따로 저장한다. Q1=q1, Q2=half−q1, Q3=q3−half, Q4=annual−q3. 재무 적재가 원본 한 기간을 쓸 때마다 그 회계연도를 다시 계산한다. 못 구한 값은 NULL과 `null_reasons`(missing_prev_period·source_null·fs_div_mismatch·needs_review)로 남긴다. EPS·재무상태표 항목은 대상이 아니다. (2026-11-13 팀 결정으로 "코드에서 계산"에서 변경)
- 기본 수집 범위는 2024년 이후다. 2024년 전년 동기 대비 계산에 필요한 2023년 대응 기간 값만 비교 데이터로 추가 수집할 수 있다.
- 유보율은 `(capital_surplus + retained_earnings) / capital_stock * 100`으로 계산한다. 분모가 0이거나 필요한 값이 NULL이면 계산하지 않는다.

### 원천값 검증 필요

현재 저장소에는 DART 재무 수집·정규화 코드가 없다. 따라서 실제 API 응답의 손익 값이 누적값인지 이 저장소만으로 확인할 수 없다. 수집 구현 시 보고서 유형과 DART 계정의 기간 정보를 확인한 뒤 누적값임이 검증된 값만 저장해야 하며, 불확실한 값을 임의로 누적값으로 간주하면 안 된다.

## 메모 revision

- 메모 생성 시 현재 제목과 본문을 revision 1로 저장한다.
- 제목 또는 본문이 바뀌면 메모별 `revision_no`를 증가시켜 새 snapshot을 만든다.
- 모든 `tracking_updates`는 생성 당시 해당 추적 항목의 원본 메모 revision을 참조한다.
- 연결된 메모 revision은 해당 추적 항목의 `memo_id`와 일치해야 한다.

## 사용자 가격 조건

- 사용자 가격 조건 업데이트는 `tracking_updates.type = 'price_condition'`으로 저장한다.
- `observed_trade_date`는 전일 종가 판정의 기준 거래일이다.
- `observed_value`에는 해당 거래일의 종가를 저장한다.
- 당시 조건가는 `tracking_revision_id`가 가리키는 `tracking_item_revisions.price_threshold`에서 읽는다.
- `price_state`는 `near`, `away`, `reached` 중 하나다.
- 사용자 가격 조건 업데이트에는 `price_events` 또는 `update_sources` 행을 만들지 않는다.
- 동일한 추적 항목·revision·거래일에는 가격 조건 업데이트를 하나만 만든다.
- `near`, `away`, `reached`의 판정 임계값은 아직 확정되지 않았다. 수집·판정 코드에서 임의의 수치를 고정하지 않는다.

## 일별 가격

- `prices_daily.trade_value`가 KRX 일별매매정보의 거래대금 `ACC_TRDVAL`을 저장하는 단일 컬럼이다.
- 기존 `trading_value` 값은 migration에서 `trade_value`로 병합한다.
- 두 컬럼에 서로 다른 non-NULL 값이 존재하면 migration은 임의 선택하지 않고 중단한다.

위 내용은 `0005` 당시 정책이다. `0011_kis_market_data` 이후 신규 개별 종목
OHLCV·거래대금은 KIS가 공급하고, KRX는 일별 시가총액·상장주식수만 결합한다.
현재 정책은 `docs/kis-market-data-policy.md`를 따른다.
