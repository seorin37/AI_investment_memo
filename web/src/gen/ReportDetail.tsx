/* eslint-disable */
// Figma에서 그대로 변환 (자동 생성)
import type { MouseEvent } from "react";
import { useLayoutEffect, useRef, useState } from "react";
import type React from "react";
function AddBtn({ on }: { on?: boolean }) {
  const [a, setA] = useState(!!on);
  return <button onClick={(e) => { e.stopPropagation(); setA(true); }} disabled={a} className={"w-[96px] h-[32px] shrink-0 flex justify-center items-center rounded-[8px] overflow-hidden transition-colors " + (a ? "bg-[#f2f3f4]" : "bg-[#15171a]")}><span className={"shrink-0 whitespace-nowrap text-[15px] font-[700] leading-[normal] " + (a ? "text-[#747d8d]" : "text-[#ffffff]")}>{a ? "✓ 추가됨" : "메모에 추가"}</span></button>;
}
/* 차트(642×230)는 칸 폭에 맞춰 비율 그대로 키움 — 눈금 글자도 같이 커짐 (11.13) */
function ScaleBox({ w, h, children }: { w: number; h: number; children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null); const [k, setK] = useState(1);
  useLayoutEffect(() => { const el = ref.current!; const fit = () => setK(el.clientWidth / w || 1); fit(); const ro = new ResizeObserver(fit); ro.observe(el); return () => ro.disconnect(); }, [w]);
  return <div ref={ref} className="relative w-full self-stretch" style={{ height: h * k }}><div className="absolute left-0 top-0 origin-top-left" style={{ width: w, transform: `scale(${k})` }}>{children}</div></div>;
}
export function ReportDetail({ onAct }: { onAct?: (a: string, e: MouseEvent) => void }) {
  const act = (e: MouseEvent) => { const t = (e.target as HTMLElement).closest("[data-act]") as HTMLElement | null; if (t && onAct) onAct(t.dataset.act!, e); };
  return (
<div onClick={act} className="contents">
<div className="flex flex-col gap-[20px]">
<div className="w-full flex flex-col gap-[18px] items-start py-[28px] px-[28px] relative bg-[linear-gradient(90deg,#17151f,#2e2550)] rounded-[20px] overflow-hidden">
  <div className="self-stretch shrink-0 flex justify-between items-center overflow-hidden">
    <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#b9a8e8] leading-[normal] tracking-[1.6px]">MEMO'S WEEKLY REPORT</p>
    <div className="shrink-0 flex items-start py-[4px] px-[10px] bg-[rgba(255,255,255,0.12)] rounded-[999px] overflow-hidden">
      <p className="shrink-0 whitespace-nowrap text-[15px] font-[500] text-[#ffffff] leading-[normal]">2026년 11월 2주</p>
    </div>
  </div>
  <div className="self-stretch shrink-0 flex flex-col gap-[6px] items-start overflow-hidden">
    <p className="shrink-0 whitespace-nowrap text-[30px] font-[700] text-[#ffffff] leading-[normal]">주간보고서</p>
    <p className="shrink-0 whitespace-nowrap text-[15px] text-[#c9c3dc] leading-[normal]">11.03(월) ~ 11.07(금) · 거래일 5일 · 3종목 · 11.09 14:02 작성</p>
  </div>
  <div className="self-stretch h-[1px] shrink-0 bg-[rgba(255,255,255,0.14)]" />
  <div className="self-stretch shrink-0 flex gap-[10px] items-start overflow-hidden">
    <div className="flex-1 min-w-0 flex flex-col gap-[10px] items-start py-[14px] px-[14px] bg-[rgba(255,255,255,0.07)] border border-[rgba(255,255,255,0.1)] rounded-[14px] overflow-hidden">
      <div className="shrink-0 flex gap-[8px] items-center overflow-hidden">
        <div className="w-[22px] h-[22px] shrink-0 flex justify-center items-center bg-[#ea002c] rounded-[6.6px]">
          <p className="shrink-0 whitespace-nowrap text-center text-[11px] font-[700] text-[#ffffff] leading-[normal]">S</p>
        </div>
        <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#ffffff] leading-[normal]">SK하이닉스</p>
      </div>
      <div className="self-stretch shrink-0 flex justify-between items-end overflow-hidden">
        <p className="shrink-0 whitespace-nowrap text-[26px] font-[700] text-[#ff7b80] leading-[normal]">+6.2%</p>
        <div className="w-[64px] h-[26px] shrink-0 relative overflow-hidden">
          <span className="absolute left-[2px] top-[2px] w-[60px] h-[22px] block"><svg width="62" height="24" viewBox="0 0 62 24" fill="none"><path d="M0.875244 22.875L15.8752 17.875L30.8752 6.875L45.8752 3.575L60.8752 0.875" stroke="#FF7B80" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"/></svg></span>
        </div>
      </div>
      <p className="shrink-0 whitespace-nowrap text-[15px] text-[#b6b0c9] leading-[normal]">공시 1 · 뉴스 2</p>
    </div>
    <div className="flex-1 min-w-0 flex flex-col gap-[10px] items-start py-[14px] px-[14px] bg-[rgba(255,255,255,0.07)] border border-[rgba(255,255,255,0.1)] rounded-[14px] overflow-hidden">
      <div className="shrink-0 flex gap-[8px] items-center overflow-hidden">
        <div className="w-[22px] h-[22px] shrink-0 flex justify-center items-center bg-[#1428a0] rounded-[6.6px]">
          <p className="shrink-0 whitespace-nowrap text-center text-[11px] font-[700] text-[#ffffff] leading-[normal]">삼</p>
        </div>
        <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#ffffff] leading-[normal]">삼성전자</p>
      </div>
      <div className="self-stretch shrink-0 flex justify-between items-end overflow-hidden">
        <p className="shrink-0 whitespace-nowrap text-[26px] font-[700] text-[#ff7b80] leading-[normal]">+1.4%</p>
        <div className="w-[64px] h-[26px] shrink-0 relative overflow-hidden">
          <span className="absolute left-[2px] top-[2px] w-[60px] h-[22px] block"><svg width="62" height="24" viewBox="0 0 62 24" fill="none"><path d="M0.875244 17.175L15.8752 22.875L30.8752 2.775L45.8752 0.875L60.8752 7.575" stroke="#FF7B80" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"/></svg></span>
        </div>
      </div>
      <p className="shrink-0 whitespace-nowrap text-[15px] text-[#b6b0c9] leading-[normal]">공시 1</p>
    </div>
    <div className="flex-1 min-w-0 flex flex-col gap-[10px] items-start py-[14px] px-[14px] bg-[rgba(255,255,255,0.07)] border border-[rgba(255,255,255,0.1)] rounded-[14px] overflow-hidden">
      <div className="shrink-0 flex gap-[8px] items-center overflow-hidden">
        <div className="w-[22px] h-[22px] shrink-0 flex justify-center items-center bg-[#03c75a] rounded-[6.6px]">
          <p className="shrink-0 whitespace-nowrap text-center text-[11px] font-[700] text-[#ffffff] leading-[normal]">N</p>
        </div>
        <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#ffffff] leading-[normal]">네이버</p>
      </div>
      <div className="self-stretch shrink-0 flex justify-between items-end overflow-hidden">
        <p className="shrink-0 whitespace-nowrap text-[26px] font-[700] text-[#8db2ff] leading-[normal]">-0.8%</p>
        <div className="w-[64px] h-[26px] shrink-0 relative overflow-hidden">
          <span className="absolute left-[2px] top-[2px] w-[60px] h-[22px] block"><svg width="62" height="24" viewBox="0 0 62 24" fill="none"><path d="M0.875 11.875L15.875 0.875L30.875 14.675L45.875 22.875L60.875 21.275" stroke="#8DB2FF" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"/></svg></span>
        </div>
      </div>
      <p className="shrink-0 whitespace-nowrap text-[15px] text-[#b6b0c9] leading-[normal]">새 소식 없음</p>
    </div>
  </div>
  <div className="shrink-0 flex gap-[16px] items-center overflow-hidden">
    <div className="shrink-0 flex gap-[6px] items-center overflow-hidden">
      <p className="shrink-0 whitespace-nowrap text-[15px] text-[#b6b0c9] leading-[normal]">공시</p>
      <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#ffffff] leading-[normal]">2건</p>
    </div>
    <div className="shrink-0 flex gap-[6px] items-center overflow-hidden">
      <p className="shrink-0 whitespace-nowrap text-[15px] text-[#b6b0c9] leading-[normal]">뉴스</p>
      <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#ffffff] leading-[normal]">2건</p>
    </div>
    <div className="shrink-0 flex gap-[6px] items-center overflow-hidden">
      <p className="shrink-0 whitespace-nowrap text-[15px] text-[#b6b0c9] leading-[normal]">메모와 연결</p>
      <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#ffffff] leading-[normal]">2개</p>
    </div>
  </div>
</div>
<div className="w-full flex flex-col gap-[10px] items-start py-[24px] px-[24px] relative bg-[#ffffff] border-l-[4px] border-[#6a42ab] rounded-[16px] overflow-hidden">
  <div className="self-stretch shrink-0 flex gap-[8px] items-center overflow-hidden">
    <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#6a42ab] leading-[normal]">이번 주 한눈에</p>
  </div>
  <p className="self-stretch shrink-0 text-[17px] text-[#2b2f36] leading-[26px]">내 종목 3곳 중 2곳이 올랐어요. SK하이닉스는 화요일 신규 시설투자 공시[1] 뒤 한 주 동안 6.2% 올라 가장 크게 움직였고, 삼성전자는 메모에 적어 둔 자기주식 취득 공시[2]가 나왔어요. 네이버는 새 공시·뉴스 없이 0.8% 내렸어요.</p>
</div>
<div className="w-full flex gap-[10px] items-center pt-[8px] relative overflow-hidden">
  <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#6a42ab] leading-[normal]">01</p>
  <p className="shrink-0 whitespace-nowrap text-[17px] font-[700] text-[#15171a] leading-[normal]">증시 핫이슈</p>
  <div className="flex-1 min-w-0 h-[1px] bg-[#dcdfe5]" />
</div>
<div className="w-full flex flex-col gap-[14px] items-start py-[24px] px-[24px] relative bg-[#ffffff] rounded-[16px] overflow-hidden">
  <div className="self-stretch shrink-0 flex gap-[10px] items-start overflow-hidden">
    <div className="flex-1 min-w-0 flex flex-col gap-[2px] items-start py-[12px] px-[14px] bg-[#f5f6f8] border border-[#e8ecf3] rounded-[12px] overflow-hidden">
      <p className="shrink-0 whitespace-nowrap text-[14px] text-[#747d8d] leading-[normal]">코스피</p>
      <div className="shrink-0 flex gap-[6px] items-center overflow-hidden">
        <p className="shrink-0 whitespace-nowrap text-[17px] font-[700] text-[#15171a] leading-[normal]">2,650.35</p>
        <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#e5484d] leading-[normal]">+2.0%</p>
      </div>
    </div>
    <div className="flex-1 min-w-0 flex flex-col gap-[2px] items-start py-[12px] px-[14px] bg-[#f5f6f8] border border-[#e8ecf3] rounded-[12px] overflow-hidden">
      <p className="shrink-0 whitespace-nowrap text-[14px] text-[#747d8d] leading-[normal]">코스닥</p>
      <div className="shrink-0 flex gap-[6px] items-center overflow-hidden">
        <p className="shrink-0 whitespace-nowrap text-[17px] font-[700] text-[#15171a] leading-[normal]">862.10</p>
        <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#e5484d] leading-[normal]">+0.6%</p>
      </div>
    </div>
    <div className="flex-1 min-w-0 flex flex-col gap-[2px] items-start py-[12px] px-[14px] bg-[#f5f6f8] border border-[#e8ecf3] rounded-[12px] overflow-hidden">
      <p className="shrink-0 whitespace-nowrap text-[14px] text-[#747d8d] leading-[normal]">원/달러</p>
      <div className="shrink-0 flex gap-[6px] items-center overflow-hidden">
        <p className="shrink-0 whitespace-nowrap text-[17px] font-[700] text-[#15171a] leading-[normal]">1,350.20</p>
        <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#2f6fe0] leading-[normal]">-1.6%</p>
      </div>
    </div>
  </div>
  <div className="self-stretch shrink-0 flex flex-col items-start overflow-hidden">
    <div className="self-stretch shrink-0 flex gap-[12px] items-center py-[11px] overflow-hidden">
      <p className="shrink-0 whitespace-nowrap text-[14px] font-[500] text-[#747d8d] leading-[normal]">11.04 화</p>
      <p className="flex-1 min-w-0 text-[17px] font-[500] text-[#15171a] leading-[normal]">미국 반도체 지수 강세에 국내 반도체주 동반 상승</p>
      <p className="shrink-0 whitespace-nowrap text-[14px] font-[500] text-[#8e8a97] leading-[normal]">[5]</p>
    </div>
    <div className="self-stretch shrink-0 flex gap-[12px] items-center py-[11px] border-t border-[#eef0f3] overflow-hidden">
      <p className="shrink-0 whitespace-nowrap text-[14px] font-[500] text-[#747d8d] leading-[normal]">11.05 수</p>
      <p className="flex-1 min-w-0 text-[17px] font-[500] text-[#15171a] leading-[normal]">외국인, 사흘 연속 코스피 순매수</p>
      <p className="shrink-0 whitespace-nowrap text-[14px] font-[500] text-[#8e8a97] leading-[normal]">[6]</p>
    </div>
    <div className="self-stretch shrink-0 flex gap-[12px] items-center py-[11px] border-t border-[#eef0f3] overflow-hidden">
      <p className="shrink-0 whitespace-nowrap text-[14px] font-[500] text-[#747d8d] leading-[normal]">11.07 금</p>
      <p className="flex-1 min-w-0 text-[17px] font-[500] text-[#15171a] leading-[normal]">원/달러 환율 1,350원대로 내려 원화 강세</p>
      <p className="shrink-0 whitespace-nowrap text-[14px] font-[500] text-[#8e8a97] leading-[normal]">[7]</p>
    </div>
  </div>
</div>
<div className="w-full flex flex-col items-start relative bg-[#ffffff] rounded-[16px] overflow-hidden">
  <div className="self-stretch h-[4px] shrink-0 bg-[#e4002b]" />
  <div className="self-stretch shrink-0 flex items-center py-[18px] px-[24px] bg-[#fdebee] overflow-hidden">
    <div className="flex-1 min-w-0 self-stretch flex justify-between items-center overflow-hidden">
      <div className="shrink-0 flex gap-[10px] items-center overflow-hidden">
        <div className="w-[32px] h-[32px] shrink-0 flex justify-center items-center bg-[#ea002c] rounded-[9.6px]">
          <p className="shrink-0 whitespace-nowrap text-center text-[15px] font-[700] text-[#ffffff] leading-[normal]">S</p>
        </div>
        <p className="shrink-0 whitespace-nowrap text-[22px] font-[700] text-[#15171a] leading-[normal]">SK하이닉스</p>
        <div className="shrink-0 flex items-start py-[2px] px-[8px] bg-[#f2f3f4] rounded-[6px] overflow-hidden">
          <p className="shrink-0 whitespace-nowrap text-[15px] font-[500] text-[#575b63] leading-[normal]">보유</p>
        </div>
      </div>
      <div className="shrink-0 flex gap-[8px] items-center overflow-hidden">
        <p className="shrink-0 whitespace-nowrap text-[22px] font-[700] text-[#15171a] leading-[normal]">180,500원</p>
        <p className="shrink-0 whitespace-nowrap text-[17px] font-[700] text-[#e5484d] leading-[normal]">+6.2%</p>
      </div>
    </div>
  </div>
  <div className="self-stretch shrink-0 flex flex-col gap-[18px] items-start pt-[20px] pr-[24px] pb-[24px] pl-[24px] overflow-hidden">
    <div className="self-stretch shrink-0 flex gap-[8px] items-start overflow-hidden">
      <div className="flex-1 min-w-0 flex flex-col gap-[2px] items-start py-[10px] px-[12px] bg-[#ffffff] border border-[#e8ecf3] rounded-[10px] overflow-hidden">
        <p className="shrink-0 whitespace-nowrap text-[14px] text-[#747d8d] leading-[normal]">주간 등락</p>
        <p className="shrink-0 whitespace-nowrap text-[17px] font-[700] text-[#e5484d] leading-[normal]">+6.2%</p>
      </div>
      <div className="flex-1 min-w-0 flex flex-col gap-[2px] items-start py-[10px] px-[12px] bg-[#ffffff] border border-[#e8ecf3] rounded-[10px] overflow-hidden">
        <p className="shrink-0 whitespace-nowrap text-[14px] text-[#747d8d] leading-[normal]">주간 최고</p>
        <p className="shrink-0 whitespace-nowrap text-[17px] font-[700] text-[#15171a] leading-[normal]">182,000</p>
      </div>
      <div className="flex-1 min-w-0 flex flex-col gap-[2px] items-start py-[10px] px-[12px] bg-[#ffffff] border border-[#e8ecf3] rounded-[10px] overflow-hidden">
        <p className="shrink-0 whitespace-nowrap text-[14px] text-[#747d8d] leading-[normal]">주간 최저</p>
        <p className="shrink-0 whitespace-nowrap text-[17px] font-[700] text-[#15171a] leading-[normal]">168,500</p>
      </div>
      <div className="flex-1 min-w-0 flex flex-col gap-[2px] items-start py-[10px] px-[12px] bg-[#ffffff] border border-[#e8ecf3] rounded-[10px] overflow-hidden">
        <p className="shrink-0 whitespace-nowrap text-[14px] text-[#747d8d] leading-[normal]">거래량</p>
        <p className="shrink-0 whitespace-nowrap text-[17px] font-[700] text-[#15171a] leading-[normal]">+18%</p>
      </div>
    </div>
    <div className="self-stretch shrink-0 flex flex-col gap-[6px] items-start overflow-hidden">
      <ScaleBox w={642} h={230}><div className="w-[642px] h-[230px] shrink-0 relative">
        <div className="absolute left-[4px] top-[200px] w-[574px] h-[1px] bg-[#dadde3]" />
        <p className="absolute left-[586px] top-[192px] w-[40px] whitespace-nowrap text-[13px] text-[#8e8a97] leading-[normal]">165,000</p>
        <div className="absolute left-[4px] top-[158px] w-[574px] h-[1px] bg-[#eef0f3]" />
        <p className="absolute left-[586px] top-[150px] w-[40px] whitespace-nowrap text-[13px] text-[#8e8a97] leading-[normal]">170,000</p>
        <div className="absolute left-[4px] top-[115px] w-[574px] h-[1px] bg-[#eef0f3]" />
        <p className="absolute left-[586px] top-[107px] w-[40px] whitespace-nowrap text-[13px] text-[#8e8a97] leading-[normal]">175,000</p>
        <div className="absolute left-[4px] top-[73px] w-[574px] h-[1px] bg-[#eef0f3]" />
        <div className="absolute left-[4px] top-[30px] w-[574px] h-[1px] bg-[#eef0f3]" />
        <p className="absolute left-[586px] top-[22px] w-[40px] whitespace-nowrap text-[13px] text-[#8e8a97] leading-[normal]">185,000</p>
        <p className="absolute left-[12px] top-[210px] w-[41px] whitespace-nowrap text-center text-[13px] text-[#747d8d] leading-[normal]">11.03 월</p>
        <p className="absolute left-[141px] top-[210px] w-[41px] whitespace-nowrap text-center text-[13px] text-[#747d8d] leading-[normal]">11.04 화</p>
        <p className="absolute left-[271px] top-[210px] w-[41px] whitespace-nowrap text-center text-[13px] text-[#747d8d] leading-[normal]">11.05 수</p>
        <p className="absolute left-[400px] top-[210px] w-[41px] whitespace-nowrap text-center text-[13px] text-[#747d8d] leading-[normal]">11.06 목</p>
        <p className="absolute left-[530px] top-[210px] w-[41px] whitespace-nowrap text-center text-[13px] text-[#747d8d] leading-[normal]">11.07 금</p>
        <span className="absolute left-[4px] top-[158px] w-[574px] h-[0px] block"><svg width="574" height="1" viewBox="0 0 574 1" fill="none"><path d="M0 0.5H574" stroke="#B8BEC8" strokeDasharray="4 4"/></svg></span>
        <span className="absolute left-[32px] top-[68.3px] w-[518px] h-[131.7px] block"><svg width="518" height="132" viewBox="0 0 518 132" fill="none"><path d="M0 90L129.5 69.6L259 24.6L388.5 11L518 0V131.7H0V90Z" fill="url(#paint0_linear_4111_68672)"/><defs><linearGradient id="paint0_linear_4111_68672" x1="0" y1="0" x2="0" y2="1"><stop stopColor="#E5484D" stopOpacity="0.16"/><stop offset="1" stopColor="#E5484D" stopOpacity="0"/></linearGradient></defs></svg></span>
        <span className="absolute left-[32px] top-[68.3px] w-[518px] h-[90px] block"><svg width="521" height="93" viewBox="0 0 521 93" fill="none"><path d="M1.25012 91.25L130.75 70.85L260.25 25.85L389.75 12.25L519.25 1.25" stroke="#E5484D" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/></svg></span>
        <div className="absolute left-[162px] top-[24px] w-[1px] h-[105.95px] bg-[#d6dae1]" />
        <div className="absolute left-[152px] top-[4px] w-[20px] h-[20px] bg-[#7046f5] border-[2px] border-[#ffffff] rounded-full" />
        <p className="absolute left-[158.5px] top-[5.5px] w-[7px] whitespace-nowrap text-center text-[13px] font-[700] text-[#ffffff] leading-[normal]">1</p>
        <div className="absolute left-[421px] top-[24px] w-[1px] h-[47.3px] bg-[#d6dae1]" />
        <div className="absolute left-[411px] top-[4px] w-[20px] h-[20px] bg-[#3d73f0] border-[2px] border-[#ffffff] rounded-full" />
        <p className="absolute left-[417.5px] top-[5.5px] w-[7px] whitespace-nowrap text-center text-[13px] font-[700] text-[#ffffff] leading-[normal]">3</p>
        <div className="absolute left-[550px] top-[24px] w-[1px] h-[36.25px] bg-[#d6dae1]" />
        <div className="absolute left-[540px] top-[4px] w-[20px] h-[20px] bg-[#3d73f0] border-[2px] border-[#ffffff] rounded-full" />
        <p className="absolute left-[546.5px] top-[5.5px] w-[7px] whitespace-nowrap text-center text-[13px] font-[700] text-[#ffffff] leading-[normal]">4</p>
        <div className="absolute left-[28.5px] top-[154.85px] w-[7px] h-[7px] bg-[#ffffff] border-[2px] border-[#e5484d] rounded-full" />
        <div className="absolute left-[158px] top-[134.45px] w-[7px] h-[7px] bg-[#ffffff] border-[2px] border-[#e5484d] rounded-full" />
        <div className="absolute left-[287.5px] top-[89.4px] w-[7px] h-[7px] bg-[#ffffff] border-[2px] border-[#e5484d] rounded-full" />
        <div className="absolute left-[417px] top-[75.8px] w-[7px] h-[7px] bg-[#ffffff] border-[2px] border-[#e5484d] rounded-full" />
        <div className="absolute left-[545px] top-[63.25px] w-[10px] h-[10px] bg-[#e5484d] border-[2.5px] border-[#ffffff] rounded-full" />
        <div className="absolute left-[582px] top-[60px] flex items-start py-[2px] px-[6px] bg-[#e5484d] rounded-[4px] overflow-hidden">
          <p className="shrink-0 whitespace-nowrap text-[13px] font-[700] text-[#ffffff] leading-[normal]">180,500</p>
        </div>
      </div></ScaleBox>
      <div className="shrink-0 flex gap-[12px] items-center overflow-hidden">
        <div className="shrink-0 flex gap-[5px] items-center overflow-hidden">
          <div className="w-[8px] h-[8px] shrink-0 bg-[#7046f5] rounded-full" />
          <p className="shrink-0 whitespace-nowrap text-[14px] text-[#747d8d] leading-[normal]">공시</p>
        </div>
        <div className="shrink-0 flex gap-[5px] items-center overflow-hidden">
          <div className="w-[8px] h-[8px] shrink-0 bg-[#3d73f0] rounded-full" />
          <p className="shrink-0 whitespace-nowrap text-[14px] text-[#747d8d] leading-[normal]">뉴스</p>
        </div>
        <div className="shrink-0 flex gap-[5px] items-center overflow-hidden">
          <span className="w-[14px] h-[0px] shrink-0 block"><svg width="14" height="1" viewBox="0 0 14 1" fill="none"><path d="M0 0.5H14" stroke="#B8BEC8" strokeDasharray="3 3"/></svg></span>
          <p className="shrink-0 whitespace-nowrap text-[14px] text-[#747d8d] leading-[normal]">지난주 종가</p>
        </div>
        <p className="shrink-0 whitespace-nowrap text-[14px] text-[#8e8a97] leading-[normal]">번호는 아래 소식·출처 번호예요</p>
      </div>
    </div>
    <p className="self-stretch shrink-0 text-[17px] text-[#2b2f36] leading-[26px]">화요일(11.04) 신규 시설투자 공시[1]가 나왔고, 다음 날 주가가 3.1% 오르며 거래량이 이번 주 가장 많았어요. 목요일에는 HBM4 공급 확대 기사[3]가 이어졌고, 금요일 180,500원으로 마감했어요.</p>
    <div className="self-stretch shrink-0 flex flex-col items-start overflow-hidden">
      <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#575b63] leading-[normal]">이번 주 소식</p>
      <div className="self-stretch shrink-0 flex gap-[10px] items-center py-[10px] overflow-hidden">
        <div className="w-[20px] h-[20px] shrink-0 flex justify-center items-center bg-[#7046f5] rounded-full overflow-hidden">
          <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#ffffff] leading-[normal]">1</p>
        </div>
        <div className="shrink-0 flex items-start py-[2px] px-[7px] bg-[#eee8ff] rounded-[5px] overflow-hidden">
          <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#7046f5] leading-[normal]">공시</p>
        </div>
        <p className="shrink-0 whitespace-nowrap text-[14px] font-[500] text-[#747d8d] leading-[normal]">11.04</p>
        <p className="flex-1 min-w-0 text-[17px] font-[500] text-[#15171a] leading-[normal]">신규 시설투자 결정</p>
        <p className="shrink-0 whitespace-nowrap text-[14px] text-[#8e8a97] leading-[normal]">DART</p>
      </div>
      <div className="self-stretch shrink-0 flex gap-[10px] items-center py-[10px] overflow-hidden">
        <div className="w-[20px] h-[20px] shrink-0 flex justify-center items-center bg-[#3d73f0] rounded-full overflow-hidden">
          <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#ffffff] leading-[normal]">3</p>
        </div>
        <div className="shrink-0 flex items-start py-[2px] px-[7px] bg-[#e3edff] rounded-[5px] overflow-hidden">
          <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#3d73f0] leading-[normal]">뉴스</p>
        </div>
        <p className="shrink-0 whitespace-nowrap text-[14px] font-[500] text-[#747d8d] leading-[normal]">11.06</p>
        <p className="flex-1 min-w-0 text-[17px] font-[500] text-[#15171a] leading-[normal]">HBM4 공급 확대 기대감</p>
        <p className="shrink-0 whitespace-nowrap text-[14px] text-[#8e8a97] leading-[normal]">한국경제</p>
      </div>
      <div className="self-stretch shrink-0 flex gap-[10px] items-center py-[10px] overflow-hidden">
        <div className="w-[20px] h-[20px] shrink-0 flex justify-center items-center bg-[#3d73f0] rounded-full overflow-hidden">
          <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#ffffff] leading-[normal]">4</p>
        </div>
        <div className="shrink-0 flex items-start py-[2px] px-[7px] bg-[#e3edff] rounded-[5px] overflow-hidden">
          <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#3d73f0] leading-[normal]">뉴스</p>
        </div>
        <p className="shrink-0 whitespace-nowrap text-[14px] font-[500] text-[#747d8d] leading-[normal]">11.07</p>
        <p className="flex-1 min-w-0 text-[17px] font-[500] text-[#15171a] leading-[normal]">반도체 장비 발주 증가</p>
        <p className="shrink-0 whitespace-nowrap text-[14px] text-[#8e8a97] leading-[normal]">매일경제</p>
      </div>
    </div>
    <div className="self-stretch shrink-0 flex flex-col gap-[6px] items-start pt-[18px] pr-[16px] pb-[14px] pl-[16px] relative bg-[#fceaaa] rounded-[12px]">
      <div className="self-stretch shrink-0 flex justify-between items-center overflow-hidden">
        <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#575b63] leading-[normal]">내 메모와의 연결</p>
        <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#15171a] leading-[normal]" data-act="memo" role="button" style={{cursor:"pointer"}}>원본 메모 보기 ›</p>
      </div>
      <div className="shrink-0 flex gap-[8px] items-center overflow-hidden">
        <p className="shrink-0 whitespace-nowrap text-[17px] font-[700] text-[#15171a] leading-[normal]">HBM 수요 계속 확인</p>
        <p className="shrink-0 whitespace-nowrap text-[15px] text-[#575b63] leading-[normal]">9.25 작성 · AI 연결 중</p>
      </div>
      <p className="self-stretch shrink-0 text-[15px] text-[#2b2f36] leading-[23px]">메모의 추적 항목 'HBM 생산 능력'과 관련된 소식 2건([1], [3])이 이번 주에 붙었어요.</p>
      <div className="absolute left-[292.27px] top-[-6px] w-[56px] h-[14px] bg-[rgba(255,255,255,0.55)]" />
    </div>
    <div className="self-stretch shrink-0 flex flex-col gap-[10px] items-start py-[16px] px-[16px] bg-[#faf8ff] border border-[#e6defa] rounded-[12px] overflow-hidden">
      <div className="shrink-0 flex gap-[6px] items-center overflow-hidden">
        <span className="w-[16px] h-[16px] shrink-0 overflow-hidden block"><svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M1.33337 8.00065C1.33337 8.00065 3.73337 3.33398 8.00004 3.33398C12.2667 3.33398 14.6667 8.00065 14.6667 8.00065C14.6667 8.00065 12.2667 12.6673 8.00004 12.6673C3.73337 12.6673 1.33337 8.00065 1.33337 8.00065Z" stroke="#6A42AB" strokeWidth="1.33333" strokeLinejoin="round"/><path d="M8 10C9.10457 10 10 9.10457 10 8C10 6.89543 9.10457 6 8 6C6.89543 6 6 6.89543 6 8C6 9.10457 6.89543 10 8 10Z" stroke="#6A42AB" strokeWidth="1.33333"/></svg></span>
        <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#6a42ab] leading-[normal]">앞으로 지켜볼 것</p>
      </div>
      <div className="self-stretch shrink-0 flex gap-[16px] items-center pt-[12px] pr-[12px] pb-[12px] pl-[14px] bg-[#ffffff] rounded-[10px] overflow-hidden">
        <div className="flex-1 min-w-0 flex flex-col gap-[2px] items-start overflow-hidden">
          <p className="self-stretch shrink-0 text-[17px] font-[500] text-[#15171a] leading-[26px]">11월 말 분기보고서에 HBM 매출이 따로 나오는지</p>
          <p className="shrink-0 whitespace-nowrap text-[14px] text-[#8e8a97] leading-[normal]">근거 · 정기 공시 일정</p>
        </div>
        <AddBtn />
      </div>
      <div className="self-stretch shrink-0 flex gap-[16px] items-center pt-[12px] pr-[12px] pb-[12px] pl-[14px] bg-[#ffffff] rounded-[10px] overflow-hidden">
        <div className="flex-1 min-w-0 flex flex-col gap-[2px] items-start overflow-hidden">
          <p className="self-stretch shrink-0 text-[17px] font-[500] text-[#15171a] leading-[26px]">메모의 가격 조건 15만 원과 지금 가격의 거리 (현재 20.3% 위)</p>
          <p className="shrink-0 whitespace-nowrap text-[14px] text-[#8e8a97] leading-[normal]">근거 · 내 메모 가격 조건</p>
        </div>
        <AddBtn on />
      </div>
    </div>
  </div>
</div>
<div className="w-full flex flex-col items-start relative bg-[#ffffff] rounded-[16px] overflow-hidden">
  <div className="self-stretch h-[4px] shrink-0 bg-[#1428a0]" />
  <div className="self-stretch shrink-0 flex items-center py-[18px] px-[24px] bg-[#eceef7] overflow-hidden">
    <div className="flex-1 min-w-0 self-stretch flex justify-between items-center overflow-hidden">
      <div className="shrink-0 flex gap-[10px] items-center overflow-hidden">
        <div className="w-[32px] h-[32px] shrink-0 flex justify-center items-center bg-[#1428a0] rounded-[9.6px]">
          <p className="shrink-0 whitespace-nowrap text-center text-[15px] font-[700] text-[#ffffff] leading-[normal]">삼</p>
        </div>
        <p className="shrink-0 whitespace-nowrap text-[22px] font-[700] text-[#15171a] leading-[normal]">삼성전자</p>
        <div className="shrink-0 flex items-start py-[2px] px-[8px] bg-[#f2f3f4] rounded-[6px] overflow-hidden">
          <p className="shrink-0 whitespace-nowrap text-[15px] font-[500] text-[#575b63] leading-[normal]">관심</p>
        </div>
      </div>
      <div className="shrink-0 flex gap-[8px] items-center overflow-hidden">
        <p className="shrink-0 whitespace-nowrap text-[22px] font-[700] text-[#15171a] leading-[normal]">71,400원</p>
        <p className="shrink-0 whitespace-nowrap text-[17px] font-[700] text-[#e5484d] leading-[normal]">+1.4%</p>
      </div>
    </div>
  </div>
  <div className="self-stretch shrink-0 flex flex-col gap-[18px] items-start pt-[20px] pr-[24px] pb-[24px] pl-[24px] overflow-hidden">
    <div className="self-stretch shrink-0 flex gap-[8px] items-start overflow-hidden">
      <div className="flex-1 min-w-0 flex flex-col gap-[2px] items-start py-[10px] px-[12px] bg-[#ffffff] border border-[#e8ecf3] rounded-[10px] overflow-hidden">
        <p className="shrink-0 whitespace-nowrap text-[14px] text-[#747d8d] leading-[normal]">주간 등락</p>
        <p className="shrink-0 whitespace-nowrap text-[17px] font-[700] text-[#e5484d] leading-[normal]">+1.4%</p>
      </div>
      <div className="flex-1 min-w-0 flex flex-col gap-[2px] items-start py-[10px] px-[12px] bg-[#ffffff] border border-[#e8ecf3] rounded-[10px] overflow-hidden">
        <p className="shrink-0 whitespace-nowrap text-[14px] text-[#747d8d] leading-[normal]">주간 최고</p>
        <p className="shrink-0 whitespace-nowrap text-[17px] font-[700] text-[#15171a] leading-[normal]">72,100</p>
      </div>
      <div className="flex-1 min-w-0 flex flex-col gap-[2px] items-start py-[10px] px-[12px] bg-[#ffffff] border border-[#e8ecf3] rounded-[10px] overflow-hidden">
        <p className="shrink-0 whitespace-nowrap text-[14px] text-[#747d8d] leading-[normal]">주간 최저</p>
        <p className="shrink-0 whitespace-nowrap text-[17px] font-[700] text-[#15171a] leading-[normal]">69,800</p>
      </div>
      <div className="flex-1 min-w-0 flex flex-col gap-[2px] items-start py-[10px] px-[12px] bg-[#ffffff] border border-[#e8ecf3] rounded-[10px] overflow-hidden">
        <p className="shrink-0 whitespace-nowrap text-[14px] text-[#747d8d] leading-[normal]">거래량</p>
        <p className="shrink-0 whitespace-nowrap text-[17px] font-[700] text-[#15171a] leading-[normal]">-4%</p>
      </div>
    </div>
    <div className="self-stretch shrink-0 flex flex-col gap-[6px] items-start overflow-hidden">
      <ScaleBox w={642} h={230}><div className="w-[642px] h-[230px] shrink-0 relative">
        <div className="absolute left-[4px] top-[200px] w-[574px] h-[1px] bg-[#dadde3]" />
        <p className="absolute left-[586px] top-[192px] w-[34px] whitespace-nowrap text-[13px] text-[#8e8a97] leading-[normal]">69,000</p>
        <div className="absolute left-[4px] top-[158px] w-[574px] h-[1px] bg-[#eef0f3]" />
        <p className="absolute left-[586px] top-[150px] w-[34px] whitespace-nowrap text-[13px] text-[#8e8a97] leading-[normal]">70,000</p>
        <div className="absolute left-[4px] top-[115px] w-[574px] h-[1px] bg-[#eef0f3]" />
        <p className="absolute left-[586px] top-[107px] w-[34px] whitespace-nowrap text-[13px] text-[#8e8a97] leading-[normal]">71,000</p>
        <div className="absolute left-[4px] top-[73px] w-[574px] h-[1px] bg-[#eef0f3]" />
        <p className="absolute left-[586px] top-[65px] w-[34px] whitespace-nowrap text-[13px] text-[#8e8a97] leading-[normal]">72,000</p>
        <div className="absolute left-[4px] top-[30px] w-[574px] h-[1px] bg-[#eef0f3]" />
        <p className="absolute left-[586px] top-[22px] w-[34px] whitespace-nowrap text-[13px] text-[#8e8a97] leading-[normal]">73,000</p>
        <p className="absolute left-[12px] top-[210px] w-[41px] whitespace-nowrap text-center text-[13px] text-[#747d8d] leading-[normal]">11.03 월</p>
        <p className="absolute left-[141px] top-[210px] w-[41px] whitespace-nowrap text-center text-[13px] text-[#747d8d] leading-[normal]">11.04 화</p>
        <p className="absolute left-[271px] top-[210px] w-[41px] whitespace-nowrap text-center text-[13px] text-[#747d8d] leading-[normal]">11.05 수</p>
        <p className="absolute left-[400px] top-[210px] w-[41px] whitespace-nowrap text-center text-[13px] text-[#747d8d] leading-[normal]">11.06 목</p>
        <p className="absolute left-[530px] top-[210px] w-[41px] whitespace-nowrap text-center text-[13px] text-[#747d8d] leading-[normal]">11.07 금</p>
        <span className="absolute left-[4px] top-[141px] w-[574px] h-[0px] block"><svg width="574" height="1" viewBox="0 0 574 1" fill="none"><path d="M0 0.5H574" stroke="#B8BEC8" strokeDasharray="4 4"/></svg></span>
        <span className="absolute left-[32px] top-[68.3px] w-[518px] h-[131.7px] block"><svg width="518" height="132" viewBox="0 0 518 132" fill="none"><path d="M0 72.2L129.5 97.7L259 8.5L388.5 0L518 29.7V131.7H0V72.2Z" fill="url(#paint0_linear_4111_68792)"/><defs><linearGradient id="paint0_linear_4111_68792" x1="0" y1="0" x2="0" y2="1"><stop stopColor="#E5484D" stopOpacity="0.16"/><stop offset="1" stopColor="#E5484D" stopOpacity="0"/></linearGradient></defs></svg></span>
        <span className="absolute left-[32px] top-[68.3px] w-[518px] h-[97.7px] block"><svg width="521" height="101" viewBox="0 0 521 101" fill="none"><path d="M1.25024 73.45L130.75 98.95L260.25 9.75L389.75 1.25L519.25 30.95" stroke="#E5484D" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/></svg></span>
        <div className="absolute left-[291px] top-[24px] w-[1px] h-[44.75px] bg-[#d6dae1]" />
        <div className="absolute left-[281px] top-[4px] w-[20px] h-[20px] bg-[#7046f5] border-[2px] border-[#ffffff] rounded-full" />
        <p className="absolute left-[287.5px] top-[5.5px] w-[7px] whitespace-nowrap text-center text-[13px] font-[700] text-[#ffffff] leading-[normal]">2</p>
        <div className="absolute left-[28.5px] top-[137px] w-[7px] h-[7px] bg-[#ffffff] border-[2px] border-[#e5484d] rounded-full" />
        <div className="absolute left-[158px] top-[162.5px] w-[7px] h-[7px] bg-[#ffffff] border-[2px] border-[#e5484d] rounded-full" />
        <div className="absolute left-[287.5px] top-[73.25px] w-[7px] h-[7px] bg-[#ffffff] border-[2px] border-[#e5484d] rounded-full" />
        <div className="absolute left-[417px] top-[64.75px] w-[7px] h-[7px] bg-[#ffffff] border-[2px] border-[#e5484d] rounded-full" />
        <div className="absolute left-[545px] top-[93px] w-[10px] h-[10px] bg-[#e5484d] border-[2.5px] border-[#ffffff] rounded-full" />
        <div className="absolute left-[582px] top-[90px] flex items-start py-[2px] px-[6px] bg-[#e5484d] rounded-[4px] overflow-hidden">
          <p className="shrink-0 whitespace-nowrap text-[13px] font-[700] text-[#ffffff] leading-[normal]">71,400</p>
        </div>
      </div></ScaleBox>
      <div className="shrink-0 flex gap-[12px] items-center overflow-hidden">
        <div className="shrink-0 flex gap-[5px] items-center overflow-hidden">
          <div className="w-[8px] h-[8px] shrink-0 bg-[#7046f5] rounded-full" />
          <p className="shrink-0 whitespace-nowrap text-[14px] text-[#747d8d] leading-[normal]">공시</p>
        </div>
        <div className="shrink-0 flex gap-[5px] items-center overflow-hidden">
          <div className="w-[8px] h-[8px] shrink-0 bg-[#3d73f0] rounded-full" />
          <p className="shrink-0 whitespace-nowrap text-[14px] text-[#747d8d] leading-[normal]">뉴스</p>
        </div>
        <div className="shrink-0 flex gap-[5px] items-center overflow-hidden">
          <span className="w-[14px] h-[0px] shrink-0 block"><svg width="14" height="1" viewBox="0 0 14 1" fill="none"><path d="M0 0.5H14" stroke="#B8BEC8" strokeDasharray="3 3"/></svg></span>
          <p className="shrink-0 whitespace-nowrap text-[14px] text-[#747d8d] leading-[normal]">지난주 종가</p>
        </div>
        <p className="shrink-0 whitespace-nowrap text-[14px] text-[#8e8a97] leading-[normal]">번호는 아래 소식·출처 번호예요</p>
      </div>
    </div>
    <p className="self-stretch shrink-0 text-[17px] text-[#2b2f36] leading-[26px]">수요일(11.05) 자기주식 취득 결정 공시[2]가 나온 날 주가가 3.0% 올랐어요. 이후 이틀은 큰 움직임 없이 71,400원으로 마감했고, 거래량은 지난주보다 4% 줄었어요.</p>
    <div className="self-stretch shrink-0 flex flex-col items-start overflow-hidden">
      <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#575b63] leading-[normal]">이번 주 소식</p>
      <div className="self-stretch shrink-0 flex gap-[10px] items-center py-[10px] overflow-hidden">
        <div className="w-[20px] h-[20px] shrink-0 flex justify-center items-center bg-[#7046f5] rounded-full overflow-hidden">
          <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#ffffff] leading-[normal]">2</p>
        </div>
        <div className="shrink-0 flex items-start py-[2px] px-[7px] bg-[#eee8ff] rounded-[5px] overflow-hidden">
          <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#7046f5] leading-[normal]">공시</p>
        </div>
        <p className="shrink-0 whitespace-nowrap text-[14px] font-[500] text-[#747d8d] leading-[normal]">11.05</p>
        <p className="flex-1 min-w-0 text-[17px] font-[500] text-[#15171a] leading-[normal]">자기주식 취득 결정</p>
        <p className="shrink-0 whitespace-nowrap text-[14px] text-[#8e8a97] leading-[normal]">DART</p>
      </div>
    </div>
    <div className="self-stretch shrink-0 flex flex-col gap-[6px] items-start pt-[18px] pr-[16px] pb-[14px] pl-[16px] relative bg-[#cfe0ff] rounded-[12px]">
      <div className="self-stretch shrink-0 flex justify-between items-center overflow-hidden">
        <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#575b63] leading-[normal]">내 메모와의 연결</p>
        <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#15171a] leading-[normal]" data-act="memo" role="button" style={{cursor:"pointer"}}>원본 메모 보기 ›</p>
      </div>
      <div className="shrink-0 flex gap-[8px] items-center overflow-hidden">
        <p className="shrink-0 whitespace-nowrap text-[17px] font-[700] text-[#15171a] leading-[normal]">자사주 매입 나오면 다시 보기</p>
        <p className="shrink-0 whitespace-nowrap text-[15px] text-[#575b63] leading-[normal]">10.02 작성 · AI 연결 꺼짐</p>
      </div>
      <p className="self-stretch shrink-0 text-[15px] text-[#2b2f36] leading-[23px]">메모에 적어 둔 자사주 매입이 이번 주 공시[2]로 나왔어요.</p>
      <div className="absolute left-[292.27px] top-[-6px] w-[56px] h-[14px] bg-[rgba(255,255,255,0.55)]" />
    </div>
    <div className="self-stretch shrink-0 flex flex-col gap-[10px] items-start py-[16px] px-[16px] bg-[#faf8ff] border border-[#e6defa] rounded-[12px] overflow-hidden">
      <div className="shrink-0 flex gap-[6px] items-center overflow-hidden">
        <span className="w-[16px] h-[16px] shrink-0 overflow-hidden block"><svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M1.33337 8.00065C1.33337 8.00065 3.73337 3.33398 8.00004 3.33398C12.2667 3.33398 14.6667 8.00065 14.6667 8.00065C14.6667 8.00065 12.2667 12.6673 8.00004 12.6673C3.73337 12.6673 1.33337 8.00065 1.33337 8.00065Z" stroke="#6A42AB" strokeWidth="1.33333" strokeLinejoin="round"/><path d="M8 10C9.10457 10 10 9.10457 10 8C10 6.89543 9.10457 6 8 6C6.89543 6 6 6.89543 6 8C6 9.10457 6.89543 10 8 10Z" stroke="#6A42AB" strokeWidth="1.33333"/></svg></span>
        <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#6a42ab] leading-[normal]">앞으로 지켜볼 것</p>
      </div>
      <div className="self-stretch shrink-0 flex gap-[16px] items-center pt-[12px] pr-[12px] pb-[12px] pl-[14px] bg-[#ffffff] rounded-[10px] overflow-hidden">
        <div className="flex-1 min-w-0 flex flex-col gap-[2px] items-start overflow-hidden">
          <p className="self-stretch shrink-0 text-[17px] font-[500] text-[#15171a] leading-[26px]">취득 기간 동안 나오는 자기주식 취득 결과 보고</p>
          <p className="shrink-0 whitespace-nowrap text-[14px] text-[#8e8a97] leading-[normal]">근거 · 이번 주 공시[2]의 취득 기간 · 추가하면 AI 연결도 켜져요</p>
        </div>
        <AddBtn />
      </div>
    </div>
  </div>
</div>
<div className="w-full flex flex-col items-start relative bg-[#ffffff] rounded-[16px] overflow-hidden">
  <div className="self-stretch h-[4px] shrink-0 bg-[#03c75a]" />
  <div className="self-stretch shrink-0 flex items-center py-[18px] px-[24px] bg-[#ebfbf2] overflow-hidden">
    <div className="flex-1 min-w-0 self-stretch flex justify-between items-center overflow-hidden">
      <div className="shrink-0 flex gap-[10px] items-center overflow-hidden">
        <div className="w-[32px] h-[32px] shrink-0 flex justify-center items-center bg-[#03c75a] rounded-[9.6px]">
          <p className="shrink-0 whitespace-nowrap text-center text-[15px] font-[700] text-[#ffffff] leading-[normal]">N</p>
        </div>
        <p className="shrink-0 whitespace-nowrap text-[22px] font-[700] text-[#15171a] leading-[normal]">네이버</p>
        <div className="shrink-0 flex items-start py-[2px] px-[8px] bg-[#f2f3f4] rounded-[6px] overflow-hidden">
          <p className="shrink-0 whitespace-nowrap text-[15px] font-[500] text-[#575b63] leading-[normal]">관심</p>
        </div>
      </div>
      <div className="shrink-0 flex gap-[8px] items-center overflow-hidden">
        <p className="shrink-0 whitespace-nowrap text-[22px] font-[700] text-[#15171a] leading-[normal]">212,300원</p>
        <p className="shrink-0 whitespace-nowrap text-[17px] font-[700] text-[#2f6fe0] leading-[normal]">-0.8%</p>
      </div>
    </div>
  </div>
  <div className="self-stretch shrink-0 flex flex-col gap-[18px] items-start pt-[20px] pr-[24px] pb-[24px] pl-[24px] overflow-hidden">
    <div className="self-stretch shrink-0 flex gap-[8px] items-start overflow-hidden">
      <div className="flex-1 min-w-0 flex flex-col gap-[2px] items-start py-[10px] px-[12px] bg-[#ffffff] border border-[#e8ecf3] rounded-[10px] overflow-hidden">
        <p className="shrink-0 whitespace-nowrap text-[14px] text-[#747d8d] leading-[normal]">주간 등락</p>
        <p className="shrink-0 whitespace-nowrap text-[17px] font-[700] text-[#2f6fe0] leading-[normal]">-0.8%</p>
      </div>
      <div className="flex-1 min-w-0 flex flex-col gap-[2px] items-start py-[10px] px-[12px] bg-[#ffffff] border border-[#e8ecf3] rounded-[10px] overflow-hidden">
        <p className="shrink-0 whitespace-nowrap text-[14px] text-[#747d8d] leading-[normal]">주간 최고</p>
        <p className="shrink-0 whitespace-nowrap text-[17px] font-[700] text-[#15171a] leading-[normal]">216,000</p>
      </div>
      <div className="flex-1 min-w-0 flex flex-col gap-[2px] items-start py-[10px] px-[12px] bg-[#ffffff] border border-[#e8ecf3] rounded-[10px] overflow-hidden">
        <p className="shrink-0 whitespace-nowrap text-[14px] text-[#747d8d] leading-[normal]">주간 최저</p>
        <p className="shrink-0 whitespace-nowrap text-[17px] font-[700] text-[#15171a] leading-[normal]">211,500</p>
      </div>
      <div className="flex-1 min-w-0 flex flex-col gap-[2px] items-start py-[10px] px-[12px] bg-[#ffffff] border border-[#e8ecf3] rounded-[10px] overflow-hidden">
        <p className="shrink-0 whitespace-nowrap text-[14px] text-[#747d8d] leading-[normal]">거래량</p>
        <p className="shrink-0 whitespace-nowrap text-[17px] font-[700] text-[#15171a] leading-[normal]">-9%</p>
      </div>
    </div>
    <div className="self-stretch shrink-0 flex flex-col gap-[6px] items-start overflow-hidden">
      <ScaleBox w={642} h={230}><div className="w-[642px] h-[230px] shrink-0 relative">
        <div className="absolute left-[4px] top-[200px] w-[574px] h-[1px] bg-[#dadde3]" />
        <p className="absolute left-[586px] top-[192px] w-[40px] whitespace-nowrap text-[13px] text-[#8e8a97] leading-[normal]">210,000</p>
        <div className="absolute left-[4px] top-[158px] w-[574px] h-[1px] bg-[#eef0f3]" />
        <div className="absolute left-[4px] top-[115px] w-[574px] h-[1px] bg-[#eef0f3]" />
        <p className="absolute left-[586px] top-[107px] w-[40px] whitespace-nowrap text-[13px] text-[#8e8a97] leading-[normal]">214,000</p>
        <div className="absolute left-[4px] top-[73px] w-[574px] h-[1px] bg-[#eef0f3]" />
        <p className="absolute left-[586px] top-[65px] w-[40px] whitespace-nowrap text-[13px] text-[#8e8a97] leading-[normal]">216,000</p>
        <div className="absolute left-[4px] top-[30px] w-[574px] h-[1px] bg-[#eef0f3]" />
        <p className="absolute left-[586px] top-[22px] w-[40px] whitespace-nowrap text-[13px] text-[#8e8a97] leading-[normal]">218,000</p>
        <p className="absolute left-[12px] top-[210px] w-[41px] whitespace-nowrap text-center text-[13px] text-[#747d8d] leading-[normal]">11.03 월</p>
        <p className="absolute left-[141px] top-[210px] w-[41px] whitespace-nowrap text-center text-[13px] text-[#747d8d] leading-[normal]">11.04 화</p>
        <p className="absolute left-[271px] top-[210px] w-[41px] whitespace-nowrap text-center text-[13px] text-[#747d8d] leading-[normal]">11.05 수</p>
        <p className="absolute left-[400px] top-[210px] w-[41px] whitespace-nowrap text-center text-[13px] text-[#747d8d] leading-[normal]">11.06 목</p>
        <p className="absolute left-[530px] top-[210px] w-[41px] whitespace-nowrap text-center text-[13px] text-[#747d8d] leading-[normal]">11.07 금</p>
        <span className="absolute left-[4px] top-[115px] w-[574px] h-[0px] block"><svg width="574" height="1" viewBox="0 0 574 1" fill="none"><path d="M0 0.5H574" stroke="#B8BEC8" strokeDasharray="4 4"/></svg></span>
        <span className="absolute left-[32px] top-[72.5px] w-[518px] h-[127.5px] block"><svg width="518" height="128" viewBox="0 0 518 128" fill="none"><path d="M0 42.5L129.5 0L259 53.1L388.5 85L518 78.6V127.5H0V42.5Z" fill="url(#paint0_linear_4111_68884)"/><defs><linearGradient id="paint0_linear_4111_68884" x1="0" y1="0" x2="0" y2="1"><stop stopColor="#2F6FE0" stopOpacity="0.16"/><stop offset="1" stopColor="#2F6FE0" stopOpacity="0"/></linearGradient></defs></svg></span>
        <span className="absolute left-[32px] top-[72.5px] w-[518px] h-[85px] block"><svg width="521" height="88" viewBox="0 0 521 88" fill="none"><path d="M1.25037 43.75L130.75 1.25L260.25 54.35L389.75 86.25L519.25 79.85" stroke="#2F6FE0" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/></svg></span>
        <div className="absolute left-[28.5px] top-[111.5px] w-[7px] h-[7px] bg-[#ffffff] border-[2px] border-[#2f6fe0] rounded-full" />
        <div className="absolute left-[158px] top-[69px] w-[7px] h-[7px] bg-[#ffffff] border-[2px] border-[#2f6fe0] rounded-full" />
        <div className="absolute left-[287.5px] top-[122.13px] w-[7px] h-[7px] bg-[#ffffff] border-[2px] border-[#2f6fe0] rounded-full" />
        <div className="absolute left-[417px] top-[154px] w-[7px] h-[7px] bg-[#ffffff] border-[2px] border-[#2f6fe0] rounded-full" />
        <div className="absolute left-[545px] top-[146.13px] w-[10px] h-[10px] bg-[#2f6fe0] border-[2.5px] border-[#ffffff] rounded-full" />
        <div className="absolute left-[582px] top-[143px] flex items-start py-[2px] px-[6px] bg-[#2f6fe0] rounded-[4px] overflow-hidden">
          <p className="shrink-0 whitespace-nowrap text-[13px] font-[700] text-[#ffffff] leading-[normal]">212,300</p>
        </div>
      </div></ScaleBox>
      <div className="shrink-0 flex gap-[12px] items-center overflow-hidden">
        <div className="shrink-0 flex gap-[5px] items-center overflow-hidden">
          <div className="w-[8px] h-[8px] shrink-0 bg-[#7046f5] rounded-full" />
          <p className="shrink-0 whitespace-nowrap text-[14px] text-[#747d8d] leading-[normal]">공시</p>
        </div>
        <div className="shrink-0 flex gap-[5px] items-center overflow-hidden">
          <div className="w-[8px] h-[8px] shrink-0 bg-[#3d73f0] rounded-full" />
          <p className="shrink-0 whitespace-nowrap text-[14px] text-[#747d8d] leading-[normal]">뉴스</p>
        </div>
        <div className="shrink-0 flex gap-[5px] items-center overflow-hidden">
          <span className="w-[14px] h-[0px] shrink-0 block"><svg width="14" height="1" viewBox="0 0 14 1" fill="none"><path d="M0 0.5H14" stroke="#B8BEC8" strokeDasharray="3 3"/></svg></span>
          <p className="shrink-0 whitespace-nowrap text-[14px] text-[#747d8d] leading-[normal]">지난주 종가</p>
        </div>
        <p className="shrink-0 whitespace-nowrap text-[14px] text-[#8e8a97] leading-[normal]">번호는 아래 소식·출처 번호예요</p>
      </div>
    </div>
    <p className="self-stretch shrink-0 text-[17px] text-[#2b2f36] leading-[26px]">이번 주 새 공시·뉴스는 없었어요. 화요일 216,000원까지 올랐다가 이후 내려 212,300원으로 마감했어요.</p>
    <div className="self-stretch shrink-0 flex flex-col gap-[10px] items-start py-[16px] px-[16px] bg-[#faf8ff] border border-[#e6defa] rounded-[12px] overflow-hidden">
      <div className="shrink-0 flex gap-[6px] items-center overflow-hidden">
        <span className="w-[16px] h-[16px] shrink-0 overflow-hidden block"><svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M1.33337 8.00065C1.33337 8.00065 3.73337 3.33398 8.00004 3.33398C12.2667 3.33398 14.6667 8.00065 14.6667 8.00065C14.6667 8.00065 12.2667 12.6673 8.00004 12.6673C3.73337 12.6673 1.33337 8.00065 1.33337 8.00065Z" stroke="#6A42AB" strokeWidth="1.33333" strokeLinejoin="round"/><path d="M8 10C9.10457 10 10 9.10457 10 8C10 6.89543 9.10457 6 8 6C6.89543 6 6 6.89543 6 8C6 9.10457 6.89543 10 8 10Z" stroke="#6A42AB" strokeWidth="1.33333"/></svg></span>
        <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#6a42ab] leading-[normal]">앞으로 지켜볼 것</p>
      </div>
      <div className="self-stretch shrink-0 flex gap-[16px] items-center pt-[12px] pr-[12px] pb-[12px] pl-[14px] bg-[#ffffff] rounded-[10px] overflow-hidden">
        <div className="flex-1 min-w-0 flex flex-col gap-[2px] items-start overflow-hidden">
          <p className="self-stretch shrink-0 text-[17px] font-[500] text-[#15171a] leading-[26px]">다음 주 새 공시·뉴스가 나오는지</p>
          <p className="shrink-0 whitespace-nowrap text-[14px] text-[#8e8a97] leading-[normal]">근거 · 이번 주 소식 0건 · 추가하면 새 메모로 남겨요</p>
        </div>
        <AddBtn />
      </div>
    </div>
  </div>
</div>
<div className="w-full flex gap-[10px] items-center pt-[8px] relative overflow-hidden">
  <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#6a42ab] leading-[normal]">03</p>
  <p className="shrink-0 whitespace-nowrap text-[17px] font-[700] text-[#15171a] leading-[normal]">출처</p>
  <div className="flex-1 min-w-0 h-[1px] bg-[#dcdfe5]" />
</div>
<div className="w-full flex flex-col gap-[8px] items-start py-[24px] px-[24px] relative bg-[#ffffff] rounded-[16px] overflow-hidden">
  <p className="shrink-0 whitespace-nowrap text-[15px] text-[#575b63] leading-[normal]">[1] DART · SK하이닉스 신규시설투자 · 2026.11.04</p>
  <p className="shrink-0 whitespace-nowrap text-[15px] text-[#575b63] leading-[normal]">[2] DART · 삼성전자 자기주식취득결정 · 2026.11.05</p>
  <p className="shrink-0 whitespace-nowrap text-[15px] text-[#575b63] leading-[normal]">[3] 한국경제 · 기사 제목 · 2026.11.06</p>
  <p className="shrink-0 whitespace-nowrap text-[15px] text-[#575b63] leading-[normal]">[4] 매일경제 · 기사 제목 · 2026.11.07</p>
  <p className="shrink-0 whitespace-nowrap text-[15px] text-[#575b63] leading-[normal]">[5] 언론사 · 기사 제목 · 2026.11.04</p>
  <p className="shrink-0 whitespace-nowrap text-[15px] text-[#575b63] leading-[normal]">[6] 언론사 · 기사 제목 · 2026.11.05</p>
  <p className="shrink-0 whitespace-nowrap text-[15px] text-[#575b63] leading-[normal]">[7] 언론사 · 기사 제목 · 2026.11.07</p>
  <p className="self-stretch shrink-0 text-[14px] text-[#8e8a97] leading-[21px]">시세는 KIS, 공시는 DART 원문을 바탕으로 정리했어요. 뉴스는 제목·언론사·날짜만 쓰고 원문 링크로 연결해요.</p>
</div>
<div className="w-full flex justify-between items-center pt-[8px] relative overflow-hidden">
  <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#575b63] leading-[normal]">memo's · 주간보고서</p>
  <p className="self-stretch shrink-0 whitespace-nowrap text-[14px] text-[#8e8a97] leading-[normal]">투자 권유나 주가 예측이 아니에요 · 숫자는 시안용 예시</p>
</div>
</div>
</div>
  );
}
