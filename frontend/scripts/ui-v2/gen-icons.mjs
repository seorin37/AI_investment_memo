// 3) WORK/svgs.json · websvgs.json → src/ui/icons/*.data.ts (react-native-svg 로 그릴 노드 배열) + 로고
// 이름은 추출 번호(갤러리 svgs.html · websvgs.html 의 번호)로 붙임. 원본이 바뀌어 번호가 밀리면 이름표도 고칠 것
import fs from 'node:fs';
import path from 'node:path';
import { APP_DIR, OUT, WEB_SRC, WORK } from './paths.mjs';
const I = WORK + path.sep;
const WEBSRC = WEB_SRC + path.sep;
const OUTD = OUT + path.sep;
fs.mkdirSync(OUTD, { recursive: true });

const APP_NAMES = `0 sbWifi,1 sbSignal,2 sbBattery,3 plugMini,4 artNoteCorner,5 waveBlue,6 playTri,7 reportFile,8 artLineUp,9 wifiOff,10 kakao,11 naver,12 google,13 back,14 check,15 chevRightSm,16 searchSm,17 template,18 sliders,19 doneCircle,20 tabHome,21 tabUpdates,22 tabStocks,23 tabJournal,24 person,25 chevRightXs,26 search,27 play,28 bell,29 stocks,30 journal,31 tabStudio,32 close,33 shield,34 plugPurple,35 tagSm,36 plusSm,37 refresh,38 chevDownSm,39 checkLg,40 plus,42 slidersSm,43 external,44 circleLg,46 grip,47 artSlider,48 ringPurple,50 checkSm,52 checkAll,53 pause,54 checkBadge,55 chevRight,56 chevDown,58 noteFold,59 checkXs,60 artMemoNews,61 plusThin,62 closeSm,63 info,64 moreV,65 stocksBlue,66 bellGold,67 trash,68 checkMini,69 circle,70 checkMini2,71 gripSm,72 plusWhite,73 closeThin,74 plugSm,75 tape,76 foldCorner,78 star,79 calc,80 trashSm,81 chevRightWhite,82 battery,83 back2,84 moreV2,85 artSparkRed,86 viewGrid,87 viewList,88 checkSquare,89 noteLines,90 docLines,91 audio,92 help,93 lab,94 docSm,95 alert,96 audioWhite,97 skipNext,98 closeGray,99 homeLg,100 frame,101 pin,102 palette,103 plug,104 copy,105 trashMd,106 moreH,107 clock,108 plugLg,109 pinSm,110 trashXs,111 checkW1,112 checkW2,113 checkOrange,114 checkW3,115 checkW4,116 noteCorner,117 docBox,118 chevDownXs,119 docSm2,120 pencil,121 chartLine,124 trend,125 edit,126 checkSquare2,127 pencilWhite,128 pencilSm,129 sparkle,130 arrowRight,131 closeWhite,134 chartSquare,135 moreHPurple,136 mic,137 compose,138 back3,139 share,140 undo,141 checklist,142 closeMd,143 pin2,144 chevDown2,145 docPurple,146 zoomOut,147 image,148 camera,149 artSparkPurple,150 bolt,151 reportLg,152 exclaim,153 playLg,154 won,155 audioWhite2,156 checkW5,158 playWhite,159 chevRight2,160 starPurple,161 lock,162 speaker,163 okCircle,164 failCircle,166 eye,171 dot,172 chevDown3,173 checkPurple,174 minus,175 starOutline,176 undo2,177 trashRed,178 sun,179 moon,180 sparkleOrange,181 bellOff,182 searchGray,183 noteSm,184 compass,185 playSm`;
const WEB_NAMES = `0 panelLg,1 panelOpenLg,2 chevUpLg,3 plusLg,5 checkWhiteSm,6 okGreen,7 sparkleSm,8 circleSm,9 sparkleNudge,10 dotsH,11 flask,12 helpRing,13 boltOutline,14 chevRightBold,15 chevLeftSm,16 arrowLeft,17 closeBold,18 checkBold,19 studioFold,20 studioUnfold,21 pauseBold,22 playBold,23 alertRed,24 pauseSm,25 playSm,26 closeWhite,27 ringBold,28 xBold,29 clockGreen,30 chevDownSm,31 checkWhite,32 checkboxOn,33 squareWhite,34 wifiOff,35 alertGray,36 pin,37 trashLine,38 copy,39 share,40 searchSm,41 swap,42 chartBox,43 checkCircle,44 bellLg,45 plug,46 sparkleWhite,52 ring,53 plusWhite,54 plusMd,55 checkSm,56 closeXs,58 arrowRightGray,59 edit,60 note,61 palette,65 caretUp,66 chevRight,68 replyDown,69 pencil,70 grip,71 minus,72 okGreenSm,73 close,74 closeThin,75 searchGray,76 pencilMd,77 chevDown,78 closeGray,79 checkWhite2,80 image,81 kakao,82 naver,83 google,84 template,85 sliders,86 gripXs,87 viewGrid,88 viewList,89 checkWhite3,90 chevLeft,91 chevRightThin,92 chevRight2,93 searchLight,94 searchMd,95 checkCircleFilled,98 closeMd,99 chevLeft2,100 checkMd,101 radioOn,104 chevDown2,105 checkThin,106 undo,107 trashMd,108 helpGray,109 checkXs,110 chevRightLight,111 plugSm,112 flagKr,113 flagKr2,114 flagUs,115 arrowCorner,116 arrowRightLong`;
const names = (s) => new Map(s.split(',').map((x) => x.trim().split(' ')).map(([i, n]) => [+i, n]));

