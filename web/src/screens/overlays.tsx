/* 4 종목 추가 · 8 설정 · 9/9.1 피드백 · 10 휴지통(최종 수정본) · 11 도움말 · 위험 확인 팝업 — 모두 Figma 2.5 그대로 */
import { useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { GoogleLogo, KakaoLogo, NaverLogo } from "./login";
import { SLogo } from "../fig";
import { Modal, PageTitle, cx, sleep, useSnack } from "../kit";
import { useUsage } from "../x";
import { LEGAL } from "../legal";
import { FixedFrame } from "./stock";
import { SEARCH_POOL, NEW_LOGO, ALL_STOCKS, type Hold } from "../data";
import { useApp, useProfile } from "../store";
import { API_MODE } from "../api/config";
import { api, type UserWire } from "../api/client";
import { newStock } from "../api/map";

const TR = "tracking-[-0.01em]";

/* ================= 4 · 종목 추가 — Page 3 '07 내 종목 · 종목 추가 시트' 내용을 가운데 팝업에 (보라 → 검정, 11.13) ================= */
const AI_OK = ["005930", "000660", "035420", "105560"]; // AI 연결 가능 (DB 4개 기업)
const DEFAULT_LIST = ["105560", "005380", "000270", "373220", "035720", "000660"]; // 11.16: 창이 커져서 6개
const josa = (w: string) => { const c = w.charCodeAt(w.length - 1); return c >= 0xac00 && c <= 0xd7a3 && (c - 0xac00) % 28 ? "을" : "를"; };
const PlugMini = () => <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M3.9 1.2V2.5M6.1 1.2V2.5" stroke="#111111" strokeWidth="1.08" strokeLinecap="round" /><path d="M2.9 2.6H7.1V4.3C7.1 5.46 6.16 6.4 5 6.4C3.84 6.4 2.9 5.46 2.9 4.3V2.6Z" fill="#111111" /><path d="M5 6.4V8.6" stroke="#111111" strokeWidth="1.08" strokeLinecap="round" /></svg>;
export function AddStock() {
  const { overlay, setOverlay, stocks, setStocks, go, setMemoOpen } = useApp();
  const snack = useSnack();
  const [q, setQ] = useState(""), [pick, setPick] = useState<string | null>(null), [hold, setHold] = useState<Hold>("관심");
  const open = overlay === "addStock";
  useEffect(() => { if (open) { setQ(""); setPick(null); setHold("관심"); } }, [open]);
  const t = q.trim();
  /* API 모드: 입력하면 서버 종목 마스터 검색 (GET /stocks/search, 0.25초 쉬었다가) */
  const [remote, setRemote] = useState<{ q: string; list: typeof SEARCH_POOL; err?: string } | null>(null);
  useEffect(() => {
    if (!API_MODE || !t) return;
    const id = window.setTimeout(() => {
      api.searchStocks(t).then(
        (r) => setRemote({ q: t, list: r.map((x) => ({ code: x.code.trim(), name: x.name, market: x.market })) }),
        (e) => setRemote({ q: t, list: [], err: e instanceof Error ? e.message : "검색하지 못했어요" }),
      );
    }, 250);
    return () => window.clearTimeout(id);
  }, [t]);
  const searching = API_MODE && !!t && remote?.q !== t;
  const list = t ? (API_MODE ? (remote?.q === t ? remote.list : []) : SEARCH_POOL.filter((s) => s.name.includes(t) || s.code.includes(t))) : DEFAULT_LIST.map((c) => SEARCH_POOL.find((s) => s.code === c)!);
  const had = (code: string) => stocks.find((x) => x.code === code);
  const sel = list.find((s) => s.code === pick && !had(s.code));
  const close = () => setOverlay(null);
  const ok = () => {
    if (!sel) return;
    const base = ALL_STOCKS.find((s) => s.code === sel.code);
    const [logo, bg] = NEW_LOGO[sel.code] ?? [sel.name[0], "#111"];
    const s = API_MODE ? newStock(sel.code, sel.name, sel.market, hold) : base ? { ...base, hold } : { code: sel.code, name: sel.name, short: logo, logo, logoBg: bg, hold, market: sel.market, price: sel.code === "105560" ? 78300 : 48250, chg: sel.code === "105560" ? 870 : 650, pct: sel.code === "105560" ? 1.12 : 1.37, seed: Number(sel.code.slice(-2)) };
    setStocks((a) => [...a, s]); close();
    snack(`${sel.name}${josa(sel.name)} ${hold} 종목에 추가했어요`, { check: true, action: { label: "메모 쓰기 ›", run: () => { go({ name: "stock", code: sel.code, tab: "board" }); setMemoOpen(-1); } } });
  };
  return (
    <Modal open={open} onClose={close} width={680} label="종목 추가">
      {/* 11.16: 휴지통과 같은 크기(680×660)·같은 머리 모양 */}
      <div data-addstock className="flex h-[660px] max-h-[calc(100vh-32px)] w-[680px] flex-col items-start gap-3 rounded-[20px] border border-[#e8eaed] bg-white p-[23px] shadow-[0px_12px_32px_-8px_rgba(28,41,64,0.08),0px_2px_8px_0px_rgba(28,41,64,0.05)]">
        <div className="mb-1 flex h-[56px] w-full shrink-0 items-center gap-4">
          <div className="flex h-[56px] min-w-0 flex-1 flex-col items-start gap-1">
            <p className="whitespace-nowrap text-[22px] font-bold leading-[31px] text-[#15171a]">종목 추가</p>
            <p className="whitespace-nowrap text-[17px] leading-[26px] text-[#747d8d]">메모를 남길 종목을 찾아 담아 두세요.</p>
          </div>
          <CloseX onClick={close} />
        </div>
        <label className="flex h-11 w-full shrink-0 items-center gap-2 rounded-[12px] border border-transparent bg-[#f3f4f6] px-3 focus-within:border-[1.5px] focus-within:border-[#111] focus-within:bg-white focus-within:px-[10.5px]">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" className="shrink-0"><circle cx="11" cy="11" r="6.2" stroke="#000" strokeWidth="1.6" /><path d="M15.6 15.6L19.2 19.2" stroke="#000" strokeWidth="1.6" strokeLinecap="round" /></svg>
          <input autoFocus value={q} onChange={(e) => { setQ(e.target.value); setPick(null); }} onKeyDown={(e) => { if (e.key === "Enter") ok(); }}
            placeholder="종목명 또는 코드" aria-label="종목 검색" className="h-[17px] min-w-0 flex-1 bg-transparent text-[14px] leading-[21px] text-[#16171a] outline-none placeholder:text-[#9a9ea7]" />
        </label>
        {t && <p className="shrink-0 text-[13px] leading-[20px] text-[#8a8f98]">{searching ? "검색 중…" : `검색 결과 ${list.length}건`}</p>}
        <div className="flex min-h-0 w-full flex-1 flex-col items-start gap-[2px] overflow-y-auto">
          {list.length === 0 && !searching && <p className="w-full py-6 text-center text-[13px] leading-[20px] text-[#8a8f98]">{remote?.q === t && remote.err ? `검색하지 못했어요 · ${remote.err}` : "찾는 종목이 없어요"}</p>}
          {list.map((s) => {
            const h = had(s.code), on = !h && s.code === pick;
            const [logo, bg] = h ? [h.logo, h.logoBg] : NEW_LOGO[s.code] ?? (ALL_STOCKS.find((x) => x.code === s.code) ? [ALL_STOCKS.find((x) => x.code === s.code)!.logo, ALL_STOCKS.find((x) => x.code === s.code)!.logoBg] : [s.name[0], "#111"]);
            return (
              <button key={s.code} disabled={!!h} onClick={() => setPick(on ? null : s.code)} onDoubleClick={() => { setPick(s.code); }} aria-pressed={on}
                className={cx("flex w-full shrink-0 items-center gap-3 rounded-[14px] py-[9px] pr-3 text-left transition-colors", on ? "bg-[#f7f7f7] pl-[10px] shadow-[inset_0_0_0_1.5px_#111]" : "pl-[10px] hover:bg-[#f9f9f9]", h && "cursor-default opacity-50 hover:bg-transparent")}>
                <span className="dk-keep flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px]" style={{ background: bg }}><span className="text-[15px] font-bold leading-[23px] text-white" style={{ fontSize: logo.length > 1 ? 12 : 15 }}>{logo}</span></span>
                <span className="flex min-w-0 flex-1 flex-col items-start gap-[1px]">
                  <span className="flex items-center gap-[6px]">
                    <span className="whitespace-nowrap text-[15px] font-bold leading-[23px] text-[#16171a]">{s.name}</span>
                    {AI_OK.includes(s.code) && <span className="flex items-center gap-[3px] rounded-[6px] bg-[#efefef] px-[6px] py-[2px]"><PlugMini /><span className="whitespace-nowrap text-[13px] font-bold leading-[20px] text-[#111]">AI 연결</span></span>}
                  </span>
                  <span className="whitespace-nowrap text-[13px] leading-[20px] text-[#8a8f98]">{s.code} · {s.market}{h ? ` · 이미 ${h.hold}에 있어요` : ""}</span>
                </span>
                {!h && (on
                  ? <svg width="22" height="22" viewBox="0 0 22 22" fill="none" className="shrink-0"><circle cx="11" cy="11" r="11" fill="#111111" /><path d="M6.8 11.2L9.6 14L15.2 8.2" stroke="white" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" /></svg>
                  : <svg width="22" height="22" viewBox="0 0 22 22" fill="none" className="shrink-0"><circle cx="11" cy="11" r="10" stroke="#c9ccd2" strokeWidth="1.6" /></svg>)}
              </button>
            );
          })}
        </div>
        <p className="shrink-0 text-[13px] leading-[20px] text-[#575b63]">어떻게 담을까요?</p>
        <div className="flex w-full shrink-0 items-start gap-2">
          {(["보유", "관심"] as const).map((h) => { const on = hold === h; return (
            <button key={h} onClick={() => setHold(h)} aria-pressed={on} className={cx("flex h-12 flex-1 items-center justify-center rounded-[12px] text-[15px] leading-[23px] transition-colors", on ? "bg-[#f7f7f7] font-medium text-[#111] shadow-[inset_0_0_0_1px_#111]" : "bg-white text-[#575b63] shadow-[inset_0_0_0_1px_#e5e7eb] hover:bg-[#f9f9f9]")}>{h}</button>
          ); })}
        </div>
        <button disabled={!sel} onClick={ok} className={cx("flex h-[46px] w-full shrink-0 items-center justify-center rounded-[14px] text-[15px] font-medium leading-[23px] text-white transition-colors", sel ? "bg-[#111] hover:bg-[#2a2a2a]" : "cursor-not-allowed bg-[#c9ccd2]")}>{sel ? `${hold} 종목으로 추가` : "종목을 골라 주세요"}</button>
      </div>
    </Modal>
  );
}

/* ================= 위험 확인 팝업 (피드백 팝업 모양 + 빨간 실행) ================= */
type Danger = "logout" | "withdraw" | "wipe";
const DANGER: Record<Danger, [string, string, string]> = {
  logout: ["로그아웃할까요?", "이 기기에서 로그아웃해요.", "로그아웃"],
  withdraw: ["정말 탈퇴할까요?", "계정과 모든 데이터가 바로 삭제되고 되돌릴 수 없어요.", "탈퇴"],
  wipe: ["모든 데이터를 삭제할까요?", "모든 메모, 기록, 종목이 영구 삭제돼요. 되돌릴 수 없어요.", "전체 삭제"],
};
function ConfirmDanger({ kind, onClose, z = 70, text, onRun }: { kind: Danger | null; onClose: () => void; z?: number; text?: [string, string, string]; onRun?: () => void }) {
  const { reset } = useApp();
  const snack = useSnack();
  const last = useRef<Danger>("logout"); if (kind) last.current = kind;
  const lastText = useRef(text); if (text) lastText.current = text;
  const [t, d, b] = lastText.current ?? DANGER[last.current];
  const run = () => {
    if (onRun) { onClose(); onRun(); return; }
    /* API 모드: 전체 삭제 · 회원 탈퇴 API가 아직 없어(분류 C) 지운 척하지 않는다 */
    if (API_MODE && last.current !== "logout") { onClose(); snack(last.current === "wipe" ? "전체 삭제는 아직 지원하지 않아요 · 데이터는 그대로예요" : "회원 탈퇴는 아직 지원하지 않아요 · 계정은 그대로예요"); return; }
    if (last.current === "wipe") { onClose(); snack("모든 데이터를 삭제했어요"); return; }
    onClose(); reset();
  };
  return (
    <Modal open={!!kind} onClose={onClose} z={z} width={400} label={t}>
      <div className="flex w-[400px] flex-col items-start gap-6 rounded-[28px] border border-[#e8ecf3] bg-white px-7 py-[27px] shadow-[0px_24px_56px_-16px_rgba(20,23,28,0.16)]">
        <div className="flex w-full flex-col items-start gap-2">
          <p className={cx("break-keep text-[22px] font-bold leading-[31px] text-[#15171a]", TR)}>{t}</p>
          <p className="w-full break-keep text-[15px] leading-[23px] text-[#747d8d]">{d}</p>
        </div>
        <div className="flex h-12 w-full items-start justify-end gap-2">
          <button onClick={onClose} className={cx("flex h-12 flex-1 items-center justify-center rounded-[12px] bg-[#f2f3f4] text-[15px] font-medium leading-[23px] text-[#15171a]", TR)}>취소</button>
          <button onClick={run} className={cx("flex h-12 flex-1 items-center justify-center rounded-[12px] bg-[#e45d6a] text-[15px] font-medium leading-[23px] text-white", TR)}>{b}</button>
        </div>
      </div>
    </Modal>
  );
}
/* 사이드바 프로필의 로그아웃 아이콘 */
export function LogoutConfirm() {
  const { overlay, setOverlay } = useApp();
  return <ConfirmDanger kind={overlay === "logout" ? "logout" : null} onClose={() => setOverlay(null)} z={60} />;
}

/* ================= 8 · 설정 (1040×780 가운데) ================= */
const S_NAV: [string, string[]][] = [["계정", ["내 프로필", "알림"]], ["서비스", ["사용량"]], ["기타", ["데이터", "정보"]]];
function NavIcon({ n, c }: { n: string; c: string }) {
  const p = { stroke: c, strokeWidth: 1.42222, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" className="shrink-0">
      {n === "내 프로필" && <><path d="M10.7731 5.96384L10.8442 5.33273L10.7731 4.70161L10.5597 4.09717L10.2219 3.55495L9.7775 3.1105L9.23527 2.77273L8.63083 2.55939L7.99972 2.48828L7.36861 2.55939L6.76416 2.77273L6.22194 3.1105L5.7775 3.55495L5.43972 4.09717L5.22638 4.70161L5.15527 5.33273L5.22638 5.96384L5.43972 6.56828L5.7775 7.1105L6.22194 7.55495L6.76416 7.89273L7.36861 8.10606L7.99972 8.17717L8.63083 8.10606L9.23527 7.89273L9.7775 7.55495L10.2219 7.1105L10.5597 6.56828L10.7731 5.96384Z" {...p} /><path d="M2.66699 13.7784C2.66699 10.8155 4.44477 9.33398 8.00033 9.33398C11.5559 9.33398 13.3337 10.8155 13.3337 13.7784" {...p} /></>}
      {n === "화면" && <><path d="M13.7782 3.11133H2.22266V10.6669H13.7782V3.11133Z" {...p} /><path d="M5.77734 13.7773H10.2218" {...p} /><path d="M8 10.666V13.7771" {...p} /></>}
      {n === "알림" && <><path d="M4.44455 10.6667L3.55566 12H12.4446L11.5557 10.6667V7.11111C11.5557 5.03704 10.3705 4 8.00011 4C5.62974 4 4.44455 5.03704 4.44455 7.11111V10.6667Z" {...p} /><path d="M6.66699 13.7773C7.55588 14.6662 8.44477 14.6662 9.33366 13.7773" {...p} /></>}
      {n === "AI 연결" && <><path d="M6.44434 3.33203V5.40611M9.55545 3.33203V5.40611" stroke={c} strokeWidth="1.42222" strokeLinecap="round" /><path d="M5.14746 5.40625H10.8512V7.48032C10.8512 8.23668 10.5507 8.96206 10.0159 9.49689C9.48105 10.0317 8.75567 10.3322 7.99931 10.3322C7.24295 10.3322 6.51757 10.0317 5.98275 9.49689C5.44792 8.96206 5.14746 8.23668 5.14746 7.48032V5.40625Z" stroke={c} strokeWidth="1.42222" strokeLinejoin="round" /><path d="M8 10.332V12.6654" stroke={c} strokeWidth="1.42222" strokeLinecap="round" /></>}
      {n === "사용량" && <path d="M3 14V10M9 14V4M15 14V7" stroke={c} strokeWidth="1.5" strokeLinecap="round" />}
      {n === "MCP 연결" && <><path d="M5.77734 2.22266V5.33377" {...p} /><path d="M10.2227 2.22266V5.33377" {...p} /><path d="M12 5.33398H4V8.00065C4 9.77843 5.33333 10.6673 8 10.6673C10.6667 10.6673 12 9.77843 12 8.00065V5.33398Z" {...p} /><path d="M8 10.666V13.7771" {...p} /></>}
      {n === "데이터" && <><path d="M13.3337 3.11068C9.7781 1.3329 6.22255 1.3329 2.66699 3.11068V10.2218C6.22255 11.9996 9.7781 11.9996 13.3337 10.2218V3.11068Z" {...p} /><path d="M2.66699 8C6.22255 9.77778 9.7781 9.77778 13.3337 8" {...p} /></>}
      {n === "정보" && <><path d="M14.0618 9.38623L14.2218 7.99957L14.0618 6.6129L13.6085 5.29734L12.8618 4.12401L11.8751 3.13734L10.7018 2.39068L9.38623 1.93734L7.99957 1.77734L6.6129 1.93734L5.29734 2.39068L4.12401 3.13734L3.13734 4.12401L2.39068 5.29734L1.93734 6.6129L1.77734 7.99957L1.93734 9.38623L2.39068 10.7018L3.13734 11.8751L4.12401 12.8618L5.29734 13.6085L6.6129 14.0618L7.99957 14.2218L9.38623 14.0618L10.7018 13.6085L11.8751 12.8618L12.8618 11.8751L13.6085 10.7018L14.0618 9.38623Z" {...p} /><path d="M8 7.28906V11.378" {...p} /><path d="M8 4.97852V5.15629" {...p} /></>}
    </svg>
  );
}
const Chev = ({ dir = "down" }: { dir?: "down" | "up" | "right" }) => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="shrink-0"><path d={dir === "down" ? "M3.11133 5.44531L7.00022 9.3342L10.8891 5.44531" : dir === "up" ? "M10.8887 8.55469L6.99978 4.6658L3.11089 8.55469" : "M5.44531 10.8887L9.3342 6.99978L5.44531 3.11089"} stroke="#8E8A97" strokeWidth="1.24444" strokeLinecap="round" strokeLinejoin="round" /></svg>
);
const CloseX = ({ onClick, label = "닫기" }: { onClick: () => void; label?: string }) => (
  <button aria-label={label} onClick={onClick} className="h-9 w-9 shrink-0 rounded-[8px] hover:bg-[#f8f7f5] focus-visible:shadow-[inset_0_0_0_1.5px_#15171a] focus-visible:outline-none">
    <svg width="36" height="36" viewBox="0 0 36 36" fill="none"><path d="M13 13L23 23" stroke="#333333" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /><path d="M23 13L13 23" stroke="#333333" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>
  </button>
);

