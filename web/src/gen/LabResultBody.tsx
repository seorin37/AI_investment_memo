/* AI 투자 실험실 · 결과 (412) — 실험 데이터로 그려요. 모양은 Figma 'lab result' 그대로 */
import type { LabResult } from "../api/types";
import type { Memo } from "../data";
import { api } from "../api";

const DIRC: Record<string, string> = { 상승: "#d93033", 유지: "#15171a", 하락: "#2f6fe0" };
const VERD = { 긍정: ["#fdecec", "#c0392b", "실적·평가에 긍정적인 경로가 더 많아요"], 부정: ["#e9f0fd", "#1f5fd6", "실적·평가에 부담이 되는 경로가 더 많아요"], 중립: ["#f2f3f4", "#404752", "긍정·부담 경로가 섞여 있어요"] } as const;
export function LabResultBody({ r, memo, onMemo }: { r: LabResult; memo?: Memo; onMemo: (id?: number) => void }) {
  const i = api.market.info(r.stock_code);
  const v = VERD[r.verdict];
  const Num = ({ n, dark }: { n: number; dark?: boolean }) => <span className={"grid h-[18px] w-[18px] shrink-0 place-items-center rounded-full text-[11px] font-bold " + (dark ? "bg-[#15171a] text-white" : "bg-[#eef0f3] text-[#575b63]")}>{n}</span>;
  return (
    <div data-lab-result className="relative flex w-full flex-col items-start gap-[16px] overflow-hidden">
      <div className="flex flex-col items-start gap-[8px] self-stretch">
        <div className="flex items-center gap-[8px]">
          <div className="dk-keep flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-[7.8px]" style={{ background: i?.logo_bg }}><p className="text-center font-bold" style={{ color: i?.logo_ink ?? "#fff", fontSize: (i?.logo.length ?? 1) > 1 ? 11 : 15 }}>{i?.logo}</p></div>
          <p className="text-[22px] font-bold text-[#15171a]">{r.name}</p>
        </div>
        <div className="flex flex-wrap items-start gap-[6px]">
          {r.vars.filter(([, d]) => d !== "유지").map(([n, d]) => <div key={n} className="rounded-[999px] bg-[#f2f3f4] px-[10px] py-[4px]"><p className="text-[15px] font-medium text-[#404752]">{n} · <span style={{ color: DIRC[d] }}>{d}</span> 가정</p></div>)}
        </div>
        <p className="self-stretch text-[14px] leading-[21px] text-[#747d8d]">바꾼 가정이 회사의 어떤 항목에 닿는지 경로로 보여 드려요.</p>
      </div>
      <div data-lab-verdict className="flex flex-col gap-1 self-stretch rounded-[12px] px-4 py-3" style={{ background: v[0] }}>
        <p className="text-[17px] font-bold" style={{ color: v[1] }}>종합 방향 · {r.verdict}</p>
        <p className="text-[14px] leading-[21px]" style={{ color: v[1] }}>{v[2]} · 크기가 아니라 방향만 보여요</p>
      </div>
      <div className="flex flex-col gap-[12px] self-stretch rounded-[12px] border border-[#e8ecf3] bg-white p-[16px]">
        <p className="text-[17px] font-bold text-[#15171a]">영향 경로 지도</p>
        {r.paths.map((p, k) => (
          <div key={k} className="flex items-center gap-2">
            <div className="flex w-[118px] shrink-0 flex-col rounded-[10px] bg-[#f5f6f8] px-[8px] py-[6px]"><p className="text-[13px] font-bold leading-[18px] text-[#15171a]">{p.from.replace(/ (상승|하락)$/, "")}</p><p className="text-[13px] leading-[18px]" style={{ color: DIRC[p.from.split(" ").pop()!] }}>가정 · {p.from.split(" ").pop()}</p></div>
            <svg width="22" height="10" viewBox="0 0 22 10" fill="none"><path d="M1 5H20M16 1L20 5L16 9" stroke={p.sign ? "#575B63" : "#A9AFBA"} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" strokeDasharray={p.sign ? undefined : "3 3"} /></svg>
            <div className="flex min-w-0 flex-1 items-center gap-2 rounded-[10px] border border-[#e3e6eb] bg-white px-[8px] py-[8px]"><Num n={k + 1} /><p className="min-w-0 flex-1 text-[13px] font-bold leading-[18px]" style={{ color: p.sign > 0 ? "#c0392b" : p.sign < 0 ? "#1f5fd6" : "#575b63" }}>{p.to}</p></div>
          </div>
        ))}
        <p className="text-[13px] leading-[20px] text-[#8e8a97]">조건끼리도 서로 영향을 주고받아요. 그래서 하나로 합치지 않고 조건별로 따로 그렸어요.</p>
      </div>
      <p className="text-[17px] font-bold text-[#15171a]">항목별 설명</p>
      {r.paths.map((p, k) => (
        <div key={k} className="flex gap-3 self-stretch">
          <span className="mt-[2px]"><Num n={k + 1} dark /></span>
          <div className="flex min-w-0 flex-1 flex-col gap-1"><p className="text-[15px] font-bold text-[#15171a]">{p.from} → {p.to}</p><p className="break-keep text-[14px] leading-[21px] text-[#575b63]">{p.why}</p><p className="text-[13px] text-[#8e8a97]">일반적인 이론 경로 · {r.name}의 실제 비중은 공시로 확인이 필요해요</p></div>
        </div>
      ))}
      <div className="flex flex-col gap-2 self-stretch rounded-[12px] bg-[#f7f8fa] p-4">
        <div className="flex items-center justify-between"><p className="text-[15px] font-bold text-[#15171a]">내 메모와 연결</p><button data-act="memo" onClick={() => onMemo(memo?.id)} className="text-[14px] font-bold text-[#575b63] hover:text-[#15171a]">{memo ? "원본 메모 보기 ›" : "메모 쓰기 ›"}</button></div>
        <p className="break-keep text-[14px] leading-[21px] text-[#575b63]">{memo ? `“${memo.title}” — 이번 실험은 시장 환경 경로예요. 메모에서 지켜보는 항목과 나눠서 보면 좋아요.` : `${r.name}에 남긴 메모가 없어요. 실험에서 본 경로를 메모로 남겨 두면 관련 소식을 모아 드려요.`}</p>
      </div>
      <div className="flex flex-col gap-1 self-stretch">{r.notes.map((n) => <p key={n} className="break-keep text-[13px] leading-[20px] text-[#8e8a97]">· {n}</p>)}</div>
    </div>
  );
}
