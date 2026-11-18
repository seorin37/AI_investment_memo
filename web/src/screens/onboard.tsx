/* 01.1 약관 동의 · 01.1a 약관 본문 · 가입 중 뒤로 가기 확인 창 · 01.2 관심 종목 고르기
   Figma page 3(앱) 내용을 로그인처럼 가운데 카드에, 보라 → 검정 (11.13) */
import { useEffect, useState, type ReactNode } from "react";
import { cx } from "../kit";
import { useApp, useSession } from "../store";
import { LEGAL } from "../legal";
import type { Hold } from "../data";
import { api } from "../api";

const INK = "#111111";
const Check = ({ on, size = 26, delay = 0 }: { on: boolean; size?: number; delay?: number }) => (
  <span className="flex shrink-0 items-center justify-center rounded-full transition-colors" style={{ width: size, height: size, background: on ? INK : "#d5d8dd", transitionDelay: `calc(${delay}ms * var(--k))`, transitionDuration: "calc(.2s * var(--k))" }}>
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2.5 6.2L5 8.6L9.5 3.6" stroke="white" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" /></svg>
  </span>
);
const Back = ({ onClick, label = "뒤로" }: { onClick: () => void; label?: string }) => (
  <button aria-label={label} onClick={onClick} className="-ml-[10px] flex h-[42px] w-[42px] items-center justify-center rounded-full hover:bg-[#f3f4f6]">
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none"><path d="M13.5 4.5L7.5 11L13.5 17.5" stroke="#18181c" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
  </button>
);
const Progress = ({ step }: { step: 0 | 1 }) => (
  <div className="flex h-[6px] items-center gap-[6px]" aria-label={`3단계 중 ${step + 1}단계`}>
    {[0, 1, 2].map((i) => <span key={i} className="h-[6px] rounded-full transition-all" style={{ width: i === step ? 18 : 6, background: i === step ? INK : "#d5d8dd" }} />)}
  </div>
);
const CTA = ({ on, onClick, children }: { on: boolean; onClick: () => void; children: ReactNode }) => (
  <button disabled={!on} onClick={onClick} className={cx("flex h-14 w-full shrink-0 items-center justify-center rounded-[16px] text-[17px] font-bold leading-[26px] text-white transition-colors", on ? "bg-[#111] hover:bg-[#2a2a2a]" : "cursor-not-allowed bg-[#d0d3d9]")}>{children}</button>
);
function Card({ children }: { children: ReactNode }) {
  return (
    <div data-onboard-scroll className="flex h-full w-full flex-col items-center overflow-y-auto bg-[#fdfdfd] py-8">
      <div className="m-pop relative my-auto flex w-[640px] shrink-0 max-w-[calc(100vw-32px)] flex-col rounded-[24px] border border-[#e5e8eb] bg-white px-14 pb-8 pt-6">{children}</div>
    </div>
  );
}

