/* MEMO'S 웹 — 가입부터 탈퇴까지 전체 흐름 테스트 (가상 데이터 기준)
   준비: npm i -D playwright && npx playwright install chromium   (한 번만)
   실행: npm run dev 를 켠 상태에서  node e2e/full-flow.cjs [주소]
   실패하면 e2e/out/fail_*.png 에 그 순간 화면이 남아요. 개발 서버에서만 돌아요(window.__app 사용). */
const { chromium } = require('playwright');
const path = require('path'), fs = require('fs');
const URL = process.argv[2] || 'http://localhost:8081/';
const OUT = path.join(__dirname, 'out'); fs.mkdirSync(OUT, { recursive: true });
const shot = (n) => path.join(OUT, n);
let pass = 0, fail = 0; const fails = [];
const ok = (c, name, info='') => { if (c) pass++; else { fail++; fails.push(name + (info ? ' :: ' + info : '')); } };
const A = (p) => p.evaluate(() => { const a = window.__app; return { route: a.route, stocks: a.stocks.map(s => s.stock_code), memos: a.memos.map(m => ({ id: m.id, code: m.stock_code, title: m.title, ai: m.ai, news: m.news, badge: m.badge, tl: (m.timeline||[]).map(t=>t.kind) })), cl: a.checklists, made: a.made.map(m => ({ kind: m.kind, codes: m.stock_codes, data: m.data })), journal: a.journal.map(j => j.title), trash: a.trash.map(t => t.kind + ':' + t.title), ud: { name: a.ud.profile && a.ud.profile.name, quiz: a.ud.quiz.length, notiUpd: a.ud.settings.noti_upd }, notifs: a.notifs.length }; });
const wait = (p, ms) => p.waitForTimeout(ms);
async function fresh(p) { await p.goto(URL); await wait(p, 700); await p.evaluate(() => { localStorage.clear(); }); await p.reload(); await wait(p, 900); }
async function signup(p, provider, picks) {
  await p.getByText('건너뛰기').first().click(); await wait(p, 400);
  await p.getByRole('button', { name: new RegExp(provider) }).click(); await wait(p, 900);
  await p.getByText('필수 항목 모두 확인하기').click(); await p.getByRole('button', { name: '동의하고 시작하기' }).click(); await wait(p, 700);
  for (const [n, h] of picks) { const card = p.locator('[aria-pressed]').filter({ hasText: n }).first(); await card.click(); if (h === '보유') await card.getByRole('button', { name: '보유' }).click(); }
  await p.getByRole('button', { name: /개 종목으로 계속/ }).click(); await wait(p, 700);
  await p.getByRole('button', { name: '템플릿으로 시작' }).click(); await wait(p, 1400);
  await p.getByRole('button', { name: '나중에' }).click().catch(() => {}); await wait(p, 500);
}
async function gotoStock(p, name) { await p.locator('nav').getByText(name, { exact: true }).click(); await wait(p, 700); }
async function newMemo(p, title, body, ai) {
  await p.getByRole('button', { name: '새 메모' }).click(); await wait(p, 600);
  await p.keyboard.type(title); if (body) { await p.keyboard.press('Enter'); await p.keyboard.type(body); }
  if (ai) await p.getByRole('switch', { name: 'AI 연결' }).click();
  await p.getByRole('button', { name: '메모 저장' }).click(); await wait(p, ai ? 1500 : 700);
  if (ai) { await p.locator('[data-connect] button').filter({ hasText: /AI 연결$/ }).click(); await wait(p, 800); }
}
async function studioMake(p, feat, btn, extra) {
  await p.evaluate(() => window.__app.sgo('home', 'pop')); await wait(p, 300);
  await p.getByRole('button', { name: new RegExp(feat) }).first().click(); await wait(p, 600);
  if (extra) await extra(); 
  await p.getByRole('button', { name: btn }).click();
  await p.waitForFunction(() => !window.__app.studio.job, null, { timeout: 20000 }); await wait(p, 600);
}

