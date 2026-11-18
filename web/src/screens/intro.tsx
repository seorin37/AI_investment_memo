/* 00 · 로그인 전 서비스 소개 3장 (11.14 멘토링 반영)
   문제 → 해결 → 시작. 한 장에 큰 글씨 한 문장 + 작은 글씨 한 줄. 건너뛰기 가능, 끝나면 로그인으로.
   Lucian UX/UI Prompt #042 · MIT License (c) 2026 Seokwoooo · https://lucianlabs.dev/uxui-prompt/#042 — 본문이 나아가는 방향으로 밀려 바뀌는 움직임을 가져옴 */
import { useEffect, useState, type ReactNode } from "react";
import { cx } from "../kit";
import { useApp } from "../store";
import { LOGIN_LOGO } from "../assets_wm";
import { SI } from "../studio";

const CHIP: Record<string, string> = { 공시: "bg-[#fbeded] text-[#e5484d]", 뉴스: "bg-[#e8edf5] text-black", 주가: "bg-[#e6f0e2] text-[#1e8e4e]", 리포트: "bg-[#f1eefb] text-[#5e5668]" };
const Kind = ({ k }: { k: string }) => <span className={cx("flex h-[22px] shrink-0 items-center rounded-[6px] px-[7px] text-[13px] font-medium leading-none", CHIP[k])}>{k}</span>;
const Bar = ({ w, dark }: { w: number; dark?: boolean }) => <span className="block h-[7px] rounded-full" style={{ width: w, background: dark ? "#c9cdd4" : "#e3e6ea" }} />;

