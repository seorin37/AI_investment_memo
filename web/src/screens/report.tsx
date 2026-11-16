/* 주간보고서 v3 · 자세히 보기 — Figma 4111:68163 main. 다른 화면처럼 860 고정 틀 안에 (본문을 860 폭에 맞춤, 차트는 비율대로 키움) (11.13) */
import { useApp } from "../store";
import { ReportDetail } from "../gen/ReportDetail";
import { FixedFrame } from "./stock";

export function ReportPage() {
  const { go } = useApp();
  return (
    <FixedFrame>
      <div className="w-[860px] break-keep pb-10 pt-8">
        <div className="w-full">
          <ReportDetail onAct={(a) => { if (a === "memo") go({ name: "stock", code: "000660", tab: "board" }); }} />
        </div>
      </div>
    </FixedFrame>
  );
}
