/* 오른쪽 스튜디오 — Figma Page 2.5 'AI 스튜디오' (412 홈 + 334 화면들을 412로 넓힘) */
import { useEffect, useRef, useState, type ReactNode } from "react";
import { cx, useSnack, Modal } from "./kit";
import { useApp, type JobKind, type SView } from "./store";
import { useUsage, UsageSheet, SpentBox } from "./x";
import { ReportSummary } from "./gen/ReportSummary";
import { LabResultBody } from "./gen/LabResultBody";

const k = () => Number(getComputedStyle(document.documentElement).getPropertyValue("--k")) || 1;
const TR = "tracking-[-0.2px]";

/* ---------- 아이콘 (Figma Studio/Icon) ---------- */
const P = { round: { strokeLinecap: "round" as const }, join: { strokeLinejoin: "round" as const } };
export const SI = {
  star: (s = 19, c = "white") => <svg width={s} height={s} viewBox="0 0 19 19" fill="none"><path d="M8.70834 2.375C9.18334 5.77917 10.8458 7.44167 14.25 7.91667C10.8458 8.39167 9.18334 10.0542 8.70834 13.4583C8.23334 10.0542 6.57084 8.39167 3.16667 7.91667C6.57084 7.44167 8.23334 5.77917 8.70834 2.375Z" fill={c} /><path d="M15.0417 11.875V15.0417M13.4583 13.4583H16.625" stroke={c} strokeWidth="1.8" {...P.round} /></svg>,
  wave: (s = 22, c = "#2F6BDB") => <svg width={s} height={s} viewBox="0 0 22 22" fill="none"><path d="M3.66675 9.16675V12.8334M7.33341 6.41675V15.5834M11.0001 3.66675V18.3334M14.6667 7.33341V14.6667M18.3334 10.0834V11.9167" stroke={c} strokeWidth="1.8" {...P.round} /></svg>,
  report: (s = 22, c = "#D6404A") => <svg width={s} height={s} viewBox="0 0 22 22" fill="none"><path d="M6.41667 2.75H12.8333L17.4167 7.33333V18.3333C17.4167 18.5764 17.3201 18.8096 17.1482 18.9815C16.9763 19.1534 16.7431 19.25 16.5 19.25H6.41667C6.17355 19.25 5.94039 19.1534 5.76849 18.9815C5.59658 18.8096 5.5 18.5764 5.5 18.3333V3.66667C5.5 3.42355 5.59658 3.19039 5.76849 3.01849C5.94039 2.84658 6.17355 2.75 6.41667 2.75Z" stroke={c} strokeWidth="1.8" {...P.join} /><path d="M12.8333 2.75V7.33333H17.4166" stroke={c} strokeWidth="1.8" {...P.join} /><path d="M8.70825 15.5834V13.7501M11.4583 15.5834V11.9167M14.2083 15.5834V12.8334" stroke={c} strokeWidth="1.8" {...P.round} /></svg>,
  lab: (s = 22, c = "#A8740A") => <svg width={s} height={s} viewBox="0 0 22 22" fill="none"><path d="M8.2499 2.75H13.7499M9.16657 2.75V8.25L4.58324 16.9583C4.4566 17.1958 4.39361 17.462 4.4004 17.731C4.40719 18 4.48352 18.2627 4.62198 18.4934C4.76043 18.7242 4.95628 18.9151 5.19045 19.0477C5.42462 19.1803 5.68913 19.25 5.95824 19.25H16.0416C16.3107 19.25 16.5752 19.1803 16.8094 19.0477C17.0435 18.9151 17.2394 18.7242 17.3778 18.4934C17.5163 18.2627 17.5926 18 17.5994 17.731C17.6062 17.462 17.5432 17.1958 17.4166 16.9583L12.8332 8.25V2.75" stroke={c} strokeWidth="1.8" {...P.round} {...P.join} /><path d="M6.875 13.75H15.125" stroke={c} strokeWidth="1.8" {...P.round} /></svg>,
  quiz: (s = 22, c = "#1F8A4C") => <svg width={s} height={s} viewBox="0 0 22 22" fill="none"><path d="M11 19.25C15.5563 19.25 19.25 15.5563 19.25 11C19.25 6.44365 15.5563 2.75 11 2.75C6.44365 2.75 2.75 6.44365 2.75 11C2.75 15.5563 6.44365 19.25 11 19.25Z" stroke={c} strokeWidth="1.8" /><path d="M8.80005 8.52499C9.0042 8.04413 9.36652 7.64746 9.82697 7.4007C10.2874 7.15393 10.8183 7.07189 11.3318 7.16816C11.8452 7.26443 12.3104 7.53324 12.6502 7.93005C12.99 8.32685 13.184 8.82783 13.2 9.34999C13.2 10.9083 11 11.3667 11 12.65" stroke={c} strokeWidth="1.8" {...P.round} /><path d="M11 15.7666H11.0092" stroke={c} strokeWidth="2.4" {...P.round} /></svg>,
  bolt: (s = 16, c = "#15171A") => <svg width={s} height={s} viewBox="0 0 24 24" fill="none"><path d="M13 3L5 13H11L10 21L18 11H12L13 3Z" stroke={c} strokeWidth={1.8 * 24 / s} {...P.join} /></svg>,
  chevR: (s = 18, c = "#9AA0AA") => <svg width={s} height={s} viewBox="0 0 18 18" fill="none"><path d="M6.75 4.5L11.25 9L6.75 13.5" stroke={c} strokeWidth="2" {...P.round} {...P.join} /></svg>,
  back: () => <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M11.25 4.5L6.75 9L11.25 13.5" stroke="#404752" strokeWidth="1.5" {...P.round} {...P.join} /></svg>,
  arrowL: () => <svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M19 12H5M12 5L5 12L12 19" stroke="black" strokeWidth="1.6" {...P.round} {...P.join} /></svg>,
  close: (s = 20) => <svg width={s} height={s} viewBox="0 0 20 20" fill="none"><path d="M5 5L15 15M15 5L5 15" stroke="#404752" strokeWidth="1.66667" {...P.round} /></svg>,
  check: (s = 12, c = "white", w = 1.5) => <svg width={s} height={s} viewBox="0 0 12 12" fill="none"><path d="M2.5 6L4.75 8.25L9.5 3.5" stroke={c} strokeWidth={w} {...P.round} {...P.join} /></svg>,
  panelClose: () => <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M13.5 3H4.5C3.25736 3 2.25 4.00736 2.25 5.25V12.75C2.25 13.9926 3.25736 15 4.5 15H13.5C14.7426 15 15.75 13.9926 15.75 12.75V5.25C15.75 4.00736 14.7426 3 13.5 3Z" stroke="#404752" strokeWidth="1.8" /><path d="M11.25 3V15" stroke="#404752" strokeWidth="1.8" /></svg>,
  panelOpen: () => <svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M4.16667 3.3335H15.8333C16.7538 3.3335 17.5 4.07969 17.5 5.00016V15.0002C17.5 15.9206 16.7538 16.6668 15.8333 16.6668H4.16667C3.24619 16.6668 2.5 15.9206 2.5 15.0002V5.00016C2.5 4.07969 3.24619 3.3335 4.16667 3.3335Z" stroke="#333333" strokeWidth="1.33333" /><path d="M13.3334 3.3335V16.6668" stroke="#333333" strokeWidth="1.33333" {...P.round} /></svg>,
  pause: (s = 22, c = "white") => <svg width={s} height={s} viewBox="0 0 22 22" fill="none"><path d="M8.06667 4.58398H6.6C5.99249 4.58398 5.5 5.07647 5.5 5.68398V16.3173C5.5 16.9248 5.99249 17.4173 6.6 17.4173H8.06667C8.67418 17.4173 9.16667 16.9248 9.16667 16.3173V5.68398C9.16667 5.07647 8.67418 4.58398 8.06667 4.58398Z" fill={c} /><path d="M15.4 4.58398H13.9334C13.3259 4.58398 12.8334 5.07647 12.8334 5.68398V16.3173C12.8334 16.9248 13.3259 17.4173 13.9334 17.4173H15.4C16.0076 17.4173 16.5 16.9248 16.5 16.3173V5.68398C16.5 5.07647 16.0076 4.58398 15.4 4.58398Z" fill={c} /></svg>,
  play: (s = 22, c = "white") => <svg width={s} height={s} viewBox="0 0 24 24" fill="none"><path d="M7.99998 5.49964V18.4996C7.99385 18.678 8.03559 18.8548 8.12086 19.0117C8.20613 19.1685 8.33183 19.2996 8.48489 19.3915C8.63796 19.4833 8.81282 19.5325 8.99132 19.5339C9.16982 19.5354 9.34545 19.489 9.49998 19.3996L19.5 12.8996C19.6447 12.81 19.7641 12.6848 19.8469 12.5361C19.9297 12.3873 19.9732 12.2199 19.9732 12.0496C19.9732 11.8794 19.9297 11.712 19.8469 11.5632C19.7641 11.4145 19.6447 11.2893 19.5 11.1996L9.49998 4.69964C9.35275 4.61416 9.18613 4.56769 9.01591 4.56462C8.84569 4.56155 8.67751 4.60198 8.52729 4.6821C8.37707 4.76222 8.24979 4.87936 8.15752 5.02243C8.06524 5.1655 8.01101 5.32976 7.99998 5.49964Z" fill={c} /></svg>,
  alert: () => <svg width="36" height="36" viewBox="0 0 36 36" fill="none"><path d="M18 31.5C25.4558 31.5 31.5 25.4558 31.5 18C31.5 10.5442 25.4558 4.5 18 4.5C10.5442 4.5 4.5 10.5442 4.5 18C4.5 25.4558 10.5442 31.5 18 31.5Z" stroke="#D93033" strokeWidth="2.7" /><path d="M18 11.25V19.5" stroke="#D93033" strokeWidth="3" {...P.round} /><path d="M18 24.75H18.015" stroke="#D93033" strokeWidth="3.9" {...P.round} /></svg>,
};
const KIND: Record<JobKind, { t: string; box: string; ic: (s?: number, c?: string) => ReactNode; c: string }> = {
  audio: { t: "AI 오디오", box: "#d6e4ff", ic: SI.wave, c: "#2F6BDB" },
  report: { t: "AI 주간보고서", box: "#ffdadb", ic: SI.report, c: "#D6404A" },
  lab: { t: "AI 투자 실험실", box: "#fce9ae", ic: SI.lab, c: "#A8740A" },
};
const FEATURES = [
  { key: "audio", t: "AI 오디오", d: "바쁠 땐 내 종목 소식을 라디오로", box: "#d6e4ff", ic: () => SI.wave() },
  { key: "report", t: "AI 주간보고서", d: "공시 읽기 힘드셨죠? 한 주를 한 장으로", box: "#ffdadb", ic: () => SI.report() },
  { key: "lab", t: "AI 투자 실험실", d: "금리·환율이 바뀌면 내 종목은?", box: "#fce9ae", ic: () => SI.lab() },
  { key: "quiz", t: "오늘의 퀴즈", d: "어제 증시에서 일어난 일 1문제 · 무료", box: "#d3f0de", ic: () => SI.quiz() },
] as const;
const GEN_T: Record<JobKind, [string, string, string]> = {
  audio: ["오디오를 만드는 중이에요", "오디오를 만들지 못했어요", "오디오가 완성됐어요"],
  report: ["주간보고서를 만드는 중이에요", "주간보고서를 만들지 못했어요", "주간보고서가 완성됐어요"],
  lab: ["실험을 하는 중이에요", "실험을 하지 못했어요", "실험 결과가 나왔어요"],
};
const STEPS: Record<JobKind, string[]> = {
  audio: ["업데이트 모으기", "두 진행자 대본 쓰기", "목소리 입히기"],
  report: ["업데이트 모으기", "종목별 흐름 정리하기", "보고서 다듬기"],
  lab: ["조건 읽기", "영향 경로 찾기", "결과 정리하기"],
};
const RESULT: Record<JobKind, SView> = { audio: "player", report: "report", lab: "labResult" };
const ACT: Record<JobKind, string> = { audio: "바로 듣기", report: "바로 보기", lab: "바로 보기" };

