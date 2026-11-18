/* 11.16 앱 통일 — 내 종목 화면(전체·보유·관심 칩, 종목마다 메모·AI 연결·새 소식·시세, 선택 모드로 옮기기·빼기) + 종목 메뉴(옮기기 · 기업정보 · 빼기) */
import { useLayoutEffect, useRef, useState } from "react";
import { Modal, PageTitle, cx, useSnack } from "../kit";
import type { Stock } from "../data";
import { useApp, mmdd } from "../store";
import { SLogo } from "../fig";
import { FixedFrame } from "./stock";
import { CtxMenu, MI, SkelPage, type MenuItem } from "../x";
import { SelectBar, Pick, Dots } from "./memox";

export function useStockActions() {
  const { act: A, memos, route, go } = useApp();
  const snack = useSnack();
  const [ask, setAsk] = useState<Stock[] | null>(null);
  const move = (list: Stock[], hold: "보유" | "관심") => {
    const ids = new Set(list.map((s) => s.stock_code));
    A.setHold([...ids], hold);
    snack(list.length > 1 ? `${list.length}개를 ${hold} 종목으로 옮겼어요` : `${list[0].name}을 ${hold} 종목으로 바꿨어요`, { check: true });
  };
  const remove = (list: Stock[]) => {
    const ids = new Set(list.map((s) => s.stock_code));
    const before = A.snapshot();
    A.removeStocks([...ids]);
    if (route.name === "stock" && ids.has(route.code)) go({ name: "home" });
    snack(list.length > 1 ? `${list.length}개 종목을 내 종목에서 뺐어요` : `${list[0].name}을 내 종목에서 뺐어요`, { undo: () => A.rollback(before) });
  };
  const menu = (s: Stock, extra: { select?: () => void } = {}): MenuItem[] => [
    { label: s.hold === "보유" ? "관심 종목으로 바꾸기" : "보유 종목으로 바꾸기", icon: MI.move, run: () => move([s], s.hold === "보유" ? "관심" : "보유") },
    { label: "기업정보 보기", icon: MI.info, run: () => go({ name: "stock", code: s.stock_code, tab: "info" }) },
    ...(extra.select ? [{ label: "여러 개 선택", icon: MI.select, run: extra.select }] : []),
    "-" as const,
    { label: "내 종목에서 빼기", icon: MI.trash, danger: true, run: () => setAsk([s]) },
  ];
  const n = ask ? memos.filter((m) => ask.some((s) => s.stock_code === m.stock_code)).length : 0, nAi = ask ? memos.filter((m) => m.ai && ask.some((s) => s.stock_code === m.stock_code)).length : 0;
  const confirm = (
    <Modal open={!!ask} onClose={() => setAsk(null)} width={400} z={75} label="내 종목에서 뺄까요?">
      <div className="flex w-[400px] flex-col gap-6 rounded-[28px] bg-white px-7 py-[27px]">
        <div className="flex flex-col gap-2"><p className="text-[22px] font-bold leading-[31px] text-[#15171a]">{ask && ask.length > 1 ? `${ask.length}개 종목을 뺄까요?` : "내 종목에서 뺄까요?"}</p><p className="break-keep text-[15px] leading-[23px] text-[#747d8d]">{n ? `메모 ${n}개는 휴지통으로 옮겨져요. 휴지통에서 복원할 수 있어요.${nAi ? ` AI 연결된 메모 ${nAi}개는 추적이 멈춰요.` : ""}` : "휴지통에서 다시 복원할 수 있어요."}</p></div>
        <div className="flex gap-2"><button onClick={() => setAsk(null)} className="flex h-12 flex-1 items-center justify-center rounded-[12px] bg-[#f2f3f4] text-[15px] font-medium text-[#15171a]">취소</button><button data-remove-ok onClick={() => { if (ask) remove(ask); setAsk(null); }} className="flex h-12 flex-1 items-center justify-center rounded-[12px] bg-[#e45d6a] text-[15px] font-medium text-white">빼기</button></div>
      </div>
    </Modal>
  );
  return { move, remove, menu, askRemove: setAsk, confirm };
}

