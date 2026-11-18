/* 5 · 투자 기록 — Figma 2.5 그대로 (목록 208 + 편집기 + 아래 가운데 도구 막대) */
import { FixedFrame } from "./stock";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { cx, PageTitle, useSnack } from "../kit";
import { CtxMenu, MI, Hl, type MenuItem } from "../x";
import { SelectBar, Pick, Dots } from "./memox";
import { useApp } from "../store";
import type { Journal } from "../data";

function nowFull() {
  const d = new Date(Date.now());
  const k = new Date(d.toLocaleString("en-US", { timeZone: "Asia/Seoul" }));
  const h = k.getHours(), m = String(k.getMinutes()).padStart(2, "0");
  return { full: `${k.getFullYear()}년 ${k.getMonth() + 1}월 ${k.getDate()}일 ${h < 12 ? "오전" : "오후"} ${h % 12 || 12}:${m}`, date: `${k.getMonth() + 1}월 ${k.getDate()}일` };
}

/* 줄 수에 맞춰 높이가 늘어나는 글 칸 */
function Grow({ value, onChange, className, placeholder, onKeyDown, autoFocus, inputRef }: { value: string; onChange: (v: string) => void; className: string; placeholder?: string; onKeyDown?: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void; autoFocus?: boolean; inputRef?: (el: HTMLTextAreaElement | null) => void }) {
  const r = useRef<HTMLTextAreaElement | null>(null);
  useEffect(() => { const el = r.current; if (!el) return; el.style.height = "0px"; el.style.height = el.scrollHeight + "px"; });
  return <textarea ref={(el) => { r.current = el; inputRef?.(el); }} rows={1} value={value} autoFocus={autoFocus} placeholder={placeholder} onKeyDown={onKeyDown} onChange={(e) => onChange(e.target.value)} className={cx("block w-full resize-none overflow-hidden bg-transparent outline-none placeholder:text-[#9a9ea7]", className)} />;
}

const CHECK_ICON = <><path d="M11.9167 10.9993L13.25 12.3327L15.6667 9.91602" /><path d="M13.5833 22.0007C14.5959 22.0007 15.4167 21.1798 15.4167 20.1673C15.4167 19.1548 14.5959 18.334 13.5833 18.334C12.5708 18.334 11.75 19.1548 11.75 20.1673C11.75 21.1798 12.5708 22.0007 13.5833 22.0007Z" /><path d="M18.1667 11H25.6667M18.1667 20.1667H25.6667" /></>;

