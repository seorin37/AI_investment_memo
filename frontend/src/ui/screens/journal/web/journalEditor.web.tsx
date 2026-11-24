import React, { useEffect, useRef, useState } from 'react';
import type { JBlock } from '../Journal.types';

/*
 * 웹 투자 기록 본문 편집기 (원본 web/src/screens/journal.tsx: contentEditable · FormatPanel · 기록 안에서 찾기)
 * DOM 을 직접 다루는 부분이라 .web.tsx 에만 둠. 글자 일부 서식(B·I·U·S)은 원본처럼 execCommand.
 */

export type EdRef = { current: HTMLDivElement | null };
export const useEdRef = (): EdRef => useRef<HTMLDivElement | null>(null);

type Fmt = { block: string; b: boolean; i: boolean; u: boolean; s: boolean; list: '' | 'ul' | 'dash' | 'ol' };
const NO_FMT: Fmt = { block: 'p', b: false, i: false, u: false, s: false, list: '' };

function readFmt(ed: HTMLElement | null): Fmt {
  const sel = window.getSelection();
  if (!ed || !sel || !sel.anchorNode || !ed.contains(sel.anchorNode)) return NO_FMT;
  let n: Node | null = sel.anchorNode;
  let block = 'p';
  let list: Fmt['list'] = '';
  while (n && n !== ed) {
    if (n instanceof HTMLElement) {
      const t = n.tagName.toLowerCase();
      if (['h1', 'h2', 'h3', 'p', 'blockquote'].includes(t) && block === 'p') block = t;
      if (t === 'blockquote') block = 'blockquote';
      if ((t === 'ul' || t === 'ol') && !list) list = t === 'ol' ? 'ol' : n.classList.contains('dash') ? 'dash' : 'ul';
    }
    n = n.parentNode;
  }
  const q = (c: string) => {
    try {
      return document.queryCommandState(c);
    } catch {
      return false;
    }
  };
  return { block, list, b: q('bold'), i: q('italic'), u: q('underline'), s: q('strikeThrough') };
}

/** 본문 DOM → 줄 (앱·목록 미리보기용 · 글자 일부 서식은 빠짐) */
export function readBlocks(el: HTMLElement | null): JBlock[] {
  if (!el) return [];
  const out: JBlock[] = [];
  Array.from(el.children).forEach((c) => {
    const t = c.tagName.toLowerCase();
    const text = (c as HTMLElement).innerText.replace(/\n+$/, '');
    if (t === 'ul' || t === 'ol') {
      const l = t === 'ol' ? 'num' : c.classList.contains('dash') ? 'dash' : 'dot';
      Array.from(c.children).forEach((li) => out.push({ s: 'body', l, text: (li as HTMLElement).innerText.replace(/\n+$/, '') }));
    } else if (t === 'blockquote') out.push({ s: 'body', l: 'quote', text });
    else out.push({ s: t === 'h1' ? 'title' : t === 'h2' ? 'head' : t === 'h3' ? 'sub' : 'body', text });
  });
  /* 빈 줄 하나만 있으면 비어 있는 본문 */
  return out.length === 1 && !out[0].text.trim() ? [] : out;
}

const CSS = `
.jr-ed{outline:none}
.jr-ed p{margin:0 0 10px}
.jr-ed h1{margin:6px 0 8px;font-size:26px;line-height:35px;font-weight:700}
.jr-ed h2{margin:6px 0 6px;font-size:20px;line-height:29px;font-weight:700}
.jr-ed h3{margin:4px 0 6px;font-size:17px;line-height:26px;font-weight:700}
.jr-ed ul,.jr-ed ol{margin:0 0 8px;padding-left:22px}
.jr-ed ul{list-style:disc}
.jr-ed ul.dash{list-style:none}
.jr-ed ul.dash>li{position:relative}
.jr-ed ul.dash>li::before{content:"–";position:absolute;left:-16px}
.jr-ed ol{list-style:decimal}
.jr-ed blockquote{margin:0 0 8px;padding-left:14px;border-left:3px solid #c9ccd2;color:#575b63}
.jr-ed b,.jr-ed strong{font-weight:700}
::highlight(jr-find){background-color:#ffe58f;color:inherit}
.jr-fmt button{border:0;cursor:pointer;font-family:inherit}
`;

