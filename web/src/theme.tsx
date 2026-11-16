/* 다크 모드 (11.13) — 사이드바 휴지통 위 토글 · 접힌 사이드바는 해·달 아이콘
   Lucian UX/UI Prompt #219 (원으로 번지는 전환·아이콘 회전) + #021 (낮·밤 하늘 스위치) 이식 */
import { useSyncExternalStore } from "react";
import { flushSync } from "react-dom";
import "./theme.css";

let dark = (() => { try { return localStorage.getItem("memos-dark") === "1"; } catch { return false; } })();
const subs = new Set<() => void>();
const apply = () => document.documentElement.classList.toggle("dark", dark);
apply();
const set = (v: boolean) => { dark = v; try { localStorage.setItem("memos-dark", v ? "1" : "0"); } catch { /* 무시 */ } apply(); subs.forEach((f) => f()); };
export const useDark = () => useSyncExternalStore((f) => { subs.add(f); return () => subs.delete(f); }, () => dark);

/* 누른 버튼 자리에서 원으로 번지며 바뀜 (#219). 지원 안 되는 브라우저·모션 줄이기는 바로 바뀜 */
export function toggleDark(from?: HTMLElement | null) {
  const next = !dark;
  const doc = document as Document & { startViewTransition?: (cb: () => void) => unknown };
  const k = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--k")) || 1;
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches || k < 0.1;
  if (!doc.startViewTransition || reduce) { set(next); return; }
  const r = from?.getBoundingClientRect();
  const x = r ? r.left + r.width / 2 : innerWidth / 2, y = r ? r.top + r.height / 2 : innerHeight / 2;
  const root = document.documentElement.style;
  root.setProperty("--vt-x", `${x}px`); root.setProperty("--vt-y", `${y}px`);
  root.setProperty("--vt-r", `${Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y))}px`);
  doc.startViewTransition(() => flushSync(() => set(next)));
}

const SUN = <svg width="20" height="20" viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="3" fill="currentColor" /><g stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><path d="M8 1.5v1.4M8 13.1v1.4M1.5 8h1.4M13.1 8h1.4M3.4 3.4l1 1M11.6 11.6l1 1M3.4 12.6l1-1M11.6 4.4l1-1" /></g></svg>;
const MOON = <svg width="20" height="20" viewBox="0 0 16 16" aria-hidden="true"><path d="M13.5 9.8A5.6 5.6 0 0 1 6.2 2.5a5.6 5.6 0 1 0 7.3 7.3z" fill="currentColor" /></svg>;

/* 펼친 사이드바: '다크 모드' 글자 + 낮·밤 스위치 (Row와 같은 40px 줄) */
export function DarkRow() {
  const on = useDark();
  return (
    <div className="flex h-10 w-[218px] shrink-0 items-center gap-2 rounded-[8px] px-3">
      <span className="grid h-5 w-5 place-items-center text-[#333333]">{on ? MOON : SUN}</span>
      <span className="min-w-0 flex-1 text-[17px] leading-[26px] text-[#1c1c1c]">다크 모드</span>
      <span className={"dk-keep u021" + (on ? " is-night" : "")}>
        <button className="u021-sw" type="button" role="switch" aria-checked={on} aria-label="다크 모드" onClick={(e) => toggleDark(e.currentTarget)}>
          <span className="u021-halo" aria-hidden="true"><i /><i /><i /></span>
          <span className="u021-stars" aria-hidden="true">
            <i style={{ left: 30, top: 20 }} /><i style={{ left: 58, top: 56, animationDelay: "-.6s", width: 3, height: 3 }} /><i style={{ left: 86, top: 26, animationDelay: "-1.2s" }} /><i style={{ left: 44, top: 72, animationDelay: "-1.8s", width: 3, height: 3 }} /><i style={{ left: 110, top: 60, animationDelay: "-.9s", width: 2, height: 2 }} /><i style={{ left: 20, top: 46, animationDelay: "-1.5s", width: 2, height: 2 }} />
          </span>
          <span className="u021-clouds" aria-hidden="true"><i /><i /></span>
          <span className="u021-knob" aria-hidden="true"><span className="u021-moon"><i /><i /><i /></span></span>
        </button>
      </span>
    </div>
  );
}

/* 접힌 사이드바: 해·달 아이콘 버튼 (#219 버튼, 누르면 돌며 바뀜) */
export function DarkRail() {
  const on = useDark();
  return (
    <button aria-label={on ? "라이트 모드로 바꾸기" : "다크 모드로 바꾸기"} aria-pressed={on} title="다크 모드" onClick={(e) => toggleDark(e.currentTarget)}
      className={"u219-tg grid h-10 w-10 place-items-center rounded-[8px] bg-white text-[#333333] hover:bg-[#f9f9f9]" + (on ? " is-dark" : "")}>
      {on ? MOON : SUN}
    </button>
  );
}
