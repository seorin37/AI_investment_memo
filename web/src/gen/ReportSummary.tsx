/* eslint-disable */
// Figma에서 그대로 변환 (자동 생성)
import type { MouseEvent } from "react";

export function ReportSummary({ onAct }: { onAct?: (a: string, e: MouseEvent) => void }) {
  const act = (e: MouseEvent) => { const t = (e.target as HTMLElement).closest("[data-act]") as HTMLElement | null; if (t && onAct) onAct(t.dataset.act!, e); };
  return (
<div onClick={act} className="contents">
<div className="w-full flex flex-col gap-[16px] items-start relative overflow-hidden">
  <div className="self-stretch shrink-0 flex flex-col gap-[4px] items-start overflow-hidden">
    <p className="shrink-0 whitespace-nowrap text-[14px] font-[500] text-[#747d8d] leading-[normal]">MEMO'S 주간보고서 · 2026년 11월 2주</p>
    <p className="shrink-0 whitespace-nowrap text-[22px] font-[700] text-[#15171a] leading-[normal]">이번 주 내 종목 보고서</p>
    <p className="shrink-0 whitespace-nowrap text-[14px] text-[#747d8d] leading-[normal]">11.03(월) ~ 11.07(금) · 거래일 5일 · 3종목</p>
  </div>
  <div className="self-stretch shrink-0 flex flex-col gap-[6px] items-start py-[14px] px-[16px] bg-[#f5f6f8] rounded-[12px] overflow-hidden">
    <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#575b63] leading-[normal]">이번 주 한눈에</p>
    <p className="self-stretch shrink-0 text-[15px] text-[#2b2f36] leading-[23px]">내 종목 3곳 중 2곳이 올랐어요. SK하이닉스는 화요일 시설투자 공시 뒤 6.2% 올라 가장 크게 움직였고, 삼성전자는 메모에 적어 둔 자기주식 취득 공시가 나왔어요.</p>
  </div>
  <div className="self-stretch shrink-0 flex gap-[8px] items-start overflow-hidden">
    <div className="flex-1 min-w-0 flex flex-col gap-[2px] items-start py-[10px] px-[12px] bg-[#f5f6f8] rounded-[10px] overflow-hidden">
      <p className="shrink-0 whitespace-nowrap text-[14px] text-[#747d8d] leading-[normal]">코스피</p>
      <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#e5484d] leading-[normal]">+2.0%</p>
    </div>
    <div className="flex-1 min-w-0 flex flex-col gap-[2px] items-start py-[10px] px-[12px] bg-[#f5f6f8] rounded-[10px] overflow-hidden">
      <p className="shrink-0 whitespace-nowrap text-[14px] text-[#747d8d] leading-[normal]">코스닥</p>
      <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#e5484d] leading-[normal]">+0.6%</p>
    </div>
    <div className="flex-1 min-w-0 flex flex-col gap-[2px] items-start py-[10px] px-[12px] bg-[#f5f6f8] rounded-[10px] overflow-hidden">
      <p className="shrink-0 whitespace-nowrap text-[14px] text-[#747d8d] leading-[normal]">원/달러</p>
      <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#2f6fe0] leading-[normal]">-1.6%</p>
    </div>
  </div>
  <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#15171a] leading-[normal]">종목별 흐름</p>
  <div className="self-stretch shrink-0 flex flex-col items-start border border-[#e8ecf3] rounded-[12px] overflow-hidden">
    <div className="self-stretch shrink-0 flex gap-[12px] items-center py-[12px] px-[14px] overflow-hidden">
      <div className="w-[28px] h-[28px] shrink-0 flex justify-center items-center bg-[#ea002c] rounded-[8.4px]">
        <p className="shrink-0 whitespace-nowrap text-center text-[15px] font-[700] text-[#ffffff] leading-[normal]">S</p>
      </div>
      <div className="flex-1 min-w-0 flex flex-col gap-[2px] items-start overflow-hidden">
        <div className="shrink-0 flex gap-[6px] items-center overflow-hidden">
          <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#15171a] leading-[normal]">SK하이닉스</p>
          <div className="shrink-0 flex items-start py-[1px] px-[6px] bg-[#f2f3f4] rounded-[5px] overflow-hidden">
            <p className="shrink-0 whitespace-nowrap text-[15px] font-[500] text-[#575b63] leading-[normal]">보유</p>
          </div>
        </div>
        <p className="shrink-0 whitespace-nowrap text-[14px] text-[#747d8d] leading-[normal]">공시 1 · 뉴스 2 · 메모 1개와 연결</p>
      </div>
      <div className="w-[52px] h-[22px] shrink-0 relative overflow-hidden">
        <span className="absolute left-[2px] top-[2px] w-[48px] h-[18px] block"><svg width="50" height="20" viewBox="0 0 50 20" fill="none"><path d="M0.875244 18.875L12.8752 14.775L24.8752 5.775L36.8752 3.075L48.8752 0.875" stroke="#E5484D" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"/></svg></span>
        <div className="absolute left-[47.5px] top-[-0.5px] w-[5px] h-[5px] bg-[#e5484d] rounded-full" />
      </div>
      <p className="shrink-0 whitespace-nowrap text-right text-[15px] font-[700] text-[#e5484d] leading-[normal]">+6.2%</p>
    </div>
    <div className="self-stretch shrink-0 flex gap-[12px] items-center py-[12px] px-[14px] border-t border-[#eef0f3] overflow-hidden">
      <div className="w-[28px] h-[28px] shrink-0 flex justify-center items-center bg-[#1428a0] rounded-[8.4px]">
        <p className="shrink-0 whitespace-nowrap text-center text-[15px] font-[700] text-[#ffffff] leading-[normal]">삼</p>
      </div>
      <div className="flex-1 min-w-0 flex flex-col gap-[2px] items-start overflow-hidden">
        <div className="shrink-0 flex gap-[6px] items-center overflow-hidden">
          <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#15171a] leading-[normal]">삼성전자</p>
          <div className="shrink-0 flex items-start py-[1px] px-[6px] bg-[#f2f3f4] rounded-[5px] overflow-hidden">
            <p className="shrink-0 whitespace-nowrap text-[15px] font-[500] text-[#575b63] leading-[normal]">관심</p>
          </div>
        </div>
        <p className="shrink-0 whitespace-nowrap text-[14px] text-[#747d8d] leading-[normal]">공시 1 · 메모 1개와 연결</p>
      </div>
      <div className="w-[52px] h-[22px] shrink-0 relative overflow-hidden">
        <span className="absolute left-[2px] top-[2px] w-[48px] h-[18px] block"><svg width="50" height="20" viewBox="0 0 50 20" fill="none"><path d="M0.875244 14.175L12.8752 18.875L24.8752 2.475L36.8752 0.875L48.8752 6.375" stroke="#E5484D" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"/></svg></span>
        <div className="absolute left-[47.5px] top-[4.98px] w-[5px] h-[5px] bg-[#e5484d] rounded-full" />
      </div>
      <p className="shrink-0 whitespace-nowrap text-right text-[15px] font-[700] text-[#e5484d] leading-[normal]">+1.4%</p>
    </div>
    <div className="self-stretch shrink-0 flex gap-[12px] items-center py-[12px] px-[14px] border-t border-[#eef0f3] overflow-hidden">
      <div className="w-[28px] h-[28px] shrink-0 flex justify-center items-center bg-[#03c75a] rounded-[8.4px]">
        <p className="shrink-0 whitespace-nowrap text-center text-[15px] font-[700] text-[#ffffff] leading-[normal]">N</p>
      </div>
      <div className="flex-1 min-w-0 flex flex-col gap-[2px] items-start overflow-hidden">
        <div className="shrink-0 flex gap-[6px] items-center overflow-hidden">
          <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#15171a] leading-[normal]">네이버</p>
          <div className="shrink-0 flex items-start py-[1px] px-[6px] bg-[#f2f3f4] rounded-[5px] overflow-hidden">
            <p className="shrink-0 whitespace-nowrap text-[15px] font-[500] text-[#575b63] leading-[normal]">관심</p>
          </div>
        </div>
        <p className="shrink-0 whitespace-nowrap text-[14px] text-[#747d8d] leading-[normal]">새 소식 없음 · 연결된 메모 없음</p>
      </div>
      <div className="w-[52px] h-[22px] shrink-0 relative overflow-hidden">
        <span className="absolute left-[2px] top-[2px] w-[48px] h-[18px] block"><svg width="50" height="20" viewBox="0 0 50 20" fill="none"><path d="M0.875 9.875L12.875 0.875L24.875 12.175L36.875 18.875L48.875 17.575" stroke="#2F6FE0" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"/></svg></span>
        <div className="absolute left-[47.5px] top-[16.15px] w-[5px] h-[5px] bg-[#2f6fe0] rounded-full" />
      </div>
      <p className="shrink-0 whitespace-nowrap text-right text-[15px] font-[700] text-[#2f6fe0] leading-[normal]">-0.8%</p>
    </div>
  </div>
  <div data-act="detail" role="button" style={{cursor:"pointer"}} className="self-stretch shrink-0 flex justify-center items-center py-[13px] bg-[#15171a] rounded-[12px] overflow-hidden">
    <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#ffffff] leading-[normal]">자세히 보기</p>
  </div>
  <p className="self-stretch shrink-0 text-[14px] text-[#8e8a97] leading-[21px]">공시·뉴스·시세에서 가져온 정보예요. 투자 권유나 주가 예측이 아니에요.</p>
</div>
</div>
  );
}