/* ===== 서식 (Aa) — 앱 서식 판 그대로, 보라 → 검정 (11.13) ===== */
const esc = (t: string) => t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const toHtml = (j: Journal) => j.html ?? (j.body.length ? j.body : [""]).map((p) => `<p>${p ? esc(p) : "<br>"}</p>`).join("");
const toBody = (el: HTMLElement) => Array.from(el.children).map((c) => (c as HTMLElement).innerText.replace(/\n+$/, "")).flatMap((t) => t.split("\n")).filter((t, _i, a) => t.trim() || a.length === 1);
type Fmt = { block: string; b: boolean; i: boolean; u: boolean; s: boolean; list: "" | "ul" | "dash" | "ol" };
const NO_FMT: Fmt = { block: "p", b: false, i: false, u: false, s: false, list: "" };
function readFmt(ed: HTMLElement | null): Fmt {
  const sel = window.getSelection();
  if (!ed || !sel || !sel.anchorNode || !ed.contains(sel.anchorNode)) return NO_FMT;
  let n: Node | null = sel.anchorNode, block = "p", list: Fmt["list"] = "";
  while (n && n !== ed) {
    if (n instanceof HTMLElement) {
      const t = n.tagName.toLowerCase();
      if (["h1", "h2", "h3", "p", "blockquote"].includes(t) && block === "p") block = t;
      if (t === "blockquote") block = "blockquote";
      if ((t === "ul" || t === "ol") && !list) list = t === "ol" ? "ol" : n.classList.contains("dash") ? "dash" : "ul";
    }
    n = n.parentNode;
  }
  const q = (c: string) => { try { return document.queryCommandState(c); } catch { return false; } };
  return { block, list, b: q("bold"), i: q("italic"), u: q("underline"), s: q("strikeThrough") };
}
function FormatPanel({ ed, onClose }: { ed: React.RefObject<HTMLDivElement | null>; onClose: () => void }) {
  const [f, setF] = useState<Fmt>(NO_FMT);
  useEffect(() => { const u = () => setF(readFmt(ed.current)); u(); document.addEventListener("selectionchange", u); return () => document.removeEventListener("selectionchange", u); }, [ed]);
  const run = (fn: () => void) => (e: React.MouseEvent) => {
    e.preventDefault();
    const el = ed.current; if (!el) return;
    if (!el.contains(window.getSelection()?.anchorNode ?? null)) { el.focus(); const r = document.createRange(); r.selectNodeContents(el); r.collapse(false); const s = window.getSelection(); s?.removeAllRanges(); s?.addRange(r); }
    fn(); el.dispatchEvent(new Event("input", { bubbles: true })); setF(readFmt(el));
  };
  const block = (t: string) => run(() => {
    const cur = readFmt(ed.current);
    if (cur.list) document.execCommand(cur.list === "ol" ? "insertOrderedList" : "insertUnorderedList");
    document.execCommand("formatBlock", false, t === "blockquote" && cur.block === "blockquote" ? "p" : t);
  });
  const list = (k: "ul" | "dash" | "ol") => run(() => {
    const cur = readFmt(ed.current);
    if (cur.block === "blockquote" || cur.block.startsWith("h")) document.execCommand("formatBlock", false, "p");
    if (cur.list === k) { document.execCommand(k === "ol" ? "insertOrderedList" : "insertUnorderedList"); return; }
    if (cur.list && (cur.list === "ol") !== (k === "ol")) document.execCommand(cur.list === "ol" ? "insertOrderedList" : "insertUnorderedList");
    if (!cur.list || (cur.list === "ol") !== (k === "ol")) document.execCommand(k === "ol" ? "insertOrderedList" : "insertUnorderedList");
    let n: Node | null = window.getSelection()?.anchorNode ?? null;
    while (n && !(n instanceof HTMLUListElement || n instanceof HTMLOListElement)) n = n.parentNode;
    if (n instanceof HTMLUListElement) n.classList.toggle("dash", k === "dash");
  });
  const BLOCKS: [string, string, string][] = [["h1", "제목", "text-[20px] font-bold"], ["h2", "머리말", "text-[17px] font-bold"], ["h3", "부제목", "text-[15px] font-bold"], ["p", "본문", "text-[15px] font-medium"]];
  const MARKS: [keyof Fmt, string, string, ReactNode][] = [["b", "bold", "굵게", <b key="b" className="font-bold">B</b>], ["i", "italic", "기울임", <i key="i" className="font-serif text-[17px]">I</i>], ["u", "underline", "밑줄", <u key="u">U</u>], ["s", "strikeThrough", "취소선", <s key="s">S</s>]];
  const LISTS: [Fmt["list"] | "quote", string][] = [["ul", "• 목록"], ["dash", "– 목록"], ["ol", "1. 목록"], ["quote", "인용"]];
  const cell = "flex h-[46px] min-w-0 flex-1 items-center justify-center text-[15px] leading-[23px] transition-colors";
  return (
    <div className="pointer-events-none absolute bottom-[76px] left-0 right-0 z-20 flex justify-center">
    <div data-fmt className="m-pop pointer-events-auto flex w-[440px] flex-col gap-3 rounded-[20px] bg-[#f3f4f6] p-4 shadow-[0px_12px_32px_-8px_rgba(18,15,31,0.18),0px_2px_8px_0px_rgba(18,15,31,0.06)]" onMouseDown={(e) => e.preventDefault()}>
      <div className="flex h-8 items-center justify-between">
        <p className="text-[20px] font-bold leading-[29px] text-[#16171a]">서식</p>
        <button aria-label="서식 닫기" onClick={onClose} className="flex h-8 w-8 items-center justify-center rounded-full bg-[#e3e5e9] hover:bg-[#d8dbe0]"><svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 2L10 10M10 2L2 10" stroke="#333" strokeWidth="1.7" strokeLinecap="round" /></svg></button>
      </div>
      <div className="flex gap-2">
        {BLOCKS.map(([t, l, c]) => { const on = !f.list && f.block === t; return <button key={t} aria-pressed={on} onMouseDown={block(t)} className={cx("flex h-[48px] items-center justify-center rounded-[14px] px-4 leading-[21px] transition-colors", c, on ? "bg-[#111] text-white" : "bg-white text-[#16171a] hover:bg-[#fafafa]")}>{l}</button>; })}
      </div>
      <div className="flex overflow-hidden rounded-[14px] bg-white">
        {MARKS.map(([k, cmd, l, g], i) => { const on = !!f[k]; return <button key={cmd} aria-label={l} aria-pressed={on} onMouseDown={run(() => document.execCommand(cmd))} className={cx(cell, "text-[17px] text-[#16171a]", i > 0 && "shadow-[inset_1px_0_0_#eceef1]", on ? "bg-[#111] !text-white" : "hover:bg-[#fafafa]")}>{g}</button>; })}
      </div>
      <div className="flex overflow-hidden rounded-[14px] bg-white">
        {LISTS.map(([k, l], i) => { const on = k === "quote" ? f.block === "blockquote" : f.list === k; return (
          <button key={l} aria-pressed={on} onMouseDown={k === "quote" ? block("blockquote") : list(k as "ul" | "dash" | "ol")} className={cx(cell, "text-[#16171a]", i > 0 && "shadow-[inset_1px_0_0_#eceef1]", on ? "bg-[#111] !text-white" : "hover:bg-[#fafafa]")}>
            {k === "quote" ? <span className="flex items-center gap-2"><span className={cx("h-4 w-[2px] rounded-full", on ? "bg-white" : "bg-[#9a9ea7]")} />인용</span> : l}
          </button>
        ); })}
      </div>
      <p className="text-[13px] leading-[20px] text-[#8a8f98]">어느 줄이든 제목·머리말·부제목·본문을 고를 수 있어요 · 첫 줄은 제목, 줄을 바꾸면 본문이에요</p>
    </div>
    </div>
  );
}

