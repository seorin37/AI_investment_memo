/* 11.16 앱 통일 — 메모 보드 · 메모 상세에 앱 기능: 보드 칩(전체·AI 연결·새 소식), 격자/목록, ⋯·우클릭 메뉴, 여러 개 선택,
   AI 연결 흐름(항목 찾기 → 고르기 → 연결), 휴지통 + 되돌리기. 모양은 웹(검정), ⋯ 메뉴 움직임은 Lucian #038 (x.css) */
import { useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Modal, cx, useSnack } from "../kit";
import { paperBg, type Memo } from "../data";
import { api, API_MODE } from "../api";
import type { TrackItem } from "../api/types";
import { useApp } from "../store";
import { CtxMenu, MI, type MenuItem } from "../x";
import { mainCenter } from "../kit";

/* ---------- AI 연결 창 (앱 12 · 12.1): 메모 저장 ✓ → 항목 확인 → 연결 시작 ---------- */
export function ConnectDialog({ memo, onClose, onDone }: { memo: { id?: number; title: string; body: string; code: string } | null; onClose: () => void; onDone: (items: TrackItem[]) => void }) {
  const last = useRef(memo); if (memo) last.current = memo;
  const m = memo ?? last.current;
  const [items, setItems] = useState<TrackItem[]>([]);
  const [sel, setSel] = useState<Record<string, boolean>>({});
  const [phase, setPhase] = useState<"find" | "pick" | "fail">("find");
  const [failMsg, setFailMsg] = useState("");
  /* API 모드: 창을 열면 서버에서 AI 연결을 켜고(PUT ai-link) 실제 분석 결과(analysis.items)를 보여 줘요.
     항목은 서버가 정해서 고를 수 없어요. 취소·실패로 닫으면 다시 꺼요(enabled:false). */
  const linked = useRef<number | null>(null);
  const close = () => { if (API_MODE && linked.current != null) { void api.ai.linkEnd(linked.current, false); linked.current = null; } onClose(); };
  const done = (list: TrackItem[]) => { if (API_MODE && linked.current != null) { void api.ai.linkEnd(linked.current, true); linked.current = null; } onDone(list); };
  useLayoutEffect(() => {
    if (!memo) return;
    setPhase("find"); let alive = true;
    if (API_MODE) {
      setItems([]); setSel({});
      if (memo.id == null) { setFailMsg("메모를 찾지 못했어요 · 다시 시도해 주세요"); setPhase("fail"); return; }
      const id = memo.id; linked.current = id;
      api.ai.linkStart(id).then((r) => {
        if (!alive) return;
        setItems(r.items); setSel(Object.fromEntries(r.items.map((i) => [i.k, true])));
        if (r.status === "failed") { setFailMsg("메모를 분석하지 못했어요 · 잠시 후 다시 시도해 주세요"); setPhase("fail"); } else setPhase("pick");
      }, (e: unknown) => {
        if (!alive) return;
        setFailMsg(`AI 연결을 켜지 못했어요 · ${e instanceof Error ? e.message : ""}`); setPhase("fail");
      });
      return () => { alive = false; };
    }
    const kk = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--k")) || 1;
    const t0 = Date.now();
    void Promise.resolve(api.ai.findItems(memo.title + " " + memo.body, memo.code)).then((it) => {
      if (!alive) return; setItems(it); setSel(Object.fromEntries(it.map((i) => [i.k, true])));
      window.setTimeout(() => alive && setPhase("pick"), Math.max(0, 700 * kk - (Date.now() - t0)));
    });
    return () => { alive = false; };
  }, [memo]);
  const n = items.filter((i) => sel[i.k]).length;
  return (
    <Modal open={!!memo} onClose={close} width={680} z={75} label="AI 연결">
      <div data-connect className="flex w-[680px] flex-col gap-5 rounded-[28px] bg-white px-8 pb-7 pt-7">
        <div className="flex items-center gap-2">
          {["메모 확인", "항목 고르기", "연결 시작"].map((s, i) => { const on = i === 0 || (i === 1 && phase === "pick"); return (
            <span key={s} className="flex items-center gap-2">
              {i > 0 && <span className="h-px w-6 bg-[#e5e7eb]" />}
              <span className={cx("flex h-7 items-center gap-1 rounded-full px-3 text-[13px] font-bold transition-colors", on ? "bg-[#15171a] text-white" : "bg-[#f2f3f4] text-[#8b95a1]")}>{i === 0 && <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2.5 6L4.8 8.3L9.5 3.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>}{s}</span>
            </span>
          ); })}
        </div>
        <div className="flex flex-col gap-1">
          <p className="text-[22px] font-bold leading-[31px] text-[#15171a]">무엇을 계속 확인할까요?</p>
          <p className="break-keep text-[15px] leading-[23px] text-[#747d8d]">메모에서 찾은 항목이에요. 고른 항목과 관련된 공시·뉴스·종가 변화만 모아 드려요.</p>
        </div>
        <div className="rounded-[16px] px-5 py-4" style={{ background: paperBg("yellow") }}>
          <p className="truncate text-[17px] font-bold leading-[26px] text-[#16161c]">{m?.title}</p>
          {m?.body && <p className="line-clamp-2 text-[14px] leading-[21px] text-[#2e2e38]">{m.body.replace(/\n/g, " ")}</p>}
        </div>
        {phase === "find" ? (
          <div data-connect-loading className="flex h-[132px] items-center justify-center gap-2 text-[15px] font-medium text-[#747d8d]"><span className="h-2 w-2 animate-pulse rounded-full bg-[#15171a]" />메모에서 계속 확인할 항목을 찾고 있어요</div>
        ) : phase === "fail" ? (
          <div data-connect-fail className="m-in flex min-h-[132px] items-center justify-center rounded-[14px] bg-[#fdf0f1] px-5 text-center text-[15px] font-bold leading-[23px] text-[#c0392b]">{failMsg}</div>
        ) : API_MODE && !items.length ? (
          <div data-connect-empty className="m-in flex min-h-[132px] items-center justify-center rounded-[14px] bg-[#f7f7f7] px-5 text-center text-[15px] leading-[23px] text-[#575b63]">메모에서 계속 확인할 항목을 찾지 못했어요 · 확인하고 싶은 공시·뉴스 주제나 가격을 메모에 적어 주세요</div>
        ) : (
          <div className="m-in flex flex-col gap-2">
            {items.map((it, i) => { const on = !!sel[it.k]; return (
              <button key={it.k} role="checkbox" aria-checked={on} aria-disabled={API_MODE || undefined} onClick={() => { if (!API_MODE) setSel((s) => ({ ...s, [it.k]: !s[it.k] })); }} style={{ ["--i" as string]: i }} className={cx("m-reveal flex h-16 w-full items-center gap-3 rounded-[14px] px-4 text-left transition-colors", on ? "bg-[#f7f7f7] shadow-[inset_0_0_0_1.5px_#111]" : "bg-white shadow-[inset_0_0_0_1px_#e5e7eb] hover:bg-[#f9f9f9]")}>
                <span className={cx("grid h-[22px] w-[22px] shrink-0 place-items-center rounded-full", on ? "bg-[#111]" : "shadow-[inset_0_0_0_1.6px_#c9ccd2]")}>{on && <svg className="m-pop" width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2.5 6L4.8 8.3L9.5 3.5" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>}</span>
                <span className="flex min-w-0 flex-1 flex-col"><span className="text-[17px] font-bold leading-[26px] text-[#15171a]">{it.t}</span><span className="text-[14px] leading-[21px] text-[#747d8d]">{it.d}</span></span>
              </button>
            ); })}
            <p className="mt-1 break-keep text-[13px] leading-[20px] text-[#8b95a1]">AI는 메모를 고치지 않아요 · 실시간 알림이 아닌 전일 확정 종가와 정기보고서·뉴스 기준이에요</p>
          </div>
        )}
        <div className="flex justify-end gap-2">
          <button onClick={close} className="flex h-12 items-center rounded-[12px] bg-[#f2f3f4] px-5 text-[15px] font-medium text-[#15171a] hover:bg-[#e9eaec]">일반 메모로 두기</button>
          <button disabled={phase !== "pick" || !n} onClick={() => done(items.filter((i) => sel[i.k]))} className="flex h-12 items-center rounded-[12px] bg-[#14171c] px-6 text-[15px] font-medium text-white disabled:cursor-not-allowed disabled:bg-[#c9ccd2]">{n ? `${n}개 항목으로 AI 연결` : "항목을 골라 주세요"}</button>
        </div>
      </div>
    </Modal>
  );
}

/* ---------- 보드 머리: 내 메모 n · 칩(전체·AI 연결·새 소식, 알약이 미끄러짐) · 격자/목록 ---------- */
export type BoardFilter = "all" | "ai" | "new";
export function BoardHead({ mine, filter, setFilter, view, setView, hint }: { mine: Memo[]; filter: BoardFilter; setFilter: (f: BoardFilter) => void; view: "grid" | "list"; setView: (v: "grid" | "list") => void; hint?: boolean }) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});
  const [pill, setPill] = useState<{ l: number; w: number } | null>(null);
  useLayoutEffect(() => { const b = refs.current[filter]; if (b) setPill({ l: b.offsetLeft, w: b.offsetWidth }); }, [filter, mine.length]);
  const C: [BoardFilter, string, number][] = [["all", "전체", mine.length], ["ai", "AI 연결", mine.filter((m) => m.ai).length], ["new", "새 소식", mine.filter((m) => m.badge > 0).length]];
  return (
    <div data-board-head className="flex h-10 w-full items-center gap-3">
      <p className="whitespace-nowrap text-[17px] font-bold leading-[26px] text-[#15171a]">내 메모 {mine.length}</p>
      <div className="relative flex items-center gap-1">
        {pill && <span className="x-pill" style={{ left: pill.l, width: pill.w }} />}
        {C.map(([k, l, n]) => <button key={k} ref={(el) => { refs.current[k] = el; }} data-filter={k} aria-pressed={filter === k} onClick={() => setFilter(k)} className={cx("relative flex h-9 items-center gap-1 rounded-full px-[14px] text-[14px] font-bold transition-colors", filter === k ? "text-white" : "text-[#8b95a1] hover:text-[#191f28]")}>{k === "new" && n > 0 && <span className={cx("h-[6px] w-[6px] rounded-full", filter === k ? "bg-white" : "bg-[#e5484d]")} />}{l}{k !== "all" && ` ${n}`}</button>)}
      </div>
      {hint && <p data-drag-hint className="m-in ml-auto hidden items-center gap-1 whitespace-nowrap text-[13px] leading-[20px] text-[#8b95a1] min-[1180px]:flex"><svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" aria-hidden><circle cx="5.5" cy="4" r="1.2" /><circle cx="10.5" cy="4" r="1.2" /><circle cx="5.5" cy="8" r="1.2" /><circle cx="10.5" cy="8" r="1.2" /><circle cx="5.5" cy="12" r="1.2" /><circle cx="10.5" cy="12" r="1.2" /></svg>꾹 눌러 끌면 위치를 바꿀 수 있어요</p>}
      <div className={cx(!hint && "ml-auto", hint && "ml-auto min-[1180px]:ml-2", "flex items-center gap-1 rounded-[10px] bg-white p-1 shadow-[inset_0_0_0_1px_#e5e7eb]")}>
        {(["grid", "list"] as const).map((v) => <button key={v} aria-label={v === "grid" ? "격자로 보기" : "목록으로 보기"} aria-pressed={view === v} data-view={v} onClick={() => setView(v)} className={cx("grid h-8 w-8 place-items-center rounded-[8px] transition-colors", view === v ? "bg-[#15171a] text-white" : "text-[#8b95a1] hover:bg-[#f5f6f8]")}>
          {v === "grid" ? <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6"><rect x="2" y="2" width="5" height="5" rx="1.2" /><rect x="9" y="2" width="5" height="5" rx="1.2" /><rect x="2" y="9" width="5" height="5" rx="1.2" /><rect x="9" y="9" width="5" height="5" rx="1.2" /></svg>
            : <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"><path d="M2.5 4h11M2.5 8h11M2.5 12h11" /></svg>}
        </button>)}
      </div>
    </div>
  );
}

/* ---------- 목록으로 보기 ---------- */
export function MemoList({ list, sel, onOpen, onMenu, onPick }: { list: Memo[]; sel: Set<number> | null; onOpen: (m: Memo) => void; onMenu: (m: Memo, at: { x: number; y: number }) => void; onPick: (m: Memo) => void }) {
  return (
    <div data-memo-list className="m-in flex w-full flex-col overflow-hidden rounded-[20px] border border-[#e5e7eb] bg-white">
      {list.map((m, i) => (
        <div key={m.id} data-memo-row={m.id} role="button" tabIndex={0} onClick={() => (sel ? onPick(m) : onOpen(m))} onKeyDown={(e) => { if (e.key === "Enter") (sel ? onPick(m) : onOpen(m)); }} onContextMenu={(e) => { e.preventDefault(); onMenu(m, { x: e.clientX, y: e.clientY }); }}
          className={cx("m-reveal flex h-[76px] w-full cursor-pointer items-center gap-4 px-5 text-left hover:bg-[#f9f9f9]", i > 0 && "border-t border-[#f0f1f3]")} style={{ ["--i" as string]: i }}>
          {sel && <Pick on={sel.has(m.id)} />}
          <span className="dk-keep h-10 w-10 shrink-0 rounded-[10px_10px_0px_10px]" style={{ background: paperBg(m.color, true) }} />
          <span className="flex min-w-0 flex-1 flex-col">
            <span className="flex items-center gap-2"><span className="truncate text-[17px] font-bold leading-[26px] text-[#15171a]">{m.title}</span>{m.pinned && <span className="shrink-0 rounded-[6px] bg-[#f2f3f4] px-[6px] text-[13px] font-medium leading-[20px] text-[#575b63]">고정</span>}</span>
            <span className="truncate text-[14px] leading-[21px] text-[#747d8d]">{m.date} 작성 · {m.body.replace(/\n/g, " ")}</span>
          </span>
          {m.ai && <span className="flex h-7 shrink-0 items-center gap-1 rounded-full bg-[#f2f3f4] px-[10px] text-[13px] font-bold text-[#15171a]">AI 연결</span>}
          {m.badge > 0 && <span className="grid h-6 min-w-6 shrink-0 place-items-center rounded-full bg-[#e5484d] px-[6px] text-[13px] font-medium text-white">{m.badge}</span>}
          {!sel && <button aria-label="메모 메뉴" onClick={(e) => { e.stopPropagation(); const r = (e.currentTarget as HTMLElement).getBoundingClientRect(); onMenu(m, { x: r.right - 220, y: r.bottom + 6 }); }} className="grid h-8 w-8 shrink-0 place-items-center rounded-[8px] text-[#8b95a1] hover:bg-[#f2f3f4]"><Dots /></button>}
        </div>
      ))}
      {list.length === 0 && <p className="px-5 py-10 text-center text-[15px] font-medium text-[#8b95a1]">조건에 맞는 메모가 없어요</p>}
    </div>
  );
}
export const Dots = () => <svg width="18" height="18" viewBox="0 0 18 18" fill="currentColor"><circle cx="4" cy="9" r="1.5" /><circle cx="9" cy="9" r="1.5" /><circle cx="14" cy="9" r="1.5" /></svg>;
export const Pick = ({ on }: { on: boolean }) => (
  <span aria-hidden className={cx("grid h-[22px] w-[22px] shrink-0 place-items-center rounded-full transition-colors", on ? "bg-[#111]" : "bg-white shadow-[inset_0_0_0_1.6px_#c9ccd2]")}>{on && <svg className="m-pop" width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2.5 6L4.8 8.3L9.5 3.5" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>}</span>
);

/* ---------- 여러 개 선택: 아래에 떠 있는 막대 (고정 · 복사 · 휴지통) ---------- */
export function SelectBar({ n, total, all, onAll, onPin, onCopy, onTrash, onEnd, extra }: { n: number; total: number; all: boolean; onAll: () => void; onPin?: () => void; onCopy?: () => void; onTrash: () => void; onEnd: () => void; extra?: ReactNode }) {
  return createPortal(
    <div className="fixed bottom-7 z-[72] -translate-x-1/2" style={{ left: mainCenter() ?? "50%" }}><div data-select-bar className="m-pop flex h-14 items-center gap-1 rounded-[18px] bg-[#15171a] pl-5 pr-2 text-white shadow-[0_16px_36px_-12px_rgba(17,17,17,.45)]">
      <span className="whitespace-nowrap text-[15px] font-bold">{n}개 선택</span>
      <button onClick={onAll} className="ml-2 h-10 rounded-[10px] px-3 text-[14px] font-bold text-white/80 hover:bg-white/10">{all ? "전체 해제" : `전체 선택 ${total}`}</button>
      <span className="mx-1 h-5 w-px bg-white/20" />
      {extra}
      {onPin && <button disabled={!n} onClick={onPin} className="flex h-10 items-center gap-1 rounded-[10px] px-3 text-[14px] font-bold hover:bg-white/10 disabled:opacity-40">{MI.pin}고정</button>}
      {onCopy && <button disabled={!n} onClick={onCopy} className="flex h-10 items-center gap-1 rounded-[10px] px-3 text-[14px] font-bold hover:bg-white/10 disabled:opacity-40">{MI.copy}복사</button>}
      <button disabled={!n} onClick={onTrash} className="flex h-10 items-center gap-1 rounded-[10px] px-3 text-[14px] font-bold text-[#ff8a8f] hover:bg-white/10 disabled:opacity-40">{MI.trash}휴지통</button>
      <span className="mx-1 h-5 w-px bg-white/20" />
      <button onClick={onEnd} className="h-10 rounded-[10px] px-3 text-[14px] font-bold hover:bg-white/10">선택 끝내기</button>
    </div></div>, document.body
  );
}

/* ---------- 메모 메뉴 묶음 + 휴지통(되돌리기) ---------- */
export function useMemoActions() {
  const { act: A } = useApp();
  const snack = useSnack();
  const trash = (list: Memo[]) => {
    const before = A.snapshot();
    A.trashMemos(list.map((m) => m.id));
    snack(list.length > 1 ? `메모 ${list.length}개를 휴지통으로 옮겼어요` : "메모를 휴지통으로 옮겼어요", { undo: () => A.rollback(before) });
  };
  const pin = (list: Memo[], on: boolean) => {
    A.pinMemos(list.map((m) => m.id), on);
    snack(on ? (list.length > 1 ? `${list.length}개를 고정했어요` : "메모를 고정했어요") : "고정을 풀었어요", { check: true });
  };
  const copy = (list: Memo[]) => {
    const txt = list.map((m) => m.title + "\n" + m.body).join("\n\n");
    try { void navigator.clipboard?.writeText(txt).catch(() => {}); } catch { /* 무시 */ }
    snack("내용을 복사했어요", { check: true });
  };
  const menu = (m: Memo, extra: { select?: () => void; open?: () => void } = {}): MenuItem[] => [
    ...(extra.open ? [{ label: "열기", icon: MI.find, run: extra.open }] : []),
    { label: m.pinned ? "테이프 떼기" : "테이프 붙여 맨 위로", icon: MI.pin, run: () => pin([m], !m.pinned) },
    { label: "내용 복사", icon: MI.copy, run: () => copy([m]) },
    ...(extra.select ? [{ label: "여러 개 선택", icon: MI.select, run: extra.select }] : []),
    "-" as const,
    { label: "휴지통으로 이동", icon: MI.trash, danger: true, run: () => trash([m]) },
  ];
  return { trash, pin, copy, menu };
}
export { CtxMenu };