/* ---------- 01.1 약관 ---------- */
/* 11.16 앱 통일(사용자 결정): 필수 3개 + 체크 없는 처리방침 링크, 전문 3개는 Codex 문서 본문 전체, 전문을 열고 닫아도 체크는 그대로 */
type DocK = "terms" | "privacy" | "invest";
const TERMS: { k: string; t: string; view?: DocK }[] = [
  { k: "age", t: "[필수] 만 14세 이상이에요" },
  { k: "svc", t: "[필수] 서비스 이용약관에 동의해요", view: "terms" },
  { k: "inv", t: "[필수] 투자 정보 이용 안내를 확인했어요", view: "invest" },
];
export function Terms() {
  const { go } = useApp();
  const sess = useSession();
  const [ok, setOk] = useState<Record<string, boolean>>({});
  const [doc, setDoc] = useState<null | DocK>(null);
  const [leave, setLeave] = useState(false);
  const all = TERMS.every((t) => ok[t.k]);
  const [cascade, setCascade] = useState(false);
  const toggleAll = () => { const v = !all; setCascade(true); setOk(Object.fromEntries(TERMS.map((t) => [t.k, v]))); window.setTimeout(() => setCascade(false), 600); };
  useEffect(() => { const f = (e: KeyboardEvent) => { if (e.key === "Escape") { if (doc) setDoc(null); else setLeave((l) => !l); } }; window.addEventListener("keydown", f); return () => window.removeEventListener("keydown", f); }, [doc]);

  if (doc) {
    const d = LEGAL[doc];
    return (
      <Card>
        <div key={doc} className="m-in flex flex-col">
          <div className="flex h-[42px] items-center gap-1"><Back onClick={() => setDoc(null)} /><p className="text-[17px] font-bold leading-[26px] text-[#18181c]">{d.t}</p></div>
          <div data-legal className="legal mt-4 max-h-[min(520px,calc(100vh-260px))] overflow-y-auto pr-2" dangerouslySetInnerHTML={{ __html: d.h }} />
          <div className="mt-6"><CTA on onClick={() => setDoc(null)}>닫기</CTA></div>
        </div>
      </Card>
    );
  }
  return (
    <Card>
      <div className="flex h-[42px] items-center justify-between"><Back onClick={() => setLeave(true)} /><Progress step={0} /></div>
      <p className="mt-[17px] whitespace-pre-line text-[26px] font-bold leading-[35px] text-[#18181c]">{"memo's를 시작하기 전에\n확인해 주세요"}</p>
      <p className="mt-[6px] text-[14px] leading-[21px] text-[#a4a8b3]">필수 항목을 확인하고 시작해요.</p>
      <button onClick={toggleAll} aria-pressed={all} className="-mx-1 mt-6 flex h-[58px] items-center gap-3 rounded-[16px] bg-[#f2f2f5] px-4 text-left hover:bg-[#ececf0]">
        <Check on={all} /><span className="text-[17px] font-bold leading-[26px] text-[#18181c]">필수 항목 모두 확인하기</span>
      </button>
      <div className="mt-2 flex flex-col">
        {TERMS.map((t, i) => (
          <div key={t.k} className="flex min-h-[54px] items-center gap-3 py-[14px] pl-[5px]">
            <button role="checkbox" aria-checked={!!ok[t.k]} aria-label={t.t} onClick={() => setOk((o) => ({ ...o, [t.k]: !o[t.k] }))} className="flex min-w-0 flex-1 items-center gap-3 text-left">
              <Check on={!!ok[t.k]} delay={cascade ? i * 90 : 0} />
              <span className="min-w-0 flex-1 text-[15px] leading-[1.5] text-[#2e2e38]">{t.t}</span>
            </button>
            {t.view && <button onClick={() => setDoc(t.view!)} className="flex shrink-0 items-center gap-[2px] text-[13px] leading-[20px] text-[#a4a8b3] hover:text-[#575b63]">보기<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M5.5 3.5L9 7L5.5 10.5" stroke="currentColor" strokeWidth="1.17" strokeLinecap="round" strokeLinejoin="round" /></svg></button>}
          </div>
        ))}
      </div>
      <button data-privacy-link onClick={() => setDoc("privacy")} className="mx-auto mt-8 flex items-center gap-[2px] text-[14px] font-medium leading-[21px] text-[#575b63] underline-offset-2 hover:underline">개인정보 처리방침 확인하기<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M5.25 3.5L8.75 7L5.25 10.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg></button>
      <p className="mt-2 text-center text-[13px] leading-[20px] text-[#a4a8b3]">이 화면의 약관 문구는 초안이에요 · 출시 전 법 검토 필요</p>
      <div className="mt-[14px]"><CTA on={all} onClick={() => go({ name: "pick" })}>동의하고 시작하기</CTA></div>
      {leave && (
        <div className="m-in absolute inset-0 z-10 flex items-center justify-center rounded-[24px] bg-black/45 px-6" onMouseDown={() => setLeave(false)}>
          <div role="dialog" aria-label="가입을 그만둘까요?" onMouseDown={(e) => e.stopPropagation()} className="m-pop flex w-[400px] max-w-full flex-col gap-2 rounded-[28px] bg-white px-7 py-[27px]">
            <p className="text-[22px] font-bold leading-[31px] text-[#18181c]">가입을 그만둘까요?</p>
            <p className="break-keep text-[15px] leading-[23px] text-[#667085]">지금 나가면 동의한 내용은 저장되지 않아요. 다음에 로그인하면 이어서 할 수 있어요.</p>
            <div className="mt-3 flex gap-2">
              <button onClick={() => setLeave(false)} className="flex h-12 flex-1 items-center justify-center rounded-[12px] bg-[#f2f2f5] text-[15px] font-bold text-[#18181c] hover:bg-[#e8e8ec]">계속하기</button>
              <button onClick={() => void sess.logout()} className="flex h-12 flex-1 items-center justify-center rounded-[12px] bg-[#111] text-[15px] font-bold text-white hover:bg-[#2a2a2a]">그만두기</button>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}

/* ---------- 01.2 관심 종목 고르기 — 앱 '변경 후(제안 적용)' 화면처럼 12종목 · 3줄 (11.13) ---------- */
const PICK_CODES = api.market.onboardPicks();
const PICKS = PICK_CODES.map((code) => { const i = api.market.info(code)!; return { code, name: i.name, logo: i.logo, bg: i.logo_bg, ink: i.logo_ink }; });
const Radio = ({ on }: { on: boolean }) => on
  ? <span className="flex h-[26px] w-[26px] items-center justify-center rounded-full bg-[#111]"><svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2.5 6.2L5 8.6L9.5 3.6" stroke="white" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" /></svg></span>
  : <span className="h-[26px] w-[26px] rounded-full shadow-[inset_0_0_0_1.6px_#d1d5db]" />;
export function Pick() {
  const { go, act, setCoachPending, setX } = useApp();
  const [sel, setSel] = useState<Record<string, Hold | undefined>>({});
  const n = Object.values(sel).filter(Boolean).length;
  const done = (skip?: boolean) => {
    act.setStocks(skip ? [] : PICK_CODES.filter((c) => sel[c]).map((c) => ({ stock_code: c, hold: sel[c]! })));
    act.onboarded();
    setCoachPending(true); // v2: 처음 홈에 들어가면 코치마크
    setX((v) => ({ ...v, first: true, firstStep: 0 })); // 11.16 앱 통일: 첫 홈 → 첫 메모 안내
    go({ name: "start" });
  };
  const toggle = (code: string) => setSel((s) => ({ ...s, [code]: s[code] ? undefined : "관심" }));
  return (
    <Card>
      <div className="flex h-[42px] items-center justify-between">
        <Back onClick={() => go({ name: "terms" })} />
        <div className="flex items-center gap-[22px]"><Progress step={1} /><button onClick={() => done(true)} className="text-[15px] leading-[23px] text-[#667085] hover:text-[#18181c]">건너뛰기</button></div>
      </div>
      <p className="mt-5 whitespace-pre-line text-[30px] font-bold leading-[40px] text-[#18181c]">{"어떤 종목의 메모를\n남기고 싶으세요?"}</p>
      <p className="mt-2 text-[15px] leading-[23px] text-[#8b919c]">여러 개 골라도 돼요. 나중에 내 종목에서 언제든 바꿀 수 있어요.</p>
      <p className="mt-7 text-[15px] font-bold leading-[23px] text-[#18181c]">많이 찾는 종목</p>
      <div className="mt-3 grid grid-cols-3 gap-3">
        {PICKS.map((p) => { const h = sel[p.code], on = !!h; return (
          <div key={p.code} role="button" tabIndex={0} aria-pressed={on} onClick={() => toggle(p.code)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(p.code); } }}
            className={cx("relative flex h-[172px] cursor-pointer flex-col items-start rounded-[20px] bg-white p-4 text-left transition-shadow", on ? "shadow-[inset_0_0_0_2px_#111]" : "shadow-[inset_0_0_0_1.5px_#e6e8ed] hover:shadow-[inset_0_0_0_1.5px_#c9ccd2]")}>
            <span className="dk-keep flex h-11 w-11 items-center justify-center rounded-[12px] text-[17px] font-bold" style={{ background: p.bg, color: p.ink ?? "#fff" }}>{p.logo}</span>
            <span className="absolute right-3 top-3"><Radio on={on} /></span>
            <span className="mt-3 w-full truncate text-[15px] font-bold leading-[23px] text-[#18181c]">{p.name}</span>
            <span className="text-[13px] leading-[20px] text-[#9aa0aa]">{p.code}</span>
            {on && (
              <div className="m-pop mt-auto flex h-8 w-full rounded-[10px] bg-[#f2f2f5] p-[2px]" onClick={(e) => e.stopPropagation()}>
                {(["보유", "관심"] as const).map((x) => <button key={x} onClick={() => setSel((s) => ({ ...s, [p.code]: x }))} aria-pressed={h === x} className={cx("flex h-7 flex-1 items-center justify-center rounded-[8px] text-[14px] leading-[21px] transition-colors", h === x ? "bg-white font-bold text-[#18181c] shadow-[0_1px_2px_rgba(0,0,0,0.06)]" : "text-[#667085]")}>{x}</button>)}
              </div>
            )}
          </div>
        ); })}
      </div>
      <div className="mt-5 flex items-start gap-2 rounded-[16px] bg-[#f4f5f7] px-5 py-4">
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none" className="mt-[2px] shrink-0"><circle cx="8" cy="8" r="5.5" stroke="#8b919c" strokeWidth="1.5" /><path d="M12.2 12.2L15 15" stroke="#8b919c" strokeWidth="1.5" strokeLinecap="round" /></svg>
        <p className="break-keep text-[14px] leading-[21px] text-[#575b63]">찾는 종목이 없나요? 시작한 뒤 <b className="font-bold text-[#18181c]">내 종목 › 종목 추가</b>에서 코스피 전체를 찾을 수 있어요</p>
      </div>
      <div className="sticky bottom-0 z-10 -mx-14 mt-4 rounded-b-[24px] bg-gradient-to-t from-white from-75% to-white/0 px-14 pb-8 pt-6 [margin-bottom:-32px]">
        <CTA on={n > 0} onClick={() => done()}>{n > 0 ? `${n}개 종목으로 계속` : "종목을 골라 주세요"}</CTA>
      </div>
    </Card>
  );
}