export function JournalPage() {
  const { journal, act: A } = useApp();
  const [sel, setSel] = useState(journal[0]?.id ?? 0);
  const [q, setQ] = useState("");
  const [fmt, setFmt] = useState(false);
  const ed = useRef<HTMLDivElement | null>(null);
  const [fresh, setFresh] = useState<number | null>(null);
  const [focusTodo, setFocusTodo] = useState<number | null>(null);
  const cur = journal.find((j) => j.id === sel) ?? journal[0];
  const list = journal.filter((j) => !q.trim() || j.title.includes(q.trim()) || j.body.join(" ").includes(q.trim()));
  /* 11.16 앱 통일: 묶음(고정됨·오늘·지난 30일·월별) · 고정 · 휴지통 · 선택 · 공유 · 기록 안에서 찾기 · 사진 */
  const snack = useSnack();
  const [grouped, setGrouped] = useState(true), [pinOpen, setPinOpen] = useState(true);
  const [pick, setPick] = useState<Set<number> | null>(null);
  const [menu, setMenu] = useState<{ items: MenuItem[]; at: { x: number; y: number } } | null>(null);
  const [find, setFind] = useState<string | null>(null);
  const photo = useRef<HTMLInputElement>(null);
  const today = nowFull().date;
  const inLast30 = (j: Journal) => Date.now() - new Date(j.created_at).getTime() < 30 * 864e5;
  const monthOf = (j: Journal) => { const d = new Date(j.created_at), y = new Date().getFullYear(); return d.getFullYear() === y ? `${d.getMonth() + 1}월` : `${d.getFullYear()}년 ${d.getMonth() + 1}월`; };
  const groups: [string, Journal[]][] = !grouped ? [["", list]] : (() => {
    const g = new Map<string, Journal[]>(); const put = (k: string, j: Journal) => { if (!g.has(k)) g.set(k, []); g.get(k)!.push(j); };
    list.forEach((j) => put(j.pinned ? "고정됨" : j.date === today ? "오늘" : inLast30(j) ? "지난 30일" : monthOf(j), j));
    return ["고정됨", "오늘", "지난 30일", ...[...g.keys()].filter((k) => !["고정됨", "오늘", "지난 30일"].includes(k))].filter((k) => g.has(k)).map((k) => [k, g.get(k)!] as [string, Journal[]]);
  })();
  const trashJ = (ls: Journal[]) => {
    const before = A.snapshot();
    A.trashJournal(ls.map((j) => j.id));
    snack(ls.length > 1 ? `기록 ${ls.length}개를 휴지통으로 옮겼어요` : "기록 1개를 휴지통으로 옮겼어요", { undo: () => A.rollback(before) });
  };
  const pinJ = (ls: Journal[], on: boolean) => { A.pinJournal(ls.map((j) => j.id), on); snack(on ? (ls.length > 1 ? `${ls.length}개를 고정했어요` : "고정했어요") : "고정을 풀었어요", { check: true }); };
  const copyJ = (j: Journal, msg = "내용을 복사했어요") => { try { void navigator.clipboard?.writeText([j.title, ...j.body].join("\n")).catch(() => {}); } catch { /* 무시 */ } snack(msg, { check: true }); };
  const rowMenu = (j: Journal): MenuItem[] => [
    { label: j.pinned ? "고정 풀기" : "맨 위에 고정", icon: MI.pin, run: () => pinJ([j], !j.pinned) },
    { label: "공유", icon: MI.share, run: () => copyJ(j, "공유할 내용을 복사했어요") },
    { label: "내용 복사", icon: MI.copy, run: () => copyJ(j) },
    { label: "기록 선택하기", icon: MI.select, run: () => setPick(new Set([j.id])) },
    "-",
    { label: "휴지통으로 이동", icon: MI.trash, danger: true, run: () => trashJ([j]) },
  ];
  /* 기록 안에서 찾기: 편집기 안 글자에 표시 (CSS Highlight) */
  const [hits, setHits] = useState(0);
  useEffect(() => {
    const H = (CSS as unknown as { highlights?: Map<string, unknown> }).highlights; const el = ed.current;
    if (!H) { setHits(0); return; } H.delete("jr-find");
    if (!find || !find.trim() || !el) { setHits(0); return; }
    const t = find.trim(), ranges: Range[] = []; const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    for (let n = w.nextNode(); n; n = w.nextNode()) { const s = n.textContent ?? ""; let i = s.indexOf(t); while (i >= 0) { const r = new Range(); r.setStart(n, i); r.setEnd(n, i + t.length); ranges.push(r); i = s.indexOf(t, i + t.length); } }
    const HL = (window as unknown as { Highlight?: new (...r: Range[]) => unknown }).Highlight; if (HL) H.set("jr-find", new HL(...ranges));
    setHits(ranges.length);
    return () => { H.delete("jr-find"); };
  }, [find, cur?.id, cur?.html, cur?.body]); // eslint-disable-line react-hooks/exhaustive-deps
  const addPhoto = (f: File) => { if (!f.type.startsWith("image/")) { snack("사진 파일만 넣을 수 있어요"); return; } const r = new FileReader(); r.onload = () => { const src = new Image(); src.onload = () => { const k = Math.min(1, 900 / Math.max(src.width, src.height)), c = document.createElement("canvas"); c.width = Math.round(src.width * k); c.height = Math.round(src.height * k); c.getContext("2d")!.drawImage(src, 0, 0, c.width, c.height); put(c.toDataURL("image/jpeg", 0.82)); }; src.src = String(r.result); }; const put = (url: string) => { const el = ed.current; if (!el) return; const p = document.createElement("p"); const img = document.createElement("img"); img.src = url; img.alt = f.name; img.style.maxWidth = "100%"; img.style.borderRadius = "12px"; p.appendChild(img); el.appendChild(p); el.dispatchEvent(new Event("input", { bubbles: true })); snack("사진을 넣었어요", { check: true }); }; r.readAsDataURL(f); };
  useEffect(() => { if (!journal.find((j) => j.id === sel) && journal[0]) setSel(journal[0].id); }, [journal, sel]);
  const edit = (p: Partial<Journal>) => { if (cur) A.updateJournal(cur.id, p); };
  /* 비어 있는 새 기록은 다른 기록으로 옮기면 지워요 */
  const prevSel = useRef(sel);
  useEffect(() => { const was = prevSel.current; if (was !== sel) A.dropEmptyJournal(was); prevSel.current = sel; }, [sel]); // eslint-disable-line react-hooks/exhaustive-deps
  const add = () => {
    const id = A.addJournal();
    setQ(""); setSel(id); setFresh(id); window.setTimeout(() => setFresh(null), 1400);
  };
  const tool = (k: string) => {
    if (!cur) return;
    if (k === "fmt") setFmt((v) => !v);
    if (k === "check") { edit({ todo: [...cur.todo, { t: "", d: false }] }); setFocusTodo(cur.todo.length); }
  };
  const bodyCls = "text-[17px] leading-[26px]";
  const [empty, setEmpty] = useState(false);
  useEffect(() => { setFmt(false); }, [cur?.id]);
  useEffect(() => { if (!fmt) return; const f = (e: MouseEvent) => { const t = e.target as HTMLElement; if (!t.closest("[data-fmt],[data-fmt-btn],.jr-ed")) setFmt(false); }; document.addEventListener("mousedown", f); return () => document.removeEventListener("mousedown", f); }, [fmt]);
  useEffect(() => { const el = ed.current; if (!el || !cur) return; el.innerHTML = toHtml(cur); setEmpty(!el.innerText.trim()); }, [cur?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { try { document.execCommand("defaultParagraphSeparator", false, "p"); } catch { /* 무시 */ } }, []);
  const onInput = () => { const el = ed.current; if (!el) return; if (!el.firstElementChild) el.innerHTML = "<p><br></p>"; setEmpty(!el.innerText.trim() && !el.querySelector("li,blockquote,h1,h2,h3")); edit({ html: el.innerHTML, body: toBody(el) }); };
  return (
    <FixedFrame fill>
    <div className="flex h-full min-h-[640px] w-[860px] flex-col items-start gap-8 pb-8 pt-8">
      <PageTitle title="투자 기록" sub={`${journal.length}개의 기록 · AI 연결 없이 나만 보는 투자 일지예요`} right={<>
          <button aria-label="보기 옵션" data-jr-view onClick={(e) => { const r = (e.currentTarget as HTMLElement).getBoundingClientRect(); setMenu({ at: { x: r.right - 220, y: r.bottom + 6 }, items: [{ label: "기록 선택하기", icon: MI.select, run: () => setPick(new Set()) }, { label: grouped ? "날짜별로 묶기 끄기" : "날짜별로 묶기", icon: MI.info, run: () => setGrouped(!grouped) }] }); }} className="flex h-11 w-11 items-center justify-center rounded-full border border-[#e5e7eb] bg-white text-[#15171a] hover:bg-[#f9f9f9]"><Dots /></button>
          <label className="flex h-11 w-[280px] items-center gap-2 rounded-[22px] border border-[#e5e7eb] bg-white px-4">
            <svg width="20" height="20" viewBox="0 0 16 16" fill="none" className="shrink-0"><path d="M7 11C9.20914 11 11 9.20914 11 7C11 4.79086 9.20914 3 7 3C4.79086 3 3 4.79086 3 7C3 9.20914 4.79086 11 7 11Z" stroke="#6B7078" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" /><path d="M13.3333 13.3333L10 10" stroke="#6B7078" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" /></svg>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="검색" aria-label="기록 검색" className="h-[23px] w-full bg-transparent text-[15px] leading-[23px] text-[#16171a] outline-none placeholder:text-[#6b7078]" />
          </label>
          <button aria-label="새 기록" onClick={add} className="flex h-11 w-11 items-center justify-center rounded-full border border-[#e5e7eb] bg-white hover:bg-[#f9f9f9]">
            <svg width="22" height="22" viewBox="0 0 18 18" fill="none"><path d="M3 15.0002H6L13.875 7.12523C14.2728 6.7274 14.4963 6.18784 14.4963 5.62523C14.4963 5.06262 14.2728 4.52305 13.875 4.12523C13.4772 3.7274 12.9376 3.50391 12.375 3.50391C11.8124 3.50391 11.2728 3.7274 10.875 4.12523L3 12.0002V15.0002Z" stroke="#1C1C1C" strokeWidth="1.35" strokeLinecap="round" strokeLinejoin="round" /><path d="M10.125 4.875L13.125 7.875" stroke="#1C1C1C" strokeWidth="1.35" strokeLinecap="round" strokeLinejoin="round" /></svg>
          </button>
      </>} />
      <div className="flex min-h-0 w-full flex-1 items-start overflow-hidden rounded-[20px] border border-[#e5e7eb] bg-white">
        <div data-jr-list className="flex w-[280px] shrink-0 flex-col items-start gap-1 self-stretch overflow-y-auto px-3 py-3 shadow-[inset_-1px_0_0_#e5e7eb]">
          {list.length === 0 && q.trim() && <div className="flex w-full flex-col items-center gap-1 px-2 py-10 text-center"><p className="text-[15px] font-bold leading-[23px] text-[#333d4b]">‘{q}’가 들어간 기록이 없어요</p><p className="text-[14px] leading-[21px] text-[#8b95a1]">다른 말로 찾아보세요</p></div>}
          {groups.map(([g, js]) => (
            <div key={g || "all"} className="flex w-full flex-col gap-1">
              {g && <button onClick={() => g === "고정됨" && setPinOpen(!pinOpen)} className={cx("flex h-8 w-full items-center gap-1 px-2 text-left text-[13px] font-bold leading-[20px] text-[#8b95a1]", g !== "고정됨" && "cursor-default")}>{g}{g === "고정됨" && <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className="transition-transform" style={{ transform: pinOpen ? "" : "rotate(-90deg)", transitionDuration: "calc(.25s * var(--k))" }}><path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>}</button>}
              <div className={cx("x-fold", (g !== "고정됨" || pinOpen) && "on")}><div className="flex flex-col gap-1">
              {js.map((j) => { const on = j.id === cur?.id; return (
                <div key={j.id} className="group relative" onContextMenu={(e) => { e.preventDefault(); if (!pick) setMenu({ items: rowMenu(j), at: { x: e.clientX, y: e.clientY } }); }}>
                  <button data-jr-row={j.id} onClick={() => (pick ? setPick((s) => { const n = new Set(s ?? []); if (n.has(j.id)) n.delete(j.id); else n.add(j.id); return n; }) : setSel(j.id))} className={cx("flex w-full shrink-0 items-center gap-3 rounded-[12px] px-4 py-3 text-left", on && !pick ? "bg-[#f1eefb]" : "hover:bg-[#f9f9f9]", fresh === j.id && "m-new")}>
                    {pick && <Pick on={pick.has(j.id)} />}
                    <span className="flex min-w-0 flex-1 flex-col items-start gap-1">
                      <p className="w-full truncate text-[17px] font-bold leading-[26px] text-[#16171a]"><Hl text={j.title || "제목 없음"} q={q} /></p>
                      <span className="flex w-full items-center gap-[6px]">
                        <span className="shrink-0 whitespace-nowrap text-[15px] font-medium leading-[23px] text-[#575b63]">{j.date}</span>
                        <span className="min-w-0 flex-1 truncate text-[15px] leading-[23px] text-[#6b7078]"><Hl text={(j.body[0] ?? "").split(/(?<=[.!?。])\s/)[0]} q={q} /></span>
                      </span>
                    </span>
                  </button>
                  {!pick && <button aria-label="기록 메뉴" data-jr-menu={j.id} onClick={(e) => { const r = (e.currentTarget as HTMLElement).getBoundingClientRect(); setMenu({ items: rowMenu(j), at: { x: r.left, y: r.bottom + 4 } }); }} className="absolute right-2 top-3 grid h-7 w-7 place-items-center rounded-[8px] bg-white/80 text-[#8b95a1] opacity-0 transition-opacity hover:bg-[#ececec] focus-visible:opacity-100 group-hover:opacity-100"><Dots /></button>}
                </div>
              ); })}
              </div></div>
            </div>
          ))}
        </div>
        {!cur && (
          <div data-jr-empty className="m-in flex min-w-0 flex-1 flex-col items-center justify-center gap-3 self-stretch px-8 text-center">
            <span className="dk-keep relative block h-[52px] w-[60px] m-pop"><span className="block h-full w-full rounded-[10px] bg-[#eceef1]" /><span className="absolute left-3 right-3 top-4 h-[3px] rounded bg-[#c9ccd2]" /><span className="absolute left-3 right-6 top-7 h-[3px] rounded bg-[#c9ccd2]" /></span>
            <p className="text-[20px] font-bold leading-[29px] text-[#191f28]">아직 기록이 없어요</p>
            <p className="break-keep text-[15px] leading-[23px] text-[#6b7684]">오늘 본 것, 다음에 확인할 것을<br />나만의 투자 기록으로 남겨 보세요</p>
            <button onClick={add} className="mt-2 h-12 rounded-[14px] bg-[#111] px-6 text-[17px] font-bold text-white hover:bg-[#2a2a2a]">첫 기록 쓰기</button>
          </div>
        )}
        {cur && (
          <div className="relative min-w-0 flex-1 self-stretch">
            <button aria-label="이 기록 메뉴" data-jr-cur-menu onClick={(e) => { const r = (e.currentTarget as HTMLElement).getBoundingClientRect(); setMenu({ at: { x: r.right - 220, y: r.bottom + 6 }, items: [{ label: "공유", icon: MI.share, run: () => copyJ(cur, "공유할 내용을 복사했어요") }, { label: "기록 안에서 찾기", icon: MI.find, run: () => setFind("") }, { label: "내용 복사", icon: MI.copy, run: () => copyJ(cur) }, { label: cur.pinned ? "고정 풀기" : "맨 위에 고정", icon: MI.pin, run: () => pinJ([cur], !cur.pinned) }, "-", { label: "휴지통으로 이동", icon: MI.trash, danger: true, run: () => trashJ([cur]) }] }); }} className="absolute right-4 top-4 z-10 grid h-9 w-9 place-items-center rounded-[10px] text-[#575b63] hover:bg-[#f3f4f6]"><Dots /></button>
            {find !== null && (
              <div data-jr-find className="m-pop absolute left-1/2 top-4 z-10 flex h-11 -translate-x-1/2 items-center gap-2 rounded-[14px] border border-[#e5e7eb] bg-white pl-3 pr-1 shadow-[0_8px_20px_-8px_rgba(17,17,17,.2)]">
                <svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="#6b7078" strokeWidth="1.6" strokeLinecap="round"><circle cx="9" cy="9" r="5.5" /><path d="M13 13l4 4" /></svg>
                <input autoFocus value={find} onChange={(e) => setFind(e.target.value)} onKeyDown={(e) => { if (e.key === "Escape") setFind(null); }} placeholder="기록 안에서 찾기" className="w-[180px] bg-transparent text-[15px] text-[#15171a] outline-none placeholder:text-[#8b95a1]" />
                <span className="min-w-[56px] text-right text-[13px] text-[#8b95a1]">{find.trim() ? `${hits}개 찾음` : ""}</span>
                <button aria-label="찾기 닫기" onClick={() => setFind(null)} className="grid h-9 w-9 place-items-center rounded-[10px] hover:bg-[#f3f4f6]"><svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M3 3l8 8M11 3l-8 8" stroke="#575b63" strokeWidth="1.6" strokeLinecap="round" /></svg></button>
              </div>
            )}
            <div key={cur.id} className="m-in h-full overflow-y-auto px-9 pb-[88px] pt-6 caret-[#5e5668]">
              <p className="w-full text-center text-[14px] leading-[21px] text-[#6b7078]">{cur.full}</p>
              <div className="h-[18px]" />
              <Grow value={cur.title} onChange={(v) => edit({ title: v })} autoFocus={fresh === cur.id} placeholder="제목" className="text-[30px] font-bold leading-[40px] text-[#16171a]"
                onKeyDown={(e) => { if (e.key === "Enter" && !e.nativeEvent.isComposing) { e.preventDefault(); ed.current?.focus(); } }} />
              <div className="h-3" />
              <div className="relative">
                {empty && <p className={cx("pointer-events-none absolute left-0 top-0 text-[#9a9ea7]", bodyCls)}>내용을 입력하세요</p>}
                <div ref={ed} contentEditable suppressContentEditableWarning role="textbox" aria-multiline aria-label="기록 내용" onInput={onInput} className={cx("jr-ed min-h-[26px] w-full text-[#16171a] outline-none", bodyCls)} />
              </div>
              {cur.todo.length > 0 && (<>
                <div className="h-[18px]" />
                <p className="text-[20px] font-bold leading-[29px] text-[#16171a]">다음 액션</p>
                <div className="h-[6px]" />
                {cur.todo.map((td, i) => (
                  <div key={i} className="flex w-full items-center gap-[10px] py-[3px]">
                    <button role="checkbox" aria-checked={td.d} aria-label={td.t || "할 일"} onClick={() => edit({ todo: cur.todo.map((x, j) => (j === i ? { ...x, d: !x.d } : x)) })}
                      className={cx("flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-full border-[1.5px] transition-colors", td.d ? "border-[#5e5668] bg-[#5e5668]" : "border-[#c7c7cc] bg-white hover:border-[#9a9ea7]")}>
                      {td.d && <svg width="10" height="10" viewBox="0 0 10 10" fill="none" className="m-pop"><path d="M2 5.2 4.1 7.2 8 3" stroke="#fff" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>}
                    </button>
                    <input value={td.t} autoFocus={focusTodo === i} onFocus={() => setFocusTodo(null)} onChange={(e) => edit({ todo: cur.todo.map((x, j) => (j === i ? { ...x, t: e.target.value } : x)) })}
                      onKeyDown={(e) => { if (e.key === "Backspace" && !td.t) { e.preventDefault(); edit({ todo: cur.todo.filter((_, j) => j !== i) }); } }}
                      aria-label="할 일" className={cx("min-w-0 flex-1 bg-transparent outline-none transition-colors", bodyCls, td.d ? "text-[#9a9ea7] line-through decoration-[#9a9ea7]" : "text-[#1c1c1c]")} />
                  </div>
                ))}
              </>)}
            </div>
            {/* 떠 있는 도구 막대 (편집기 가운데, 아래 20) — 리스트 · Aa 두 개만 (11.13), 크기 키움 */}
            {fmt && <FormatPanel ed={ed} onClose={() => setFmt(false)} />}
            <div className="absolute bottom-5 left-1/2 flex -translate-x-1/2 items-center gap-1 rounded-[24px] border border-[#e5e7eb] bg-white p-1 shadow-[0px_6px_20px_0px_rgba(18,15,31,0.1),0px_1px_3px_0px_rgba(0,0,0,0.05)]">
              <button aria-label="체크리스트" title="체크리스트" onMouseDown={(e) => e.preventDefault()} onClick={() => tool("check")} className="flex h-10 w-[52px] items-center justify-center rounded-[20px] hover:bg-[#f3f4f6]">
                <svg width="44" height="38" viewBox="2.5 -0.5 33 33" fill="none" stroke="#1C1C1C" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">{CHECK_ICON}</svg>
              </button>
              <button aria-label="사진" title="사진 넣기" onMouseDown={(e) => e.preventDefault()} onClick={() => photo.current?.click()} className="flex h-10 w-[52px] items-center justify-center rounded-[20px] hover:bg-[#f3f4f6]">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#1C1C1C" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><rect x="3.5" y="5" width="17" height="14" rx="3" /><circle cx="9" cy="10" r="1.8" /><path d="M20.5 15.5l-4.5-4.5-8.5 8" /></svg>
              </button>
              <input ref={photo} type="file" accept="image/*" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) addPhoto(f); e.target.value = ""; }} />
              <button data-fmt-btn aria-label="서식" title="서식" aria-expanded={fmt} onMouseDown={(e) => e.preventDefault()} onClick={() => tool("fmt")} className={cx("flex h-10 w-[52px] items-center justify-center rounded-[20px] transition-colors", fmt ? "bg-[#111] text-white" : "text-[#1c1c1c] hover:bg-[#f3f4f6]")}>
                <span className="text-[20px] font-semibold leading-[29px] tracking-[-0.02em]">Aa</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
    <CtxMenu at={menu?.at ?? null} items={menu?.items ?? []} onClose={() => setMenu(null)} />
    {pick && (() => { const ls = journal.filter((j) => pick.has(j.id)); return <SelectBar n={pick.size} total={list.length} all={pick.size === list.length && list.length > 0} onAll={() => setPick(pick.size === list.length ? new Set() : new Set(list.map((j) => j.id)))} onPin={() => { pinJ(ls, true); setPick(null); }} onTrash={() => { trashJ(ls); setPick(null); }} onEnd={() => setPick(null)} />; })()}
    </FixedFrame>
  );
}
