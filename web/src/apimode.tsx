/* API 모드(VITE_USE_API=true)에서만 쓰는 화면 부품.
   - ApiNotes: 저장 실패 · 불러오기 실패를 기존 하단 토스트로 알림
   - SampleNotice: 아직 서버와 연결되지 않은 화면(분류 C) 위에 '예시 데이터' 안내 — 저장되거나 실제 값인 것처럼 오인되지 않게 */
import { useEffect, useState } from "react";
import { mainCenter, useSnack } from "./kit";
import { useApp, type Route } from "./store";
import { API_MODE } from "./api/config";

export function ApiNotes() {
  const { apiNote } = useApp();
  const snack = useSnack();
  useEffect(() => { if (API_MODE && apiNote) snack(apiNote.text); }, [apiNote]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

function sampleText(r: Route): string | null {
  switch (r.name) {
    case "home": case "custom": return "예시 데이터 · 시장 지수·뉴스·일정·업데이트 위젯은 아직 서버와 연결되지 않았어요";
    case "updates": return "예시 데이터 · 최신 업데이트 목록은 아직 서버와 연결되지 않았어요 (메모 안 AI 업데이트는 실제 데이터)";
    case "journal": return "예시 데이터 · 투자 기록은 아직 서버에 저장되지 않아요";
    case "report": return "예시 데이터 · 주간보고서는 아직 서버와 연결되지 않았어요";
    case "stock": return r.tab === "info" ? "예시 데이터 · 기업정보·시세·재무는 아직 서버와 연결되지 않았어요" : null;
    default: return null;
  }
}

export function SampleNotice() {
  const { route, nav, sideOpen, studio } = useApp();
  const [left, setLeft] = useState<number | null>(null);
  const text = API_MODE ? sampleText(route) : null;
  useEffect(() => {
    let raf = 0; const t0 = performance.now();
    const f = () => { const c = mainCenter(); setLeft((l) => (c === null ? l : l !== null && Math.abs(l - c) < 0.25 ? l : c)); if (performance.now() - t0 < 1400) raf = requestAnimationFrame(f); };
    f(); window.addEventListener("resize", f); return () => { cancelAnimationFrame(raf); window.removeEventListener("resize", f); };
  }, [nav, sideOpen, studio.open]);
  if (!text) return null;
  return (
    <div role="note" data-sample-notice className="pointer-events-none fixed top-3 z-[45] flex max-w-[640px] -translate-x-1/2 items-center gap-2 rounded-full border border-[#e5e7eb] bg-white/95 px-3 py-[5px] shadow-[0_2px_8px_rgba(0,0,0,0.04)]" style={{ left: left ?? "50%" }}>
      <span className="h-[6px] w-[6px] shrink-0 rounded-full bg-[#c4c9d0]" />
      <p className="truncate text-[13px] font-medium leading-[20px] text-[#575b63]">{text}</p>
    </div>
  );
}