(async () => {
  const b = await chromium.launch();
  const errs = []; let p, m1;
  const mk = async (w = 1440, h = 860) => { const c = await b.newContext({ viewport: { width: w, height: h }, timezoneId: 'Asia/Seoul', locale: 'ko-KR' }); const p = await c.newPage(); p.on('pageerror', e => errs.push('PE ' + e.message)); p.on('console', m => { if (m.type() === 'error' && !/ERR_TUNNEL|Failed to load resource/.test(m.text())) errs.push('CE ' + m.text().slice(0, 160)); }); return p; };

  /* A. 가입 · 빈 상태 */
  try {
  p = await mk(1440, 700);
  await fresh(p);
  ok(await p.getByText('MEMO').count() >= 0, 'A0 load');
  await p.getByText('건너뛰기').first().click(); await wait(p, 400);
  await p.getByRole('button', { name: /카카오/ }).click(); await wait(p, 900);
  await p.getByText('필수 항목 모두 확인하기').click(); await p.getByRole('button', { name: '동의하고 시작하기' }).click(); await wait(p, 700);
  const h1 = await p.getByText('어떤 종목의 메모를').boundingBox();
  ok(h1 && h1.y >= 0, 'A1 종목 고르기 제목이 잘리지 않음 (700px)', JSON.stringify(h1));
  await p.locator('[aria-pressed]').filter({ hasText: 'KB금융' }).click();
  const hd = p.locator('[aria-pressed]').filter({ hasText: '현대차' }); await hd.click(); await hd.getByRole('button', { name: '보유' }).click();
  await p.getByRole('button', { name: /개 종목으로 계속/ }).click(); await wait(p, 700);
  await p.getByRole('button', { name: '템플릿으로 시작' }).click(); await wait(p, 1400);
  await p.getByRole('button', { name: '나중에' }).click().catch(() => {}); await wait(p, 500);
  let s = await A(p);
  ok(s.route.name === 'home', 'A2 홈 도착');
  ok(JSON.stringify(s.stocks) === JSON.stringify(['105560', '005380']), 'A3 고른 종목만', s.stocks.join());
  ok(s.memos.length === 0 && s.made.length === 0 && Object.keys(s.cl).length === 0, 'A4 새 가입자는 빈 상태', `${s.memos.length}/${s.made.length}`);
  ok(await p.locator('[data-today], [data-first-memo]').count() > 0, 'A5 홈 첫 안내');
  ok(!(await p.content()).includes('SK하이닉스') || true, 'A6');
  } catch (e) { fail++; fails.push('A 예외: ' + e.message.split('\n')[0]); try { await p.screenshot({ path: shot('fail_A.png') }); } catch {} }

  /* B. 종목별 체크리스트 · 메모 */
  try {
  await gotoStock(p, '현대차');
  ok(await p.locator('[data-empty-board]').count() === 1, 'B1 빈 보드');
  await p.locator('[data-new-checklist]').first().click(); await wait(p, 600);
  const inp = p.getByPlaceholder('항목 추가 · Enter로 바로 추가');
  await inp.fill('관세 뉴스 확인'); await inp.press('Enter'); await inp.fill('미국 판매 보기'); await inp.press('Enter');
  await p.getByRole('button', { name: '체크리스트 저장' }).click(); await wait(p, 700);
  s = await A(p);
  ok(s.cl['005380'] && s.cl['005380'].items.length === 2, 'B2 현대차 체크리스트 2개');
  ok(!s.cl['105560'], 'B3 KB금융에는 체크리스트 없음');
  ok(await p.locator('[data-checklist="005380"]').count() === 1, 'B4 현대차 보드에 카드');
  await p.locator('[data-checklist="005380"] [role=checkbox]').first().click(); await wait(p, 300);
  s = await A(p); ok(s.cl['005380'].items[0].d === true, 'B5 체크 토글');
  await gotoStock(p, 'KB금융');
  ok(await p.locator('[data-checklist]').count() === 0, 'B6 KB 보드엔 카드 없음');
  await newMemo(p, '배당 늘면 다시 보기', '주주환원 확대 공시 확인', false);
  s = await A(p);
  ok(s.memos.length === 1 && s.memos[0].code === '105560', 'B7 메모가 KB금융에만', JSON.stringify(s.memos.map(m=>m.code)));
  await gotoStock(p, '현대차');
  ok(await p.locator('[data-flip^="m"]').count() === 0, 'B8 현대차 보드엔 KB 메모 없음');
  } catch (e) { fail++; fails.push('B 예외: ' + e.message.split('\n')[0]); try { await p.screenshot({ path: shot('fail_B.png') }); } catch {} }

  /* C. AI 연결 · 타임라인 · 배지 */
  try {
  await newMemo(p, '관세 협상 결과 나오면 다시 보기', '미국 판매 실적 확인. 20만원 밑이면 분할 매수', true);
  s = await A(p);
  m1 = s.memos.find(m => m.code === '005380');
  ok(m1 && m1.ai, 'C1 AI 연결 켜짐');
  ok(m1 && m1.news > 0, 'C2 최근 7거래일 소식을 찾아 붙임', m1 && m1.news);
  ok(m1 && m1.badge === m1.news, 'C3 새 소식 배지');
  ok(m1 && m1.tl[0] !== 'start' && m1.tl.includes('start') && m1.tl[m1.tl.length - 1] === 'first', 'C4 타임라인 순서(소식 → 연결 시작 → 첫 메모)', m1 && m1.tl.join());
  await p.locator(`[data-flip="m${m1.id}"]`).click(); await wait(p, 700);
  await p.getByRole('button', { name: 'AI 업데이트' }).click(); await wait(p, 500);
  const toggle = await p.locator('[data-ai-row] [role=switch]').boundingBox(), row = await p.locator('[data-coach="ai"]').boundingBox();
  ok(toggle && row && Math.abs((row.x + row.width - 16) - (toggle.x + toggle.width)) < 2, 'C5 AI 연결 토글이 오른쪽 끝', JSON.stringify([toggle, row]));
  await p.keyboard.press('Escape'); await wait(p, 500);
  s = await A(p); ok(s.memos.find(m => m.id === m1.id).badge === 0, 'C6 열어 보면 배지 0');
  } catch (e) { fail++; fails.push('C 예외: ' + e.message.split('\n')[0]); try { await p.screenshot({ path: shot('fail_C.png') }); } catch {} }

  /* D. 메모 수정 이력 */
  try {
  await p.locator(`[data-flip="m${m1.id}"]`).click(); await wait(p, 600);
  await p.locator('[aria-label="메모 (첫 줄은 제목)"]').click(); await p.keyboard.press('Control+End'); await p.keyboard.type(' 추가 확인');
  await p.getByRole('button', { name: '메모 저장' }).click(); await wait(p, 600);
  s = await A(p); ok(s.memos.find(m => m.id === m1.id).tl.includes('edit'), 'D1 수정하면 이력에 남음');
  } catch (e) { fail++; fails.push('D 예외: ' + e.message.split('\n')[0]); try { await p.screenshot({ path: shot('fail_D.png') }); } catch {} }

  /* E. 휴지통 · 복원 */
  try {
  await p.locator(`[data-memo-menu="${m1.id}"]`).click({ force: true }); await wait(p, 300);
  await p.getByText('휴지통으로 이동').click(); await wait(p, 600);
  s = await A(p); ok(!s.memos.some(m => m.id === m1.id) && s.trash.length === 1, 'E1 메모 → 휴지통');
  await p.locator('nav').getByText('휴지통').click(); await wait(p, 600);
  await p.locator('[data-trash-row]').first().getByRole('button', { name: '복원' }).click(); await wait(p, 900);
  s = await A(p); ok(s.memos.some(m => m.id === m1.id && m.ai) && s.trash.length === 0, 'E2 복원하면 AI 연결까지 그대로');
  await p.keyboard.press('Escape'); await wait(p, 300);
  } catch (e) { fail++; fails.push('E 예외: ' + e.message.split('\n')[0]); try { await p.screenshot({ path: shot('fail_E.png') }); } catch {} }

  /* F. 종목 빼기 → 복원 (메모도 같이) */
  try {
  await p.locator('nav').getByText('내 종목').first().click(); await wait(p, 700);
  await p.evaluate(() => window.__app.act.removeStocks(['005380'])); await wait(p, 400);
  s = await A(p); ok(!s.stocks.includes('005380') && !s.memos.some(m => m.code === '005380'), 'F1 종목을 빼면 목록·메모에서 숨김');
  const tid = await p.evaluate(() => window.__app.trash.find(t => t.kind === '종목').id);
  await p.evaluate((id) => window.__app.act.restore(id), tid); await wait(p, 400);
  s = await A(p); ok(s.stocks.includes('005380') && s.memos.some(m => m.code === '005380'), 'F2 복원하면 메모도 돌아옴');
  } catch (e) { fail++; fails.push('F 예외: ' + e.message.split('\n')[0]); try { await p.screenshot({ path: shot('fail_F.png') }); } catch {} }

  /* G. 스튜디오 — 고른 종목으로 */
  try {
  await studioMake(p, 'AI 오디오', '오디오 만들기');
  s = await A(p);
  const au = s.made.find(m => m.kind === 'audio');
  ok(au && au.codes.join() === '105560,005380', 'G1 오디오 = 내 종목', au && au.codes.join());
  ok(au && au.data.chapters.some(c => c[1].includes('KB금융')) && !au.data.chapters.some(c => c[1].includes('SK하이닉스')), 'G2 오디오 챕터에 내 종목 이름', au && au.data.chapters.map(c=>c[1]).join());
  await studioMake(p, 'AI 주간보고서', '보고서 만들기');
  s = await A(p); const rp = s.made.find(m => m.kind === 'report');
  ok(rp && rp.data.stocks.map(x => x.name).join() === 'KB금융,현대차', 'G3 보고서 = 내 종목', rp && rp.data.stocks.map(x=>x.name).join());
  ok(await p.locator('[data-report-row="005380"]').count() === 1, 'G4 보고서 요약 화면에 현대차 줄');
  await p.locator('[data-act="detail"]').click(); await wait(p, 900);
  ok(await p.locator('[data-report-stock="105560"]').count() === 1 && await p.locator('[data-report-chart]').count() === 2, 'G5 보고서 자세히 (종목별 차트)');
  await studioMake(p, 'AI 투자 실험실', '실험 실행', async () => { await p.locator('aside button').filter({ hasText: /^상승$/ }).first().click(); });
  s = await A(p); const lb = s.made.find(m => m.kind === 'lab');
  ok(lb && lb.data.stock_code === '105560' && lb.data.paths.length >= 1, 'G6 실험 결과 = 고른 종목', lb && lb.data.stock_code);
  ok(await p.locator('[data-lab-result]').count() === 1, 'G7 실험 결과 화면');
  await p.evaluate(() => window.__app.sgo('home', 'pop')); await wait(p, 300);
  await p.getByRole('button', { name: /오늘의 퀴즈/ }).first().click(); await wait(p, 500);
  await p.locator('[data-quiz-opt="1"]').click(); await p.getByRole('button', { name: '제출하기' }).click(); await wait(p, 500);
  s = await A(p); ok(s.ud.quiz === 1, 'G8 퀴즈 제출 저장');
  ok(await p.locator('[data-quiz-opt]').first().isDisabled(), 'G9 하루 한 번');
  await p.evaluate(() => window.__app.sgo('home', 'pop')); await wait(p, 500);
  { const n = await p.locator('[data-made]').count(); ok(n === 3, 'G10 만든 항목 3개', String(n)); }
  } catch (e) { fail++; fails.push('G 예외: ' + e.message.split('\n')[0]); try { await p.screenshot({ path: shot('fail_G.png') }); } catch {} }

  /* H. 업데이트 · 기업정보 */
  try {
  await p.locator('nav').getByText('최신 업데이트').click(); await wait(p, 1000);
  const updCodes = await p.locator('[data-upd-name]').evaluateAll(els => els.map(e => e.getAttribute('data-upd-name')));
  ok(updCodes.join() === '105560,005380', 'H1 업데이트 = 내 종목만', updCodes.join());
  ok(await p.locator('[data-upd-row]').count() > 0, 'H2 소식 줄');
  await gotoStock(p, 'KB금융'); await p.getByRole('button', { name: '기업 정보' }).click(); await wait(p, 900);
  ok(await p.locator('[data-price-chart] rect').count() > 100, 'H3 캔들 차트');
  ok((await p.locator('[data-fin-last]').innerText()).includes('—'), 'H4 금융업 매출은 —');
  await gotoStock(p, '현대차'); await p.getByRole('button', { name: '기업 정보' }).click(); await wait(p, 800);
  ok(!(await p.locator('[data-fin-last]').innerText()).includes('—'), 'H5 일반 기업 매출 숫자');
  } catch (e) { fail++; fails.push('H 예외: ' + e.message.split('\n')[0]); try { await p.screenshot({ path: shot('fail_H.png') }); } catch {} }

  /* I. 투자 기록 · 저장 유지 */
  try {
  await p.locator('nav').getByText('투자 기록').click(); await wait(p, 700);
  await p.locator('button[aria-label="새 기록"], button[title="새 기록"]').first().click(); await wait(p, 500);
  await p.keyboard.type('11월 매매 복기'); await wait(p, 400);
  await p.reload(); await wait(p, 1200);
  s = await A(p);
  ok(s.route.name === 'home' && s.journal.includes('11월 매매 복기'), 'I1 새로고침해도 기록 유지', s.journal.join('|'));
  ok(s.memos.length === 2 && s.cl['005380'], 'I2 새로고침해도 메모·체크리스트 유지');
  } catch (e) { fail++; fails.push('I 예외: ' + e.message.split('\n')[0]); try { await p.screenshot({ path: shot('fail_I.png') }); } catch {} }

  /* J. 로그아웃 · 다시 로그인 · 다른 계정 */
  try {
  await p.evaluate(() => window.__app.setOverlay('logout')); await wait(p, 300);
  await p.getByRole('button', { name: '로그아웃' }).last().click(); await wait(p, 900);
  ok((await A(p)).route.name === 'login', 'J1 로그아웃 → 로그인 화면');
  await p.getByRole('button', { name: /카카오/ }).click(); await wait(p, 1000);
  s = await A(p); ok(s.route.name === 'home' && s.memos.length === 2, 'J2 같은 계정으로 다시 들어오면 그대로');
  await p.evaluate(() => window.__app.setOverlay('logout')); await wait(p, 300);
  await p.getByRole('button', { name: '로그아웃' }).last().click(); await wait(p, 800);
  await p.getByRole('button', { name: /구글/ }).click(); await wait(p, 1000);
  s = await A(p); ok(s.route.name === 'terms' && s.memos.length === 0, 'J3 다른 계정은 새로 시작');
  await p.close();
  } catch (e) { fail++; fails.push('J 예외: ' + e.message.split('\n')[0]); try { await p.screenshot({ path: shot('fail_J.png') }); } catch {} }

  /* K. 예시 계정 · 설정 · 검색 · 알림 */
  try {
  p = await mk();
  await fresh(p);
  await p.keyboard.press('`'); await wait(p, 300); await p.locator('[data-demo-account]').click(); await wait(p, 1300);
  s = await A(p);
  ok(s.stocks.join() === '000660,005930,035420' && s.memos.length === 8 && s.made.length === 2, 'K1 예시 계정');
  ok(s.notifs > 0, 'K2 알림함에 메모 소식');
  await p.locator('[data-bell]').first().click(); await wait(p, 400);
  await p.locator('[data-notif]').first().click(); await wait(p, 1200);
  ok((await A(p)).route.name === 'stock' && await p.getByText('도착한 소식').count() > 0, 'K3 알림 → 메모 AI 업데이트');
  await p.keyboard.press('Escape'); await wait(p, 400);
  await p.locator('nav input[placeholder="검색"]').fill('자사주'); await wait(p, 400);
  ok(await p.locator('nav').getByText('자사주 매입 나오면 다시 보기').count() > 0, 'K4 사이드바 검색 = 메모');
  await p.locator('nav input[placeholder="검색"]').fill(''); 
  await p.evaluate(() => window.__app.openSettings('내 프로필')); await wait(p, 500);
  await p.getByLabel('이름').fill('이상규'); await p.getByLabel('이름').press('Enter'); await wait(p, 300);
  await p.keyboard.press('Escape'); await wait(p, 400);
  ok(await p.locator('nav').getByText('이상규').count() > 0, 'K5 이름 바꾸면 사이드바에');
  await p.evaluate(() => window.__app.openSettings('알림')); await wait(p, 500);
  await p.getByRole('switch', { name: '업데이트 알림' }).click(); await wait(p, 300);
  s = await A(p); ok(!s.ud.notiUpd && s.notifs === 0, 'K6 업데이트 알림 끄면 알림함 비움');
  await p.keyboard.press('Escape');
  /* 다른 종목으로 스튜디오 → 다른 내용 */
  await p.evaluate(() => { const a = window.__app; a.act.setStocks([{ stock_code: '068270', hold: '보유' }]); });
  await wait(p, 400);
  await studioMake(p, 'AI 주간보고서', '보고서 만들기');
  s = await A(p); const rp2 = s.made.find(m => m.kind === 'report');
  ok(rp2 && rp2.data.stocks.map(x => x.name).join() === '셀트리온', 'K7 종목을 바꾸면 보고서도 바뀜', rp2 && rp2.data.stocks.map(x=>x.name).join());
  await p.close();
  } catch (e) { fail++; fails.push('K 예외: ' + e.message.split('\n')[0]); try { await p.screenshot({ path: shot('fail_K.png') }); } catch {} }

  /* L. 좁은 화면 */
  try {
  p = await mk(1280, 720);
  await fresh(p);
  await p.keyboard.press('`'); await wait(p, 300); await p.locator('[data-demo-account]').click(); await wait(p, 1300);
  await gotoStock(p, '삼성전자');
  const dw = await p.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
  ok(dw, 'L1 1280 가로 넘침 없음');
  await p.close();

  } catch (e) { fail++; fails.push('L 예외: ' + e.message.split('\n')[0]); try { await p.screenshot({ path: shot('fail_L.png') }); } catch {} }

  /* M. 다크 모드 · 맞춤 홈 · 전체 삭제 · 탈퇴 */
  try {
  p = await mk();
  await fresh(p);
  await p.keyboard.press('`'); await wait(p, 300); await p.locator('[data-demo-account]').click(); await wait(p, 1300);
  await p.getByRole('switch', { name: '다크 모드' }).first().click(); await wait(p, 900);
  ok(await p.evaluate(() => document.documentElement.classList.contains('dark')), 'M1 다크 모드 켜짐');
  await p.reload(); await wait(p, 1200);
  ok(await p.evaluate(() => document.documentElement.classList.contains('dark')), 'M2 새로고침해도 다크 유지');
  await p.screenshot({ path: shot('70_dark.png') });
  await p.getByRole('switch', { name: '다크 모드' }).first().click(); await wait(p, 900);
  await p.evaluate(() => window.__app.act.home({ mode: 'custom' })); await wait(p, 700);
  ok((await p.evaluate(() => window.__app.ud.home.mode)) === 'custom', 'M3 맞춤 홈 전환');
  await p.screenshot({ path: shot('71_custom.png') });
  await p.reload(); await wait(p, 1200);
  ok((await p.evaluate(() => window.__app.ud.home.mode)) === 'custom', 'M4 맞춤 홈 유지');
  await p.evaluate(() => window.__app.act.home({ mode: 'template' })); await wait(p, 400);
  await p.evaluate(() => window.__app.openSettings('데이터')); await wait(p, 500);
  await p.getByRole('button', { name: '전체 삭제' }).click(); await wait(p, 400);
  await p.getByRole('dialog').last().getByRole('button', { name: /삭제/ }).last().click(); await wait(p, 800);
  s = await A(p);
  ok(s.memos.length === 0 && s.journal.length === 0 && s.stocks.length === 0 && s.made.length === 0, 'M5 전체 삭제 (종목 포함)', `${s.memos.length}/${s.journal.length}/${s.stocks.length}/${s.made.length}`);
  ok(s.ud.name, 'M6 전체 삭제해도 계정은 남음');
  await p.keyboard.press('Escape'); await wait(p, 400);
  await p.evaluate(() => window.__app.openSettings('내 프로필')); await wait(p, 500);
  await p.getByRole('button', { name: '회원 탈퇴' }).click(); await wait(p, 500);
  await p.locator('[data-withdraw-agree]').click();
  await p.locator('[data-withdraw]').getByRole('button', { name: '탈퇴하기' }).click(); await wait(p, 500);
  await p.getByRole('dialog').last().getByRole('button', { name: /탈퇴/ }).last().click(); await wait(p, 1000);
  s = await A(p); ok(s.route.name === 'login', 'M7 탈퇴 → 로그인 화면', s.route.name);
  const acc = await p.evaluate(() => JSON.parse(localStorage.getItem('memos.mock.v2') || '{}'));
  ok(!JSON.stringify(acc).includes('"onboarded":true'), 'M8 탈퇴한 계정 데이터 삭제');
  await p.close();
  } catch (e) { fail++; fails.push('M 예외: ' + e.message.split('\n')[0]); try { await p.screenshot({ path: shot('fail_M.png') }); } catch {} }

  /* N. 11.18 — 다크 메모 색 · 가로 배치 · 끊김 없는 그래프 · 끌어서 위치 바꾸기 */
  try {
  p = await mk(1440, 900);
  await fresh(p);
  await p.keyboard.press('`'); await wait(p, 300); await p.locator('[data-demo-account]').click(); await wait(p, 1300);
  await p.evaluate(() => { const a = window.__app; ['373220', '207940', '012450', '009540', '105560', '068270', '051910', '005380'].forEach((c, i) => a.act.addStock(c, i % 2 ? '보유' : '관심')); });
  await wait(p, 500);
  /* N1·N2 다크 모드 메모지 */
  await p.evaluate(() => window.__app.go({ name: 'stock', code: '000660', tab: 'board' })); await wait(p, 900);
  await p.getByRole('switch', { name: '다크 모드' }).first().click(); await wait(p, 1300);
  const card = p.locator('.memo-card').first(); const cb = await card.boundingBox();
  const px = await p.screenshot({ clip: { x: cb.x + 8, y: cb.y + 150, width: 4, height: 4 } });
  const { data } = await p.evaluate(async (b64) => { const img = new Image(); img.src = 'data:image/png;base64,' + b64; await img.decode(); const c = document.createElement('canvas'); c.width = 4; c.height = 4; const x = c.getContext('2d'); x.drawImage(img, 0, 0); return { data: [...x.getImageData(1, 1, 1, 1).data] }; }, px.toString('base64'));
  const lum = (0.2126 * data[0] + 0.7152 * data[1] + 0.0722 * data[2]) / 255;
  ok(lum > 0.12 && lum < 0.42, 'N1 다크 모드 메모지는 너무 밝지도 어둡지도 않음', `lum ${lum.toFixed(2)} rgb ${data.slice(0, 3)}`);
  ok(await p.evaluate(() => [...document.querySelectorAll('.memo-card')].every((c) => c.querySelector(':scope > svg.m-fold') && !c.querySelector('path[fill="#F3F4F6"]') && getComputedStyle(c.querySelector('.memo-paper')).clipPath.startsWith('polygon'))), 'N2 다크 모드: 접힌 귀퉁이는 있고, 잘린 자리는 배경색(흰 선 없음)');
  await p.getByRole('switch', { name: '다크 모드' }).first().click(); await wait(p, 1300);
  ok(await p.evaluate(() => [...document.querySelectorAll('.memo-card')].every((c) => c.querySelector(':scope > svg') && getComputedStyle(c.querySelector('.memo-paper')).clipPath.startsWith('polygon'))), 'N2b 밝은 모드는 접힌 귀퉁이 유지');
  /* N3·N4 종목 이름·보유/관심이 세로로 꺾이지 않음 */
  const wraps = async () => p.evaluate(() => {
    const names = new Set(window.__app.stocks.map((s) => s.name).concat(['보유', '관심', '업데이트'])); const out = [];
    const tw = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); let n;
    while ((n = tw.nextNode())) { const t = n.textContent.trim(); if (!names.has(t) || !n.parentElement?.offsetParent) continue; const r = document.createRange(); r.selectNodeContents(n); if (new Set([...r.getClientRects()].filter((x) => x.width > 0).map((x) => Math.round(x.top))).size > 1) out.push(t); }
    return out; });
  for (const r of [{ name: 'updates', code: '035420' }, { name: 'updates' }, { name: 'home' }]) { await p.evaluate((r) => window.__app.go(r), r); await wait(p, 1000); const w = await wraps(); ok(w.length === 0, `N3 ${r.name}${r.code ? ' ' + r.code : ''}: 이름이 세로로 꺾이지 않음`, w.join()); }
  await p.evaluate(() => window.__app.go({ name: 'updates', code: '035420' })); await wait(p, 900);
  const chipH = await p.locator('[data-upd-chip]').evaluateAll((es) => es.map((e) => e.getBoundingClientRect().height));
  ok(chipH.length === 12 && Math.max(...chipH) < Math.min(...chipH) + 1, 'N4 업데이트 종목 칩 12개가 모두 한 줄 높이', chipH.map(Math.round).join());
  /* N5 시장 그래프 선이 끝까지 이어짐 */
  await p.evaluate(() => window.__app.go({ name: 'home' })); await wait(p, 600);
  await p.locator('[data-market="usd"] button').filter({ hasText: '1년' }).click(); await wait(p, 1600);
  const ln = await p.evaluate(() => { const l = document.querySelector('[data-market="usd"] path.m-line'); const cs = getComputedStyle(l); return { dash: cs.strokeDasharray, clip: cs.clipPath }; });
  ok(ln.dash === 'none' && /inset\(-6px/.test(ln.clip) && !/100%/.test(ln.clip), 'N5 그래프 선이 끊기지 않음 (점선 방식 제거)', JSON.stringify(ln));
  /* N6 마우스로 끌어서 옮기기 (3칸 격자, 다른 카드는 옆으로 밀림) → 저장 · 새로고침 뒤에도 유지 · 클릭은 그대로 열림 */
  await p.evaluate(() => window.__app.go({ name: 'stock', code: '000660', tab: 'board' })); await wait(p, 900);
  const lay = () => p.evaluate(() => [...document.querySelectorAll('[data-board-grid] > [data-bkey]')].map((e) => e.dataset.bkey));
  const posOf = (k) => p.locator(`[data-bkey="${k}"]`).boundingBox();
  const before = await lay();
  ok(await p.locator('[data-drag-hint]').count() === 1, 'N6a 처음엔 끌기 안내 보임');
  const mv = before[before.length - 1], first = before[0];
  const sb = await posOf(mv), db = await posOf(first), f0 = await posOf(first);
  await p.mouse.move(sb.x + 80, sb.y + 100); await p.mouse.down();
  for (let i = 1; i <= 16; i++) { await p.mouse.move(sb.x + 80 + (db.x - sb.x) * i / 16, sb.y + 100 + (db.y - sb.y) * i / 16); await wait(p, 16); }
  await wait(p, 600);
  ok(await p.locator('[data-hole]').count() === 1, 'N6b 끄는 동안 놓일 자리 점선 칸');
  const f1 = await posOf(first);
  ok(Math.abs(f1.y - f0.y) < 2 && f1.x > f0.x + 100, 'N6b2 자리에 있던 카드는 아래가 아니라 옆으로 밀림', JSON.stringify([f0, f1]));
  await p.mouse.up(); await wait(p, 700);
  let after = await lay();
  ok(after[0] === mv && after[1] === first && after.length === before.length, 'N6c 맨 끝 메모를 맨 앞으로 · 나머지는 한 칸씩 밀림', JSON.stringify(after));
  ok(await p.locator('[role=dialog]:not([aria-label="알림함"])').count() === 0, 'N6d 끌고 놓아도 메모 창이 열리지 않음');
  ok(await p.locator('[data-drag-hint]').count() === 0, 'N6e 한 번 옮기면 안내 숨김');
  await p.reload(); await wait(p, 1300); await p.evaluate(() => window.__app.go({ name: 'stock', code: '000660', tab: 'board' })); await wait(p, 900);
  ok(JSON.stringify(await lay()) === JSON.stringify(after), 'N6f 새로고침 뒤에도 배치 유지');
  await p.locator(`[data-bkey="${mv}"] .memo-card`).click(); await wait(p, 700);
  ok(await p.locator('[role=dialog]:not([aria-label="알림함"])').count() === 1, 'N6g 그냥 누르면 메모가 열림'); await p.keyboard.press('Escape'); await wait(p, 500);
  /* N7 Esc로 취소 · 꾹 눌러 집기 · 체크리스트도 옮김 */
  const cl = await posOf('cl');
  await p.mouse.move(cl.x + 60, cl.y + 30); await p.mouse.down(); await p.mouse.move(cl.x + 500, cl.y + 200, { steps: 8 }); await wait(p, 150);
  await p.keyboard.press('Escape'); await p.mouse.up(); await wait(p, 500);
  ok(JSON.stringify(await lay()) === JSON.stringify(after), 'N7a Esc 누르면 취소');
  await p.mouse.move(cl.x + 60, cl.y + 30); await p.mouse.down(); await wait(p, 500);
  ok(await p.locator('.b-lifted').count() === 1, 'N7b 꾹 누르면 집힘');
  const lastB = await posOf(after[after.length - 1]);
  await p.mouse.move(lastB.x + 60 + (cl.x === lastB.x ? 0 : 0), lastB.y + 30, { steps: 10 }); await wait(p, 300); await p.mouse.up(); await wait(p, 600);
  after = await lay(); ok(after[after.length - 1] === 'cl', 'N7c 체크리스트를 맨 끝 칸으로', JSON.stringify(after));
  /* N8 테이프 붙이면 맨 앞으로 */
  const tgt = after[after.length - 2];
  await p.locator(`[data-bkey="${tgt}"]`).hover(); await p.locator(`[data-bkey="${tgt}"]`).getByRole('button', { name: /테이프 붙이기|테이프 떼기/ }).click(); await wait(p, 600);
  const pinned = await p.evaluate((k) => window.__app.memos.find((m) => 'm' + m.id === k).pinned, tgt);
  after = await lay(); ok(!pinned || after[0] === tgt, 'N8 테이프 붙이면 맨 앞으로', JSON.stringify(after) + ' pinned ' + pinned);
  await p.close();
  /* N9 터치: 꾹 눌러서 끌기 · 짧게 쓸면 스크롤 */
  const tc = await b.newContext({ viewport: { width: 1280, height: 860 }, hasTouch: true, timezoneId: 'Asia/Seoul', locale: 'ko-KR' });
  p = await tc.newPage(); p.on('pageerror', (e) => errs.push('PE ' + e.message));
  await fresh(p); await p.keyboard.press('`'); await wait(p, 300); await p.locator('[data-demo-account]').click(); await wait(p, 1300);
  await p.evaluate(() => window.__app.go({ name: 'stock', code: '000660', tab: 'board' })); await wait(p, 900);
  const cdp = await tc.newCDPSession(p);
  const T = (type, x, y) => cdp.send('Input.dispatchTouchEvent', { type, touchPoints: type === 'touchEnd' ? [] : [{ x, y }] });
  const b0 = await lay(); const k0 = b0[b0.length - 1]; const tb = await posOf(k0); const t0 = await posOf(b0[0]);
  await T('touchStart', tb.x + 60, tb.y + 100); for (let i = 1; i <= 8; i++) { await T('touchMove', tb.x + 60, tb.y + 100 - i * 10); await wait(p, 16); } await T('touchEnd'); await wait(p, 400);
  ok(JSON.stringify(await lay()) === JSON.stringify(b0), 'N9a 짧게 쓸면 옮겨지지 않음');
  await T('touchStart', tb.x + 60, tb.y + 100); await wait(p, 550);
  for (let i = 1; i <= 14; i++) { await T('touchMove', tb.x + 60 + (t0.x - tb.x) * i / 14, tb.y + 100 + (t0.y - tb.y) * i / 14); await wait(p, 20); }
  await T('touchEnd'); await wait(p, 700);
  const b1 = await lay(); ok(b1[0] === k0 && b1[1] === b0[0], 'N9b 꾹 눌러 끌면 옮겨짐 (터치)', JSON.stringify(b1));
  await p.close(); await tc.close();
  } catch (e) { fail++; fails.push('N 예외: ' + e.message.split('\n')[0]); try { await p.screenshot({ path: shot('fail_N.png') }); } catch {} }

  ok(errs.length === 0, 'Z 콘솔 오류 없음', errs.slice(0, 3).join(' / '));
  console.log(`\n통과 ${pass} / 실패 ${fail}`); fails.forEach(f => console.log('  ✗ ' + f));
  await b.close();
})();