/** 본문 칸 (원본 jr-ed: 17/26 · 비면 '내용을 입력하세요') — 고른 기록이 바뀔 때만 HTML 을 다시 넣음 */
export function BodyEditor({ edRef, docKey, html, onInput, onFocusEnd }: { edRef: EdRef; docKey: string; html: string; onInput: (html: string, body: JBlock[]) => void; onFocusEnd?: number }) {
  const [empty, setEmpty] = useState(false);
  useEffect(() => {
    try {
      document.execCommand('defaultParagraphSeparator', false, 'p');
    } catch {
      /* 무시 */
    }
  }, []);
  useEffect(() => {
    const el = edRef.current;
    if (!el) return;
    el.innerHTML = html;
    setEmpty(!el.innerText.trim());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [docKey]);
  /* 제목에서 Enter → 본문 끝으로 */
  useEffect(() => {
    if (!onFocusEnd) return;
    const el = edRef.current;
    if (!el) return;
    el.focus();
    const r = document.createRange();
    r.selectNodeContents(el);
    r.collapse(false);
    const s = window.getSelection();
    s?.removeAllRanges();
    s?.addRange(r);
  }, [onFocusEnd, edRef]);
  const input = () => {
    const el = edRef.current;
    if (!el) return;
    if (!el.firstElementChild) el.innerHTML = '<p><br></p>';
    setEmpty(!el.innerText.trim() && !el.querySelector('li,blockquote,h1,h2,h3'));
    onInput(el.innerHTML, readBlocks(el));
  };
  return (
    <div style={{ position: 'relative' }}>
      <style>{CSS}</style>
      {empty ? <p style={{ position: 'absolute', left: 0, top: 0, margin: 0, fontSize: 17, lineHeight: '26px', color: '#9a9ea7', pointerEvents: 'none' }}>내용을 입력하세요</p> : null}
      <div ref={edRef} contentEditable suppressContentEditableWarning role="textbox" aria-multiline aria-label="기록 내용" onInput={input} className="jr-ed" style={{ minHeight: 26, width: '100%', fontSize: 17, lineHeight: '26px', color: '#16171a', caretColor: '#5e5668' }} />
    </div>
  );
}

/** 서식 창 (원본 FormatPanel: 440 · #F3F4F6 · 라운드 20 · 안쪽 16 · 사이 12 · 고르면 #111) */
export function FormatPanel({ edRef, onClose, onChanged }: { edRef: EdRef; onClose: () => void; onChanged: () => void }) {
  const [f, setF] = useState<Fmt>(NO_FMT);
  useEffect(() => {
    const u = () => setF(readFmt(edRef.current));
    u();
    document.addEventListener('selectionchange', u);
    return () => document.removeEventListener('selectionchange', u);
  }, [edRef]);
  /* 바깥을 누르면 닫힘 (원본: 서식 창 · 서식 버튼 · 본문 밖) */
  useEffect(() => {
    const h = (e: MouseEvent) => {
      const t = e.target as HTMLElement;
      if (!t.closest('[data-fmt],[data-fmt-btn],.jr-ed')) onClose();
    };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, [onClose]);
  const run = (fn: () => void) => (e: React.MouseEvent) => {
    e.preventDefault();
    const el = edRef.current;
    if (!el) return;
    if (!el.contains(window.getSelection()?.anchorNode ?? null)) {
      el.focus();
      const r = document.createRange();
      r.selectNodeContents(el);
      r.collapse(false);
      const s = window.getSelection();
      s?.removeAllRanges();
      s?.addRange(r);
    }
    fn();
    el.dispatchEvent(new Event('input', { bubbles: true }));
    setF(readFmt(el));
    onChanged();
  };
  const block = (t: string) =>
    run(() => {
      const cur = readFmt(edRef.current);
      if (cur.list) document.execCommand(cur.list === 'ol' ? 'insertOrderedList' : 'insertUnorderedList');
      document.execCommand('formatBlock', false, t === 'blockquote' && cur.block === 'blockquote' ? 'p' : t);
    });
  const list = (k: 'ul' | 'dash' | 'ol') =>
    run(() => {
      const cur = readFmt(edRef.current);
      if (cur.block === 'blockquote' || cur.block.startsWith('h')) document.execCommand('formatBlock', false, 'p');
      if (cur.list === k) {
        document.execCommand(k === 'ol' ? 'insertOrderedList' : 'insertUnorderedList');
        return;
      }
      if (cur.list && (cur.list === 'ol') !== (k === 'ol')) document.execCommand(cur.list === 'ol' ? 'insertOrderedList' : 'insertUnorderedList');
      if (!cur.list || (cur.list === 'ol') !== (k === 'ol')) document.execCommand(k === 'ol' ? 'insertOrderedList' : 'insertUnorderedList');
      let n: Node | null = window.getSelection()?.anchorNode ?? null;
      while (n && !(n instanceof HTMLUListElement || n instanceof HTMLOListElement)) n = n.parentNode;
      if (n instanceof HTMLUListElement) n.classList.toggle('dash', k === 'dash');
    });
  const BLOCKS: [string, string, React.CSSProperties][] = [
    ['h1', '제목', { fontSize: 20, fontWeight: 700 }],
    ['h2', '머리말', { fontSize: 17, fontWeight: 700 }],
    ['h3', '부제목', { fontSize: 15, fontWeight: 700 }],
    ['p', '본문', { fontSize: 15, fontWeight: 500 }],
  ];
  const MARKS: ['b' | 'i' | 'u' | 's', string, string, React.ReactNode][] = [
    ['b', 'bold', '굵게', <b key="b" style={{ fontWeight: 700 }}>B</b>],
    ['i', 'italic', '기울임', <i key="i" style={{ fontFamily: 'serif', fontSize: 17 }}>I</i>],
    ['u', 'underline', '밑줄', <u key="u">U</u>],
    ['s', 'strikeThrough', '취소선', <s key="s">S</s>],
  ];
  const LISTS: ['ul' | 'dash' | 'ol' | 'quote', string][] = [
    ['ul', '• 목록'],
    ['dash', '– 목록'],
    ['ol', '1. 목록'],
    ['quote', '인용'],
  ];
  const cell = (on: boolean, i: number, hov: string | null, id: string): React.CSSProperties => ({ display: 'flex', height: 46, minWidth: 0, flex: 1, alignItems: 'center', justifyContent: 'center', fontSize: 15, lineHeight: '23px', color: on ? '#fff' : '#16171a', background: on ? '#111' : hov === id ? '#fafafa' : '#fff', boxShadow: i > 0 ? 'inset 1px 0 0 #eceef1' : undefined, transition: 'background-color .15s' });
  const [hov, setHov] = useState<string | null>(null);
  const hv = (id: string) => ({ onMouseEnter: () => setHov(id), onMouseLeave: () => setHov((h) => (h === id ? null : h)) });
  return (
    <div style={{ pointerEvents: 'none', position: 'absolute', bottom: 76, left: 0, right: 0, zIndex: 20, display: 'flex', justifyContent: 'center' }}>
      <div data-fmt className="jr-fmt" onMouseDown={(e) => e.preventDefault()} style={{ pointerEvents: 'auto', display: 'flex', width: 440, flexDirection: 'column', gap: 12, borderRadius: 20, background: '#f3f4f6', padding: 16, boxShadow: '0px 12px 32px -8px rgba(18,15,31,0.18), 0px 2px 8px 0px rgba(18,15,31,0.06)' }}>
        <div style={{ display: 'flex', height: 32, alignItems: 'center', justifyContent: 'space-between' }}>
          <p style={{ margin: 0, fontSize: 20, fontWeight: 700, lineHeight: '29px', color: '#16171a' }}>서식</p>
          <button aria-label="서식 닫기" onClick={onClose} {...hv('x')} style={{ display: 'flex', height: 32, width: 32, alignItems: 'center', justifyContent: 'center', borderRadius: 16, background: hov === 'x' ? '#d8dbe0' : '#e3e5e9' }}>
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path d="M2 2L10 10M10 2L2 10" stroke="#333" strokeWidth="1.7" strokeLinecap="round" />
            </svg>
          </button>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {BLOCKS.map(([t, l, c]) => {
            const on = !f.list && f.block === t;
            return (
              <button key={t} aria-pressed={on} onMouseDown={(e) => block(t)(e)} {...hv(t)} style={{ display: 'flex', height: 48, alignItems: 'center', justifyContent: 'center', borderRadius: 14, padding: '0 16px', lineHeight: '21px', ...c, color: on ? '#fff' : '#16171a', background: on ? '#111' : hov === t ? '#fafafa' : '#fff' }}>
                {l}
              </button>
            );
          })}
        </div>
        <div style={{ display: 'flex', overflow: 'hidden', borderRadius: 14, background: '#fff' }}>
          {MARKS.map(([k, cmd, l, g], i) => {
            const on = !!f[k];
            return (
              <button key={cmd} aria-label={l} aria-pressed={on} onMouseDown={(e) => run(() => document.execCommand(cmd))(e)} {...hv(cmd)} style={{ ...cell(on, i, hov, cmd), fontSize: 17 }}>
                {g}
              </button>
            );
          })}
        </div>
        <div style={{ display: 'flex', overflow: 'hidden', borderRadius: 14, background: '#fff' }}>
          {LISTS.map(([k, l], i) => {
            const on = k === 'quote' ? f.block === 'blockquote' : f.list === k;
            return (
              <button key={l} aria-pressed={on} onMouseDown={(e) => (k === 'quote' ? block('blockquote') : list(k))(e)} {...hv(l)} style={cell(on, i, hov, l)}>
                {k === 'quote' ? (
                  <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ height: 16, width: 2, borderRadius: 1, background: on ? '#fff' : '#9a9ea7' }} />
                    인용
                  </span>
                ) : (
                  l
                )}
              </button>
            );
          })}
        </div>
        <p style={{ margin: 0, fontSize: 13, lineHeight: '20px', color: '#8a8f98' }}>어느 줄이든 제목·머리말·부제목·본문을 고를 수 있어요 · 첫 줄은 제목, 줄을 바꾸면 본문이에요</p>
      </div>
    </div>
  );
}

