"""실행 폴더의 미리듣기 페이지 (player.html). 오디오·챕터·대본 따라가기·출처를 한 화면에서 본다 (브라우저로 파일을 열면 된다)."""
from __future__ import annotations

import html
import json

PAGE = """<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
 body{font-family:-apple-system,"Malgun Gothic","Apple SD Gothic Neo",sans-serif;max-width:760px;margin:24px auto;padding:0 16px;color:#1A1A1A}
 h1{font-size:20px;margin:0 0 4px} .meta{color:#666;font-size:13px;margin-bottom:12px}
 audio{width:100%;margin:8px 0 16px}
 .chapters button{border:1px solid #ccd;background:#F5F5F5;border-radius:14px;padding:4px 10px;margin:0 6px 6px 0;cursor:pointer;font-size:13px}
 .line{display:flex;gap:10px;padding:6px 8px;border-radius:6px;cursor:pointer}
 .line:hover{background:#F5F5F5} .line.on{background:#E8EDF5}
 .t{color:#888;font-size:12px;min-width:38px;padding-top:2px} .sp{font-weight:700;min-width:16px;color:#1A3C6E}
 .sp.B{color:#555} .say{font-size:12px;color:#888;margin-top:2px} .refs{font-size:11px;color:#1A3C6E}
 h2{font-size:15px;margin:22px 0 8px} li{font-size:13px;margin:4px 0} .warn{color:#C0392B;font-size:13px}
 label{font-size:12px;color:#666}
</style></head><body>
<h1>__TITLE__</h1>
<div class="meta" id="meta"></div>
<div class="warn" id="warn"></div>
__AUDIO__
<div class="chapters" id="chapters"></div>
<label><input type="checkbox" id="showSay"> TTS에 보낸 읽기 문장도 보기</label>
<div id="script"></div>
<h2>출처</h2><ul id="sources"></ul>
<h2>메모 연결</h2><div id="memo" style="font-size:13px"></div>
<script>
const C = __CONTENT__;
const LINES = __LINES__;
const audio = document.getElementById('audio');
const fmt = s => `${Math.floor(s/60)}:${String(Math.floor(s%60)).padStart(2,'0')}`;
document.getElementById('meta').textContent =
  `${C.period.start} ~ ${C.period.end} · ${C.stocks.length}종목 · ${fmt(C.dur)} · 대본 ${({llm: 'LLM', rules: '규칙(대체)', file: '파일'})[C.source] || C.source} · ${C.prompt_version || ''}`;
if (C.source === 'rules') document.getElementById('warn').textContent = 'LLM 대본이 검사를 통과하지 못해 규칙 대본으로 만들었어요 (meta.json 확인).';
const seek = t => { if (audio) { audio.currentTime = t; audio.play(); } };
const ch = document.getElementById('chapters');
C.chapters.forEach(([t, name]) => { const b = document.createElement('button'); b.textContent = `${fmt(t)} ${name}`; b.onclick = () => seek(t); ch.appendChild(b); });
const box = document.getElementById('script');
const rows = C.script.map(([t, sp, text], i) => {
  const d = document.createElement('div'); d.className = 'line';
  const refs = (LINES[i] && LINES[i].refs.length) ? `<div class="refs">${LINES[i].refs.join(', ')}</div>` : '';
  d.innerHTML = `<div class="t">${fmt(t)}</div><div class="sp ${sp}">${sp}</div><div><div>${esc(text)}</div>`
    + `<div class="say" style="display:none">${esc(LINES[i] ? LINES[i].speech : '')}</div>${refs}</div>`;
  d.onclick = () => seek(t); box.appendChild(d); return d;
});
function esc(s){ return String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
document.getElementById('showSay').onchange = e => document.querySelectorAll('.say').forEach(x => x.style.display = e.target.checked ? 'block' : 'none');
if (audio) audio.ontimeupdate = () => {
  let k = -1; C.script.forEach(([t], i) => { if (audio.currentTime >= t) k = i; });
  rows.forEach((r, i) => r.classList.toggle('on', i === k));
};
const ul = document.getElementById('sources');
C.sources.forEach(s => { const li = document.createElement('li');
  li.innerHTML = `[${esc(s.kind)}] ${s.url ? `<a href="${esc(s.url)}" target="_blank">${esc(s.text)}</a>` : esc(s.text)} ${s.memo ? '· ' + esc(s.memo) : ''}`
    + ` <a href="#" onclick="return false">${fmt(s.seek)}</a>`;
  li.lastChild.onclick = () => seek(s.seek); ul.appendChild(li); });
const m = C.memo_link;
document.getElementById('memo').textContent = m ? `${m.head} · “${m.title}” · ${m.count} — ${m.body}` : '없음';
</script></body></html>
"""


def render(content: dict, lines: list[dict], audio_file: str | None) -> str:
    audio = (f'<audio id="audio" controls preload="metadata" src="{html.escape(audio_file)}"></audio>' if audio_file
             else '<div class="warn">오디오 없이 대본만 만들었어요 (--tts none). 시각은 글자 수로 어림한 값이에요.</div>'
                  '<audio id="audio"></audio>')
    dump = lambda v: json.dumps(v, ensure_ascii=False).replace("</", "<\\/")
    return (PAGE.replace("__TITLE__", html.escape(content.get("title") or "AI 오디오"))
            .replace("__AUDIO__", audio).replace("__CONTENT__", dump(content)).replace("__LINES__", dump(lines)))