/* 설정 공통 부품 (QA/Settings 상태 그대로) */
const T15 = ({ children, w }: { children: ReactNode; w?: number }) => <p className={cx("text-[17px] font-medium leading-[26px] text-[#15171a]", TR)} style={w ? { width: w } : undefined}>{children}</p>;
const D14 = ({ children, w }: { children: ReactNode; w?: number }) => <p className="text-[15px] leading-[23px] text-[#8e8a97]" style={w ? { width: w } : undefined}>{children}</p>;
const H16 = ({ children }: { children: ReactNode }) => <p className="whitespace-nowrap text-[20px] font-bold leading-[29px] text-[#15171a]">{children}</p>;
const Hr = () => <div className="h-px w-full shrink-0 bg-[#e5e3e8]" />;
function Row({ t, d, w, children }: { t: string; d?: ReactNode; w: number; children?: ReactNode }) {
  return <div className="flex w-[718px] items-center gap-6"><div className="flex shrink-0 flex-col items-start gap-1" style={{ width: w }}><T15 w={w}>{t}</T15>{d && <D14 w={w}>{d}</D14>}</div>{children}</div>;
}
function Switch({ on, set, label }: { on: boolean; set: (v: boolean) => void; label: string }) {
  return (
    <button role="switch" aria-checked={on} aria-label={label} onClick={() => set(!on)} className={cx("relative h-6 w-10 shrink-0 rounded-full p-[2px] transition-colors hover:shadow-[inset_0_0_0_1px_#8e8a97]", on ? "bg-[#15171a]" : "bg-[#d1d1d1]")}>
      <span className="block h-5 w-5 rounded-full bg-white transition-transform" style={{ transform: on ? "translateX(16px)" : "none", transitionDuration: "calc(.25s * var(--k))" }} />
    </button>
  );
}
function SBtn({ children, w, red, onClick }: { children: ReactNode; w: number; red?: boolean; onClick?: () => void }) {
  return <button onClick={onClick} className={cx("flex h-9 shrink-0 items-center justify-center rounded-[8px] border border-[#e5e3e8] bg-white px-3 py-2 text-[15px] leading-[23px] hover:bg-[#f8f7f5] focus:border-[#15171a] focus:outline-none", red ? "text-[#e45d6a]" : "text-[#15171a]")} style={{ width: w }}>{children}</button>;
}
const Card = ({ children, gap = 20, className }: { children: ReactNode; gap?: number; className?: string }) => <div className={cx("flex w-[718px] flex-col items-start rounded-[12px] border border-[#e5e3e8] bg-white p-5", className)} style={{ gap }}>{children}</div>;
const Stat = ({ l, v }: { l: string; v: string }) => <div className="flex h-20 w-[215.33px] flex-col items-start gap-2"><p className="whitespace-nowrap text-[14px] font-medium leading-[21px] text-[#8e8a97]">{l}</p><p className={cx("whitespace-nowrap text-[26px] font-bold leading-[35px] text-[#15171a]", TR)}>{v}</p></div>;
const LoginBadge = ({ n }: { n: "구글" | "카카오" | "네이버" }) => (
  <div className={cx("flex h-9 w-9 shrink-0 items-center justify-center rounded-[8px]", n === "구글" ? "bg-white shadow-[inset_0_0_0_1px_#e8ecf3]" : n === "카카오" ? "bg-[#fee500]" : "bg-[#03a94d]")}>
    {n === "구글" ? <GoogleLogo size={20} /> : n === "카카오" ? <KakaoLogo size={20} /> : <NaverLogo size={16} />}
  </div>
);