const camel = (k) => (k.startsWith('aria-') || k.startsWith('data-') ? null : k.replace(/-([a-z])/g, (_, c) => c.toUpperCase()));
const DROP = new Set(['class', 'className', 'style', 'xmlns', 'role', 'focusable', 'xmlns:xlink', 'xml:space', 'version']);
function parse(svg, prefix) {
  const root = { tag: 'root', attrs: {}, kids: [] }; const st = [root];
  /* 태그 안에 JSX 찌꺼기(`}`)나 값 없는 속성(aria-hidden)이 있어도 읽히게: 속성은 아래에서 따로 뽑음 */
  for (const m of svg.matchAll(/<(\/?)([a-zA-Z]+)((?:"[^"]*"|[^>"])*?)(\/?)>/g)) {
    const [, close, tag, a, self] = m;
    if (close) { st.pop(); continue; }
    const attrs = {};
    for (const x of a.matchAll(/([\w:-]+)="([^"]*)"/g)) {
      if (DROP.has(x[1])) continue; const k = camel(x[1]); if (!k) continue;
      let v = x[2];
      /* JS 식(${...})을 바꾼 자리: 색이 아닌 속성이면 버림 (네이티브는 'currentColor' 를 숫자·경로로 못 읽음) */
      if (v.includes('currentColor') && !['stroke', 'fill', 'stopColor', 'color'].includes(k)) continue;
      if (k === 'id') v = prefix + '_' + v;
      v = v.replace(/url\(#([^)]+)\)/g, (_, id) => `url(#${prefix}_${id})`);
      attrs[k] = /^-?\d+(\.\d+)?$/.test(v) && !['d', 'points', 'viewBox', 'offset'].includes(k) ? +v : v;
    }
    const node = { tag, attrs, kids: [] };
    st[st.length - 1].kids.push(node);
    if (!self && tag !== 'stop') st.push(node);
    else if (tag === 'stop' && !self) st.push(node);
  }
  return root.kids[0];
}
const PAINTS = ['stroke', 'fill', 'stopColor'];
function mainColor(n, cnt = new Map()) {
  for (const k of PAINTS) { const v = n.attrs[k]; if (typeof v === 'string' && !/^(none|white|#fff|#ffffff|transparent)$/i.test(v) && !v.startsWith('url(')) cnt.set(v.toUpperCase() === 'CURRENTCOLOR' ? 'currentColor' : v, (cnt.get(v) || 0) + 1); }
  n.kids.forEach((k) => mainColor(k, cnt));
  return cnt;
}
const ser = (n) => { const a = JSON.stringify(n.attrs); return n.kids.length ? `['${n.tag}', ${a}, [${n.kids.map(ser).join(', ')}]]` : `['${n.tag}', ${a}]`; };
function def(name, raw) {
  const svg = parse(raw, name);
  const vb = svg.attrs.viewBox || `0 0 ${svg.attrs.width} ${svg.attrs.height}`;
  const [, , vw, vh] = String(vb).split(/[\s,]+/).map(Number);
  const w = +svg.attrs.width || vw, h = +svg.attrs.height || vh;
  // svg 자체의 fill/stroke 는 첫 g 처럼 물려줌
  const rootPaint = {}; for (const k of ['fill', 'stroke', 'strokeWidth', 'strokeLinecap', 'strokeLinejoin']) if (svg.attrs[k] != null) rootPaint[k] = svg.attrs[k];
  const kids = Object.keys(rootPaint).length ? [{ tag: 'g', attrs: rootPaint, kids: svg.kids }] : svg.kids;
  const cnt = mainColor({ attrs: {}, kids }); const main = [...cnt.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? '#16171A';
  return `  ${name}: { vb: '${vb}', w: ${w}, h: ${h}, main: '${main}', nodes: [${kids.map(ser).join(', ')}] },`;
}
function file(kind, title, entries) {
  return `/* 자동 생성 (frontend/scripts/ui-v2/gen-icons.mjs) — ${title}. 손으로 고치지 말고 생성기를 다시 돌릴 것 */
import type { IconDef } from './iconTypes';

export const ${kind} = {
${entries.join('\n')}
} satisfies Record<string, IconDef>;
`;
}
// 앱
const app = JSON.parse(fs.readFileSync(I + 'svgs.json', 'utf8'));
const an = names(APP_NAMES);
const appEntries = app.filter((e) => an.has(e.i)).map((e) => def(an.get(e.i), e.raw));
fs.writeFileSync(OUTD + 'appIcons.data.ts', file('APP_ICONS', '앱 원본 HTML 10개 + x/app.js 의 아이콘 (모양이 같으면 하나)', appEntries));
// 웹: fig.tsx 의 Icon 세트(S() 로 그린 것) + 화면 tsx 인라인 svg
const fig = fs.readFileSync(WEBSRC + 'fig.tsx', 'utf8');
const figEntries = [];
for (const m of fig.matchAll(/case "(\w+)": return <svg \{\.\.\.v\} viewBox="([^"]+)">([\s\S]*?)<\/svg>;/g)) {
  const [, n, vb, body] = m; const parts = [];
  for (const s of body.matchAll(/S\(\{([^}]*)\}\)/g)) {
    const o = s[1]; const d = /d: "([^"]+)"/.exec(o)[1]; const fill = /fill: true/.test(o); const sw = /sw: ([\d.]+)/.exec(o)?.[1] ?? '1.33333';
    const c = /c: c === "#333333" \? "(#\w+)"/.exec(o)?.[1] ?? 'currentColor';
    parts.push(fill ? `<path d="${d}" fill="${c}"/>` : `<path d="${d}" stroke="currentColor" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round" fill="none"/>`);
  }
  for (const s of body.matchAll(/<path ([^>]*)\/>/g)) parts.push('<path ' + s[1].replace(/=\{c\}/g, '="currentColor"').replace(/strokeWidth/g, 'stroke-width').replace(/strokeLinecap/g, 'stroke-linecap').replace(/strokeLinejoin/g, 'stroke-linejoin') + '/>');
  figEntries.push(def(n, `<svg width="20" height="20" viewBox="${vb}">${parts.join('')}</svg>`).replace(/main: '[^']*'/, "main: 'currentColor'"));
}
const web = JSON.parse(fs.readFileSync(I + 'websvgs.json', 'utf8'));
const wn = names(WEB_NAMES);
const webEntries = web.filter((e) => wn.has(e.i)).map((e) => def(wn.get(e.i), e.raw));
fs.writeFileSync(OUTD + 'webIcons.data.ts', file('WEB_ICONS', '웹 원본 fig.tsx Icon 세트 + 화면 tsx 인라인 svg (앱 아이콘과 같은 모양은 앱 세트에)', [...figEntries, ...webEntries]));
console.log('app', appEntries.length, 'web fig', figEntries.length, 'web inline', webEntries.length);

// 로고: 앱 홈 머리의 svg.logo (171×54) · 웹 kit.tsx Logo (LOGO_D) · 웹 사이드바 워드마크 PNG
const home = fs.readFileSync(path.join(APP_DIR, 'home.html'), 'utf8');
const appLogo = /<svg class="logo"[\s\S]*?<\/svg>/.exec(home)[0];
const logoTs = fs.readFileSync(WEBSRC + 'logo.ts', 'utf8');
const LD = /LOGO_D = "([^"]+)"/.exec(logoTs)[1], LVB = /LOGO_VB = "([^"]+)"/.exec(logoTs)[1];
const [, , lw, lh] = LVB.split(' ').map(Number);
const webLogo = `<svg width="${lw}" height="${lh}" viewBox="${LVB}"><path fill-rule="evenodd" fill="#111111" d="${LD}"/></svg>`;
fs.writeFileSync(OUTD + 'logo.data.ts', `/* 자동 생성 (frontend/scripts/ui-v2/gen-icons.mjs) — 로고. 손으로 고치지 말고 생성기를 다시 돌릴 것 */
import type { IconDef } from './iconTypes';

export const LOGOS = {
${def('app', appLogo)}
${def('web', webLogo)}
} satisfies Record<string, IconDef>;
`);
const wm = fs.readFileSync(WEBSRC + 'assets_wm.ts', 'utf8');
const b64 = /WORDMARK = "data:image\/png;base64,([^"]+)"/.exec(wm)[1];
fs.writeFileSync(OUTD + 'wordmark-web.png', Buffer.from(b64, 'base64'));
console.log('logos ok', appLogo.length, LD.length);