/* ---------- 공통 조각 ---------- */
export function GBtn({ children, dark, flex, h = 46, onClick, disabled, className }: { children: ReactNode; dark?: boolean; flex?: boolean; h?: number; onClick?: () => void; disabled?: boolean; className?: string }) {
  return (
    <button disabled={disabled} onClick={onClick} style={{ height: h }}
      className={cx("flex shrink-0 items-center justify-center gap-[6px] rounded-[14px] px-[18px] font-bold leading-none", TR, "text-[17px]", flex && "min-w-0 flex-1",
        disabled ? "bg-[#e8ecf3] text-[#8e8a97]" : dark ? "bg-[#15171a] text-white hover:bg-[#2a2c31]" : "bg-[#f5f6f8] text-[#15171a] hover:bg-[#eceef1]", className)}>{children}</button>
  );
}
function Chip({ children, dark, color }: { children: ReactNode; dark?: boolean; color?: string }) {
  return <span className={cx("flex h-6 shrink-0 items-center gap-[5px] rounded-full px-[9px] text-[13px] font-bold leading-none", TR, dark ? "bg-[#15171a] text-white" : "bg-[#f5f6f8] text-[#404752]")} style={color ? { color } : undefined}>{children}</span>;
}
function BackLink({ onClick }: { onClick: () => void }) {
  return <button onClick={onClick} className="flex shrink-0 items-center gap-[2px] pr-2"><SIw>{SI.back()}</SIw><span className={cx("whitespace-nowrap text-[15px] font-bold leading-none text-[#404752]", TR)}>스튜디오</span></button>;
}
const SIw = ({ children }: { children: ReactNode }) => <span className="block shrink-0">{children}</span>;
function SubHead({ title, onBack }: { title: string; onBack: () => void }) {
  return (
    <div className="sticky top-0 z-10 flex h-12 w-full items-center gap-2 bg-white px-4">
      <button aria-label="뒤로" onClick={onBack} className="-m-1 rounded-md p-1 hover:bg-[#f9f9f9]">{SI.arrowL()}</button>
      <p className="whitespace-nowrap text-[20px] font-bold leading-[29px] text-[#16171a]">{title}</p>
    </div>
  );
}
function Box({ children }: { children: ReactNode }) { return <div className="flex w-full flex-col gap-3 px-4 pb-[18px] pt-[6px]">{children}</div>; }
function FeatHead({ icon, title, sub, chips }: { icon: ReactNode; title: string; sub?: string; chips?: ReactNode }) {
  return (
    <div className="flex w-full items-center gap-3">
      <span className="grid h-[46px] w-[46px] shrink-0 place-items-center rounded-[14px] bg-[#f5f6f8]">{icon}</span>
      <div className={cx("flex min-w-0 flex-1 flex-col items-start", chips ? "gap-1" : "gap-[2px]")}>
        <p className="whitespace-nowrap text-[20px] font-bold leading-[1.3] tracking-[-0.4px] text-[#15171a]">{title}</p>
        {sub && <p className={cx("w-full text-[15px] leading-[23px] text-[#8e8a97]", TR)}>{sub}</p>}
        {chips && <div className="flex gap-[6px]">{chips}</div>}
      </div>
    </div>
  );
}

/* ============ 스튜디오 기둥 ============ */
export function StudioColumn() {
  const app = useApp();
  const { studio, setStudio, demo, stocks, memos } = app;
  const snack = useSnack();
  const [narrow, setNarrow] = useState(() => window.innerWidth <= 1280);
  useEffect(() => {
    const f = () => { const n = window.innerWidth <= 1280; setNarrow((was) => { if (n && !was) setStudio((s) => ({ ...s, open: false })); return n; }); };
    if (window.innerWidth <= 1280) setStudio((s) => ({ ...s, open: false }));
    window.addEventListener("resize", f); return () => window.removeEventListener("resize", f);
  }, [setStudio]);

  /* 만들기 진행 */
  useEffect(() => {
    if (!studio.job) return;
    const id = window.setInterval(() => {
      setStudio((s) => {
        if (!s.job) return s;
        const pct = Math.min(100, s.job.pct + 2);
        const step = pct < 34 ? 0 : pct < 72 ? 1 : 2;
        if (demo.fail && pct >= 56) return { ...s, job: null, failKind: s.job.kind, view: "fail", dir: "push" };
        if (demo.ranOut && pct >= 64) return { ...s, job: null, failKind: s.job.kind, view: "ranOut", dir: "push", creditOut: true };
        if (pct >= 100) {
          const kind = s.job.kind;
          const made = [{ id: Date.now(), kind, title: s.job.title, meta: s.job.meta, when: "11.09", left: "30일 뒤 삭제" }, ...s.made];
          return { ...s, job: null, made, view: RESULT[kind], dir: "push", badge: s.open ? s.badge : kind, done: kind, ...(kind === "audio" ? { playing: true, mini: false, t: 0 } : {}) };
        }
        return { ...s, job: { ...s.job, pct, step } };
      });
    }, 90 * k());
    return () => clearInterval(id);
  }, [studio.job?.kind, studio.job?.title, demo.fail, demo.ranOut, setStudio]); // eslint-disable-line
  /* 완료 토스트 */
  useEffect(() => {
    if (!studio.done) return;
    const kind = studio.done;
    snack(`${GEN_T[kind][2]} · 만든 항목에 저장했어요`, { star: true, action: { label: ACT[kind], run: () => setStudio((s) => ({ ...s, open: true, view: RESULT[kind], dir: "push", badge: null })) } });
    setStudio((s) => ({ ...s, done: null }));
  }, [studio.done]); // eslint-disable-line

  const aiN = memos.filter((m) => m.ai).length;
  const pct = useUsage();
  const [usageOpen, setUsageOpen] = useState(false);
  const openFeat = (f: string) => {
    setStudio((s) => ({ ...s, open: true, badge: s.badge === f ? null : s.badge }));
    if (f === "quiz") return app.sgo("quiz");
    if (studio.creditOut) return app.setOverlay("credit");
    if (f === "audio") return app.setOverlay("audio");
    if (f === "report") return app.setOverlay("reportPick");
    if (f === "lab") return app.sgo("lab");
  };

  if (!studio.open)
    return (
      <aside aria-label="스튜디오 (접힘)" className="st-col flex w-[96px] shrink-0 flex-col py-6 pr-6">
        <div className="flex h-[800px] max-h-full w-[72px] flex-col items-center gap-[10px] rounded-[20px] border border-[#e5e7eb] bg-white py-[18px]">
          <button aria-label="스튜디오 펼치기" title="스튜디오 펼치기" onClick={() => setStudio((s) => ({ ...s, open: true }))} className="grid h-10 w-10 place-items-center rounded-[12px] hover:bg-[#f9f9f9]">{SI.panelOpen()}</button>
          <span className="invisible h-4" aria-hidden />
          <span className="h-px w-8 bg-[#e8ecf3]" />
          {([["audio", "#d6e4ff", SI.wave(20)], ["report", "#ffdadb", SI.report(20)], ["quiz", "#d3f0de", SI.quiz(20)], ["lab", "#fce9ae", SI.lab(20)]] as const).map(([f, bg, ic]) => (
            <button key={f} aria-label={FEATURES.find((x) => x.key === f)!.t} title={FEATURES.find((x) => x.key === f)!.t} onClick={() => openFeat(f)} className="relative grid h-10 w-10 place-items-center rounded-[12px] hover:brightness-[.97]" style={{ background: bg }}>
              {ic}
              {(studio.badge === f || (f !== "quiz" && studio.job?.kind === f)) && (
                <span className="st-dot absolute -right-3 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full border-2 border-white bg-[#e45d6a] px-[3px] text-[11px] font-medium leading-none text-white">{studio.job?.kind === f ? "·" : "1"}</span>
              )}
            </button>
          ))}
        </div>
      </aside>
    );

  return (
    <aside aria-label="스튜디오" className={cx("st-col flex w-[436px] shrink-0 pb-6 pr-6 pt-6", narrow && "fixed bottom-0 right-0 top-0 z-[45] bg-[#f3f4f6] pl-6 shadow-[-16px_0_40px_rgba(17,17,17,.12)]")}>
      <div data-coach="studio" className="relative flex break-keep w-[412px] flex-col overflow-hidden rounded-[22px] border border-[#e4e4e7] bg-white">
        <header className="flex h-[72px] shrink-0 items-center gap-[10px] pb-[10px] pl-5 pr-3 pt-5">
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-[10px] bg-[#15171a]">{SI.star()}</span>
          <div className="flex min-w-0 flex-1 flex-col">
            <p className="whitespace-nowrap text-[22px] font-bold leading-[1.3] tracking-[-0.4px] text-[#15171a]">스튜디오</p>
            <p className={cx("truncate whitespace-nowrap text-[14px] leading-[21px] text-[#8e8a97]", TR)}>내 종목 {stocks.length} · AI 연결 메모 {aiN}</p>
          </div>
          <button data-usage-chip onClick={() => setUsageOpen(true)} className={cx("flex h-8 shrink-0 items-center gap-[6px] rounded-full px-3 text-[13px] font-bold", pct >= 100 ? "bg-[#fff4e5] text-[#7a4a00]" : "bg-[#f2f3f4] text-[#15171a] hover:bg-[#e9eaec]")}><span className="relative block h-[6px] w-6 overflow-hidden rounded-full bg-black/10"><span className="absolute inset-y-0 left-0 rounded-full" style={{ width: `${pct}%`, background: pct >= 100 ? "#c27a00" : "#15171a" }} /></span>AI 사용량 {pct}%</button>
          <button aria-label="스튜디오 접기" title="접기" onClick={() => setStudio((s) => ({ ...s, open: false }))} className="grid h-8 w-8 shrink-0 place-items-center rounded-[10px] hover:bg-[#f9f9f9]">{SI.panelClose()}</button>
        </header>
        <div className="relative min-h-0 flex-1"><View openFeat={openFeat} /></div>
        {studio.mini && studio.view !== "player" && <Mini />}
      </div>
      <UsageSheet open={usageOpen} onClose={() => setUsageOpen(false)} />
    </aside>
  );
}

export function useStartJob() {
  const { setStudio, setOverlay } = useApp();
  return (kind: JobKind, title: string, meta: string) => {
    setOverlay(null);
    setStudio((s) => ({ ...s, open: true, view: "gen", dir: "push", job: { kind, title, meta, step: 0, pct: 0 }, ...(kind === "audio" ? { mini: false, playing: false } : {}) }));
  };
}

function View({ openFeat }: { openFeat: (f: string) => void }) {
  const { studio } = useApp();
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { ref.current?.scrollTo({ top: 0 }); }, [studio.view]);
  const V: Record<SView, () => ReactNode> = { home: () => <Home openFeat={openFeat} />, gen: () => <Gen />, fail: () => <Fail />, ranOut: () => <RanOut />, player: () => <Player />, quiz: () => <Quiz />, report: () => <ReportSum />, lab: () => <Lab />, labResult: () => <LabResult /> };
  return (
    <div ref={ref} className={cx("absolute inset-0 overflow-y-auto overflow-x-hidden", studio.mini && studio.view !== "player" && "pb-[84px]")} data-studio-scroll>
      <div key={studio.view} className={cx("min-h-full", studio.dir === "push" ? "st-push" : "st-pop")}>{V[studio.view]()}</div>
    </div>
  );
}

