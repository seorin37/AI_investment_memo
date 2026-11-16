/* 스튜디오 넛지 (11.14 멘토링 반영) — 소식을 보는 도중 필요한 자리에서 뜨는 검정 알약 하나.
   누르면 스튜디오의 해당 기능이 열리고, 안 눌러도 아무것도 막지 않음. 닫으면 다시 띄우지 않음(시연 도구에서 되살릴 수 있음).
   Lucian UX/UI Prompt #252 · MIT License (c) 2026 Seokwoooo · https://lucianlabs.dev/uxui-prompt/#252 — 빛줄기가 훑고 지나가는 알약 · 올리면 앞으로 밀리는 화살표 */
import { useEffect, useRef, useState } from "react";
import { cx } from "./kit";
import { useApp, type NudgeId } from "./store";
import { NEW_N } from "./data";

export const Spark = ({ s = 18, c = "white" }: { s?: number; c?: string }) => <svg width={s} height={s} viewBox="0 0 19 19" fill="none" className="shrink-0"><path d="M8.70834 2.375C9.18334 5.77917 10.8458 7.44167 14.25 7.91667C10.8458 8.39167 9.18334 10.0542 8.70834 13.4583C8.23334 10.0542 6.57084 8.39167 3.16667 7.91667C6.57084 7.44167 8.23334 5.77917 8.70834 2.375Z" fill={c} /><path d="M15.0417 11.875V15.0417M13.4583 13.4583H16.625" stroke={c} strokeWidth="1.8" strokeLinecap="round" /></svg>;
export const Arrow = ({ c = "white" }: { c?: string }) => <svg className="u252-ar" width="16" height="16" viewBox="0 0 14 14" fill="none" aria-hidden><path d="M3 7h8M7.5 3.5 11 7l-3.5 3.5" stroke={c} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>;
export const Cross = ({ c = "white", o = 0.7 }: { c?: string; o?: number }) => <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden><path d="M3.5 3.5L10.5 10.5M10.5 3.5L3.5 10.5" stroke={c} strokeOpacity={o} strokeWidth="1.6" strokeLinecap="round" /></svg>;

/* 넛지에서 스튜디오 기능 열기 (다른 화면에서도 같이 씀) */
export function useStudioOpen() {
  const { studio, setStudio, setOverlay, setPreset, sgo } = useApp();
  return {
    report: (codes: string[]) => { setPreset({ codes }); setStudio((s) => ({ ...s, open: true })); setOverlay(studio.creditOut ? "credit" : "reportPick"); },
    audio: (codes: string[]) => { setPreset({ codes }); setStudio((s) => ({ ...s, open: true })); setOverlay(studio.creditOut ? "credit" : "audio"); },
    lab: () => { setStudio((s) => ({ ...s, open: true, labVars: { "원/달러 환율": "상승" } })); sgo("lab"); },
  };
}

