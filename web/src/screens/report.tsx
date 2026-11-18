/* 주간보고서 v3 · 자세히 보기 — 다른 화면처럼 860 고정 틀 안에. 만든 보고서(id)를 그려요 */
import { useApp } from "../store";
import { ReportDetail } from "../gen/ReportDetail";
import { FixedFrame } from "./stock";
import type { WeeklyReport } from "../api/types";

export function ReportPage({ id }: { id?: number }) {
  const { go, made, setMemoOpen, sgo } = useApp();
  const m = made.find((x) => x.id === id && x.kind === "report") ?? made.find((x) => x.kind === "report");
  return (
    <FixedFrame>
      <div className="w-[860px] break-keep pb-10 pt-8">
        {m ? <ReportDetail r={m.data as WeeklyReport} made={m} onMemo={(code, mid) => { go({ name: "stock", code, tab: "board" }); setMemoOpen(mid ?? -1); }} />
          : <div className="flex flex-col items-center gap-3 py-24 text-center"><p className="text-[22px] font-bold text-[#15171a]">보고서를 찾을 수 없어요</p><p className="text-[15px] text-[#6b7684]">만든 지 30일이 지나 지워졌거나 아직 만들지 않았어요.</p><button onClick={() => sgo("home")} className="mt-2 h-11 rounded-[12px] bg-[#111] px-5 text-[15px] font-bold text-white">스튜디오에서 만들기</button></div>}
      </div>
    </FixedFrame>
  );
}
