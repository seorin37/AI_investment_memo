/* API 모드(VITE_USE_API=true)에서만 쓰는 화면 부품. 시연 모드에서는 아무것도 그리지 않아요.
   - ApiBridge: remote.ts의 알림(저장 실패·불러오기 실패)을 기존 하단 토스트로, 실패하면 서버 상태로 다시 불러오기
   - ModeNotice: 아직 서버와 연결되지 않은 화면 위 안내 — mock 시세·소식 화면은 '예시 데이터', 이 기기에만 저장되는 화면은 '이 기기에만 저장돼요' */
import { useEffect, useState } from "react";
import { mainCenter, useSnack } from "./kit";
import { useApp, type Route } from "./store";
import { api, API_MODE } from "./api";
import { onRemote } from "./api/remote";
import { emptyState } from "./api/mock/db";

export function ApiBridge() {
  const app = useApp();
  const snack = useSnack();
  useEffect(() => {
    if (!API_MODE) return;
    const offs = [
      onRemote("note", (t) => snack(t)),
      onRemote("reload", () => {
        void Promise.resolve(api.auth.session()).then((s) => {
          if (s) app.setUd(s);
          else { app.setUd(emptyState(null)); app.go({ name: "login" }); }
        });
      }),
      /* 타임라인을 새로 받았을 때 메모 카드(새 소식 배지·타임라인)를 다시 그리게 */
      onRemote("change", () => app.setUd((s) => ({ ...s, memos: [...s.memos] }))),
    ];
    return () => offs.forEach((f) => f());
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

function noticeOf(r: Route): { kind: "sample" | "local"; text: string } | null {
  switch (r.name) {
    case "home": case "custom": return { kind: "sample", text: "예시 데이터 · 시장 지수·소식·뉴스·일정은 아직 서버와 연결되지 않았어요" };
    case "updates": return { kind: "sample", text: "예시 데이터 · 최신 업데이트 소식은 아직 서버와 연결되지 않았어요 (메모 안 AI 업데이트는 실제 데이터)" };
    case "stock": return r.tab === "info" ? { kind: "sample", text: "예시 데이터 · 기업 정보·차트·재무는 아직 서버와 연결되지 않았어요" } : null;
    case "report": return { kind: "sample", text: "예시 데이터 · 주간보고서는 아직 서버와 연결되지 않았어요" };
    case "journal": return { kind: "local", text: "이 기기에만 저장돼요 · 투자 기록은 아직 서버에 저장되지 않아요" };
    default: return null;
  }
}

export function ModeNotice() {
  const { route, nav, sideOpen, studio } = useApp();
  const [left, setLeft] = useState<number | null>(null);
  const n = API_MODE ? noticeOf(route) : null;
  useEffect(() => {
    if (!API_MODE) return;
    let raf = 0; const t0 = performance.now();
    const f = () => { const c = mainCenter(); setLeft((l) => (c === null ? l : l !== null && Math.abs(l - c) < 0.25 ? l : c)); if (performance.now() - t0 < 1400) raf = requestAnimationFrame(f); };
    f(); window.addEventListener("resize", f); return () => { cancelAnimationFrame(raf); window.removeEventListener("resize", f); };
  }, [nav, sideOpen, studio.open]);
  if (!n) return null;
  return (
    <div role="note" data-mode-notice={n.kind} className="pointer-events-none fixed top-3 z-[45] flex max-w-[640px] -translate-x-1/2 items-center gap-2 rounded-full border border-[#e5e7eb] bg-white/95 px-3 py-[5px] shadow-[0_2px_8px_rgba(17,19,23,.06)]" style={{ left: left ?? "50%" }}>
      <span className="h-[6px] w-[6px] shrink-0 rounded-full" style={{ background: n.kind === "local" ? "#8b95a1" : "#c4c9d0" }} />
      <p className="truncate text-[13px] font-medium leading-[20px] text-[#575b63]">{n.text}</p>
    </div>
  );
}