export function NudgeHost() {
  const { route, nav, coach, coachPending, nudgeOff, hideNudge, nudgeAsk, askNudge, stocks, sideOpen, studio } = useApp();
  const open = useStudioOpen();
  const [box, setBox] = useState<{ left: number; max: number } | null>(null);
  useEffect(() => {
    const main = document.querySelector("main"); if (!main) return;
    const f = () => { const r = main.getBoundingClientRect();
      /* 좁은 화면에서는 스튜디오가 가운데 화면 위를 덮으므로, 가려지지 않은 부분의 가운데에 둠 */
      const st = document.querySelector('aside[aria-label="스튜디오"]')?.getBoundingClientRect();
      const right = st && st.width > 0 && st.left > r.left && st.left < r.right ? st.left : r.right, width = right - r.left;
      const left = r.left + width / 2, max = Math.max(240, width - 32); setBox((b) => (b && Math.abs(b.left - left) < 0.25 && Math.abs(b.max - max) < 0.25 ? b : { left, max })); };
    f(); const ro = new ResizeObserver(f); ro.observe(main); window.addEventListener("resize", f);
    /* 사이드바·스튜디오가 접히고 펴지는 동안에는 가운데 화면이 크기뿐 아니라 자리도 움직이므로, 움직임이 끝날 때까지 따라가며 다시 잼 */
    let raf = 0; const t0 = performance.now(); const follow = () => { f(); if (performance.now() - t0 < 1400) raf = requestAnimationFrame(follow); }; raf = requestAnimationFrame(follow);
    return () => { ro.disconnect(); window.removeEventListener("resize", f); cancelAnimationFrame(raf); };
  }, [nav, sideOpen, studio.open]);

  /* 코치마크가 끝난 바로 그 화면에서는 띄우지 않음 */
  const block = useRef<number | null>(null), was = useRef(false);
  if (coach) was.current = true; else if (was.current) { was.current = false; block.current = nav; }
  useEffect(() => { askNudge(null); }, [nav]); // eslint-disable-line react-hooks/exhaustive-deps

  const all = stocks.map((s) => s.code), total = all.reduce((a, c) => a + (NEW_N[c] ?? 0), 0);
  let n: { id: NudgeId; text: string; run: () => void } | null = null;
  if (route.name === "home") {
    if (nudgeAsk === "lab" && !nudgeOff.lab) n = { id: "lab", text: "환율이 바뀌면 내 종목은? 실험해 보기", run: open.lab };
    else if (!nudgeOff.home && all.length) n = { id: "home", text: "이번 주 내 종목, 한 장으로 볼까요?", run: () => open.report(all) };
  } else if (route.name === "updates") {
    const cnt = route.code ? NEW_N[route.code] ?? 0 : total;
    if (cnt > 0 && !nudgeOff.updates) n = { id: "updates", text: `오늘 소식 ${cnt}건, 라디오로 들을까요?`, run: () => open.audio(route.code ? [route.code] : all) };
  } else if (route.name === "stock" && route.tab === "info") {
    if (!nudgeOff.info) n = { id: "info", text: "공시·재무 읽기 어려우셨죠? 핵심만 정리해 드려요", run: () => open.report([route.code]) };
  }
  const id = n?.id ?? null;
  const [armed, setArmed] = useState(false);
  useEffect(() => { setArmed(false); if (!id) return; const t = window.setTimeout(() => setArmed(true), id === "lab" ? 250 : 1000); return () => window.clearTimeout(t); }, [nav, id]);
  const on = !!n && armed && !coach && !coachPending && !(block.current === nav && id !== "lab");
  const keep = useRef(n); if (n) keep.current = n; // 사라지는 동안 글자가 비지 않게
  const v = n ?? keep.current;
  if (!box || !v) return null;
  return (
    <div role="complementary" aria-label="스튜디오 제안" aria-hidden={!on} data-nudge={v.id} data-on={on ? "1" : "0"}
      className={cx("v2-nudge u252-pl fixed z-40 flex h-12 items-center rounded-full bg-[#15171a] shadow-[0px_12px_30px_0px_rgba(20,23,26,0.25)]", on && "on")} style={{ left: box.left, bottom: 28, maxWidth: box.max }}>
      <button tabIndex={on ? 0 : -1} onClick={() => { hideNudge(v.id); v.run(); }} className="u252-go flex h-12 min-w-0 items-center gap-2 rounded-l-full pl-4 pr-3">
        <Spark />
        <span className="min-w-0 truncate text-[15px] font-bold leading-[23px] text-white">{v.text}</span>
        <Arrow />
      </button>
      <span className="h-5 w-px shrink-0 bg-white/20" />
      <button tabIndex={on ? 0 : -1} aria-label="제안 닫기" title="닫기" onClick={() => hideNudge(v.id)} className="grid h-12 w-11 shrink-0 place-items-center rounded-r-full hover:bg-white/10"><Cross /></button>
    </div>
  );
}
