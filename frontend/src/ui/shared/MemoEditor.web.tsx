import React, { useImperativeHandle, useLayoutEffect, useRef, useState } from 'react';
import { fonts } from '@/theme/tokens';
import type { MemoEditorProps } from './MemoEditor.types';

/**
 * 웹 한 칸 메모 편집기 (원본 board.tsx PaperEditor: 줄마다 <div> · 첫 줄 = 제목 · 붙여 넣기는 글자만).
 * 원본 .memo-ed: 15.5px 줄 1.6 #333D4B · 첫 줄 21px 700 줄 25px #15171A 아래 8 / 앱 체험판(.ed): 15.5px 줄 1.8 #2E2E38 · 첫 줄 21px 800 줄 1.4.
 * 글자 칸이 RN 글자가 아니라서 AppText 대신 굵기별 Pretendard 글꼴 이름을 font 로 직접 줌 (원본과 같은 글꼴 파일).
 */
const LOOK = {
  web: {
    title: { font: `21px/25px ${fonts.bold}`, color: '#15171A', margin: '0 0 8px' },
    body: { font: `15.5px/1.6 ${fonts.regular}`, color: '#333D4B', margin: '0' },
  },
  app: {
    title: { font: `21px/1.4 ${fonts.extrabold}`, color: '#16171A', margin: '4px 0 8px' },
    body: { font: `15.5px/1.8 ${fonts.regular}`, color: '#2E2E38', margin: '0' },
  },
} as const;

const esc = (t: string) => t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
/* 원본 readEditor: 줄 묶음 사이 빈 줄이 두 번씩 잡히는 것을 반으로 */
const read = (el: HTMLDivElement) => el.innerText.replace(/ /g, ' ').replace(/\n{2,}/g, (m) => '\n'.repeat(Math.ceil(m.length / 2))).replace(/\n$/, '');

export function MemoEditor({ value, onChangeText, editable, autoFocus, variant, onFocus, focusRef, accessibilityLabel }: MemoEditorProps) {
  const el = useRef<HTMLDivElement | null>(null);
  const [init] = useState(value);
  const look = LOOK[variant];
  const paint = () => {
    const e = el.current;
    if (!e) return;
    Array.from(e.children).forEach((c, i) => Object.assign((c as HTMLElement).style, i === 0 ? look.title : look.body));
  };
  const caretEnd = () => {
    const e = el.current;
    if (!e) return;
    e.focus();
    const r = document.createRange();
    r.selectNodeContents(e);
    r.collapse(false);
    const s = window.getSelection();
    s?.removeAllRanges();
    s?.addRange(r);
  };
  useImperativeHandle(focusRef, () => ({ focus: caretEnd, blur: () => el.current?.blur() }));
  useLayoutEffect(() => {
    const e = el.current;
    if (!e) return;
    e.innerHTML = init ? init.split('\n').map((l) => `<div>${esc(l) || '<br>'}</div>`).join('') : '<div><br></div>';
    Array.from(e.children).forEach((c, i) => Object.assign((c as HTMLElement).style, i === 0 ? look.title : look.body));
    if (autoFocus) {
      e.focus();
      const r = document.createRange();
      r.selectNodeContents(e);
      r.collapse(!init);
      const s = window.getSelection();
      s?.removeAllRanges();
      s?.addRange(r);
    }
  }, [init, autoFocus, look]);
  /* 원본 fix(): 첫 줄이 줄 묶음 밖에 생기면 감싸고, 다 지우면 빈 줄 하나 */
  const fix = () => {
    const e = el.current;
    if (!e) return;
    const f = e.firstChild;
    if (f && f.nodeName !== 'DIV') {
      const sel = window.getSelection();
      const an = sel?.anchorNode;
      const ao = sel?.anchorOffset ?? 0;
      const d = document.createElement('div');
      while (e.firstChild && e.firstChild.nodeName !== 'DIV') d.appendChild(e.firstChild);
      e.insertBefore(d, e.firstChild);
      if (an && sel) sel.collapse(an, ao);
    }
    if (!e.firstChild) e.innerHTML = '<div><br></div>';
    paint();
    onChangeText(read(e));
  };
  return React.createElement('div', {
    ref: el,
    contentEditable: editable,
    suppressContentEditableWarning: true,
    spellCheck: false,
    role: 'textbox',
    'aria-multiline': true,
    'aria-label': accessibilityLabel ?? '메모 (첫 줄은 제목)',
    onInput: fix,
    onFocus,
    onPaste: (e: React.ClipboardEvent) => {
      e.preventDefault();
      document.execCommand('insertText', false, e.clipboardData.getData('text/plain'));
    },
    style: { position: 'relative', minHeight: '100%', width: '100%', whiteSpace: 'pre-wrap', overflowWrap: 'break-word', outline: 'none', caretColor: variant === 'app' ? '#6A42AB' : '#15171A' },
  });
}