/* ============ 홈 (2.1) ============ */
function Home({ openFeat }: { openFeat: (f: string) => void }) {
  const { studio, setStudio, sgo } = useApp();
  return (
    <div className="flex w-full flex-col gap-[10px] px-4 pb-6 pt-2">
      {studio.creditOut && <SpentBox title="이번 달 AI 사용량을 다 썼어요" sub={"12월 1일에 새로 채워져요.\n이미 만든 결과와 오늘의 퀴즈는 계속 쓸 수 있어요."} />}
      <p className="w-full text-[14px] leading-[21px] text-[#9a9ea7]">쌓인 소식을 듣고, 읽고, 실험해 보세요</p>
      {FEATURES.map((f) => (
        <button key={f.key} onClick={() => openFeat(f.key)} className="flex w-full items-center gap-3 rounded-[16px] bg-white px-3 py-[14px] text-left hover:bg-[#f9f9f9]">
          <span className="grid h-11 w-11 shrink-0 place-items-center rounded-[13px]" style={{ background: f.box }}>{f.ic()}</span>
          <span className="flex min-w-0 flex-1 flex-col gap-[3px]">
            <span className="whitespace-nowrap text-[17px] font-bold leading-[1.4] text-[#16171a]">{f.t}</span>
            <span className="w-full text-[15px] leading-[1.45] text-[#575b63]">{f.d}</span>
          </span>
          {SI.chevR()}
        </button>
      ))}
      <div className="flex w-full items-end gap-[6px] pt-2">
        <p className="whitespace-nowrap text-[17px] font-bold leading-[26px] text-[#16171a]">만든 항목</p>
        <p className="whitespace-nowrap text-[14px] leading-[21px] text-[#9a9ea7]">30일 보관 · 다시 보기 무료</p>
      </div>
      <div className="flex w-full flex-col rounded-[18px] bg-white px-4">
        {studio.made.map((m, i) => (
          <button key={m.id} onClick={() => { setStudio((s) => ({ ...s, badge: null, ...(m.kind === "audio" ? { mini: false, playing: true } : {}) })); sgo(RESULT[m.kind]); }}
            className={cx("flex h-[72px] w-full items-center gap-3 text-left", i < studio.made.length - 1 && "border-b border-[#f0f1f3]", i === 0 && m.when === "11.09" && "m-new")}>
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-[10px]" style={{ background: KIND[m.kind].box }}>{KIND[m.kind].ic(20)}</span>
            <span className="flex min-w-0 flex-1 flex-col gap-1">
              <span className="truncate text-[17px] font-medium leading-[26px] text-[#16171a]">{m.title}</span>
              <span className="truncate text-[14px] leading-[21px] text-[#9a9ea7]">{m.meta}</span>
            </span>
            {m.kind === "audio"
              ? <span role="button" tabIndex={0} aria-label="바로 재생" data-quick-play onClick={(e) => { e.stopPropagation(); setStudio((s) => ({ ...s, mini: true, playing: !(s.mini && s.playing) })); }} className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-[#15171a] text-white hover:bg-[#2a2a2a]">{studio.mini && studio.playing ? <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor"><rect x="3" y="2.5" width="3" height="9" rx="1" /><rect x="8" y="2.5" width="3" height="9" rx="1" /></svg> : <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor"><path d="M4 2.5v9l7.5-4.5z" /></svg>}</span>
              : <span className="shrink-0 whitespace-nowrap text-[14px] leading-[21px] text-[#9a9ea7]">{m.left}</span>}
          </button>
        ))}
      </div>
      <p className="w-full pt-1 text-center text-[13px] leading-[20px] text-[#9a9ea7]">스튜디오는 투자 권유나 주가 예측을 하지 않아요.</p>
    </div>
  );
}

/* ============ 생성 중 ============ */
function Gen() {
  const { studio } = useApp();
  const j = studio.job;
  if (!j) return null;
  return (
    <div className="flex w-full flex-col items-center gap-[18px] px-4 pb-[18px] pt-[120px]">
      <span className="grid h-[72px] w-[72px] place-items-center rounded-[22px] bg-[#f5f6f8]">{KIND[j.kind].ic(36, "#15171A")}</span>
      <div className="flex w-full flex-col items-center gap-[6px]">
        <p className="w-full text-center text-[22px] font-bold leading-[1.5] tracking-[-0.4px] text-[#15171a]">{GEN_T[j.kind][0]}</p>
        <p className={cx("w-full text-center text-[15px] leading-[23px] text-[#8e8a97]", TR)}>다른 화면으로 가도 계속 만들어요.<br />끝나면 알려 드릴게요.</p>
      </div>
      <div className="h-[6px] w-[200px] overflow-hidden rounded-[3px] bg-[#f5f6f8]"><div className="h-[6px] rounded-[3px] bg-[#15171a] transition-[width] duration-150" style={{ width: `${j.pct}%` }} /></div>
      <div className="flex flex-col items-start gap-[10px]">
        {STEPS[j.kind].map((t, i) => (
          <div key={t} className="flex items-center gap-[10px]">
            <span className={cx("st-step grid h-[22px] w-[22px] place-items-center rounded-full transition-colors", i < j.step ? "bg-[#15171a]" : i === j.step ? "bg-[#e5e3e8]" : "bg-[#f5f6f8]")}>{i < j.step ? SI.check() : i === j.step ? SI.check(12, "#15171A") : null}</span>
            <p className={cx("whitespace-nowrap text-[15px] leading-[1.2]", TR, i < j.step ? "text-[#15171a]" : i === j.step ? "font-bold text-[#15171a]" : "text-[#8e8a97]")}>{t}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ============ 실패 · 크레딧 소진 ============ */
function FailLike({ title, sub, right, rightAct, note }: { title: string; sub: string; right: string; rightAct: () => void; note: string }) {
  const { sgo } = useApp();
  return (
    <div className="flex w-full flex-col items-center gap-[18px] px-4 pb-[18px] pt-[120px]">
      <span className="grid h-[72px] w-[72px] place-items-center rounded-[22px] bg-[#f5f6f8]">{SI.alert()}</span>
      <div className="flex w-full flex-col items-center gap-[6px]">
        <p className="w-full text-center text-[22px] font-bold leading-[1.5] tracking-[-0.4px] text-[#15171a]">{title}</p>
        <p className={cx("w-full text-center text-[15px] leading-[23px] text-[#8e8a97]", TR)}>{sub}</p>
      </div>
      <div className="flex w-full items-start gap-2">
        <GBtn flex onClick={() => sgo("home", "pop")}>스튜디오로</GBtn>
        <GBtn flex dark onClick={rightAct}>{right}</GBtn>
      </div>
      <p className={cx("w-full text-center text-[14px] leading-[21px] text-[#8e8a97]", TR)}>{note}</p>
    </div>
  );
}
function Fail() {
  const { studio, setStudio } = useApp();
  const kind = studio.failKind ?? "audio";
  const retry = () => setStudio((s) => ({ ...s, view: "gen", dir: "push", job: { kind, title: s.lastJob?.title ?? "", meta: s.lastJob?.meta ?? "", step: 0, pct: 0 } }));
  return <FailLike title={GEN_T[kind][1]} sub="잠시 후 다시 시도해 주세요." right="다시 시도" rightAct={retry} note="크레딧 사용 내역은 설정 › 크레딧에서 볼 수 있어요." />;
}
function RanOut() {
  const { studio, setOverlay } = useApp();
  return <FailLike title={GEN_T[studio.failKind ?? "audio"][1]} sub="만드는 도중에 크레딧을 다 써서 멈췄어요." right="크레딧 충전하기" rightAct={() => setOverlay("charge")} note="매달 1일 무료 크레딧이 채워져요. 사용 내역은 설정 › 크레딧에서 볼 수 있어요." />;
}

/* ============ 오디오 플레이어 ============ */
const DUR = 402;
const CHAPTERS: [string, string, number][] = [["01", "오프닝", 0], ["02", "직전 거래일 증시 요약", 18], ["03", "SK하이닉스", 65], ["04", "삼성전자", 220], ["05", "네이버", 295], ["06", "마무리", 370]];
const mmss = (t: number) => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`;
function usePlayback() {
  const { studio, setStudio } = useApp();
  useEffect(() => {
    if (!studio.playing) return;
    const id = window.setInterval(() => setStudio((s) => { const t = Math.min(DUR, s.t + s.speed); return { ...s, t, playing: t < DUR }; }), 1000);
    return () => clearInterval(id);
  }, [studio.playing, setStudio]);
  const ch = [...CHAPTERS].reverse().find((c) => studio.t >= c[2]) ?? CHAPTERS[0];
  return { t: studio.t, playing: studio.playing, ch, toggle: () => setStudio((s) => ({ ...s, playing: !s.playing, t: s.t >= DUR ? 0 : s.t })), seek: (t: number) => setStudio((s) => ({ ...s, t: Math.max(0, Math.min(DUR, t)) })) };
}
function Player() {
  const { studio, setStudio, sgo, setOverlay } = useApp();
  const p = usePlayback();
  const back = () => { setStudio((s) => ({ ...s, mini: s.playing || s.t > 0 })); sgo("home", "pop"); };
  const Face = ({ dark }: { dark?: boolean }) => (
    <svg width="36" height="36" viewBox="0 0 36 36" fill="none"><path d="M12.6 18.1807C13.6935 18.1807 14.58 17.2942 14.58 16.2007C14.58 15.1072 13.6935 14.2207 12.6 14.2207C11.5065 14.2207 10.62 15.1072 10.62 16.2007C10.62 17.2942 11.5065 18.1807 12.6 18.1807Z" fill={dark ? "white" : "#15171A"} /><path d="M23.4 18.1807C24.4935 18.1807 25.38 17.2942 25.38 16.2007C25.38 15.1072 24.4935 14.2207 23.4 14.2207C22.3065 14.2207 21.42 15.1072 21.42 16.2007C21.42 17.2942 22.3065 18.1807 23.4 18.1807Z" fill={dark ? "white" : "#15171A"} />{dark ? <path d="M18 25.5602C19.1929 25.5602 20.16 24.5932 20.16 23.4002C20.16 22.2073 19.1929 21.2402 18 21.2402C16.807 21.2402 15.84 22.2073 15.84 23.4002C15.84 24.5932 16.807 25.5602 18 25.5602Z" fill="white" /> : <path d="M12.6 22.5C16.2 25.5 19.8 25.5 23.4 22.5" stroke="#15171A" strokeWidth="1.98" strokeLinecap="round" />}</svg>
  );
  const talking = p.playing ? (Math.floor(p.t / 4) % 2 === 0 ? "A" : "B") : null;
  return (
    <Box>
      <BackLink onClick={back} />
      <div className="flex w-full flex-col items-center gap-[14px] rounded-[20px] bg-[#f5f6f8] p-[18px]">
        <div className="flex items-start gap-7">
          {(["A", "B"] as const).map((h) => (
            <div key={h} className="flex flex-col items-center gap-[6px]">
              <span className={cx("grid h-14 w-14 place-items-center rounded-full transition-transform duration-300", h === "A" ? "border-[2.5px] border-[#15171a] bg-white" : "border border-[#e5e3e8] bg-[#15171a]", talking === h && "scale-[1.06]")}><Face dark={h === "B"} /></span>
              <p className={cx("whitespace-nowrap text-[14px] font-bold leading-[1.2] text-[#404752]", TR)}>{h === "A" ? "진행자 A · 메인" : "진행자 B · 해설"}</p>
            </div>
          ))}
        </div>
        <div className="flex w-full flex-col items-center gap-[2px]">
          <p className="w-full text-center text-[22px] font-bold leading-[1.5] tracking-[-0.4px] text-[#15171a]">11.09 내 종목 라디오</p>
          <p className={cx("w-full text-center text-[14px] leading-[1.5] text-[#8e8a97]", TR)}>종목 3 · 전날 · 증시 요약 포함 · 6:42</p>
        </div>
        <div className="h-[6px] w-full cursor-pointer overflow-hidden rounded-[3px] bg-[#e5e3e8]" onClick={(e) => { const r = e.currentTarget.getBoundingClientRect(); p.seek(((e.clientX - r.left) / r.width) * DUR); }}>
          <div className="h-[6px] rounded-[3px] bg-[#15171a] transition-[width] duration-300" style={{ width: `${(p.t / DUR) * 100}%` }} />
        </div>
        <div className="flex w-full items-start justify-between">
          {[mmss(p.t), `지금 · ${p.ch[1]}`, "6:42"].map((t, i) => <p key={i} className={cx("whitespace-nowrap text-[14px] font-bold leading-[1.5] text-[#404752]", TR)}>{t}</p>)}
        </div>
        <div className="flex items-center gap-[18px]">
          <button onClick={() => p.seek(p.t - 10)} className={cx("text-[15px] font-bold leading-[1.5] text-[#404752]", TR)}>-10</button>
          <button aria-label={p.playing ? "일시정지" : "재생"} onClick={p.toggle} className="grid h-14 w-14 place-items-center rounded-full bg-[#15171a]">{p.playing ? SI.pause() : SI.play(22)}</button>
          <button onClick={() => p.seek(p.t + 10)} className={cx("text-[15px] font-bold leading-[1.5] text-[#404752]", TR)}>+10</button>
          <button onClick={() => setStudio((s) => ({ ...s, speed: s.speed === 1 ? 1.5 : s.speed === 1.5 ? 2 : 1 }))} className={cx("flex h-7 items-center rounded-full bg-white px-[10px] text-[14px] font-bold leading-none text-[#404752]", TR)}>{studio.speed.toFixed(1)}x</button>
        </div>
      </div>
      <p className={cx("w-full text-[14px] font-bold leading-[1.5] text-[#8e8a97]", TR)}>챕터</p>
      <div className="flex w-full flex-col gap-[2px]">
        {CHAPTERS.map((c) => (
          <button key={c[0]} onClick={() => p.seek(c[2])} className={cx("flex w-full items-center gap-[10px] rounded-[12px] px-3 py-3 text-left", p.ch[0] === c[0] ? "bg-[#f5f6f8]" : "hover:bg-[#f9f9f9]")}>
            <span className={cx("whitespace-nowrap text-[14px] leading-none text-[#8e8a97]", TR)}>{c[0]}</span>
            <span className={cx("min-w-0 flex-1 text-[15px] leading-[1.2] text-[#15171a]", TR, p.ch[0] === c[0] && "font-bold")}>{c[1]}</span>
            <span className={cx("whitespace-nowrap text-[14px] leading-none text-[#8e8a97]", TR)}>{mmss(c[2])}</span>
          </button>
        ))}
      </div>
      <p className={cx("w-full text-[14px] font-bold leading-[1.5] text-[#8e8a97]", TR)}>대본</p>
      <div className="flex w-full flex-col gap-3">
        {([["A", "이제 보유 종목 SK하이닉스예요. 전에 “실적 나오면 다시 보기” 메모를 남기셨죠?"], ["B", "네. 이번에 신규 설비투자 관련 공시가 나왔어요. 메모에 적어 둔 실적 확인과 함께 보시면 좋아요."], ["A", "HBM 이야기도 많았다고요?"]] as const).map(([h, t], i) => (
          <div key={i} className="flex w-full items-start gap-[10px]">
            <span className={cx("grid h-6 w-6 shrink-0 place-items-center rounded-full text-[13px] font-bold leading-none", TR, h === "A" ? "border border-[#15171a] bg-white text-[#15171a]" : "bg-[#15171a] text-white")}>{h}</span>
            <p className={cx("min-w-0 flex-1 text-[15px] leading-[23px]", TR, i === 1 ? "font-medium text-[#15171a]" : "text-[#8e8a97]")}>{t}</p>
          </div>
        ))}
      </div>
      <div className="flex w-full flex-col gap-[10px] rounded-[18px] border border-[#e5e3e8] bg-white p-4">
        <p className={cx("w-full text-[14px] font-bold leading-[1.5] text-[#8e8a97]", TR)}>들은 소식의 출처 · 연결된 메모</p>
        {([["시장", false, "11.06 코스피·코스닥·원/달러 종가", ""], ["공시", true, "SK하이닉스 · 신규 설비투자 관련 공시", "메모 “실적 나오면 다시 보기”와 연결"], ["뉴스", false, "SK하이닉스 · HBM4 공급 확대 기대감", "메모 “요즘 반도체 분위기 좋아 보여”와 연결"]] as const).map(([c, d, t, m]) => (
          <div key={t} className="flex w-full flex-col gap-1">
            <div className="flex w-full items-center gap-2"><Chip dark={d}>{c}</Chip><p className={cx("min-w-0 flex-1 text-[15px] font-bold leading-[1.5] text-[#15171a]", TR)}>{t}</p></div>
            {m && <p className={cx("w-full text-[14px] leading-[1.5] text-[#8e8a97]", TR)}>{m}</p>}
          </div>
        ))}
      </div>
      <GBtn onClick={() => setOverlay("audio")} className="w-full">조건 바꿔 새로 만들기</GBtn>
    </Box>
  );
}
function Mini() {
  const { setStudio, sgo } = useApp();
  const p = usePlayback();
  return (
    <div className="st-mini absolute bottom-3 left-3 right-3 z-20 flex items-center gap-[10px] overflow-hidden rounded-[18px] bg-[#15171a] py-[10px] pl-[10px] pr-2">
      <button aria-label={p.playing ? "일시정지" : "재생"} onClick={p.toggle} className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-white">{p.playing ? SI.pause(16, "#15171A") : SI.play(16, "#15171A")}</button>
      <button onClick={() => { setStudio((s) => ({ ...s, mini: false })); sgo("player"); }} className="flex min-w-0 flex-1 flex-col gap-[1px] text-left">
        <span className={cx("whitespace-nowrap text-[15px] font-bold leading-[1.3] text-white", TR)}>11.09 내 종목 라디오</span>
        <span className={cx("whitespace-nowrap text-[14px] leading-[1.3] text-[#b8bfc8]", TR)}>지금 · {p.ch[1]} · {mmss(p.t)}</span>
      </button>
      <button aria-label="닫기" onClick={() => setStudio((s) => ({ ...s, mini: false, playing: false }))} className="grid h-[18px] w-[18px] shrink-0 place-items-center"><svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M4.5 4.5L13.5 13.5M13.5 4.5L4.5 13.5" stroke="white" strokeWidth="1.5" strokeLinecap="round" /></svg></button>
      <span className="absolute bottom-0 left-0 h-[3px] bg-[#8e8a97] transition-[width] duration-300" style={{ width: `${(p.t / DUR) * 100}%` }} />
    </div>
  );
}

/* ============ 오늘의 퀴즈 ============ */
const OX = { q: "11월 6일(금) 코스피는 전 거래일보다 올라서 마감했다.", ans: "O", exp: "코스피는 2,612.40으로 마감해 전 거래일보다 21.30포인트(+0.82%) 올랐어요. 지수가 오르면 빨간색, 내리면 파란색으로 표시해요.", src: "출처 · 한국거래소 지수 종가 (시안용 예시 수치)" };
const Q4 = { q: "11월 6일(금) 코스피에서 거래대금이 가장 많았던 종목은?", opts: ["삼성전자", "SK하이닉스", "현대차", "LG에너지솔루션"], ans: 1, exp: "SK하이닉스가 약 2조 1,000억 원으로 거래대금 1위였어요. 거래대금은 거래량에 가격을 곱한 값이라, 비싼 종목이 많이 거래될수록 커져요.", src: "출처 · 한국거래소 종목별 거래대금 (시안용 예시 수치)" };
const OIcon = () => <svg width="35" height="35" viewBox="0 0 35 35" fill="none" style={{ width: 28.8, height: 28.8 }}><path d="M17.1 31.4992C25.0529 31.4992 31.5 25.0521 31.5 17.0992C31.5 9.14632 25.0529 2.69922 17.1 2.69922C9.14705 2.69922 2.69995 9.14632 2.69995 17.0992C2.69995 25.0521 9.14705 31.4992 17.1 31.4992Z" stroke="#15171A" strokeWidth="5.4" /></svg>;
const XIcon = () => <svg width="30" height="30" viewBox="0 0 30 30" fill="none" style={{ width: 24, height: 24 }}><path d="M2.69995 2.69922L26.7 26.6992M26.7 2.69922L2.69995 26.6992" stroke="#15171A" strokeWidth="5.4" strokeLinecap="round" /></svg>;
function Quiz() {
  const { studio, setStudio, sgo, demo } = useApp();
  const [pick, setPick] = useState<string | null>(studio.quizDone?.picked ?? null);
  const [yesterday, setYesterday] = useState(false);
  const four = demo.quiz4;
  const done = studio.quizDone;
  const submit = () => { if (pick == null) return; const correct = four ? pick === String(Q4.ans) : pick === OX.ans; setStudio((s) => ({ ...s, quizDone: { correct, picked: pick } })); };
  const head = <FeatHead icon={SI.quiz(23, "#15171A")} title="오늘의 퀴즈" chips={<><Chip>11.06(금) 증시</Chip><Chip dark>{four ? "4지선다" : "O/X"}</Chip></>} />;
  if (demo.quizLocked && !yesterday)
    return (
      <Box>
        <BackLink onClick={() => sgo("home", "pop")} />{head}
        <div className="flex w-full flex-col items-center gap-3 pb-2 pt-12">
          <span className="grid h-[72px] w-[72px] place-items-center rounded-[20px] bg-[#e9f7ef]"><svg width="30" height="30" viewBox="0 0 30 30" fill="none"><path d="M15 26.25C21.2132 26.25 26.25 21.2132 26.25 15C26.25 8.7868 21.2132 3.75 15 3.75C8.7868 3.75 3.75 8.7868 3.75 15C3.75 21.2132 8.7868 26.25 15 26.25Z" stroke="#2FAE68" strokeWidth="2.25" /><path d="M15 9.375V15L18.75 17.5" stroke="#2FAE68" strokeWidth="2.25" strokeLinecap="round" strokeLinejoin="round" /></svg></span>
          <p className="whitespace-nowrap text-center text-[22px] font-bold leading-[31px] text-[#15171a]">오늘 퀴즈는 오전 10시에 열려요</p>
          <p className="whitespace-nowrap text-center text-[15px] leading-[23px] text-[#8e8a97]">어제(11.06 금) 증시에서 실제로 일어난 일로<br />1문제가 나와요.</p>
          <button onClick={() => setYesterday(true)} className="flex h-12 w-full items-center justify-center rounded-[14px] bg-[#f5f6f8] text-[17px] font-bold text-[#15171a] hover:bg-[#eceef1]">어제 결과 보기</button>
          <p className="whitespace-nowrap text-[14px] font-bold text-[#2fae68]">3일 연속 · 오늘도 참여하면 4일</p>
        </div>
      </Box>
    );
  const shown = yesterday ? { correct: true, picked: four ? String(Q4.ans) : OX.ans } : done;
  const p = shown?.picked ?? pick;
  return (
    <Box>
      <BackLink onClick={() => (yesterday ? setYesterday(false) : sgo("home", "pop"))} />{head}
      <p className="w-full text-[22px] font-bold leading-[1.45] tracking-[-0.4px] text-[#15171a]">{four ? Q4.q : OX.q}</p>
      {!four ? (
        <div className="flex w-full items-start gap-[10px]">
          {(["O", "X"] as const).map((o) => {
            const isAns = o === OX.ans, mine = p === o;
            const cls = shown ? (isAns ? (mine ? "bg-[#f5f6f8] border-[1.5px] border-[#6e6396]" : "bg-[#f5f6f8] border-[1.5px] border-[#6e6396]") : mine ? "bg-[#f5f6f8] border-[1.5px] border-[#d93033]" : "bg-white border border-[#e5e3e8] opacity-50") : mine ? "bg-[#f5f6f8] border-[1.5px] border-[#15171a]" : "bg-white border border-[#e5e3e8] hover:bg-[#f9f9f9]";
            const label = shown ? (isAns ? "정답" : mine ? "내 선택" : o === "O" ? "맞아요" : "아니에요") : o === "O" ? "맞아요" : "아니에요";
            return (
              <button key={o} disabled={!!shown} onClick={() => setPick(o)} className={cx("flex h-[124px] min-w-0 flex-1 flex-col items-center justify-center gap-[6px] overflow-hidden rounded-[20px] transition-colors", cls)}>
                <span className="grid h-12 w-12 place-items-center">{o === "O" ? <OIcon /> : <XIcon />}</span>
                <span className={cx("whitespace-nowrap text-[15px] font-bold leading-none", TR, shown && !isAns && !mine ? "text-[#8e8a97]" : shown && mine && !isAns ? "text-[#d93033]" : "text-[#15171a]")}>{label}</span>
              </button>
            );
          })}
        </div>
      ) : (
        <div className="flex w-full flex-col gap-2">
          {Q4.opts.map((o, i) => {
            const isAns = i === Q4.ans, mine = p === String(i);
            const cls = shown ? (isAns ? "bg-[#f5f6f8] border-[1.5px] border-[#6e6396]" : mine ? "bg-[#f5f6f8] border-[1.5px] border-[#d93033]" : "bg-white border border-[#e5e3e8] opacity-50") : mine ? "bg-[#f5f6f8] border-[1.5px] border-[#15171a]" : "bg-white border border-[#e5e3e8] hover:bg-[#f9f9f9]";
            return (
              <button key={o} disabled={!!shown} onClick={() => setPick(String(i))} className={cx("flex w-full items-center gap-3 overflow-hidden rounded-[14px] px-[14px] py-3 text-left transition-colors", cls)}>
                <span className={cx("grid h-[26px] w-[26px] shrink-0 place-items-center rounded-full bg-[#f5f6f8] text-[13px] font-bold leading-none text-[#15171a]", TR)}>{i + 1}</span>
                <span className={cx("min-w-0 flex-1 text-[17px] leading-[1.2] text-[#15171a]", TR, shown && isAns ? "font-bold" : "font-medium")}>{o}</span>
                {shown && mine && !isAns && <span className={cx("whitespace-nowrap text-[14px] font-bold leading-none text-[#d93033]", TR)}>내 선택</span>}
                {shown && isAns && <span className={cx("whitespace-nowrap text-[14px] font-bold leading-none text-[#383b40]", TR)}>정답</span>}
              </button>
            );
          })}
        </div>
      )}
      {!shown ? (
        <>
          <GBtn dark disabled={pick == null} onClick={submit} className="w-full">제출하기</GBtn>
          <p className={cx("w-full text-center text-[14px] leading-[21px] text-[#8e8a97]", TR)}>하루 한 번, 처음 제출한 답만 인정돼요 · 맞히면 +2, 참여만 해도 +1</p>
        </>
      ) : (
        <>
          {shown.correct ? (
            <div className="m-pop flex w-full items-center justify-between rounded-[18px] bg-[#15171a] px-4 py-[14px]"><p className="whitespace-nowrap text-[17px] font-bold leading-[1.2] tracking-[-0.4px] text-white">정답이에요!</p></div>
          ) : (
            <div className="m-pop flex w-full items-center justify-between rounded-[18px] bg-[#f5f6f8] px-4 py-[14px]"><p className={cx("whitespace-nowrap text-[17px] font-bold leading-[1.2] text-[#15171a]", TR)}>아쉬워요, 정답은 {four ? Q4.opts[Q4.ans] : OX.ans}</p></div>
          )}
          <div className="flex w-full flex-col gap-[6px] rounded-[18px] bg-[#f5f6f8] p-4">
            <p className={cx("w-full text-[14px] font-bold leading-[1.5] text-[#8e8a97]", TR)}>해설</p>
            <p className={cx("w-full text-[15px] leading-[1.6] text-[#15171a]", TR)}>{four ? Q4.exp : OX.exp}</p>
            <p className={cx("w-full text-[14px] leading-[1.5] text-[#8e8a97]", TR)}>{four ? Q4.src : OX.src}</p>
          </div>
          {!four && (
            <div className="flex w-full flex-col gap-[10px] rounded-[18px] border border-[#e5e3e8] bg-white p-4">
              <p className={cx("whitespace-nowrap text-[17px] font-bold leading-[1.5] text-[#15171a]", TR)}>4일 연속 참여 중</p>
              <div className="flex w-full gap-[6px]">
                {["월", "화", "수", "목", "금", "토", "일"].map((d, i) => <span key={d} className={cx("flex h-9 min-w-0 flex-1 items-center justify-center rounded-[10px] text-[14px] font-bold leading-none", TR, i < 4 ? "bg-[#15171a] text-white" : "bg-[#f5f6f8] text-[#8e8a97]")}>{d}</span>)}
              </div>
            </div>
          )}
          <p className={cx("w-full text-center text-[14px] leading-[21px] text-[#8e8a97]", TR)}>내일 오전 10시에 새 문제가 열려요</p>
        </>
      )}
    </Box>
  );
}

/* ============ 투자 실험실 ============ */
type Dir = "상승" | "유지" | "하락";
const DIRC: Record<Dir, string> = { 상승: "#d93033", 유지: "#15171a", 하락: "#2f6fe0" };
const VARS: [string, string][] = [["원/달러 환율", "현재 1,384.5원 (예시)"], ["국제유가(WTI)", "현재 배럴당 71.2달러 (예시)"], ["한국 기준금리", "현재 2.50% (예시)"], ["미국 10년물 국채금리", "현재 4.32% (예시)"]];
function Lab() {
  const { studio, setStudio, sgo, stocks, setOverlay } = useApp();
  const start = useStartJob();
  const [open, setOpen] = useState(false);
  const cur = stocks.find((s) => s.name === studio.labStock) ?? stocks[0];
  const picked = VARS.filter(([n]) => (studio.labVars[n] ?? "유지") !== "유지");
  const run = () => {
    if (!picked.length) return;
    if (studio.creditOut) return setOverlay("credit");
    setStudio((s) => ({ ...s, lastJob: { title: `${cur.name} · ${picked.map(([n]) => n).join(" · ")} 실험`, meta: `투자 실험실 · ${cur.name} · 11.09` } }));
    start("lab", `${cur.name} · ${picked.map(([n]) => n.replace(/\(.*\)/, "")).join("·")} 실험`, `투자 실험실 · ${cur.name} · 11.09`);
  };
  return (
    <Box>
      <BackLink onClick={() => sgo("home", "pop")} />
      <FeatHead icon={SI.lab(23, "#15171A")} title="투자 실험실" sub="시장 환경을 바꿔 보고, 내 종목에 닿는 경로를 살펴봐요" />
      {/* v2: 변수 범위와 한계를 먼저 밝힘 (11.14 멘토링 반영) */}
      <div data-lab-limit className="flex w-full items-start gap-[10px] rounded-[14px] bg-[#f5f6f8] px-[14px] py-3">
        <span className="mt-[2px] grid h-[18px] w-[18px] shrink-0 place-items-center rounded-full border border-[#9aa3b2] text-[12px] font-bold leading-none text-[#747d8d]">i</span>
        <p className={cx("min-w-0 flex-1 text-[14px] leading-[21px] text-[#575b63]", TR)}>지금은 환율·유가·기준금리·미국 10년물 금리 4가지만 바꿀 수 있어요. 실제 주가는 이 밖의 많은 요인으로 움직여요. 예측이 아니라 영향 경로만 보여 드려요.</p>
      </div>
      <p className={cx("w-full text-[14px] font-bold leading-[1.5] text-[#8e8a97]", TR)}>실험할 종목</p>
      <div className="relative w-full">
        <button onClick={() => setOpen(!open)} className="flex h-[52px] w-full items-center justify-between rounded-[14px] border border-[#d9d9d9] px-[14px]">
          <span className="flex items-center gap-[6px]"><span className={cx("whitespace-nowrap text-[17px] font-bold leading-none text-[#15171a]", TR)}>{cur.name}</span><span className={cx("whitespace-nowrap text-[14px] leading-none text-[#8e8a97]", TR)}>· {cur.hold}</span></span>
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none" style={{ transform: open ? "rotate(180deg)" : "", transition: "transform .2s" }}><path d="M4.5 6.75L9 11.25L13.5 6.75" stroke="#404752" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
        </button>
        {open && (
          <div className="m-pop absolute left-0 right-0 top-[56px] z-20 flex flex-col overflow-hidden rounded-[14px] border border-[#d9d9d9] bg-white p-1">
            {stocks.map((s) => (
              <button key={s.code} onClick={() => { setStudio((x) => ({ ...x, labStock: s.name })); setOpen(false); }} className={cx("flex h-12 w-full items-center gap-[6px] rounded-[10px] px-[10px] text-left", s.name === cur.name ? "bg-[#f5f6f8]" : "hover:bg-[#f9f9f9]")}>
                <span className={cx("whitespace-nowrap text-[17px] font-bold leading-none text-[#15171a]", TR)}>{s.name}</span><span className={cx("whitespace-nowrap text-[14px] leading-none text-[#8e8a97]", TR)}>· {s.hold}</span>
              </button>
            ))}
          </div>
        )}
      </div>
      <p className={cx("w-full text-[14px] font-bold leading-[1.5] text-[#8e8a97]", TR)}>{picked.length ? "시장 환경 바꾸기 " : "시장 환경 바꾸기 · 바꾸고 싶은 것만"}</p>
      {VARS.map(([n, cur2]) => {
        const v = (studio.labVars[n] ?? "유지") as Dir;
        return (
          <div key={n} className="flex w-full flex-col gap-[10px] rounded-[16px] border border-[#e5e3e8] bg-white p-3">
            <div className="flex w-full items-center justify-between">
              <div className="flex flex-col"><p className={cx("whitespace-nowrap text-[17px] font-bold leading-[1.3] text-[#15171a]", TR)}>{n}</p><p className={cx("whitespace-nowrap text-[14px] leading-[1.3] text-[#8e8a97]", TR)}>{cur2}</p></div>
              <Chip color={v === "유지" ? "#404752" : DIRC[v]}>{v}</Chip>
            </div>
            <div className="flex w-full gap-1 rounded-[12px] bg-[#f5f6f8] p-1">
              {(["상승", "유지", "하락"] as Dir[]).map((d) => (
                <button key={d} onClick={() => setStudio((s) => ({ ...s, labVars: { ...s.labVars, [n]: d } }))} className={cx("flex h-10 min-w-0 flex-1 items-center justify-center rounded-[9px] text-[15px] font-bold leading-none transition-colors", TR, v === d ? "bg-white shadow-[0_1px_3px_rgba(0,0,0,0.08)]" : "text-[#8e8a97]")} style={v === d ? { color: DIRC[d] } : undefined}>{d}</button>
              ))}
            </div>
          </div>
        );
      })}
      <div className="flex w-full flex-col gap-2 rounded-[18px] bg-[#f5f6f8] p-[14px]">
        {picked.length ? (
          <>
            <p className={cx("w-full text-[15px] font-bold leading-[1.5] text-[#15171a]", TR)}>{cur.name}에 아래 시장 환경을 가정해요</p>
            <div className="flex w-full flex-wrap gap-[6px]">{picked.map(([n]) => <Chip key={n} color={DIRC[studio.labVars[n] as Dir]}>{n} · {studio.labVars[n]}</Chip>)}</div>
          </>
        ) : (
          <p className={cx("w-full text-[15px] font-bold leading-[1.5] text-[#8e8a97]", TR)}>바꾸고 싶은 시장 환경을 하나 이상 골라 주세요</p>
        )}
      </div>
      <div className="flex w-full items-start gap-2">
        <GBtn onClick={() => setStudio((s) => ({ ...s, labVars: {} }))}>초기화</GBtn>
        <GBtn flex dark disabled={!picked.length} onClick={run}>실험 실행</GBtn>
      </div>
    </Box>
  );
}
function LabResult() {
  const { sgo, go } = useApp();
  return (
    <div className="flex min-h-full flex-col">
      <SubHead title="실험 결과" onBack={() => sgo("lab", "pop")} />
      <div className="flex-1 px-4 pb-6 pt-2"><LabResultBody onAct={(a) => { if (a === "memo") go({ name: "stock", code: "000660", tab: "board" }); }} /></div>
      <div className="sticky bottom-0 flex w-full gap-2 border-t border-[#e5e7eb] bg-white px-4 py-3">
        <button onClick={() => sgo("lab", "pop")} className="flex min-w-0 flex-1 items-center justify-center rounded-[14px] bg-[#16171a] px-3 py-[14px] text-[17px] font-bold text-white">조건 바꿔 다시 실험</button>
      </div>
    </div>
  );
}
function ReportSum() {
  const { sgo, go } = useApp();
  return (
    <div className="flex min-h-full flex-col">
      <SubHead title="AI 주간보고서" onBack={() => sgo("home", "pop")} />
      <div className="px-4 pb-6 pt-[6px]"><ReportSummary onAct={(a) => { if (a === "detail") go({ name: "report" }); }} /></div>
    </div>
  );
}

/* ============ 팝업 (스튜디오) ============ */
const POP = "break-keep w-[468px] max-w-[calc(100vw-32px)] overflow-hidden rounded-[28px] bg-white shadow-[0px_30px_80px_0px_rgba(20,23,26,0.22)]";
const SCRIM = "rgba(21,23,26,0.4)";
function PopHead({ icon, title, sub, onClose, dark }: { icon: ReactNode; title: string; sub: string; onClose: () => void; dark?: boolean }) {
  return (
    <div className="flex w-full items-center gap-3">
      <span className={cx("grid h-11 w-11 shrink-0 place-items-center", dark ? "rounded-[14px] bg-[#15171a]" : "rounded-[13px] bg-[#f5f6f8]")}>{icon}</span>
      <div className="flex min-w-0 flex-1 flex-col gap-[2px]">
        <p className="whitespace-nowrap text-[22px] font-bold leading-[1.3] tracking-[-0.4px] text-[#15171a]">{title}</p>
        <p className={cx("whitespace-nowrap leading-[1.3] text-[#8e8a97]", TR, "text-[14px]")}>{sub}</p>
      </div>
      <button aria-label="닫기" onClick={onClose} className="-m-1 rounded-md p-1 hover:bg-[#f9f9f9]">{SI.close()}</button>
    </div>
  );
}
function CheckBox({ on }: { on: boolean }) {
  return <span className={cx("grid h-6 w-6 shrink-0 place-items-center rounded-[8px] transition-colors", on ? "bg-[#15171a]" : "border border-[#d9d9d9] bg-white")}>{on && <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2.91667 7.00065L5.54167 9.62565L11.0833 4.08398" stroke="white" strokeWidth="1.86667" strokeLinecap="round" strokeLinejoin="round" /></svg>}</span>;
}
function Presets({ sel, set, stocks }: { sel: string[]; set: (v: string[]) => void; stocks: { code: string; hold: string }[] }) {
  const all = stocks.map((s) => s.code), hold = stocks.filter((s) => s.hold === "보유").map((s) => s.code), watch = stocks.filter((s) => s.hold === "관심").map((s) => s.code);
  const eq = (a: string[]) => a.length === sel.length && a.every((x) => sel.includes(x));
  return (
    <div className="flex w-full items-start gap-[6px]">
      {([["전체 종목", all], ["보유 종목 전체", hold], ["관심 종목 전체", watch]] as const).map(([l, v]) => (
        <button key={l} onClick={() => set([...v])} className={cx("flex h-10 shrink-0 items-center rounded-full px-4 text-[15px] font-bold leading-none", TR, eq([...v]) ? "bg-[#15171a] text-white" : "border border-[#d9d9d9] bg-white text-[#404752] hover:bg-[#f9f9f9]")}>{l}</button>
      ))}
    </div>
  );
}
const AUDIO_N: Record<string, Record<string, number>> = { d1: { "000660": 3, "005930": 1, "035420": 1 }, d3: { "000660": 4, "005930": 2, "035420": 1 }, d7: { "000660": 4, "005930": 2, "035420": 2 } };
export function AudioPopup() {
  const { overlay, setOverlay, stocks, demo, setStudio, preset, setPreset } = useApp();
  const start = useStartJob();
  const open = overlay === "audio";
  const [sel, setSel] = useState<string[]>(stocks.map((s) => s.code));
  const [sum, setSum] = useState(true);
  const [per, setPer] = useState<"d1" | "d3" | "d7">("d1");
  useEffect(() => { if (open) { const pre = preset?.codes?.filter((c) => stocks.some((s) => s.code === c)); setSel(pre?.length ? pre : stocks.map((s) => s.code)); setSum(!demo.noNews); setPer("d1"); if (preset) setPreset(null); } }, [open]); // eslint-disable-line -- v2: 넛지에서 오면 그 종목만 미리 고름
  const n = (c: string) => (demo.noNews && per !== "d7" ? 0 : AUDIO_N[per][c] ?? 0);
  const total = sel.reduce((a, c) => a + n(c), 0);
  const empty = total === 0 && !sum;
  const close = () => setOverlay(null);
  const make = () => { setStudio((s) => ({ ...s, lastJob: { title: "11.09 내 종목 라디오", meta: `AI 오디오 · ${sel.length}종목 · 11.09` } })); start("audio", "11.09 내 종목 라디오", `AI 오디오 · ${sel.length}종목 · 11.09`); };
  return (
    <Modal open={open} onClose={close} label="AI 오디오 만들기" scrim={SCRIM}>
      <div className={POP}>
        <div className="px-[22px] pb-3 pt-[22px]"><PopHead icon={SI.wave(22, "#15171A")} title="AI 오디오 만들기" sub="들을 종목과 기간을 골라 주세요" onClose={close} /></div>
        <div className="flex w-full flex-col gap-[14px] px-[22px] pb-4 pt-1">
          <Presets sel={sel} set={setSel} stocks={stocks} />
          <div className="flex w-full flex-col gap-[2px] rounded-[18px] border border-[#e5e3e8] p-[6px]">
            {stocks.map((s) => (
              <button key={s.code} onClick={() => setSel((a) => (a.includes(s.code) ? a.filter((x) => x !== s.code) : [...a, s.code]))} className="flex h-[58px] w-full items-center gap-3 rounded-[14px] px-3 text-left hover:bg-[#f9f9f9]">
                <CheckBox on={sel.includes(s.code)} />
                <span className={cx("min-w-0 flex-1 text-[17px] font-bold leading-none text-[#15171a]", TR)}>{s.name}</span>
                <span className={cx("whitespace-nowrap text-[14px] leading-none text-[#8e8a97]", TR)}>{n(s.code) ? `새 업데이트 ${n(s.code)}건` : "새 업데이트 없음"}</span>
                <Chip>{s.hold}</Chip>
              </button>
            ))}
            <span className="h-px w-full bg-[#e8ecf3]" />
            <button onClick={() => setSum(!sum)} className="flex w-full items-center gap-3 rounded-[14px] px-3 py-[10px] text-left hover:bg-[#f9f9f9]">
              <CheckBox on={sum} />
              <span className="flex min-w-0 flex-1 flex-col gap-[1px]"><span className={cx("whitespace-nowrap text-[17px] font-bold leading-[1.3] text-[#15171a]", TR)}>직전 거래일 증시 요약</span><span className={cx("whitespace-nowrap text-[14px] leading-[1.3] text-[#8e8a97]", TR)}>11.06(금) 코스피·코스닥·원/달러</span></span>
              <Chip>+1</Chip>
            </button>
          </div>
          <p className={cx("w-full text-[14px] font-bold leading-[1.5] text-[#8e8a97]", TR)}>업데이트 기간</p>
          <div className="flex w-full gap-1 rounded-[12px] bg-[#f5f6f8] p-1">
            {([["d1", "전날"], ["d3", "최근 3일"], ["d7", "최근 7일"]] as const).map(([k2, l]) => (
              <button key={k2} onClick={() => setPer(k2)} className={cx("flex h-10 min-w-0 flex-1 items-center justify-center rounded-[9px] text-[15px] font-bold leading-none transition-colors", TR, per === k2 ? "bg-white text-[#15171a] shadow-[0_1px_3px_rgba(0,0,0,0.08)]" : "text-[#8e8a97]")}>{l}</button>
            ))}
          </div>
          {empty && (
            <div className="m-pop flex w-full items-center gap-3 rounded-[18px] bg-[#fff4e5] px-4 py-[14px]">
              <div className="flex min-w-0 flex-1 flex-col gap-[3px]">
                <p className={cx("whitespace-nowrap text-[15px] font-bold leading-[1.3] text-[#7a4a00]", TR)}>새로 들려줄 소식이 없어요</p>
                <p className={cx("w-full text-[14px] leading-[1.5] text-[#7a4a00]", TR)}>고른 종목에 {per === "d1" ? "전날" : "최근 3일 동안"} 생긴 업데이트가 없어요. 기간을 늘리거나 증시 요약을 넣으면 만들 수 있어요.</p>
              </div>
            </div>
          )}
        </div>
        <div className="flex w-full items-start gap-2 px-[22px] pb-5 pt-3">
          {empty ? <GBtn h={48} onClick={() => setPer("d7")}>최근 7일로 늘리기</GBtn> : <GBtn h={48} onClick={close}>취소</GBtn>}
          <GBtn h={48} flex dark disabled={empty || !sel.length && !sum} onClick={make}>{empty ? "만들 소식이 없어요" : "오디오 만들기"}</GBtn>
        </div>
      </div>
    </Modal>
  );
}
const REP_N: Record<string, string> = { "000660": "공시 2 · 뉴스 2", "005930": "공시 1 · 뉴스 1", "035420": "공시 0 · 뉴스 2" };
export function ReportPopup() {
  const { overlay, setOverlay, stocks, setStudio, preset, setPreset } = useApp();
  const start = useStartJob();
  const open = overlay === "reportPick";
  const [sel, setSel] = useState<string[]>(stocks.map((s) => s.code));
  const [sum, setSum] = useState(false);
  useEffect(() => { if (open) { const pre = preset?.codes?.filter((c) => stocks.some((s) => s.code === c)); setSel(pre?.length ? pre : stocks.map((s) => s.code)); setSum(false); if (preset) setPreset(null); } }, [open]); // eslint-disable-line -- v2: 넛지에서 오면 그 종목만 미리 고름
  const close = () => setOverlay(null);
  const make = () => { setStudio((s) => ({ ...s, lastJob: { title: "이번 주 내 종목 보고서", meta: `주간보고서 · ${sel.length}종목 · 11.09` } })); start("report", "이번 주 내 종목 보고서", `주간보고서 · ${sel.length}종목 · 11.09`); };
  return (
    <Modal open={open} onClose={close} label="주간보고서 만들기" scrim={SCRIM}>
      <div className={POP}>
        <div className="px-[22px] pb-3 pt-[22px]"><PopHead icon={SI.report(22, "#15171A")} title="주간보고서 만들기" sub="최근 7일(11.03 – 11.09) 보고서에 넣을 종목" onClose={close} /></div>
        <div className="flex w-full flex-col gap-[14px] px-[22px] pb-4 pt-1">
          <Presets sel={sel} set={setSel} stocks={stocks} />
          <div className="flex w-full flex-col gap-[2px] rounded-[18px] border border-[#e5e3e8] p-[6px]">
            {stocks.map((s) => (
              <button key={s.code} onClick={() => setSel((a) => (a.includes(s.code) ? a.filter((x) => x !== s.code) : [...a, s.code]))} className="flex h-[58px] w-full items-center gap-3 rounded-[14px] px-3 text-left hover:bg-[#f9f9f9]">
                <CheckBox on={sel.includes(s.code)} />
                <span className={cx("min-w-0 flex-1 text-[17px] font-bold leading-none text-[#15171a]", TR)}>{s.name}</span>
                <span className={cx("whitespace-nowrap text-[14px] leading-none text-[#8e8a97]", TR)}>{REP_N[s.code] ?? "공시 0 · 뉴스 0"}</span>
                <Chip>{s.hold}</Chip>
              </button>
            ))}
            <span className="h-px w-full bg-[#e8ecf3]" />
            <button onClick={() => setSum(!sum)} className="flex w-full items-center gap-3 rounded-[14px] px-3 py-[10px] text-left hover:bg-[#f9f9f9]">
              <CheckBox on={sum} />
              <span className="flex min-w-0 flex-1 flex-col gap-[1px]"><span className={cx("whitespace-nowrap text-[17px] font-bold leading-[1.3] text-[#15171a]", TR)}>국내 증시 주간 요약</span><span className={cx("whitespace-nowrap text-[14px] leading-[1.3] text-[#8e8a97]", TR)}>코스피·코스닥·원/달러 한 주 흐름</span></span>
              <Chip>+1</Chip>
            </button>
          </div>
        </div>
        <div className="flex w-full items-start gap-2 px-[22px] pb-5 pt-3">
          <GBtn h={48} onClick={close}>취소</GBtn>
          <GBtn h={48} flex dark disabled={!sel.length && !sum} onClick={make}>보고서 만들기</GBtn>
        </div>
      </div>
    </Modal>
  );
}
export function CreditPopup() {
  const { overlay, setOverlay, openSettings, setPlanOpen, setPreset } = useApp();
  const close = () => { setPreset(null); setOverlay(null); };
  return (
    <Modal open={overlay === "credit"} onClose={close} label="이 기능부터는 PLUS예요" scrim={SCRIM}>
      <div className="flex w-[400px] max-w-[calc(100vw-32px)] break-keep flex-col items-start gap-[14px] overflow-hidden rounded-[28px] bg-white px-6 pb-[22px] pt-6 shadow-[0px_30px_80px_0px_rgba(20,23,26,0.22)]">
        <span className="grid h-[52px] w-[52px] place-items-center rounded-[16px] bg-[#15171a]">{SI.bolt(26, "white")}</span>
        <p className="whitespace-nowrap text-[22px] font-bold leading-[1.3] tracking-[-0.4px] text-[#15171a]">이 기능부터는 PLUS예요</p>
        <p className={cx("w-full text-[15px] leading-[1.55] text-[#8e8a97]", TR)}>이번 달 무료 크레딧을 다 썼어요. PLUS에서는 매달 더 많이 만들 수 있어요. 이미 만든 항목과 오늘의 퀴즈는 계속 쓸 수 있어요.</p>
        <div className="flex w-full items-start gap-2">
          <GBtn h={48} flex onClick={close}>닫기</GBtn>
          <GBtn h={48} flex dark onClick={() => { setPreset(null); setPlanOpen(true); openSettings("사용량"); }}>PLUS 살펴보기</GBtn>
        </div>
        <button onClick={() => { setPreset(null); setOverlay("charge"); }} className={cx("w-full text-center text-[14px] font-bold leading-[21px] text-[#8e8a97] underline underline-offset-2 hover:text-[#15171a]", TR)}>이번만 크레딧 충전하기</button>
      </div>
    </Modal>
  );
}
export function ChargePopup() {
  const { overlay, setOverlay, setStudio } = useApp();
  const open = overlay === "charge";
  const [pk, setPk] = useState("300");
  const [pay, setPay] = useState("카드");
  const [agree, setAgree] = useState(true);
  const [paid, setPaid] = useState(false);
  useEffect(() => { if (open) { setPk("300"); setPay("카드"); setAgree(true); setPaid(false); } }, [open]);
  const close = () => setOverlay(null);
  return (
    <Modal open={open} onClose={close} label="크레딧 충전" scrim={SCRIM}>
      <div className={cx(POP, "flex flex-col items-start gap-[14px] px-6 pb-[22px] pt-6")}>
        <PopHead dark icon={SI.bolt(22, "white")} title="크레딧 충전" sub="충전한 크레딧은 바로 쓸 수 있어요" onClose={close} />
        <div className="flex w-full flex-col gap-2">
          {([["100", "100 크레딧"], ["300", "300 크레딧"], ["1000", "1,000 크레딧"]] as const).map(([k2, l]) => (
            <button key={k2} onClick={() => !paid && setPk(k2)} className={cx("flex w-full items-center gap-3 overflow-hidden rounded-[16px] px-4 py-[14px] text-left transition-colors", pk === k2 ? "border-[1.5px] border-[#15171a] bg-[#f5f6f8]" : "border border-[#e5e3e8] bg-white hover:bg-[#f9f9f9]")}>
              <span className={cx("h-5 w-5 shrink-0 rounded-full transition-[border-width]", pk === k2 ? "border-[6px] border-[#15171a]" : "border-2 border-[#d9d9d9]")} />
              <span className="flex min-w-0 flex-1 items-center gap-2">
                <span className={cx("whitespace-nowrap text-[17px] font-bold leading-none text-[#15171a]", TR)}>{l}</span>
                {k2 === "300" && <span className={cx("flex h-[22px] items-center rounded-full bg-[#15171a] px-[9px] text-[13px] font-bold leading-none text-white", TR)}>많이 쓰는 분께</span>}
              </span>
              <span className={cx("whitespace-nowrap text-[17px] font-bold leading-none text-[#15171a]", TR)}>[가격]</span>
            </button>
          ))}
        </div>
        <p className={cx("w-full text-[14px] leading-[1.5] text-[#8e8a97]", TR)}>상품 구성·가격은 팀 확정 전 임시예요.</p>
        <p className={cx("w-full text-[14px] font-bold leading-[1.5] text-[#8e8a97]", TR)}>결제 수단</p>
        <div className="flex w-full items-start gap-2">
          {["카드", "간편결제", "계좌이체"].map((m) => (
            <button key={m} onClick={() => !paid && setPay(m)} className={cx("flex h-11 min-w-0 flex-1 items-center justify-center rounded-[12px] text-[15px] font-bold leading-none", TR, pay === m ? "bg-[#15171a] text-white" : "border border-[#e5e3e8] bg-white text-[#15171a] hover:bg-[#f9f9f9]")}>{m}</button>
          ))}
        </div>
        <button onClick={() => setAgree(!agree)} className="flex w-full items-start gap-2 rounded-[12px] bg-[#f5f6f8] px-[14px] py-3 text-left">
          {agree ? <svg width="18" height="18" viewBox="0 0 18 18" fill="none" className="shrink-0"><path d="M11.25 3H6.75C4.67893 3 3 4.67893 3 6.75V11.25C3 13.3211 4.67893 15 6.75 15H11.25C13.3211 15 15 13.3211 15 11.25V6.75C15 4.67893 13.3211 3 11.25 3Z" fill="#15171A" /><path d="M6 9L8.25 11.25L12 6.75" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
            : <svg width="18" height="18" viewBox="0 0 18 18" fill="none" className="shrink-0"><path d="M11.25 3.75H6.75C5.09315 3.75 3.75 5.09315 3.75 6.75V11.25C3.75 12.9069 5.09315 14.25 6.75 14.25H11.25C12.9069 14.25 14.25 12.9069 14.25 11.25V6.75C14.25 5.09315 12.9069 3.75 11.25 3.75Z" stroke="#d9d9d9" strokeWidth="1.5" fill="white" /></svg>}
          <span className={cx("min-w-0 flex-1 text-[14px] leading-[1.55] text-[#404752]", TR)}>구매한 크레딧 중 쓰지 않은 만큼만 환불돼요. 다른 사람에게 넘기거나 현금으로 바꿀 수 없어요. (약관 동의)</span>
        </button>
        <GBtn h={48} dark disabled={!agree && !paid} onClick={() => { if (paid) return; setPaid(true); setStudio((s) => ({ ...s, creditOut: false })); }} className="w-full">{paid ? "결제 완료" : `${pk === "1000" ? "1,000" : pk} 크레딧 결제하기`}</GBtn>
        <p className={cx("w-full text-center text-[14px] leading-[1.5] text-[#8e8a97]", TR)}>앱에서는 Google Play 결제로 진행돼요.</p>
      </div>
    </Modal>
  );
}
