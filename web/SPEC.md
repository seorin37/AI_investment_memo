# Figma 2.5 추출 수치 (1440×900 기준, 프레임 좌표)
폰트 Noto Sans KR. 색: 메인 배경 #f3f4f6, 진한 글자 #16171a/#191f28/#15171a, 회색 #575b63 #6b7078 #6b7684 #8f8f8f #747d8d, 보더 #e5e7eb #e5e8eb.

## 레이아웃
- 사이드바 250 흰색, pad 24/16, 간격 8. 접힘 72(아이콘 40칸).
- 메인: x250, pad 32(홈·업데이트·기록·기업정보), 2.0/2.2 pad 40, 6 메모장 pad top 80.
- 스튜디오 칸 436 = pad top24 right24 bottom24, 패널 412×852 r22 흰 bd#e4e4e7. 접힘: 칸 96, 패널 72×800 r20 bd#e5e7eb.

## 사이드바 (Main Sidebar)
- 브랜드: 워드마크 이미지 117×72 at (16,8) / 접기 버튼 24×24 at (210,32).
- 검색 (16,88) 218×40 bg#f9f9f9 r8 pad10/12 gap4: 아이콘20 + "검색" 16 Regular #6b7078(lh20).
- 메뉴 row 40h r8 pad 0/12 gap8: 아이콘20 + 라벨 16 Regular #1c1c1c. 선택: bg#f3f1ef, 라벨 Bold #5e5668, 아이콘 stroke #5E5668.
- 홈(152) 최신 업데이트(200) 투자 기록(248). 내 종목 header (296): 버튼 154 + '+' 28×32 + chevron 28×32.
- 종목 목록 (348): 그룹 헤더 40h pad-left40 "보유"/"관심" 13 Medium #6b7078 + chevron. children pad-left 44 gap3: tree-line 1px #e5e7eb at x60, companies x64 w170 gap12, row 40h r8 pad 0/12/0/8 gap8: 로고 24 r7.2 + 이름 16 Regular.
- 하단 (699): 휴지통, 설정 및 지원(40h), divider (807) #f9f9f9, 프로필 (828) 아바타48 원 + 김나라 16 / 대학생 12 #6b7078(lh16), 로그아웃 아이콘18 at x212.

