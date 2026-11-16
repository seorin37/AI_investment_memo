/* eslint-disable */
// Figma에서 그대로 변환 (자동 생성)
import type { MouseEvent } from "react";

export function LabResultBody({ onAct }: { onAct?: (a: string, e: MouseEvent) => void }) {
  const act = (e: MouseEvent) => { const t = (e.target as HTMLElement).closest("[data-act]") as HTMLElement | null; if (t && onAct) onAct(t.dataset.act!, e); };
  return (
<div onClick={act} className="contents">
<div className="w-full flex flex-col gap-[16px] items-start relative overflow-hidden">
  <div className="self-stretch shrink-0 flex flex-col gap-[8px] items-start overflow-hidden">
    <div className="shrink-0 flex gap-[8px] items-center overflow-hidden">
      <div className="w-[26px] h-[26px] shrink-0 flex justify-center items-center bg-[#ea002c] rounded-[7.8px]">
        <p className="shrink-0 whitespace-nowrap text-center text-[15px] font-[700] text-[#ffffff] leading-[normal]">S</p>
      </div>
      <p className="shrink-0 whitespace-nowrap text-[22px] font-[700] text-[#15171a] leading-[normal]">SK하이닉스</p>
    </div>
    <div className="shrink-0 flex gap-[6px] items-start flex-wrap overflow-hidden">
      <div className="shrink-0 flex items-start py-[4px] px-[10px] bg-[#f2f3f4] rounded-[999px] overflow-hidden">
        <p className="shrink-0 whitespace-nowrap text-[15px] font-[500] text-[#404752] leading-[normal]">원/달러 환율 · 하락 가정</p>
      </div>
      <div className="shrink-0 flex items-start py-[4px] px-[10px] bg-[#f2f3f4] rounded-[999px] overflow-hidden">
        <p className="shrink-0 whitespace-nowrap text-[15px] font-[500] text-[#404752] leading-[normal]">미국 10년물 국채금리 · 상승 가정</p>
      </div>
    </div>
    <p className="self-stretch shrink-0 text-[14px] text-[#747d8d] leading-[21px]">바꾼 가정이 회사의 어떤 항목에 닿는지 경로로 보여 드려요.</p>
  </div>
  <div className="self-stretch shrink-0 flex flex-col gap-[12px] items-start py-[16px] px-[16px] bg-[#ffffff] border border-[#e8ecf3] rounded-[12px] overflow-hidden">
    <p className="shrink-0 whitespace-nowrap text-[17px] font-[700] text-[#15171a] leading-[normal]">영향 경로 지도</p>
    <div className="w-[346px] h-[268px] shrink-0 relative mx-auto">
      <span className="absolute left-[188px] top-[206px] w-[20px] h-[36px] block"><svg width="22" height="38" viewBox="0 0 22 38" fill="none"><path d="M0.75 0.75C10.75 0.75 10.75 36.75 20.75 36.75" stroke="#A9AFBA" strokeWidth="1.5" strokeLinecap="round" strokeDasharray="4 3"/></svg></span>
      <span className="absolute left-[188px] top-[170px] w-[20px] h-[36px] block"><svg width="22" height="38" viewBox="0 0 22 38" fill="none"><path d="M0.75 36.75C10.75 36.75 10.75 0.75 20.75 0.75" stroke="#A9AFBA" strokeWidth="1.5" strokeLinecap="round" strokeDasharray="4 3"/></svg></span>
      <span className="absolute left-[96px] top-[206px] w-[16px] h-[0px] block"><svg width="22" height="2" viewBox="0 0 22 2" fill="none"><path d="M0.75 0.75C10.75 0.75 10.75 0.75 20.75 0.75" stroke="#575B63" strokeWidth="1.5" strokeLinecap="round"/></svg></span>
      <span className="absolute left-[188px] top-[62px] w-[20px] h-[36px] block"><svg width="22" height="38" viewBox="0 0 22 38" fill="none"><path d="M0.75 0.75C10.75 0.75 10.75 36.75 20.75 36.75" stroke="#A9AFBA" strokeWidth="1.5" strokeLinecap="round" strokeDasharray="4 3"/></svg></span>
      <span className="absolute left-[188px] top-[26px] w-[20px] h-[36px] block"><svg width="22" height="38" viewBox="0 0 22 38" fill="none"><path d="M0.75 36.75C10.75 36.75 10.75 0.75 20.75 0.75" stroke="#575B63" strokeWidth="1.5" strokeLinecap="round"/></svg></span>
      <span className="absolute left-[96px] top-[62px] w-[16px] h-[0px] block"><svg width="22" height="2" viewBox="0 0 22 2" fill="none"><path d="M0.75 0.75C10.75 0.75 10.75 0.75 20.75 0.75" stroke="#575B63" strokeWidth="1.5" strokeLinecap="round"/></svg></span>
      <div className="absolute left-[0px] top-[36px] w-[96px] h-[52px] flex flex-col gap-[1px] justify-center items-start px-[8px] bg-[#f5f6f8] rounded-[10px] overflow-hidden">
        <p className="self-stretch shrink-0 text-[14px] font-[700] text-[#15171a] leading-[20px]">원/달러 환율</p>
        <p className="self-stretch shrink-0 text-[14px] text-[#747d8d] leading-[20px]">가정 · 하락</p>
      </div>
      <div className="absolute left-[112px] top-[38px] w-[76px] h-[48px] flex flex-col gap-[1px] justify-center items-start px-[8px] bg-[#ffffff] border border-[#e3e6eb] rounded-[10px] overflow-hidden">
        <p className="self-stretch shrink-0 text-[14px] font-[500] text-[#2b2f36] leading-[20px]">원화 가치<br/>변화</p>
      </div>
      <div className="absolute left-[208px] top-[0px] w-[134px] h-[52px] flex flex-col gap-[1px] justify-center items-start px-[8px] bg-[#f7f4ff] border border-[#d9ccf5] rounded-[10px] overflow-hidden">
        <p className="self-stretch shrink-0 text-[14px] font-[500] text-[#15171a] leading-[20px]">① 달러 매출의<br/>원화 환산액</p>
      </div>
      <div className="absolute left-[205px] top-[23px] w-[6px] h-[6px] bg-[#575b63] rounded-full" />
      <div className="absolute left-[208px] top-[72px] w-[134px] h-[52px] flex flex-col gap-[1px] justify-center items-start px-[8px] bg-[#ffffff] border border-[#e3e6eb] rounded-[10px] overflow-hidden">
        <p className="self-stretch shrink-0 text-[14px] font-[500] text-[#15171a] leading-[20px]">② 달러로 사는<br/>원가·장비</p>
      </div>
      <div className="absolute left-[205px] top-[95px] w-[6px] h-[6px] bg-[#a9afba] rounded-full" />
      <div className="absolute left-[0px] top-[174px] w-[96px] h-[64px] flex flex-col gap-[1px] justify-center items-start px-[8px] bg-[#f5f6f8] rounded-[10px] overflow-hidden">
        <p className="self-stretch shrink-0 text-[14px] font-[700] text-[#15171a] leading-[20px]">미국 10년물<br/>국채금리</p>
        <p className="self-stretch shrink-0 text-[14px] text-[#747d8d] leading-[20px]">가정 · 상승</p>
      </div>
      <div className="absolute left-[112px] top-[182px] w-[76px] h-[48px] flex flex-col gap-[1px] justify-center items-start px-[8px] bg-[#ffffff] border border-[#e3e6eb] rounded-[10px] overflow-hidden">
        <p className="self-stretch shrink-0 text-[14px] font-[500] text-[#2b2f36] leading-[20px]">장기금리<br/>변화</p>
      </div>
      <div className="absolute left-[208px] top-[144px] w-[134px] h-[52px] flex flex-col gap-[1px] justify-center items-start px-[8px] bg-[#ffffff] border border-[#e3e6eb] rounded-[10px] overflow-hidden">
        <p className="self-stretch shrink-0 text-[14px] font-[500] text-[#15171a] leading-[20px]">③ 설비투자<br/>자금 조달</p>
      </div>
      <div className="absolute left-[205px] top-[167px] w-[6px] h-[6px] bg-[#a9afba] rounded-full" />
      <div className="absolute left-[208px] top-[216px] w-[134px] h-[52px] flex flex-col gap-[1px] justify-center items-start px-[8px] bg-[#ffffff] border border-[#e3e6eb] rounded-[10px] overflow-hidden">
        <p className="self-stretch shrink-0 text-[14px] font-[500] text-[#15171a] leading-[20px]">④ 주식 가치 평가의<br/>할인율</p>
      </div>
      <div className="absolute left-[205px] top-[239px] w-[6px] h-[6px] bg-[#a9afba] rounded-full" />
    </div>
    <div className="shrink-0 flex gap-[14px] items-center overflow-hidden">
      <div className="shrink-0 flex gap-[6px] items-center overflow-hidden">
        <span className="w-[18px] h-[0px] shrink-0 block"><svg width="18" height="2" viewBox="0 0 18 2" fill="none"><path d="M0 0.75H18" stroke="#575B63" strokeWidth="1.5"/></svg></span>
        <p className="shrink-0 whitespace-nowrap text-[14px] text-[#747d8d] leading-[normal]">회사 공시에 근거 있음</p>
      </div>
      <div className="shrink-0 flex gap-[6px] items-center overflow-hidden">
        <span className="w-[18px] h-[0px] shrink-0 block"><svg width="18" height="2" viewBox="0 0 18 2" fill="none"><path d="M0 0.75H18" stroke="#A9AFBA" strokeWidth="1.5" strokeDasharray="4 3"/></svg></span>
        <p className="shrink-0 whitespace-nowrap text-[14px] text-[#747d8d] leading-[normal]">일반적인 이론 경로</p>
      </div>
    </div>
    <p className="self-stretch shrink-0 text-[14px] text-[#8e8a97] leading-[21px]">조건끼리도 서로 영향을 주고받아요. 그래서 하나로 합치지 않고 조건별로 따로 그렸어요.</p>
  </div>
  <div className="self-stretch shrink-0 flex flex-col gap-[10px] items-start overflow-hidden">
    <p className="shrink-0 whitespace-nowrap text-[17px] font-[700] text-[#15171a] leading-[normal]">항목별 설명</p>
    <div className="self-stretch shrink-0 flex flex-col gap-[6px] items-start py-[14px] px-[16px] bg-[#ffffff] border border-[#e8ecf3] rounded-[12px] overflow-hidden">
      <div className="shrink-0 flex gap-[6px] items-center overflow-hidden">
        <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#15171a] leading-[normal]">①</p>
        <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#15171a] leading-[normal]">달러 매출의 원화 환산액</p>
      </div>
      <p className="self-stretch shrink-0 text-[15px] text-[#2b2f36] leading-[23px]">매출 대부분이 달러로 들어와, 환율이 바뀌면 원화로 바꾼 매출 금액도 달라질 수 있어요.</p>
      <div className="self-stretch shrink-0 flex gap-[6px] items-center py-[6px] px-[10px] bg-[#f7f4ff] rounded-[8px] overflow-hidden">
        <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#6a42ab] leading-[normal]">공시</p>
        <p className="flex-1 min-w-0 text-[15px] text-[#575b63] leading-[23px]">2025 사업보고서 · 환율 10% 변동 시 세전이익 약 ○○억 원 변동</p>
      </div>
      <p className="self-stretch shrink-0 text-[14px] text-[#747d8d] leading-[21px]">함께 볼 점 · 판매 가격과 물량이 함께 바뀌면 환율 효과만 따로 떼어 보기 어려워요.</p>
    </div>
    <div className="self-stretch shrink-0 flex flex-col gap-[6px] items-start py-[14px] px-[16px] bg-[#ffffff] border border-[#e8ecf3] rounded-[12px] overflow-hidden">
      <div className="shrink-0 flex gap-[6px] items-center overflow-hidden">
        <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#15171a] leading-[normal]">②</p>
        <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#15171a] leading-[normal]">달러로 사는 원가·장비</p>
      </div>
      <p className="self-stretch shrink-0 text-[15px] text-[#2b2f36] leading-[23px]">장비·원재료를 달러로 사는 만큼 원화 비용도 함께 달라져, ①과 일부 상쇄될 수 있어요.</p>
      <div className="self-stretch shrink-0 flex gap-[6px] items-center py-[6px] px-[10px] bg-[#f5f6f8] rounded-[8px] overflow-hidden">
        <p className="shrink-0 whitespace-nowrap text-[14px] font-[700] text-[#747d8d] leading-[normal]">이론</p>
        <p className="flex-1 min-w-0 text-[15px] text-[#575b63] leading-[23px]">일반적인 경로 · 달러 매입 비중은 공시로 확인이 필요해요</p>
      </div>
    </div>
    <div className="self-stretch shrink-0 flex flex-col gap-[6px] items-start py-[14px] px-[16px] bg-[#ffffff] border border-[#e8ecf3] rounded-[12px] overflow-hidden">
      <div className="shrink-0 flex gap-[6px] items-center overflow-hidden">
        <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#15171a] leading-[normal]">③</p>
        <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#15171a] leading-[normal]">설비투자 자금 조달</p>
      </div>
      <p className="self-stretch shrink-0 text-[15px] text-[#2b2f36] leading-[23px]">장기금리가 바뀌면 새로 빌리는 돈의 이자 조건도 달라질 수 있어요.</p>
      <div className="self-stretch shrink-0 flex gap-[6px] items-center py-[6px] px-[10px] bg-[#f5f6f8] rounded-[8px] overflow-hidden">
        <p className="shrink-0 whitespace-nowrap text-[14px] font-[700] text-[#747d8d] leading-[normal]">이론</p>
        <p className="flex-1 min-w-0 text-[15px] text-[#575b63] leading-[23px]">일반적인 경로 · 회사 공시 없음</p>
      </div>
      <p className="self-stretch shrink-0 text-[14px] text-[#747d8d] leading-[21px]">함께 볼 점 · 현금 보유와 차입 구조에 따라 체감 정도가 달라요.</p>
    </div>
    <div className="self-stretch shrink-0 flex flex-col gap-[6px] items-start py-[14px] px-[16px] bg-[#ffffff] border border-[#e8ecf3] rounded-[12px] overflow-hidden">
      <div className="shrink-0 flex gap-[6px] items-center overflow-hidden">
        <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#15171a] leading-[normal]">④</p>
        <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#15171a] leading-[normal]">주식 가치 평가의 할인율</p>
      </div>
      <p className="self-stretch shrink-0 text-[15px] text-[#2b2f36] leading-[23px]">장기금리는 미래 이익을 지금 가치로 바꿀 때 쓰는 할인율에 반영되곤 해요.</p>
      <div className="self-stretch shrink-0 flex gap-[6px] items-center py-[6px] px-[10px] bg-[#f5f6f8] rounded-[8px] overflow-hidden">
        <p className="shrink-0 whitespace-nowrap text-[14px] font-[700] text-[#747d8d] leading-[normal]">이론</p>
        <p className="flex-1 min-w-0 text-[15px] text-[#575b63] leading-[23px]">일반적인 경로 · 이론</p>
      </div>
      <p className="self-stretch shrink-0 text-[14px] text-[#747d8d] leading-[21px]">함께 볼 점 · 실제 주가는 이것 말고도 많은 요인으로 움직여요.</p>
    </div>
  </div>
  <div className="self-stretch shrink-0 flex flex-col gap-[6px] items-start pt-[18px] pr-[16px] pb-[14px] pl-[16px] relative bg-[#fceaaa] rounded-[12px]">
    <div className="self-stretch shrink-0 flex justify-between items-center overflow-hidden">
      <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#575b63] leading-[normal]">내 메모와 연결</p>
      <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#15171a] leading-[normal]" data-act="memo" role="button" style={{cursor:"pointer"}}>원본 메모 보기 ›</p>
    </div>
    <p className="self-stretch shrink-0 text-[17px] font-[700] text-[#15171a] leading-[normal]">HBM 점유율이 유지되면 계속 들고 간다</p>
    <p className="self-stretch shrink-0 text-[15px] text-[#2b2f36] leading-[23px]">이번 실험의 ①은 실적 숫자에 닿는 경로예요. 메모에서 중요하게 본 HBM 수요·점유율과는 다른 요인이라, 둘을 나눠서 보면 좋아요.</p>
    <div className="absolute left-[161.27px] top-[-6px] w-[56px] h-[14px] bg-[rgba(255,255,255,0.55)]" />
  </div>
  <div className="self-stretch shrink-0 flex flex-col gap-[10px] items-start py-[16px] px-[16px] bg-[#faf8ff] border border-[#e6defa] rounded-[12px] overflow-hidden">
    <div className="shrink-0 flex gap-[6px] items-center overflow-hidden">
      <span className="w-[16px] h-[16px] shrink-0 overflow-hidden block"><svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M1.33325 8.00065C1.33325 8.00065 3.73325 3.33398 7.99992 3.33398C12.2666 3.33398 14.6666 8.00065 14.6666 8.00065C14.6666 8.00065 12.2666 12.6673 7.99992 12.6673C3.73325 12.6673 1.33325 8.00065 1.33325 8.00065Z" stroke="#6A42AB" strokeWidth="1.33333" strokeLinejoin="round"/><path d="M8 10C9.10457 10 10 9.10457 10 8C10 6.89543 9.10457 6 8 6C6.89543 6 6 6.89543 6 8C6 9.10457 6.89543 10 8 10Z" stroke="#6A42AB" strokeWidth="1.33333"/></svg></span>
      <p className="shrink-0 whitespace-nowrap text-[15px] font-[700] text-[#6a42ab] leading-[normal]">추가로 확인할 것</p>
    </div>
    <div className="self-stretch shrink-0 flex flex-col gap-[2px] items-start py-[12px] px-[14px] bg-[#ffffff] rounded-[10px] overflow-hidden">
      <p className="self-stretch shrink-0 text-[15px] font-[500] text-[#15171a] leading-[normal]">다음 분기보고서의 환율 영향 설명</p>
      <p className="self-stretch shrink-0 text-[14px] text-[#8e8a97] leading-[normal]">근거 · ① 공시 민감도의 최신 값</p>
    </div>
    <div className="self-stretch shrink-0 flex flex-col gap-[2px] items-start py-[12px] px-[14px] bg-[#ffffff] rounded-[10px] overflow-hidden">
      <p className="self-stretch shrink-0 text-[15px] font-[500] text-[#15171a] leading-[normal]">달러로 사는 원가·장비 비중</p>
      <p className="self-stretch shrink-0 text-[14px] text-[#8e8a97] leading-[normal]">근거 · ② 상쇄 정도를 가늠하려면 필요해요</p>
    </div>
    <div className="self-stretch shrink-0 flex flex-col gap-[2px] items-start py-[12px] px-[14px] bg-[#ffffff] rounded-[10px] overflow-hidden">
      <p className="self-stretch shrink-0 text-[15px] font-[500] text-[#15171a] leading-[normal]">설비투자 계획과 자금 조달 공시</p>
      <p className="self-stretch shrink-0 text-[14px] text-[#8e8a97] leading-[normal]">근거 · ③ 차입 구조 확인</p>
    </div>
  </div>
  <p className="self-stretch shrink-0 text-center text-[14px] text-[#8e8a97] leading-[21px]">AI가 가정을 바탕으로 정리한 결과예요. 실제와 다를 수 있으니 공시와 함께 확인해 주세요.</p>
</div>
</div>
  );
}
