import { useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { cx } from "../kit";
import { useApp } from "../store";
import { Board, StockHead } from "./board";
import { CompanyInfo } from "./company";

/* 고정 틀 (11.13): 노션처럼 860px 고정. 비율을 지킨 채 자리에 맞춰 줄거나(양옆 8px) 사이드바를 접으면 최대 115%까지 살짝 커짐.
   fill: 투자 기록처럼 화면 높이를 채우는 화면 (틀 높이 = 보이는 높이 ÷ 배율) */
const FRAME = 860, GUT = 24, KMAX = 1.15; // 11.16: 사이드바를 펼쳤을 때 제목이 너무 붙어 보여 양옆 여백 8 → 24
export function FixedFrame({ children, fill }: { children: ReactNode; fill?: boolean }) {
  const outer = useRef<HTMLDivElement>(null), inner = useRef<HTMLDivElement>(null);
  const [k, setK] = useState(1), [h, setH] = useState<number | undefined>(undefined), [fh, setFh] = useState<number | undefined>(undefined);
  useLayoutEffect(() => {
    const o = outer.current!, i = inner.current!;
    /* 높이는 % 대신 메인 칸의 실제 높이를 재서 씀 — Safari·Firefox에서 0이 되던 문제 (11.13) */
    const main = o.closest("main") as HTMLElement | null;
    const fit = () => {
      const w = o.clientWidth || main?.clientWidth || window.innerWidth;
      const kk = Math.max(0.5, Math.min(KMAX, (w - GUT * 2) / FRAME));
      setK(kk);
      if (fill) { const vh = Math.max(560, main?.clientHeight || window.innerHeight); setFh(vh / kk); setH(vh); } else setH(i.offsetHeight * kk);
    };
    fit();
    const ro = new ResizeObserver(fit); ro.observe(o); ro.observe(i); if (main) ro.observe(main);
    window.addEventListener("resize", fit);
    return () => { ro.disconnect(); window.removeEventListener("resize", fit); };
  }, [fill]);
  const ease = "calc(.35s * var(--k)) cubic-bezier(.2,.8,.2,1)";
  return (
    <div ref={outer} className={cx("w-full", fill && "overflow-hidden")} style={fill ? { height: h } : undefined}>
      <div className="relative mx-auto" style={{ width: FRAME * k, height: h, transition: `width ${ease}` }}>
        <div ref={inner} className="absolute left-0 top-0 origin-top-left" style={{ width: FRAME, height: fill ? fh : undefined, transform: `scale(${k})`, transition: `transform ${ease}` }}>{children}</div>
      </div>
    </div>
  );
}

/* ============ 6 · 기업 메모장 / 7 · 기업 정보 (머리 · 탭 · 본문) ============ */
export function StockPage({ code, tab }: { code: string; tab: "board" | "info" }) {
  const { stocks, go } = useApp();
  const s = stocks.find((x) => x.stock_code === code) ?? stocks[0];
  if (!s) return null;
  const info = tab === "info";
  return (
    <FixedFrame>
      <div className={cx("flex w-[860px] flex-col items-stretch gap-5 pt-14", info ? "pb-10" : "pb-6")}>
        <StockHead s={s} />
        <div className="flex shrink-0 items-start gap-2">
          {(["board", "info"] as const).map((t) => (
            <button key={t} onClick={() => go({ name: "stock", code: s.stock_code, tab: t })} className={cx("flex h-10 items-center rounded-[20px] px-5 text-[15px] font-medium leading-[23px] transition-colors", tab === t ? "bg-black text-white" : "bg-white text-[#8f8f8f] hover:text-[#191f28]")}>{t === "board" ? "보드" : "기업 정보"}</button>
          ))}
        </div>
        <div key={tab} className="m-in flex w-full flex-1 flex-col">{tab === "board" ? <Board s={s} /> : <CompanyInfo s={s} />}</div>
      </div>
    </FixedFrame>
  );
}