## 스튜디오 412 홈 (2.1)
- 머리줄 72h pad 12/10/0/20? : 로고 32 r10 #15171a (x20,y25), 제목 "스튜디오" 19 Bold lh130% ls-0.4%, sub "내 종목 3 · AI 연결 메모 3" 11.5 #8e8a97. 접기 32 at right 12.
- content x16 w380 top 80, gap10: "지금 보는 화면과 상관없이, 고른 종목으로 만들어요" 12 #9a9ea7.
- feature row 380×72 r16 pad14/12 gap12: icon-box 44 r13 (blue #d6e4ff/#2F6BDB, red #ffdadb/#D6404A, yellow #fce9ae/#A8740A, green #d3f0de/#1F8A4C), 제목 15.5 Bold, 설명 12.5 #575b63, chevron #9aa0aa.
  AI 오디오 "두 진행자가 내 종목 소식을 대화로 들려줘요" / AI 주간보고서 "최근 7일 내 종목 흐름을 보고서로" / AI 투자 실험실 "시장 환경을 바꿔 보고 영향 경로 보기" / 오늘의 퀴즈 "어제 증시에서 일어난 일 1문제"
- "만든 항목" 14 Bold + "30일 보관 · 다시 보기 무료" 12 #9a9ea7 (pad-top 8 gap6).
- 만든 항목 카드 r18 pad 0/16: icon 36 r10, 제목 13.5 Medium, 메타 12 #9a9ea7, 우측 "23일 뒤 삭제" 12.

## 2.1 홈 메인
- 헤더: "홈" 26 Bold lh30 ls-0.5% at y56; sub 14 "내 메모와 연결된 [새 소식 5건 Bold #111]이 도착했어요." #575b63 at y90. 칩(y57): 내 종목 3 (흰 bd#e5e7eb r999 pad6/12 12.5 Medium #575b63 + Bold 숫자), AI 연결 메모 3 (bg#e7e7e7 + plug12).
- 시장 한눈에 보기 (y140) 17 Bold; 카드 3개 219×196 gap16 흰 bd#e5e7eb r20 pad12/16 gap6: 국기12+이름 12 Medium #575b63, 값 24 Bold lh28, 변화 12.5 Bold(#2f6bdb 하락/#e5484d 상승) + 오늘 12 #6b7078, plot 204×66, 기간칩 bg#f3f4f6 r9 pad2 (각 54×20 r7, 선택 흰 11.5 Bold).
- 아래 row (y404) gap24: 업데이트 320×472 r20 bd#aeaeae pad20 gap12 / 뉴스 346×472 r20 bd#e5e7eb pad18/24/14/24.
  업데이트 카드 278 r14 pad14 gap10: 로고28 r8 + 이름 14.5 Bold + 상태칩(bg#f3f4f6 r6 11.5 Medium) + 배지22 #e45d6a. linked-update bg#f3f4f6 r10 pad10 gap6: 타입칩 흰 bd r6 11.5 Bold + 헤드라인 13 Medium / 메모연결아이콘 + 색 10×10 r3 + 메모제목 12.5 Medium #111. 선택카드 bg#f8f8f8 bd#111 1.5, linked bg#e7e7e7.
  삼성전자 관심 2 "공시 3분기 실적 발표가 예정돼 있어요"/"실적 나오면 다시 보기"(노랑) ; SK하이닉스 보유 3 "뉴스 HBM4 공급 확대 소식이 나왔어요"/"요즘 반도체 분위기 좋아 보여"(파랑) ; 네이버 관심 "모두 확인했어요".
  "전체 업데이트 보기  →" 13 Bold #111.
  뉴스: 헤더 "뉴스" 17 Bold / "오늘 · 8건" 12; 헤드라인 박스 bg#f3f4f6 r12 pad12/14: 연합뉴스 칩(흰 bd r10) + "13:12 · 방금", 제목 17 Bold lh26, "원문 읽기 ↗" 12.5 Bold; 목록 행 pad 9/2 gap10 bottom border: 시간 12 #6b7078 w38, 제목 14 Medium lh20 w220, 출처 12 Medium #575b63, ↗ 14 #6b7078.

## 2.0 시작: 메인 pad 0/40, content y125 w674 gap24. eyebrow "처음 시작하기" 104×30 bg#efefef r15 12 Medium; 제목 32 Bold lh44 #000; sub 16 #6b7684. 카드 326×380 r20 pad24/28: 템플릿 bg#f7f8fa bd#000 2, 커스텀 흰 bd#eaecf0. 아이콘48 r14, 추천 배지 56×28 #000 r14. 제목 21 Bold lh30, 설명 14 lh21 #6b7684, 체크 18 r9 + 13 #191f28 (gap8), 버튼 266×48 r12 15 Medium. footer i 18 + 13 #8f8f8f.

## 로그인: 배경 #fdfdfd, 카드 480×427 at (480,237) r24 bd#e5e8eb pad40/48 gap28. 로고 150×50, 제목 26 Bold #191f28, sub 14 #8f8f8f. 버튼 382×56 r12 gap12: 카카오 #fee500 / 네이버 #03a94d 흰글 / 구글 흰 bd#e8ecf3. 아이콘24 + 16 Bold 가운데.

## 2.2: 헤더 674×80 흰배경(!), 제목 28 Bold lh42 #15171a, sub 15 #747d8d. 버튼 "시작 화면으로" 144×44 흰 bd#e8ecf3 r12 14 Medium. 보드 674×620 bg#f5f6f8 r24 pad24, 24px 격자선 #e6eaf0. 위젯 추가 카드 280(240) 흰 dash 2 #e8ecf3 8-6 r20: ＋ 36 #477bff, "위젯 추가" 19 Bold, "클릭해서 위젯을 골라보세요" 13 #747d8d. 하단 안내 13 #747d8d. 편집 중 위젯: bd#477bff 1.5 r16, 상단 손잡이 32h "⠿ 끌어서 이동"/"↗ 크기 조절", 모서리 핸들 10×10.

## 3.1/3.2: 헤더 y84 제목 26 Bold #191f28, sub 14. 탭 y162 h32 r20 pad8/16 13 Medium (선택 #000/흰, 3.1 비선택 흰/#8f8f8f, 3.2 비선택 #f7f8fa/#6b7684). 3.1 카드 376 흰 bd#e5e8eb r16 pad20 gap14 세로 쌓기: 이름 18 Bold + 칩(bg#e8edf5 r6 12 Medium #000), 코드 12 #6b7684, 구분선, 행 20h gap10: 칩 공시 bg#fbeded #e5484d / 뉴스 bg#e8edf5? / 주가 bg#e6f0e2 #1e8e4e, 제목 14 Medium, 시간 12. 3.2 리스트 690 r16, 행 52h pad16/20 gap12: 종목칩 bg#f7f8fa + 타입칩 + 제목 + "DART · 10분 전".

## 4 종목 추가: 오버레이 #000@0.45, 모달 520 at (460,170) r20 pad28 gap16. 제목 20 Bold / 닫기 13 Medium #6b7684. 단계원 20 #000 + 13 Bold. 검색 464×48 bg#f7f8fa bd#000 r12 15 Medium. 결과행 41h r10 pad12/14 (선택 bg#efefef 14 Bold) 코드 12 #8f8f8f. 세그 228×41 r10 (선택 #000 흰 / #f7f8fa #8f8f8f). 버튼 82×41 r10 14 Bold.

## 5 투자 기록: 헤더 제목 26 Bold, "4개의 기록" 14 #8f8f8f; 검색 240×36 r18 흰 bd + 새 기록 36 원. workspace 690×768 흰 r20 bd. note-list 208 pad12/10 gap4, 선택 bg#f1eefb r10 pad10/12: 제목 14 Bold, 날짜 12 Medium #575b63 + 미리보기 12 #6b7078. editor pad 24/36/40/36: 날짜 12 #6b7078 가운데, 제목 26 Bold lh36, 본문 15 lh26, "다음 액션" 17 Bold, 체크 32h 15. 도구막대 216×42 흰 bd r22 at bottom(y805) 가운데, 버튼 38×32: 가가 / 체크 / 표 / 첨부 / 마크업.

## 6 메모장: 메인 pad 80/32/24/32 gap20. 로고32 r10 + 이름 28 Bold; 코드 12 + 칩 "보유 중". 가격 26 Bold, 변화 13 Bold #e5484d, 기준 11. 탭 y164. 보드 열 3개 219 gap16 (x282,517,753) top 230, 열 gap24. 메모 219×180 pad18/20/40/20 gap8: 날짜 12.5 Medium #4a4a55, 플러그 28 원(흰80%/40%), 제목 18 Bold lh136% #16161c, 본문 14 lh150% #2e2e38, 접힌모서리 30, 테이프 84×32 (top -16), 배지 24 #e5484d 흰테 2.
 색: 노랑 #fceaaa/#efbf2a, 파랑 #cfe0ff/#3d73f0, 보라 #d2beff/#7046f5, 초록 #cdefd9/#2fae68, 분홍 #f7c6f0/#d62bc4.
 체크리스트 카드 흰 bd#ebe9ed r16 pad16: "체크리스트" 14 Bold, "하나씩 확인해 보세요" 10 #96929d, 링 34, 행 30h 원18 + 11 #504b58, 완료 #ada0c5 원 + #a29da9.
 새 메모 칸 dash6-4 #e5e8eb r12 180h: "+ 새 메모 🔌" / "(더블클릭)" 11.

## 메모 팝업 640 r30 bd#e8ecf3 그림자 60/24 #6e6396@0.16, 오버레이 #000@0.45. 헤더 pad20/24: 부제 12 Medium #747d8d, 제목 20 Bold. 탭 bg#f2f3f4 r14 pad4 (탭 290×40 r12 15 Medium). 메모 종이 592×277 r16 pad20: 제목 21 Bold, 본문 15.5 lh160%, 안내(점선 위) 첫 줄은 제목이 돼요… 색 34 원 gap8, 라벨 "메모 색상" 12, 힌트 "보기·수정 칸에 같은 색상". AI 카드 bg#f2f3f4 r12: "AI 연결 🔌" + "메모는 자유롭게, 지켜볼 내용만 AI로." 13.5 #4e5968 / 토글 45×25. Actions: "AI 연결은 선택사항이에요" 13 + 취소 64×44 #f2f3f4 r12 + 메모 저장 107×44 #14171c.
 AI 업데이트: "도착한 소식 4" 16 Bold + 최신순 12; 카드 78h r16 pad16 gap12 (뉴스 #e3edff 선#3d73f0, 주가 #fff1d6 선#c98a0b, 공시 #eee8ff 선#7046f5), 아이콘 32 r10 흰, 메타 12, 제목 16 Bold, "자세히 ⌄"; 이벤트 46h (아이콘슬롯 32×22 #f2f3f4 r8, 14 #575b63); "9월 25일 · AI 연결 시작" 점; 하단 안내 12.

## 프레임 ID (Page 2.5)
1 로그인 3666:21907 | 사이드바 3666:21937 | 12 지원팝업 3666:30534
2.0 3666:21988 | 2.1 3792:67043 | 2.2 3666:22167 | 2.4.1 3666:22182 | 2.4.2 3666:22283 | 2.4.3 3666:22390 | 2.4.4 3666:22548
3.1 접힘 3877:68512 | 3.1 3666:23814 | 3.2 3666:23912 | 4 종목추가 3666:24031
6 3666:26301 | 6.1 3666:26460 | 6.2 3666:26668 | 메모카드 컴포넌트 3885:68621
메모팝업 1~5: 3666:27150 / 27153 / 27156 / 27159 / 27208 | AI 업데이트 3666:27211 | 세부 3666:27230
7 3666:24214 | 7.1 3666:24830 | 7.2 3666:25611 | 5 투자기록 3666:24090
스튜디오 컴포넌트 3712:59132 | 화면모음 3715:63663 | 주간보고서 v3 4109:68139
설정 8-1 27454, 8-2 27555, 8-3 27656, 8-4 27757, 8-5 27858, 8-6 27959, 8-7 28060, 8-8 30433 (모두 3666:)
9 피드백 3666:27345 | 9.1 3666:27394 | 11 도움말 3666:29218 | 휴지통 최종 3666:28451
## 사이드바 상세 (확인)
- 지원 팝업: 사이드바 오른쪽 끝(x250)에 붙고, 아래 끝이 '설정 및 지원' 줄 아래 끝과 같음. 192 폭, pad 12/8, gap4, 흰 r8, 그림자 0 4 16 #000@12%. 줄 176×40 (설정/피드백/도움말 아이콘).
- 프로필: 아바타 48 원, 김나라 16 #1c1c1c / 대학생 12 #9f9f9f (gap4), 로그아웃 18 at x212.
- 내 종목: 그룹 간격 12, 헤더→목록 4, 회사 줄 간격 12, 트리선 x60.

## 작업 방식 (11.12, 압축 후에도 이어서)
- Figma→JSX 변환기: Figma 파일 root sharedPluginData('memos.conv','src')에 저장됨. use_figma에서
  `const AF=Object.getPrototypeOf(async function(){}).constructor; const src=figma.root.getSharedPluginData('memos.conv','src'); const fn=new AF('figma','id','opt','return ('+src+')(figma,id,opt)'); return '@@ID@@'+(await fn(figma,'노드ID',{names:false}));`
  → 결과는 대화 기록(jsonl)에 남음 → `python3 figma/extract.py` 가 figma/jsx/<id>.jsx 로 저장. (끝나면 sharedPluginData 지우기: setSharedPluginData('memos.conv','src',''))
- figma/gen.py: 정적 화면(주간보고서 상세·실험 결과·보고서 요약) → src/gen/*.tsx 생성.
- 화면 비교: get_screenshot(enableBase64Response:true) 이미지는 /root/.claude/projects/-home-claude/<세션>/tool-results/mcp-Figma-blob-*.png 로 저장됨 → figref/ 로 복사.
  `node memos-test/shot.cjs dist/index.html out.png "__app.go({name:'home'})"` (window.__app = useApp()), `python3 memos-test/cmp.py web.png fig.png out.png [x y w h]`.
- 빌드: `npx vite build` (tsc 오류는 components/ui 쪽 기존 것만, 무시).
- 완료: 사이드바(shell.tsx), 스튜디오 전체(studio.tsx + 팝업 4개 + 토스트), 홈 2.1(home.tsx), 주간보고서 1440 상세(report.tsx).
- 남음: 로그인, 2.0, 2.2/2.4.x(home_old의 CustomPage 대체), 3.1/3.2, 4, 5, 6/6.1/6.2+메모카드+메모팝업1~5+AI업데이트, 7 기업정보(차트 데이터는 figma/candles.txt), 설정 8-1~8-8, 9/9.1, 11, 휴지통 최종, 로그아웃/위험 확인 팝업, DemoTools 정리, 아티팩트 게시(ca3cdfaa 읽고 같은 URL로) + 댓글 스레드 15353d44 답글.