/* 1 · 문제: 끝없이 올라오는 공시·뉴스·리포트 */
const FLOW: [string, number, number][][] = [
  [["공시", 84, 52], ["뉴스", 70, 90], ["리포트", 92, 60], ["뉴스", 64, 78], ["공시", 88, 48], ["주가", 58, 84]],
  [["뉴스", 78, 64], ["리포트", 90, 50], ["공시", 66, 88], ["주가", 82, 56], ["뉴스", 72, 92], ["공시", 94, 62]],
  [["주가", 62, 80], ["공시", 90, 58], ["뉴스", 74, 86], ["리포트", 86, 54], ["뉴스", 68, 76], ["공시", 80, 66]],
];
function ArtFlood() {
  return (
    <div className="relative h-full w-full overflow-hidden">
      <div className="absolute inset-x-2 top-0 flex gap-4">
        {FLOW.map((col, ci) => (
          <div key={ci} className="v2-flow flex min-w-0 flex-1 flex-col" style={{ ["--d" as string]: `${[22, 17, 26][ci]}s` }}>
            {[...col, ...col].map(([k, a, b], i) => (
              <div key={i} className="mb-3 flex h-[52px] w-full shrink-0 items-center gap-[10px] rounded-[12px] border border-[#e9ebee] bg-white px-3">
                <Kind k={k} />
                <span className="flex min-w-0 flex-1 flex-col gap-[6px]"><Bar w={a} dark /><Bar w={b} /></span>
              </div>
            ))}
          </div>
        ))}
      </div>
      <div className="pointer-events-none absolute inset-x-0 top-0 h-14 bg-gradient-to-b from-[#f4f5f7] to-[#f4f5f7]/0" />
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-14 bg-gradient-to-t from-[#f4f5f7] to-[#f4f5f7]/0" />
    </div>
  );
}

/* 2 · 해결: 메모 한 줄 → AI가 붙여 주는 소식 */
const PlugOn = () => <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M5.25 1.75V4.08333M8.75 1.75V4.08333" stroke="black" strokeWidth="1.2" strokeLinecap="round" /><path d="M3.7915 4.08301H10.2082V6.41634C10.2082 7.26724 9.87015 8.0833 9.26847 8.68498C8.66679 9.28665 7.85074 9.62467 6.99984 9.62467C6.14893 9.62467 5.33288 9.28665 4.7312 8.68498C4.12952 8.0833 3.7915 7.26724 3.7915 6.41634V4.08301Z" fill="#16161C" /><path d="M7 9.625V12.25" stroke="black" strokeWidth="1.2" strokeLinecap="round" /></svg>;
export function ArtAttach() {
  return (
    <div className="flex h-full w-full items-center justify-center gap-3 px-6">
      <div className="v2-rise dk-keep relative h-[152px] w-[184px] shrink-0" style={{ ["--i" as string]: 0 }}>
        <div className="flex h-full w-full flex-col items-start gap-2 rounded-[16px_16px_0px_16px] bg-[#fceaaa] px-4 pb-8 pt-[14px]">
          <div className="flex w-full items-center justify-between">
            <p className="whitespace-nowrap text-[13px] font-medium leading-[20px] text-[#4a4a55]">내 메모</p>
            <span className="grid h-7 w-7 place-items-center rounded-full bg-white/80"><PlugOn /></span>
          </div>
          <p className="w-full break-keep text-[20px] font-bold leading-[1.36] text-[#16161c]">HBM 수요 계속 갈까?</p>
        </div>
        <svg className="absolute bottom-0 right-0" width="30" height="30" viewBox="0 0 30 30" fill="none"><path d="M30 0V30H0L30 0Z" fill="#F4F5F7" /><path d="M0 9C0 3 3 0 9 0H30L0 30V9Z" fill="#efbf2a" /></svg>
      </div>
      <div className="relative h-[2px] w-9 shrink-0 rounded-full bg-[#d5d8dd]"><span className="v2-dotrun absolute top-[-2px] h-[6px] w-[6px] rounded-full bg-[#111]" /></div>
      <div className="flex min-w-0 flex-1 flex-col gap-[10px]">
        {([["뉴스", "#e3edff", "#3d73f0", "HBM4 공급 확대 소식이 나왔어요"], ["공시", "#eee8ff", "#7046f5", "3분기 실적 발표가 예정돼 있어요"]] as const).map(([k, bg, bar, t], i) => (
          <div key={k} className="v2-rise relative flex h-[66px] w-full items-center overflow-hidden rounded-[14px] pl-4 pr-3" style={{ background: bg, ["--i" as string]: i + 2 }}>
            <span className="absolute left-0 top-[18px] h-[30px] w-[3px] rounded-[1.5px]" style={{ background: bar }} />
            <span className="flex min-w-0 flex-col gap-[2px]">
              <span className="whitespace-nowrap text-[13px] font-medium leading-[20px] text-[#575b63]">{k} · AI가 찾아 붙임</span>
              <span className="truncate text-[15px] font-bold leading-[23px] text-[#15171a]">{t}</span>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* 3 · 시작: 라디오와 주간보고서 */
function ArtStudio() {
  return (
    <div className="flex h-full w-full items-center justify-center gap-4 px-6">
      <div className="v2-rise flex h-[168px] min-w-0 flex-1 flex-col items-start justify-between rounded-[18px] border border-[#e5e7eb] bg-white p-4" style={{ ["--i" as string]: 0 }}>
        <div className="flex w-full items-center gap-[10px]">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-[12px] bg-[#d6e4ff]">{SI.wave()}</span>
          <span className="flex min-w-0 flex-col"><span className="whitespace-nowrap text-[15px] font-bold leading-[23px] text-[#16171a]">AI 오디오</span><span className="whitespace-nowrap text-[13px] leading-[20px] text-[#8e8a97]">내 종목 라디오</span></span>
        </div>
        <div className="wave flex h-9 w-full items-center justify-center gap-[5px]">{[14, 26, 18, 34, 22, 30, 12, 28, 20, 32, 16, 24].map((h, i) => <i key={i} className="block w-[4px] rounded-full bg-[#2f6bdb]" style={{ height: h, animationDelay: `${i * 0.09}s`, opacity: 0.85 }} />)}</div>
        <div className="flex w-full items-center gap-[10px]">
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-[#15171a]">{SI.play(16)}</span>
          <span className="relative h-[4px] min-w-0 flex-1 rounded-full bg-[#eceef1]"><span className="absolute left-0 top-0 h-[4px] w-[38%] rounded-full bg-[#15171a]" /></span>
        </div>
      </div>
      <div className="v2-rise flex h-[168px] min-w-0 flex-1 flex-col items-start justify-between rounded-[18px] border border-[#e5e7eb] bg-white p-4" style={{ ["--i" as string]: 1 }}>
        <div className="flex w-full items-center gap-[10px]">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-[12px] bg-[#ffdadb]">{SI.report()}</span>
          <span className="flex min-w-0 flex-col"><span className="whitespace-nowrap text-[15px] font-bold leading-[23px] text-[#16171a]">AI 주간보고서</span><span className="whitespace-nowrap text-[13px] leading-[20px] text-[#8e8a97]">한 주를 한 장으로</span></span>
        </div>
        <svg width="100%" height="40" viewBox="0 0 200 40" preserveAspectRatio="none" fill="none"><path d="M0 30L28 26L56 29L84 18L112 21L140 10L168 13L200 4" stroke="#E5484D" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" /><path d="M0 30L28 26L56 29L84 18L112 21L140 10L168 13L200 4V40H0Z" fill="#E5484D" fillOpacity="0.08" /></svg>
        <div className="flex w-full flex-col gap-[7px]"><Bar w={170} dark /><Bar w={120} /></div>
      </div>
    </div>
  );
}

const PAGES: { t: string; d: string; art: () => ReactNode }[] = [
  { t: "정보는 넘치는데,\n내 종목엔 뭐가 중요할까요?", d: "공시·뉴스·리포트를 다 읽을 시간은 없죠.", art: () => <ArtFlood /> },
  { t: "떠오른 생각 한 줄이면\n충분해요", d: "“HBM 수요 계속 갈까?”처럼 적어 두면, AI가 관련 공시·뉴스를 매일 대신 확인해 붙여 드려요.", art: () => <ArtAttach /> },
  { t: "바쁠 땐 듣고,\n주말엔 한 번에", d: "쌓인 소식은 라디오나 주간보고서로 받아 보세요.", art: () => <ArtStudio /> },
];

export function Intro() {
  const { go } = useApp();
  const [cur, setCur] = useState(0);
  const last = cur === PAGES.length - 1;
  const done = () => go({ name: "login" });
  const next = () => (last ? done() : setCur((c) => c + 1));
  const prev = () => setCur((c) => Math.max(0, c - 1));
  useEffect(() => {
    const f = (e: KeyboardEvent) => { if (e.key === "ArrowRight") setCur((c) => Math.min(PAGES.length - 1, c + 1)); if (e.key === "ArrowLeft") setCur((c) => Math.max(0, c - 1)); };
    window.addEventListener("keydown", f); return () => window.removeEventListener("keydown", f);
  }, []);
  return (
    <div className="flex h-full min-h-[600px] w-full flex-col items-center justify-center overflow-auto bg-[#fdfdfd] py-8">
      <div data-intro className="m-pop relative flex w-[640px] max-w-[calc(100vw-32px)] shrink-0 flex-col rounded-[24px] border border-[#e5e8eb] bg-white px-14 pb-8 pt-6">
        <div className="flex h-[42px] items-center justify-between">
          <img src={LOGIN_LOGO} alt="MEMO'S" className="h-[34px] w-[102px]" draggable={false} />
          <div className="flex items-center gap-[22px]">
            <div className="flex h-[6px] items-center gap-[6px]" aria-label={`3장 중 ${cur + 1}장`}>
              {PAGES.map((_, i) => <span key={i} className="h-[6px] rounded-full transition-all" style={{ width: i === cur ? 18 : 6, background: i === cur ? "#111111" : "#d5d8dd", transitionDuration: "calc(.3s * var(--k))" }} />)}
            </div>
            <button onClick={done} className="text-[15px] leading-[23px] text-[#667085] hover:text-[#18181c]">건너뛰기</button>
          </div>
        </div>
        <div className="u042-view -mx-2 mt-5 h-[404px]" aria-live="polite">
          {PAGES.map((p, i) => (
            <section key={i} aria-hidden={i !== cur} className={cx("u042-pane flex flex-col px-2", i === cur && "on")} style={{ opacity: i === cur ? 1 : 0, transform: i === cur ? "none" : `translateX(${i < cur ? -40 : 40}%)`, pointerEvents: i === cur ? undefined : "none" }}>
              <div className="h-[236px] w-full shrink-0 overflow-hidden rounded-[20px] bg-[#f4f5f7]">{p.art()}</div>
              <p className="mt-7 whitespace-pre-line break-keep text-[30px] font-bold leading-[40px] text-[#18181c]">{p.t}</p>
              <p className="mt-2 break-keep text-[15px] leading-[23px] text-[#8b919c]">{p.d}</p>
            </section>
          ))}
        </div>
        <div className="mt-6 flex gap-2">
          {cur > 0 && <button onClick={prev} className="u042-b flex h-14 w-[96px] shrink-0 items-center justify-center rounded-[16px] bg-[#f2f2f5] text-[17px] font-bold leading-[26px] text-[#18181c] hover:bg-[#e8e8ec]">이전</button>}
          <button onClick={next} className="u042-b flex h-14 min-w-0 flex-1 items-center justify-center rounded-[16px] bg-[#111] text-[17px] font-bold leading-[26px] text-white hover:bg-[#2a2a2a]">{last ? "시작하기" : "다음"}</button>
        </div>
      </div>
    </div>
  );
}