/** 기록 안에서 찾기 (원본: CSS Highlight 로 본문 글자에 노랑) — 찾은 수 */
export function useFindHits(edRef: EdRef, find: string | null, dep: unknown) {
  const [hits, setHits] = useState(0);
  useEffect(() => {
    const H = (CSS_ as unknown as { highlights?: Map<string, unknown> }).highlights;
    const el = edRef.current;
    if (!H) return;
    H.delete('jr-find');
    if (!find || !find.trim() || !el) {
      setHits(0);
      return;
    }
    const t = find.trim();
    const ranges: Range[] = [];
    const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    for (let n = w.nextNode(); n; n = w.nextNode()) {
      const s = n.textContent ?? '';
      let i = s.indexOf(t);
      while (i >= 0) {
        const r = new Range();
        r.setStart(n, i);
        r.setEnd(n, i + t.length);
        ranges.push(r);
        i = s.indexOf(t, i + t.length);
      }
    }
    const HL = (window as unknown as { Highlight?: new (...r: Range[]) => unknown }).Highlight;
    if (HL) H.set('jr-find', new HL(...ranges));
    setHits(ranges.length);
    return () => {
      H.delete('jr-find');
    };
  }, [find, dep, edRef]);
  return hits;
}
const CSS_ = (globalThis as { CSS?: unknown }).CSS ?? {};