const HEAD: Record<string, { sub?: string; beta?: boolean; plug?: boolean }> = {
  "알림": { sub: "내 메모와 연결된 새 소식을 어떻게 받을지 정해요." },
  "사용량": { sub: "AI 업데이트에 쓰인 사용량을 확인해요." },
};

export function Settings() {
  const { overlay, setOverlay, settingsTab, planOpen, setPlanOpen } = useApp();
  const [tab, setTab] = useState(settingsTab);
  const [danger, setDanger] = useState<Danger | null>(null);
  const [plan, setPlan] = useState(false);
  const open = overlay === "settings";
  useEffect(() => { if (open) { setTab(settingsTab); setPlan(planOpen && settingsTab === "사용량"); if (planOpen) setPlanOpen(false); } }, [open, settingsTab]); // eslint-disable-line react-hooks/exhaustive-deps -- v2: 'PLUS 살펴보기'에서 오면 플랜 화면부터
  useEffect(() => { if (tab !== "사용량") setPlan(false); }, [tab]);
  const close = () => setOverlay(null);
  const h = plan ? { sub: "필요한 만큼 AI 업데이트와 스튜디오를 쓸 수 있게 골라요. 가격·한도는 아직 정해지지 않았어요." } : HEAD[tab] ?? {};
  return (
    <Modal open={open} onClose={close} width={1040} scrim="rgba(0,0,0,0.32)" label="설정">
      <div className="flex h-[780px] max-h-[calc(100vh-32px)] w-[1040px] items-start overflow-hidden rounded-[20px] bg-white shadow-[0px_12px_32px_-8px_rgba(28,41,64,0.08),0px_2px_8px_0px_rgba(28,41,64,0.05)]">
        <nav className="flex h-full w-[250px] shrink-0 flex-col items-start gap-5 border-r border-[#e5e3e8] bg-white px-4 py-6">
          <div className="flex h-[52px] w-[218px] items-center gap-3 px-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#f3f1ef]"><p className={cx("text-[17px] font-medium leading-[26px] text-[#15171a]", TR)}>김</p></div>
            <div className="flex w-[146px] flex-col items-start gap-1"><p className={cx("text-[17px] font-medium leading-[26px] text-[#15171a]", TR)}>김나라</p><p className="text-[14px] font-medium leading-[21px] text-[#8e8a97]">설정</p></div>
          </div>
          {S_NAV.map(([g, items]) => (
            <div key={g} className="flex w-[218px] flex-col items-start gap-1">
              <div className="flex h-[26px] w-[218px] flex-col items-start px-3"><p className="text-[14px] font-medium leading-[21px] text-[#8e8a97]">{g}</p></div>
              {items.map((it) => { const on = tab === it; return (
                <button key={it} onClick={() => setTab(it)} className={cx("flex h-[42px] w-[218px] items-center gap-3 rounded-[8px] px-3 py-2 text-left", on ? "bg-[#f3f1ef]" : "hover:bg-[#f8f7f5]")}>
                  <NavIcon n={it} c={on ? "#5E5668" : "#333333"} />
                  <span className={cx("whitespace-nowrap text-[15px]", on ? "font-bold leading-[20px] text-[#15171a]" : "leading-[21px] text-[#15171a]")}>{it}</span>
                </button>
              ); })}
            </div>
          ))}
        </nav>
        <section className="flex h-full w-[790px] shrink-0 flex-col items-start bg-white">
          <div className="flex h-[112px] w-[790px] shrink-0 items-start justify-between overflow-hidden px-9 py-7">
            <div className="flex w-[620px] flex-col items-start gap-2">
              <div className="flex h-[34px] items-center gap-2">
                {plan && <button aria-label="사용량으로 돌아가기" onClick={() => setPlan(false)} className="-ml-2 flex h-8 w-8 items-center justify-center rounded-[8px] hover:bg-[#f8f7f5]"><svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M12.5 4.5L7 10L12.5 15.5" stroke="#15171A" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg></button>}
                <p className={cx("whitespace-nowrap text-[26px] font-bold leading-[35px] text-[#15171a]", TR)}>{plan ? "플랜 살펴보기" : tab}</p>
                {h.beta && <div className="flex h-6 w-10 items-center justify-center rounded-[8px] bg-[#f8f7f5]"><p className="text-[14px] font-medium leading-[21px] text-[#8e8a97]">베타</p></div>}
                {h.plug && <svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M9 3V7M15 3V7" stroke="#15171A" strokeWidth="2" strokeLinecap="round" /><path d="M6.5 7H17.5V11C17.5 12.4587 16.9205 13.8576 15.8891 14.8891C14.8576 15.9205 13.4587 16.5 12 16.5C10.5413 16.5 9.14236 15.9205 8.11091 14.8891C7.07946 13.8576 6.5 12.4587 6.5 11V7Z" fill="#15171A" /><path d="M12 16.5V21" stroke="#15171A" strokeWidth="2" strokeLinecap="round" /></svg>}
              </div>
              {h.sub && <p className="w-[620px] text-[15px] leading-[23px] text-[#8e8a97]">{h.sub}</p>}
            </div>
            <CloseX onClick={close} />
          </div>
          <div key={tab + (plan ? "-plan" : "")} className="m-in min-h-0 w-[790px] flex-1 overflow-y-auto">
            {tab === "사용량" && plan ? <PlanView /> : <div className="flex w-[790px] flex-col items-start gap-6 px-9 py-6">
              {tab === "내 프로필" && <TabProfile danger={setDanger} />}
              {tab === "알림" && <TabNoti />}
              {tab === "데이터" && <TabData danger={setDanger} />}
              {tab === "정보" && <TabInfo />}
              {tab === "사용량" && <TabUsage onPlan={() => setPlan(true)} />}
            </div>}
          </div>
        </section>
      </div>
      <ConfirmDanger kind={danger} onClose={() => setDanger(null)} />
    </Modal>
  );
}

/* 8-3 내 프로필 */
/* 회원 탈퇴 (앱과 같이: 지워지는 것 → 떠나는 이유(선택) → 동의 체크 → 빨간 버튼 → 한 번 더 확인) */
const REASONS = ["자주 쓰지 않아요", "원하는 기능이 없어요", "사용이 어려워요", "개인정보가 걱정돼요", "기타"];
function Withdraw({ open, onClose, danger }: { open: boolean; onClose: () => void; danger: (d: Danger) => void }) {
  const { memos, journal, stocks } = useApp();
  const [why, setWhy] = useState<string[]>([]), [ok, setOk] = useState(false);
  useEffect(() => { if (open) { setWhy([]); setOk(false); } }, [open]);
  return (
    <Modal open={open} onClose={onClose} width={680} z={65} label="회원 탈퇴">
      <div data-withdraw className="flex w-[680px] flex-col gap-5 rounded-[28px] bg-white px-8 py-7">
        <div className="flex flex-col gap-1"><p className="text-[22px] font-bold leading-[31px] text-[#15171a]">탈퇴하면 되돌릴 수 없어요</p><p className="break-keep text-[17px] leading-[26px] text-[#747d8d]">계정과 함께 아래 내용이 모두 삭제돼요.</p></div>
        <div className="grid grid-cols-4 gap-2">{[["메모", memos.length], ["투자 기록", journal.length], ["내 종목", stocks.length], ["AI 연결", memos.filter((m) => m.ai).length]].map(([l, n]) => <div key={l as string} className="flex flex-col rounded-[14px] bg-[#f5f6f8] px-4 py-3"><span className="text-[14px] text-[#747d8d]">{l}</span><span className="text-[20px] font-bold text-[#15171a]">{n}개</span></div>)}</div>
        <div className="flex flex-col gap-2"><p className="text-[17px] font-bold text-[#15171a]">떠나는 이유 <span className="font-medium text-[#8b95a1]">(선택)</span></p><div className="flex flex-wrap gap-2">{REASONS.map((r) => { const on = why.includes(r); return <button key={r} aria-pressed={on} onClick={() => setWhy((w) => (on ? w.filter((x) => x !== r) : [...w, r]))} className={cx("h-10 rounded-full px-4 text-[15px] font-bold transition-colors", on ? "bg-[#15171a] text-white" : "bg-white text-[#575b63] shadow-[inset_0_0_0_1px_#e5e7eb] hover:bg-[#f9f9f9]")}>{r}</button>; })}</div></div>
        <button role="checkbox" aria-checked={ok} data-withdraw-agree onClick={() => setOk(!ok)} className="flex items-center gap-3 text-left"><span className={cx("grid h-[22px] w-[22px] shrink-0 place-items-center rounded-[6px] transition-colors", ok ? "bg-[#e45d6a]" : "shadow-[inset_0_0_0_1.6px_#c9ccd2]")}>{ok && <svg className="m-pop" width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2.5 6L4.8 8.3L9.5 3.5" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>}</span><span className="text-[17px] font-medium text-[#15171a]">안내를 모두 확인했고, 탈퇴에 동의해요</span></button>
        <div className="flex justify-end gap-2"><button onClick={onClose} className="h-12 rounded-[12px] bg-[#f2f3f4] px-5 text-[17px] font-medium text-[#15171a]">취소</button><button disabled={!ok} onClick={() => { onClose(); danger("withdraw"); }} className="h-12 rounded-[12px] px-6 text-[17px] font-medium text-white transition-colors disabled:cursor-not-allowed disabled:bg-[#c9ccd2] enabled:bg-[#e45d6a]">탈퇴하기</button></div>
      </div>
    </Modal>
  );
}
/* 연결된 로그인 줄: 시연은 Figma 문구, API 모드는 /auth/me 의 providers (계정 추가 연결 API는 아직 없음 · 분류 C) */
type LoginRow = readonly ["구글" | "카카오" | "네이버", string, boolean];
const DEMO_LOGINS: LoginRow[] = [["구글", "nara@gmail.com · 현재 로그인 중", true], ["카카오", "연결되지 않음", false], ["네이버", "연결되지 않음", false]];
function loginRows(user: UserWire | null): LoginRow[] {
  const list = Array.isArray(user?.providers) ? (user.providers as { provider?: string; email?: string | null }[]) : [];
  return ([["google", "구글"], ["kakao", "카카오"], ["naver", "네이버"]] as const).map(([p, n]) => {
    const hit = list.find((x) => x.provider === p);
    return [n, hit ? `${hit.email || "연결됨"} · 연결됨` : "연결되지 않음", !!hit] as const;
  });
}
function TabProfile({ danger }: { danger: (d: Danger) => void }) {
  const { user } = useApp();
  const [wd, setWd] = useState(false);
  const profile = useProfile(); // API 모드: 로그인한 사용자. 프로필 수정 API는 아직 없음(분류 C) — 입력은 이 화면에서만 바뀜
  const [name, setName] = useState(profile.name), [intro, setIntro] = useState(profile.sub);
  const field = (l: string, v: string, set: (s: string) => void) => (
    <div className="flex w-[351px] flex-col items-start gap-2">
      <p className="text-[14px] font-medium leading-[21px] text-[#8e8a97]">{l}</p>
      <input value={v} onChange={(e) => set(e.target.value)} aria-label={l} className="h-[42px] w-[351px] rounded-[8px] border border-[#e5e3e8] bg-white px-3 py-[10px] text-[15px] leading-[23px] text-[#15171a] outline-none focus:border-[#15171a]" />
    </div>
  );
  return (<>
    <div className="flex h-[72px] w-[718px] items-center gap-5">
      <div className="flex h-[72px] w-[72px] items-center justify-center rounded-full bg-[#f3f1ef]"><p className={cx("text-[26px] font-bold leading-[35px] text-[#15171a]", TR)}>{profile.name.slice(0, 1)}</p></div>
      <div className="flex w-[300px] flex-col items-start gap-3"><T15>프로필 사진</T15><div className="flex h-9 w-[300px] items-start gap-2"><SBtn w={94}>사진 변경</SBtn><SBtn w={64}>삭제</SBtn></div></div>
    </div>
    <div className="flex items-start gap-4">{field("이름", name, setName)}{field("한 줄 소개", intro, setIntro)}</div>
    <div className="flex w-[718px] flex-col items-start gap-5">
      <H16>연결된 로그인</H16>
      <D14 w={718}>연결한 계정으로 MEMO'S에 로그인할 수 있어요.</D14>
      <Card>
        {(API_MODE ? loginRows(user) : DEMO_LOGINS).map(([n, d, on], i) => (
          <div key={n} className="contents">
            {i > 0 && <Hr />}
            <div className="flex h-12 w-[678px] items-center gap-3">
              <LoginBadge n={n} />
              <div className="flex w-[534px] flex-col items-start gap-1"><T15>{n}</T15><p className="whitespace-nowrap text-[14px] font-medium leading-[21px] text-[#8e8a97]">{d}</p></div>
              {on ? <p className="whitespace-nowrap text-[14px] font-medium leading-[21px] text-[#15171a]">사용 중</p> : <SBtn w={80}>연결</SBtn>}
            </div>
          </div>
        ))}
      </Card>
    </div>
    <Hr />
    <Row t="로그아웃" d="이 기기에서 로그아웃해요." w={598}><SBtn w={96} onClick={() => danger("logout")}>로그아웃</SBtn></Row>
    <Card>
      <div className="flex w-[678px] items-center gap-6">
        <div className="flex w-[554px] flex-col items-start gap-1"><T15 w={554}>회원 탈퇴</T15><D14 w={554}>탈퇴하면 모든 메모와 기록이 삭제되며 되돌릴 수 없어요.</D14></div>
        <SBtn w={100} red onClick={() => setWd(true)}>회원 탈퇴</SBtn>
      </div>
    </Card>
  <Withdraw open={wd} onClose={() => setWd(false)} danger={danger} />
  </>);
}

/* 8-4 알림 (11.13: 업데이트 알림 + 스튜디오 알림만) */
function TabNoti() {
  const { x, setX } = useApp();
  const snack = useSnack();
  const key = (k: string) => (k === "업데이트" ? "upd" : "studio") as "upd" | "studio";
  const S = (k: string, l: string) => <Switch on={x.noti[key(k)]} set={(v) => { setX((y) => ({ ...y, noti: { ...y.noti, [key(k)]: v } })); snack(v ? "알림을 켰어요 · 알림함에 다시 보여요" : "알림을 껐어요 · 알림함에서도 안 보여요", { check: true }); }} label={l} />;
  return (
    <div className="flex w-[718px] flex-col items-start gap-5">
      <H16>받을 알림</H16>
      <Row t="업데이트 알림" d="내 메모에 새 소식이 도착하면 알려줘요." w={654}>{S("업데이트", "업데이트 알림")}</Row>
      <Hr />
      <Row t="스튜디오 알림" d="스튜디오에서 만든 항목이 완성되면 알려줘요." w={654}>{S("스튜디오", "스튜디오 알림")}</Row>
      <p className="w-[718px] break-keep text-[14px] leading-[21px] text-[#8e8a97]">여기서 켠 알림만 사이드바 종(알림함)에 쌓여요. 알림을 꺼 두면 휴대폰 알림도 오지 않아요.</p>
    </div>
  );
}

/* 8-6 데이터 */
function TabData({ danger }: { danger: (d: Danger) => void }) {
  const { memos, journal, stocks } = useApp();
  return (<>
    <Card><div className="flex h-20 w-[678px] items-start gap-4"><Stat l="메모" v={`${memos.length}개`} /><Stat l="투자 기록" v={`${journal.length}개`} /><Stat l="종목" v={`${stocks.length}개`} /></div></Card>
    <Card>
      <p className={cx("whitespace-nowrap text-[17px] font-medium leading-[26px] text-[#e45d6a]", TR)}>위험 구역</p>
      <div className="flex w-[678px] items-center gap-6">
        <div className="flex w-[554px] flex-col items-start gap-1"><T15 w={554}>모든 데이터 삭제</T15><D14 w={554}>모든 메모, 기록, 종목이 영구 삭제돼요. 되돌릴 수 없어요.</D14></div>
        <SBtn w={100} red onClick={() => danger("wipe")}>전체 삭제</SBtn>
      </div>
    </Card>
  </>);
}

/* 8-7 정보 */
function TabInfo() {
  const { setOverlay, setCoach, setCoachPending } = useApp();
  const replay = () => { setOverlay(null); setCoachPending(false); window.setTimeout(() => setCoach({ step: -1 }), 320); }; // v2: 사용법 다시 보기
  const [doc, setDoc] = useState<null | "terms" | "privacy" | "invest">(null);
  return (<>
    <Row t="버전" d="MEMO'S v0.1.0 (베타)" w={558}><div className="flex h-7 w-[136px] items-center"><p className="whitespace-nowrap text-[14px] font-medium leading-[21px] text-[#8e8a97]">최신 버전이에요</p></div></Row>
    <Hr />
    <div className="flex w-[718px] flex-col items-start">
      {["사용법 다시 보기", "이용약관", "개인정보 처리방침", "오픈소스 라이선스", "피드백 보내기", "문의하기"].map((t) => (
        <div key={t} className="contents">
          <button onClick={t === "피드백 보내기" ? () => setOverlay("feedback") : t === "사용법 다시 보기" ? replay : t === "이용약관" ? () => setDoc("terms") : t === "개인정보 처리방침" ? () => setDoc("privacy") : undefined} className="-mx-3 flex h-[52px] w-[742px] items-center justify-between rounded-[8px] px-3 hover:bg-[#f8f7f5]">
            <span className="whitespace-nowrap text-[15px] leading-[23px] text-[#15171a]">{t}</span><Chev dir="right" />
          </button>
          <Hr />
        </div>
      ))}
    </div>
    <div className="flex w-[718px] flex-col items-start gap-5">
      <H16>데이터 출처</H16>
      <p className="w-[718px] whitespace-pre text-[15px] leading-[23px] text-[#8e8a97]">공시 · DART   뉴스 · 서울경제, 매일경제, 한국경제, 연합뉴스   주가 · KIS, KRX, ECOS, FRED</p>
    </div>
    <div className="flex w-[718px] flex-col items-start gap-1 rounded-[12px] bg-[#f8f7f5] p-4"><p className="w-[686px] text-[15px] leading-[23px] text-[#8e8a97]">MEMO'S는 투자 권유를 하지 않으며, 제공되는 모든 정보는 참고용이에요. 투자 판단과 그 결과에 대한 책임은 투자자 본인에게 있어요.</p></div>
    <p className="w-[718px] text-[14px] font-medium leading-[21px] text-[#8e8a97]">SIG · Saram Is Good</p>
    <Modal open={!!doc} onClose={() => setDoc(null)} width={680} z={70} label={doc ? LEGAL[doc].t : "문서"}>
      <div className="flex w-[680px] flex-col gap-4 rounded-[28px] bg-white px-8 py-7">
        <div className="flex items-center justify-between"><p className="text-[22px] font-bold leading-[31px] text-[#15171a]">{doc ? LEGAL[doc].t : ""}</p><CloseX onClick={() => setDoc(null)} /></div>
        <div className="legal max-h-[min(560px,calc(100vh-200px))] overflow-y-auto pr-2" dangerouslySetInnerHTML={{ __html: doc ? LEGAL[doc].h : "" }} />
      </div>
    </Modal>
  </>);
}

/* 8-8 사용량 — 앱 'MY · 사용량'처럼 (11.13 오후) */
const CHK = "#15171a";
const Chip = ({ children, dark }: { children: ReactNode; dark?: boolean }) => <span className={cx("flex h-6 items-center rounded-[6px] px-2 text-[14px] font-medium leading-[21px]", dark ? "bg-[#efefef] text-[#15171a]" : "bg-[#f3f4f6] text-[#6b6f78]")}>{children}</span>;
function TabUsage({ onPlan }: { onPlan: () => void }) {
  const { memos, setOverlay, go, setMemoOpen } = useApp();
  const pct = useUsage();
  const [open, setOpen] = useState<string | null>(null);
  const tracked = (code: string) => memos.filter((m) => m.code === code && m.ai).map((m) => ({ t: m.title, id: m.id as number | null, k: m.tracks }));
  const rows: [string, string, { t: string; id: number | null; k?: string }[]][] = [
    ["SK하이닉스", "000660", tracked("000660")],
    ["삼성전자", "005930", [{ t: "HBM 실적 변화", id: null, k: "뉴스 · HBM 공급 동향" }, { t: "파운드리 신규 수주", id: null, k: "뉴스 · 파운드리" }]],
    ["NAVER", "035420", tracked("035420")],
  ];
  const total = rows.reduce((a, r) => a + r[2].length, 0);
  const openMemo = (code: string, id: number | null) => { setOverlay(null); go({ name: "stock", code, tab: "board" }); if (id != null) setMemoOpen(id); };
  return (<>
    <Card gap={0} className="!p-6">
      <div className="flex h-6 w-[670px] items-center justify-between"><div className="flex items-center gap-2"><p className={cx("text-[17px] font-bold leading-[26px] text-[#15171a]", TR)}>무료 플랜</p><Chip>가정</Chip></div><Chip>예시 데이터</Chip></div>
      <p className={cx("mt-4 whitespace-nowrap text-[36px] font-bold leading-[40px] text-[#15171a]", "tracking-[-0.02em]")}>{pct}% 사용</p>
      <div className="mt-5 flex h-2 w-[670px] items-start rounded-full bg-[#eceef1]"><div className="h-2 rounded-full transition-[width]" style={{ width: (pct / 100) * 670, background: pct >= 100 ? "#e5484d" : "#15171a", transitionDuration: "calc(.6s * var(--k))" }} /></div>
      <div className="mt-3 flex h-[22px] w-[670px] items-center justify-between"><p className="text-[15px] leading-[23px] text-[#575b63]">남은 사용량 {100 - pct}%</p><p className="text-[15px] leading-[23px] text-[#8e8a97]">다음 갱신 11.30</p></div>
    </Card>
    {pct >= 90 && <div data-usage-warn className={cx("flex w-[718px] flex-col gap-1 rounded-[16px] px-5 py-4", pct >= 100 ? "bg-[#fdf0f1]" : "bg-[#fff4e5]")}><p className={cx("text-[17px] font-bold leading-[26px]", pct >= 100 ? "text-[#c0392b]" : "text-[#7a4a00]")}>{pct >= 100 ? "AI 업데이트가 일시 중단되었어요" : "사용량이 거의 다 찼어요"}</p><p className={cx("text-[15px] leading-[23px]", pct >= 100 ? "text-[#a8433a]" : "text-[#8a5a00]")}>{pct >= 100 ? "사용량을 모두 썼어요. 메모 작성과 기존 기록 확인은 그대로 할 수 있어요." : `이번 기간 사용량의 ${pct}%를 썼어요. 11.30에 다시 채워져요.`}</p></div>}
    <div className="flex w-[718px] flex-col items-start gap-3">
      <div className="flex h-5 w-[718px] items-center justify-between px-1"><p className="text-[15px] leading-[23px] text-[#8e8a97]">종목별 추적 현황</p><p className="text-[15px] leading-[23px] text-[#8e8a97]">추적 항목 {total}개</p></div>
      <div className="flex w-[718px] flex-col items-start overflow-hidden rounded-[16px] border border-[#e5e3e8] bg-white">
        {rows.map(([n, code, items], i) => { const on = open === n; return (
          <div key={n} className={cx("flex w-full flex-col items-start bg-white", i < rows.length - 1 && "border-b border-[#efeff2]")}>
            <button onClick={() => setOpen(on ? null : n)} aria-expanded={on} className={cx("flex h-[72px] w-full items-center gap-3 px-6", on ? "bg-[#f8f7f5]" : "hover:bg-[#f8f7f5]")}>
              <SLogo code={code} size={32} r={8} />
              <span className={cx("min-w-0 flex-1 text-left text-[17px] font-bold leading-[26px] text-[#15171a]", TR)}>{n}</span>
              <span className="whitespace-nowrap text-[15px] leading-[23px] text-[#8e8a97]">{items.length}개 추적 중</span><Chev dir={on ? "up" : "down"} />
            </button>
            <div className={cx("grid w-full transition-[grid-template-rows]", on ? "grid-rows-[1fr]" : "grid-rows-[0fr]")} style={{ transitionDuration: "calc(.3s * var(--k))" }}>
              <div className="overflow-hidden">
                <div className="flex w-full flex-col items-start px-6 pb-3 pt-1">
                  {items.map((t) => (
                    <button key={t.t} onClick={() => openMemo(code, t.id)} className="flex min-h-[52px] w-full items-center justify-between gap-3 rounded-[8px] py-1 pl-11 pr-2 text-left hover:bg-[#f8f7f5]">
                      <span className="flex min-w-0 flex-col"><span className="truncate whitespace-nowrap text-[17px] leading-[26px] text-[#15171a]">{t.t}</span>{t.k && <span className="truncate text-[14px] leading-[21px] text-[#8e8a97]">{t.k}</span>}</span>
                      <span className="flex shrink-0 items-center gap-[6px]"><span className={cx("h-[5px] w-[5px] rounded-full", pct >= 100 ? "bg-[#c9ccd2]" : "bg-[#15171a]")} /><span className="whitespace-nowrap text-[14px] font-medium leading-[21px] text-[#8e8a97]">{pct >= 100 ? "추적 일시 중단" : "추적 중"}</span><Chev dir="right" /></span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        ); })}
      </div>
      <p className="w-[718px] px-1 text-[14px] leading-[21px] text-[#8e8a97]">AI 연결을 켠 메모만 분석하고, 연결하지 않은 메모는 분석하지 않아요. 항목을 누르면 그 메모가 열려요.</p>
    </div>
    <button onClick={onPlan} className="flex h-[84px] w-[718px] items-center justify-between rounded-[16px] border border-[#e5e3e8] bg-white px-6 text-left hover:bg-[#f8f7f5]">
      <span className="flex flex-col gap-1"><span className={cx("text-[17px] font-bold leading-[26px] text-[#15171a]", TR)}>플랜 살펴보기</span><span className="text-[15px] leading-[23px] text-[#8e8a97]">무료 · PLUS · PRO 비교</span></span>
      <Chev dir="right" />
    </button>
    <p className="w-[718px] px-1 text-[14px] leading-[21px] text-[#8e8a97]">메모 작성과 기존 기록 확인은 사용량과 관계없이 이용할 수 있어요.</p>
  </>);
}

/* 플랜 살펴보기 — 앱 화면 그대로 (보라 → 검정) */
const PLANS = [
  { k: "무료", price: "0원", tag: "현재 플랜", f: ["메모·투자 기록 무제한", "AI 업데이트 · 기본 사용량", "스튜디오 크레딧 · 매달 기본 제공"] },
  { k: "PLUS", price: "[가격]", tag: "추천", f: ["무료 플랜의 모든 기능", "AI 업데이트 · 더 많은 사용량", "스튜디오 크레딧 · 매달 더 많이"] },
  { k: "PRO", price: "[가격]", tag: "", f: ["PLUS의 모든 기능", "AI 업데이트 · 가장 많은 사용량", "스튜디오 크레딧 · 매달 가장 많이"] },
];
const Tick = () => <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="shrink-0"><path d="M3 8.4L6.4 11.6L13 4.8" stroke={CHK} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>;
function PlanView() {
  const snack = useSnack();
  const [per, setPer] = useState<"월간" | "연간">("월간"), [pick, setPick] = useState("PLUS");
  const unit = per === "월간" ? "/ 월" : "/ 년";
  const CMP: [string, ReactNode[]][] = [["메모·투자 기록", [<Tick key={1} />, <Tick key={2} />, <Tick key={3} />]], ["AI 업데이트 사용량", ["기본", "[미정]", "[미정]"]], ["스튜디오 크레딧(월)", ["[미정]", "[미정]", "[미정]"]], ["추가 크레딧 충전", [<Tick key={1} />, <Tick key={2} />, <Tick key={3} />]]];
  return (
    <div className="flex min-h-full w-[790px] flex-col items-start">
      <div className="flex w-[790px] flex-col items-center gap-5 px-9 pb-6 pt-6">
        <div className="relative flex h-12 w-[316px] shrink-0 items-center rounded-[14px] bg-[#eceef1] p-1">
          <span className="absolute left-1 top-1 h-10 w-[154px] rounded-[11px] bg-white shadow-[0_1px_3px_rgba(0,0,0,0.08)] transition-transform" style={{ transform: per === "연간" ? "translateX(154px)" : "none", transitionDuration: "calc(.3s * var(--k))" }} />
          {(["월간", "연간"] as const).map((p) => <button key={p} onClick={() => setPer(p)} aria-pressed={per === p} className={cx("relative z-[1] h-10 flex-1 text-[17px] leading-[26px]", per === p ? "font-bold text-[#15171a]" : "text-[#6b6f78]")}>{p}</button>)}
        </div>
        {PLANS.map((p) => { const on = pick === p.k; return (
          <button key={p.k} onClick={() => setPick(p.k)} aria-pressed={on} className={cx("relative flex w-[718px] flex-col items-start gap-3 rounded-[20px] bg-white px-6 py-6 text-left transition-shadow", on ? "shadow-[inset_0_0_0_2px_#15171a]" : "shadow-[inset_0_0_0_1px_#e5e3e8] hover:shadow-[inset_0_0_0_1px_#c9ccd2]")}>
            <span className="flex items-center gap-2"><span className={cx("text-[20px] font-bold leading-[29px] text-[#15171a]", TR)}>{p.k}</span>{p.tag && <Chip dark={p.tag === "추천"}>{p.tag}</Chip>}</span>
            <span className="flex items-baseline gap-2"><span className={cx("text-[26px] font-bold leading-[35px] text-[#15171a]", TR)}>{p.price}</span><span className="text-[15px] leading-[23px] text-[#8e8a97]">{unit}</span></span>
            <span className="flex flex-col gap-2">{p.f.map((f) => <span key={f} className="flex items-center gap-2"><Tick /><span className="text-[17px] leading-[26px] text-[#33363d]">{f}</span></span>)}</span>
            <span className="absolute right-6 top-6">{on
              ? <svg width="28" height="28" viewBox="0 0 28 28" fill="none"><circle cx="14" cy="14" r="13" fill="#15171a" /><circle cx="14" cy="14" r="5" fill="white" /></svg>
              : <svg width="28" height="28" viewBox="0 0 28 28" fill="none"><circle cx="14" cy="14" r="12.2" stroke="#c9ccd2" strokeWidth="1.6" /></svg>}</span>
          </button>
        ); })}
        <div className="flex w-[718px] flex-col items-start gap-3">
          <p className="px-1 text-[15px] leading-[23px] text-[#8e8a97]">한눈에 비교</p>
          <div className="flex w-[718px] flex-col items-start rounded-[20px] border border-[#e5e3e8] bg-white px-6 py-2">
            <div className="flex h-12 w-full items-center border-b border-[#efeff2]"><span className="w-[250px]" />{["무료", "PLUS", "PRO"].map((h) => <span key={h} className="flex-1 text-center text-[17px] font-bold leading-[26px] text-[#15171a]">{h}</span>)}</div>
            {CMP.map(([l, v], i) => (
              <div key={l} className={cx("flex h-[52px] w-full items-center", i < CMP.length - 1 && "border-b border-[#efeff2]")}>
                <span className="w-[250px] text-[15px] leading-[23px] text-[#575b63]">{l}</span>
                {v.map((x, k) => <span key={k} className="flex flex-1 justify-center text-[15px] leading-[23px] text-[#15171a]">{x}</span>)}
              </div>
            ))}
          </div>
          <div className="flex flex-col gap-1 px-1">{["가격·사용량·크레딧은 팀 확정 전 자리표시예요.", "언제든 해지할 수 있고, 해지해도 쓴 기간까지는 그대로 써요.", "투자 권유·수익 보장 기능은 어떤 플랜에도 없어요."].map((t) => <p key={t} className="text-[14px] leading-[21px] text-[#8e8a97]">· {t}</p>)}</div>
        </div>
      </div>
      <div className="sticky bottom-0 mt-auto flex w-[790px] flex-col items-center gap-2 bg-gradient-to-t from-white from-70% to-white/0 px-9 pb-5 pt-6">
        <button disabled={pick === "무료"} onClick={() => snack("결제는 아직 연동 전이에요")} className={cx("flex h-[52px] w-[718px] items-center justify-center rounded-[14px] text-[17px] font-bold leading-[26px] text-white", pick === "무료" ? "cursor-not-allowed bg-[#c9ccd2]" : "bg-[#15171a] hover:bg-[#2a2c30]")}>{pick === "무료" ? "현재 플랜" : `${pick} 시작하기`}</button>
        <p className="text-[14px] leading-[21px] text-[#8e8a97]">결제는 스토어 결제 창에서 진행돼요 (연동 전)</p>
      </div>
    </div>
  );
}

/* ================= 9 · 피드백 / 9.1 · 오류 신고 ================= */
const STAR = "M16 3L20 11.4L29 12.6L22.4 18.8L24 27.8L16 23.4L8 27.8L9.6 18.8L3 12.6L12 11.4L16 3Z";
const KINDS = [["기능 작동 오류", 148], ["화면·표시 오류", 148], ["데이터·연결 오류", 148], ["속도·접속 문제", 140], ["기타", 72]] as const;
export function Feedback() {
  const { overlay, setOverlay } = useApp();
  const snack = useSnack();
  const [tab, setTab] = useState<"g" | "b">("g"), [star, setStar] = useState(0), [hov, setHov] = useState(0);
  const [txt, setTxt] = useState(""), [txt2, setTxt2] = useState(""), [where, setWhere] = useState(""), [kinds, setKinds] = useState<string[]>([]);
  const open = overlay === "feedback";
  useEffect(() => { if (open) { setTab("g"); setStar(0); setHov(0); setTxt(""); setTxt2(""); setWhere(""); setKinds([]); } }, [open]);
  const close = () => setOverlay(null);
  const send = () => { close(); snack(tab === "g" ? "피드백을 보냈어요" : "오류 신고를 보냈어요"); };
  const L = ({ children }: { children: ReactNode }) => <p className={cx("whitespace-nowrap text-[15px] font-medium leading-[23px] text-[#15171a]", TR)}>{children}</p>;
  const Note = ({ n }: { n: number }) => (
    <div className="flex w-full items-start justify-between"><p className="text-[13px] font-medium leading-[20px] text-[#747d8d]">개인정보는 입력하지 말아 주세요.</p><p className="text-[13px] font-medium leading-[20px] text-[#747d8d]">{n} / 500</p></div>
  );
  const area = "w-full resize-none rounded-[12px] border border-[#e8ecf3] bg-[#fafbfc] p-4 text-[14px] leading-[21px] text-[#15171a] outline-none placeholder:text-[#747d8d]";
  return (
    <Modal open={open} onClose={close} width={680} label="피드백 보내기">
      <div className={cx("relative flex w-[680px] flex-col items-start overflow-hidden rounded-[28px] border border-[#e8ecf3] bg-white px-8 py-[31px] shadow-[0px_24px_56px_-16px_rgba(20,23,28,0.16)]", tab === "g" ? "gap-6" : "gap-4")}>
        <div className="flex w-full flex-col items-start gap-2">
          <p className={cx("text-[26px] font-bold leading-[35px] text-[#15171a]", TR)}>{tab === "g" ? "피드백 보내기" : "오류 신고"}</p>
          <p className="w-[616px] text-[14px] leading-[21px] text-[#747d8d]">{tab === "g" ? <>MEMO’S(메모스)를 사용하며 느낀 점을 알려주세요.<br />소중한 의견을 모아 더 좋은 서비스를 만들겠습니다.</> : <>서비스 이용 중 발생한 문제를 알려주세요.<br />남겨주신 내용을 확인하고 개선하겠습니다.</>}</p>
        </div>
        <p aria-hidden className={cx("pointer-events-none absolute left-[574px] top-[-2px] w-[65px] whitespace-nowrap text-[112px] font-bold leading-[112px] text-[#15171a] opacity-[0.18]", TR)}>“</p>
        <div className="flex h-12 w-full items-start gap-1 rounded-[12px] bg-[#f2f3f4] p-1">
          {([["g", "일반 피드백"], ["b", "오류 신고"]] as const).map(([k, l]) => <button key={k} onClick={() => setTab(k)} className={cx("flex flex-1 items-center justify-center self-stretch rounded-[12px] text-[15px] font-medium leading-[23px] transition-colors", TR, tab === k ? "bg-white text-[#15171a]" : "text-[#747d8d] hover:text-[#15171a]")}>{l}</button>)}
        </div>
        {tab === "g" ? (<>
          <div className="flex w-full flex-col items-center gap-2">
            <L>얼마나 만족하셨나요?</L>
            <div className="flex h-[78px] w-full flex-col items-center justify-center gap-2">
              <div className="flex items-start gap-2" onMouseLeave={() => setHov(0)}>
                {[1, 2, 3, 4, 5].map((n) => (
                  <button key={n} aria-label={`${n}점`} onMouseEnter={() => setHov(n)} onClick={() => setStar(n)} className="m-press flex h-11 w-11 items-center justify-center">
                    <svg width="32" height="32" viewBox="0 0 32 32" fill="none"><path d={STAR} fill={(hov || star) >= n ? "#15171A" : "#E8ECF3"} style={{ transition: "fill calc(.15s * var(--k))" }} /></svg>
                  </button>
                ))}
              </div>
              <p className="whitespace-nowrap text-[14px] leading-[21px] text-[#747d8d]">별점을 선택해 주세요</p>
            </div>
          </div>
          <div className="flex w-full flex-col items-start gap-2">
            <L>피드백 내용</L>
            <textarea value={txt} onChange={(e) => setTxt(e.target.value.slice(0, 500))} placeholder={"좋았던 점이나 개선이 필요한 점을\n자유롭게 작성해 주세요."} className={cx(area, "h-[156px]")} />
            <Note n={txt.length} />
          </div>
        </>) : (<>
          <div className="flex w-full flex-col items-start gap-2">
            <L>문제가 발생한 화면·기능 (선택)</L>
            <input value={where} onChange={(e) => setWhere(e.target.value)} placeholder="예: 로그인, 투자 기록, 최신 업데이트" className="h-11 w-full rounded-[12px] border border-[#e8ecf3] bg-[#fafbfc] px-4 text-[14px] leading-[21px] text-[#15171a] outline-none placeholder:text-[#747d8d]" />
            <p className="text-[13px] font-medium leading-[20px] text-[#747d8d]">문제가 발생한 위치를 알면 더 빠르게 확인할 수 있어요.</p>
          </div>
          <div className="flex w-full flex-col items-start gap-2">
            <L>신고 유형 · 복수 선택 가능</L>
            {[KINDS.slice(0, 2), KINDS.slice(2)].map((row, ri) => (
              <div key={ri} className="flex items-start gap-2">
                {row.map(([k, w]) => { const on = kinds.includes(k); return (
                  <button key={k} aria-pressed={on} onClick={() => setKinds((a) => on ? a.filter((x) => x !== k) : [...a, k])} className={cx("flex h-9 items-center justify-center rounded-full border px-3 text-[14px] leading-[21px] transition-colors", on ? "border-[#15171a] bg-[#15171a] text-white" : "border-[#e8ecf3] bg-white text-[#15171a] hover:bg-[#fafbfc]")} style={{ width: w }}>{k}</button>
                ); })}
              </div>
            ))}
          </div>
          <div className="flex w-full flex-col items-start gap-2">
            <L>상세 내용</L>
            <textarea value={txt2} onChange={(e) => setTxt2(e.target.value.slice(0, 500))} placeholder={"어떤 작업 중에 문제가 발생했나요?\n발생 상황과 기대했던 동작을 알려주세요."} className={cx(area, "h-[120px]")} />
            <Note n={txt2.length} />
          </div>
        </>)}
        <div className="flex h-12 w-full items-start justify-end gap-2">
          <button onClick={close} className={cx("flex h-12 w-[104px] items-center justify-center rounded-[12px] bg-[#f2f3f4] text-[15px] font-medium leading-[23px] text-[#15171a]", TR)}>취소</button>
          <button onClick={send} className={cx("flex h-12 w-[136px] items-center justify-center rounded-[12px] bg-[#14171c] text-[15px] font-medium leading-[23px] text-white", TR)}>보내기</button>
        </div>
      </div>
    </Modal>
  );
}

/* ================= 10 · 휴지통 · 최종 수정본 (440,170 · 560×560) ================= */
const TICON: Record<string, ReactNode> = {
  memo: <><path d="M4.39984 14.1768L3.6665 18.3324L7.82206 17.599L18.0887 7.33238L14.6665 3.91016L4.39984 14.1768Z" /><path d="M12.7109 5.86719L16.1332 9.28941" /></>,
  journal: <><path d="M13.4442 2.44531H4.88867V19.5564H17.722V6.72309L13.4442 2.44531Z" /><path d="M13.4443 2.44531V6.72309H17.7221" /><path d="M7.94434 11.6094H14.6666" /><path d="M7.94434 15.2773H14.6666" /></>,
  stock: <><path d="M18.9446 7.33203H3.05566V18.332H18.9446V7.33203Z" /><path d="M7.94434 7.33507V4.89062H14.0554V7.33507" /><path d="M3.05566 12.2227H18.9446" /></>,
};
/* 툴팁은 목록 스크롤 칸에 잘리지 않도록 body에 띄움 (11.13) */
function TipBtn({ tip, danger, onClick, children }: { tip: string; danger?: boolean; onClick: () => void; children: (c: string) => ReactNode }) {
  const [h, setH] = useState(false);
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);
  const ref = useRef<HTMLButtonElement>(null);
  const show = () => { const r = ref.current?.getBoundingClientRect(); if (r) setPos({ x: r.left + r.width / 2, y: r.top }); setH(true); };
  const hide = () => setH(false);
  return (
    <button ref={ref} aria-label={tip} onClick={() => { hide(); onClick(); }} onMouseEnter={show} onMouseLeave={hide} onFocus={show} onBlur={hide}
      className={cx("relative flex h-10 w-10 shrink-0 items-center justify-center rounded-[8px] focus-visible:shadow-[inset_0_0_0_1.5px_#15171a] focus-visible:outline-none", h && (danger ? "bg-[#fbefef]" : "bg-[#f8f7f5]"))}>
      {children(h && danger ? "#E45D6A" : "#333333")}
      {h && pos && createPortal(<span className="pointer-events-none fixed z-[100] flex -translate-x-1/2 whitespace-nowrap rounded-[6px] bg-[#111] px-2 py-[5px] text-[13px] font-medium leading-[20px] text-white" style={{ left: pos.x, top: pos.y - 34 }}>{tip}</span>, document.body)}
    </button>
  );
}
const TYPES = ["전체", "메모", "투자 기록", "종목"];
export function Trash() {
  const { overlay, setOverlay, trash, setTrash, setMemos, setJournal, setStocks, stocks } = useApp();
  const snack = useSnack();
  const [q, setQ] = useState(""), [type, setType] = useState<string | null>(null), [menu, setMenu] = useState(false), [gone, setGone] = useState<string | null>(null);
  const fref = useRef<HTMLDivElement>(null);
  const open = overlay === "trash";
  useEffect(() => { if (open) { setQ(""); setType(null); setMenu(false); } }, [open]);
  useEffect(() => { if (!menu) return; const f = (e: MouseEvent) => { if (!fref.current?.contains(e.target as Node)) setMenu(false); }; document.addEventListener("mousedown", f); return () => document.removeEventListener("mousedown", f); }, [menu]);
  const t0 = type ?? "전체";
  const list = trash.filter((t) => (t0 === "전체" || t.type === t0) && (!q.trim() || t.t.includes(q.trim()) || t.s.includes(q.trim())));
  const restore = async (t: (typeof trash)[number]) => {
    /* API 모드: 이 기기에서 지운 원래 메모·종목을 다시 저장한다 (서버에 복원 API가 없어 새로 저장 · 분류 B). 예시 항목은 없음 */
    if (API_MODE) {
      if (!t.memo && !t.stock) { snack("이 항목은 아직 복원할 수 없어요"); return; }
      setGone(t.t); await sleep(280); setTrash((a) => a.filter((x) => x !== t)); setGone(null);
      if (t.stock) { const st = t.stock; setStocks((a) => (a.some((s) => s.code === st.code) ? a : [...a, st])); }
      if (t.memo) { const m = t.memo; setMemos((a) => (a.some((x) => x.id === m.id) ? a : [...a, m])); }
      snack("복원했어요");
      return;
    }
    setGone(t.t); await sleep(280); setTrash((a) => a.filter((x) => x.t !== t.t)); setGone(null);
    if (t.type === "메모") setMemos((a) => a.some((m) => m.title === t.t) ? a : [...a, { id: Date.now(), code: "000660", date: "10.20", title: t.t, body: "", color: "yellow", ai: false, pinned: false, badge: 0, col: 0 }]);
    if (t.type === "투자 기록") setJournal((a) => a.some((j) => j.title === t.t) ? a : [...a, { id: Date.now(), title: t.t, date: "10월 8일", full: "2026년 10월 8일 오후 9:02", body: ["발표일 확인하고 체크리스트 정리.", "컨센서스 대비 가이던스 문구를 꼭 볼 것."], todo: [] }]);
    const back = ALL_STOCKS.find((s) => s.name === t.t);
    if (t.type === "종목" && back && !stocks.some((s) => s.code === back.code)) setStocks((a) => [...a, back]);
    else if (t.type === "종목" && !stocks.some((s) => s.name === t.t)) setStocks((a) => [...a, { code: "005380", name: t.t, short: "H", logo: "H", logoBg: "#002c5f", hold: "관심", market: "KOSPI", price: 214500, chg: -1500, pct: -0.69, seed: 21 }]);
    snack("복원했어요");
  };
  const [ask, setAsk] = useState<(typeof trash)[number] | null>(null);
  const [askAll, setAskAll] = useState(false);
  const kill = async (t: (typeof trash)[number]) => {
    setGone(t.t); await sleep(280); setTrash((a) => a.filter((x) => x.t !== t.t)); setGone(null);
    snack(API_MODE ? "휴지통 목록에서 지웠어요" : "영구 삭제했어요"); // API 모드: 서버에는 영구 삭제 API가 없음 (분류 C)
  };
  const sp = { strokeWidth: 1.95556, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  return (
    <Modal open={open} onClose={() => setOverlay(null)} width={680} scrim="rgba(0,0,0,0.32)" label="휴지통">
      <div className="flex h-[660px] max-h-[calc(100vh-32px)] w-[680px] flex-col items-start gap-4 rounded-[20px] border border-[#e8eaed] bg-white p-[23px] shadow-[0px_12px_32px_-8px_rgba(28,41,64,0.08),0px_2px_8px_0px_rgba(28,41,64,0.05)]">
        <div className="flex h-[56px] w-[634px] shrink-0 items-center gap-4">
          <div className="flex h-[56px] min-w-0 flex-1 flex-col items-start gap-1">
            <p className="whitespace-nowrap text-[22px] font-bold leading-[31px] text-[#15171a]">휴지통</p>
            <p className="whitespace-nowrap text-[17px] leading-[26px] text-[#747d8d]">삭제한 항목을 확인하고 복원할 수 있어요.</p>
          </div>
          <CloseX onClick={() => setOverlay(null)} />
        </div>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="휴지통에서 항목 검색" aria-label="휴지통에서 항목 검색"
          className="h-12 w-full shrink-0 rounded-[12px] border border-transparent bg-[#f8f7f5] px-4 text-[17px] leading-[26px] text-[#15171a] outline-none placeholder:text-[#747d8d] hover:border-[#e8eaed] focus:border-[1.5px] focus:border-[#15171a] focus:px-[15.5px]" />
        <div ref={fref} className="relative flex h-9 w-[634px] shrink-0 items-center gap-2">
          <button onClick={() => setMenu(!menu)} aria-expanded={menu} className={cx("flex h-9 items-center gap-2 rounded-[8px]", menu ? "bg-white pl-[14px] pr-[13px] shadow-[inset_0_0_0_1.5px_#15171a]" : "bg-white px-[13px] shadow-[inset_0_0_0_1px_#e8eaed] hover:bg-[#f6f6f6]")}>
            <span className="whitespace-nowrap text-[15px] font-medium leading-[23px] text-[#333]">{type ?? "유형"}</span>
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M3.11133 5.44531L7.00022 9.3342L10.8891 5.44531" stroke="#333333" strokeWidth="1.24444" strokeLinecap="round" strokeLinejoin="round" /></svg>
          </button>
          <div role="listbox" className={cx("m-drop absolute left-0 top-11 z-20 flex w-[180px] flex-col items-start rounded-[12px] border border-[#e8eaed] bg-white p-2 shadow-[0px_12px_32px_-8px_rgba(28,41,64,0.08),0px_2px_8px_0px_rgba(28,41,64,0.05)]", menu && "on")}>
            {TYPES.map((t) => { const on = t === t0; return (
              <button key={t} role="option" aria-selected={on} onClick={() => { setType(t); setMenu(false); }} className={cx("flex h-10 w-full items-center gap-2 rounded-[8px] px-3 py-2 text-left", on ? "bg-[#f8f7f5]" : "hover:bg-[#f8f7f5]")}>
                <span className="min-w-0 flex-1 text-[15px] font-medium leading-[23px] text-[#333]">{t}</span>
                {on && <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M3.11133 8.44531L6.66688 12.0009L12.8891 4.44531" stroke="#333333" strokeWidth="1.42222" strokeLinecap="round" strokeLinejoin="round" /></svg>}
              </button>
            ); })}
          </div>
        </div>
        <div className="flex min-h-0 w-[634px] flex-1 flex-col items-start gap-2">
          <div className="flex h-[22px] w-[634px] shrink-0 items-center gap-2"><p className="text-[14px] font-medium leading-[21px] text-[#747d8d]">삭제한 항목</p><p className="text-[14px] font-medium leading-[21px] text-[#333]">{list.length}</p></div>
          <div className="flex min-h-0 w-[634px] flex-1 flex-col items-start overflow-y-auto">
            {list.length === 0 && <div data-trash-empty className="m-in flex w-full flex-col items-center gap-1 py-16 text-center"><p className="text-[17px] font-bold leading-[26px] text-[#333d4b]">{trash.length ? "찾는 항목이 없어요" : "휴지통이 비어 있어요"}</p><p className="text-[14px] leading-[21px] text-[#8b95a1]">{trash.length ? "다른 말로 찾아보세요" : "지운 메모·기록·종목이 여기에 모여요"}</p></div>}
            {list.map((t) => (
              <div key={t.t} className={cx("m-w flex h-[72px] w-[634px] shrink-0 items-center gap-3 border-b border-[#e8eaed] py-2 pl-2 pr-1", gone === t.t && "m-gone")}>
                <svg width="24" height="24" viewBox="0 0 22 22" fill="none" stroke="#333333" {...sp} className="shrink-0">{TICON[t.icon]}</svg>
                <div className="flex h-[46px] min-w-0 flex-1 flex-col items-start gap-[2px]">
                  <p className={cx("w-full truncate text-[17px] font-medium leading-[26px] text-[#15171a]", TR)}>{t.t}</p>
                  <p className="w-full truncate text-[14px] leading-[21px] text-[#747d8d]">{t.s}</p>
                </div>
                <div className="flex h-10 w-[88px] shrink-0 items-center gap-2">
                  <TipBtn tip="복원" onClick={() => restore(t)}>{(c) => <svg width="22" height="22" viewBox="0 0 20 20" fill="none"><path d="M7.22226 5L3.33337 8.88889L7.22226 12.7778" stroke={c} strokeWidth="1.77778" strokeLinecap="round" strokeLinejoin="round" /><path d="M3.33337 8.89062H11.6667C15 8.89062 16.6667 10.5573 16.6667 13.8906V15.0017" stroke={c} strokeWidth="1.77778" strokeLinecap="round" strokeLinejoin="round" /></svg>}</TipBtn>
                  <TipBtn tip="영구 삭제" danger onClick={() => setAsk(t)}>{(c) => <svg width="22" height="22" viewBox="0 0 20 20" fill="none" stroke={c} strokeWidth="1.77778" strokeLinecap="round" strokeLinejoin="round"><path d="M3.33337 5H16.6667" /><path d="M7.77783 4.9987V3.33203H12.2223V4.9987" /><path d="M5 5L5.88889 17.2222H14.1111L15 5" /><path d="M8.33337 8.89062V13.8906" /><path d="M11.6666 8.89062V13.8906" /></svg>}</TipBtn>
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="flex h-9 w-[634px] shrink-0 items-center gap-2">
          <p className="min-w-0 flex-1 text-[14px] leading-[21px] text-[#747d8d]">보관 기간과 자동 삭제 여부는 추후 안내합니다.</p>
          <button data-trash-empty-all disabled={!trash.length} onClick={() => setAskAll(true)} className="h-9 rounded-[10px] px-3 text-[14px] font-bold text-[#e45d6a] enabled:hover:bg-[#fdf0f1] disabled:opacity-40">휴지통 비우기</button>
          <svg width="18" height="18" viewBox="0 0 16 16" fill="none" stroke="#6B7280" strokeWidth="1.42222" strokeLinecap="round" strokeLinejoin="round"><path d="M14.0623 9.38623L14.2223 7.99957L14.0623 6.6129L13.6089 5.29734L12.8623 4.12401L11.8756 3.13734L10.7023 2.39068L9.38672 1.93734L8.00005 1.77734L6.61339 1.93734L5.29783 2.39068L4.1245 3.13734L3.13783 4.12401L2.39117 5.29734L1.93783 6.6129L1.77783 7.99957L1.93783 9.38623L2.39117 10.7018L3.13783 11.8751L4.1245 12.8618L5.29783 13.6085L6.61339 14.0618L8.00005 14.2218L9.38672 14.0618L10.7023 13.6085L11.8756 12.8618L12.8623 11.8751L13.6089 10.7018L14.0623 9.38623Z" /><path d="M6.22217 6.39887C6.22217 5.21369 6.81476 4.62109 7.99995 4.62109C9.18513 4.62109 9.77772 5.15443 9.77772 6.22109C9.77772 6.93221 9.18513 7.5248 7.99995 7.99887V9.06554" /><path d="M8 11.0234V11.2012" /></svg>
        </div>
      </div>
      <ConfirmDanger kind={askAll ? "wipe" : null} onClose={() => setAskAll(false)} text={askAll ? ["휴지통을 비울까요?", `${trash.length}개 항목이 영구 삭제돼요. 되돌릴 수 없어요.`, "비우기"] : undefined} onRun={() => { setTrash([]); snack("휴지통을 비웠어요"); }} />
      <ConfirmDanger kind={ask ? "wipe" : null} onClose={() => setAsk(null)} text={ask ? ["영구 삭제할까요?", `'${ask.t}'을(를) 영구 삭제하면 되돌릴 수 없어요.`, "영구 삭제"] : undefined} onRun={() => { if (ask) void kill(ask); }} />
    </Modal>
  );
}

/* ================= 11 · 도움말 ================= */
export function HelpPage() {
  const { setCoach, setCoachPending } = useApp();
  return (
    <FixedFrame>
    <div className="flex w-[860px] flex-col items-start gap-8 pb-8 pt-8">
      <PageTitle title="도움말" sub="서비스 이용 안내는 준비 중입니다." />
      {/* v2: 처음 안내(코치마크)를 다시 볼 수 있게 */}
      <button data-help-replay onClick={() => { setCoachPending(false); setCoach({ step: -1 }); }} className="flex w-[420px] max-w-full items-center gap-4 rounded-[16px] border border-[#e5e8eb] bg-white p-5 text-left hover:bg-[#f9f9f9]">
        <span className="grid h-11 w-11 shrink-0 place-items-center rounded-[14px] bg-[#111111]"><svg width="20" height="20" viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="7.2" stroke="white" strokeWidth="1.6" /><path d="M12.9 7.1L11.3 11.3L7.1 12.9L8.7 8.7L12.9 7.1Z" fill="white" /></svg></span>
        <span className="flex min-w-0 flex-1 flex-col"><span className="text-[17px] font-bold leading-[26px] text-[#191f28]">사용법 다시 보기</span><span className="text-[14px] leading-[21px] text-[#6b7684]">메모 쓰기부터 스튜디오까지 30초 안내</span></span>
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M6.75 4.5L11.25 9L6.75 13.5" stroke="#9AA0AA" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
      </button>
    </div>
    </FixedFrame>
  );
}