export function MinePage() {
  const { stocks, memos, go, setOverlay, newN: NEW_N } = useApp();
  const act = useStockActions();
  const [tab, setTab] = useState<"all" | "보유" | "관심">("all");
  const [sel, setSel] = useState<Set<string> | null>(null);
  const [menu, setMenu] = useState<{ s: Stock; at: { x: number; y: number } } | null>(null);
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});
  const [pill, setPill] = useState<{ l: number; w: number } | null>(null);
  useLayoutEffect(() => { const b = refs.current[tab]; if (b) setPill({ l: b.offsetLeft, w: b.offsetWidth }); }, [tab, stocks.length]);
  const groups = (["보유", "관심"] as const).filter((g) => tab === "all" || tab === g).map((g) => [g, stocks.filter((s) => s.hold === g)] as const);
  const shown = groups.flatMap(([, l]) => l);
  const tog = (s: Stock) => setSel((x) => { const n = new Set(x ?? []); if (n.has(s.stock_code)) n.delete(s.stock_code); else n.add(s.stock_code); return n; });
  const list = stocks.filter((s) => sel?.has(s.stock_code));
  return (
    <FixedFrame>
    <div className="flex w-[860px] flex-col items-start gap-8 pb-10 pt-8">
      <PageTitle title="내 종목" sub="관심을 둔 이유까지, 메모와 함께 보관해요" right={<>
        <button onClick={() => setSel(sel ? null : new Set())} className="rounded-full border border-[#e5e7eb] bg-white px-3 py-[6px] text-[13px] font-bold leading-[20px] text-[#15171a] hover:bg-[#f9f9f9]">{sel ? "선택 끝내기" : "선택"}</button>
        <button onClick={() => setOverlay("addStock")} className="rounded-full bg-[#15171a] px-3 py-[6px] text-[13px] font-bold leading-[20px] text-white hover:bg-[#2a2a2a]">＋ 종목 추가</button>
      </>} />
      <div className="flex w-full flex-col gap-6">
        <div className="relative flex items-start gap-2">
          {pill && <span className="x-pill" style={{ left: pill.l, width: pill.w }} />}
          {([["all", `전체 ${stocks.length}`], ["보유", `보유 ${stocks.filter((s) => s.hold === "보유").length}`], ["관심", `관심 ${stocks.filter((s) => s.hold === "관심").length}`]] as const).map(([k, l]) => (
            <button key={k} ref={(el) => { refs.current[k] = el; }} data-mine-tab={k} onClick={() => setTab(k)} className={cx("relative rounded-[20px] px-4 py-2 text-[13px] font-medium leading-[20px] transition-colors", tab === k ? "text-white" : "bg-white text-[#8f8f8f] hover:text-[#191f28]")}>{l}</button>
          ))}
        </div>
        <SkelPage id="mine" className="flex w-full flex-col gap-6">
          {stocks.length === 0 && (
            <div data-mine-empty className="m-in flex w-full flex-col items-center gap-3 rounded-[20px] border border-dashed border-[#cfd3d9] bg-white px-8 py-12 text-center">
              <p className="text-[22px] font-bold leading-[31px] text-[#191f28]">관심 있는 종목을 추가해 보세요</p>
              <p className="break-keep text-[15px] leading-[23px] text-[#6b7684]">종목마다 생각을 메모로 남기면, AI가 관련 공시·뉴스를 이어 붙여 드려요.</p>
              <button onClick={() => setOverlay("addStock")} className="mt-2 h-12 rounded-[14px] bg-[#111] px-6 text-[17px] font-bold text-white">종목 추가</button>
            </div>
          )}
          {groups.filter(([, l]) => l.length).map(([g, l]) => (
            <div key={g} data-sk className="flex w-full flex-col overflow-hidden rounded-[20px] border border-[#e5e7eb] bg-white">
              <div className="flex h-12 items-center justify-between px-5"><p className="text-[15px] font-bold text-[#15171a]">{g}</p><p className="text-[13px] text-[#8b95a1]">{l.length}종목</p></div>
              {l.map((s, i) => { const mm = memos.filter((m) => m.stock_code === s.stock_code), up = s.chg >= 0, nn = NEW_N[s.stock_code] ?? 0; return (
                <div key={s.stock_code} data-mine-row={s.stock_code} role="button" tabIndex={0} onClick={() => (sel ? tog(s) : go({ name: "stock", code: s.stock_code, tab: "board" }))} onKeyDown={(e) => { if (e.key === "Enter") go({ name: "stock", code: s.stock_code, tab: "board" }); }} onContextMenu={(e) => { e.preventDefault(); if (!sel) setMenu({ s, at: { x: e.clientX, y: e.clientY } }); }}
                  className={cx("m-reveal flex h-[72px] cursor-pointer items-center gap-4 border-t border-[#f0f1f3] px-5 hover:bg-[#f9f9f9]", sel?.has(s.stock_code) && "bg-[#f7f7f7]")} style={{ ["--i" as string]: i }}>
                  {sel && <Pick on={sel.has(s.stock_code)} />}
                  <SLogo code={s.stock_code} size={36} r={10} />
                  <span className="flex min-w-0 flex-1 flex-col"><span className="flex items-center gap-2"><span className="truncate text-[17px] font-bold leading-[26px] text-[#15171a]">{s.name}</span>{nn > 0 && <span className="grid h-5 min-w-5 place-items-center rounded-full bg-[#e5484d] px-[5px] text-[12px] font-bold text-white">{nn}</span>}</span><span className="text-[13px] leading-[20px] text-[#8b95a1]">메모 {mm.length} · AI 연결 {mm.filter((m) => m.ai).length}</span></span>
                  <span className="flex flex-col items-end"><span className="text-[15px] font-bold leading-[23px] text-[#15171a]">{s.price.toLocaleString("ko-KR")}원</span><span className="text-[13px] font-bold leading-[20px]" style={{ color: up ? "#e5484d" : "#2f6bdb" }}>{up ? "+" : ""}{s.pct.toFixed(2)}%</span></span>
                  {!sel && <button aria-label={`${s.name} 메뉴`} onClick={(e) => { e.stopPropagation(); const r = (e.currentTarget as HTMLElement).getBoundingClientRect(); setMenu({ s, at: { x: r.right - 220, y: r.bottom + 6 } }); }} className="grid h-8 w-8 shrink-0 place-items-center rounded-[8px] text-[#8b95a1] hover:bg-[#f2f3f4]"><Dots /></button>}
                </div>
              ); })}
            </div>
          ))}
        </SkelPage>
        <p className="text-center text-[13px] leading-[20px] text-[#8b95a1]">시세는 {stocks[0] ? `${mmdd(stocks[0].as_of)} 종가 기준` : "종가 기준"} · 종목을 우클릭하면 바로 옮기거나 뺄 수 있어요</p>
      </div>
    </div>
    <CtxMenu at={menu?.at ?? null} items={menu ? act.menu(menu.s, { select: () => setSel(new Set([menu.s.stock_code])) }) : []} onClose={() => setMenu(null)} />
    {sel && <SelectBar n={sel.size} total={shown.length} all={sel.size === shown.length && shown.length > 0} onAll={() => setSel(sel.size === shown.length ? new Set() : new Set(shown.map((s) => s.stock_code)))} onTrash={() => { act.askRemove(list); setSel(null); }} onEnd={() => setSel(null)}
      extra={<><button disabled={!sel.size} onClick={() => { act.move(list, "보유"); setSel(null); }} className="h-10 rounded-[10px] px-3 text-[14px] font-bold hover:bg-white/10 disabled:opacity-40">보유로 옮기기</button><button disabled={!sel.size} onClick={() => { act.move(list, "관심"); setSel(null); }} className="h-10 rounded-[10px] px-3 text-[14px] font-bold hover:bg-white/10 disabled:opacity-40">관심으로 옮기기</button></>} />}
    {act.confirm}
    </FixedFrame>
  );
}