/** 찾기 칸 (원본 data-jr-find: 가운데 위 16 · 높이 44 · 라운드 14 · 입력 180 · 'N개 찾음') */
export function FindBar({ value, hits, onChange, onClose }: { value: string; hits: number; onChange: (v: string) => void; onClose: () => void }) {
  return (
    <div style={{ position: 'absolute', left: '50%', top: 16, zIndex: 10, display: 'flex', height: 44, transform: 'translateX(-50%)', alignItems: 'center', gap: 8, borderRadius: 14, border: '1px solid #e5e7eb', background: '#fff', paddingLeft: 12, paddingRight: 4, boxShadow: '0 8px 20px -8px rgba(17,17,17,.2)' }}>
      <svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="#6b7078" strokeWidth="1.6" strokeLinecap="round">
        <circle cx="9" cy="9" r="5.5" />
        <path d="M13 13l4 4" />
      </svg>
      <input
        autoFocus
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Escape') onClose();
        }}
        placeholder="기록 안에서 찾기"
        style={{ width: 180, border: 0, background: 'transparent', fontSize: 15, color: '#15171a', outline: 'none', fontFamily: 'inherit' }}
      />
      <span style={{ minWidth: 56, textAlign: 'right', fontSize: 13, color: '#8b95a1' }}>{value.trim() ? `${hits}개 찾음` : ''}</span>
      <button aria-label="찾기 닫기" onClick={onClose} style={{ display: 'grid', height: 36, width: 36, placeItems: 'center', borderRadius: 10, border: 0, background: 'transparent', cursor: 'pointer' }}>
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <path d="M3 3l8 8M11 3l-8 8" stroke="#575b63" strokeWidth="1.6" strokeLinecap="round" />
        </svg>
      </button>
    </div>
  );
}
