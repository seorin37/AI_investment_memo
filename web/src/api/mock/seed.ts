/* 발표용 '예시 계정' — 메모·체크리스트·투자 기록·만든 항목이 미리 채워진 상태
   새 가입자에게는 쓰지 않아요. 시연 도구 › 예시 계정으로 시작 에서만 써요. 백엔드 연결 후 삭제 */
import type { ColorKey, Memo, UserState } from "../types";
import { findItems, makeAudio, makeReport, quizFor } from "./ai";
import { emptyState } from "./db";
import { now, tradingDays } from "./market";
import { AVATAR } from "../../assets_wm";

const ago = (days: number, h = 21, m = 10) => { const d = now(); d.setDate(d.getDate() - days); d.setHours(h, m, 0, 0); return d.toISOString(); };

export function seedState(base: UserState): UserState {
  const s = emptyState(base.profile ? { ...base.profile, photo: base.profile.photo ?? AVATAR } : null);
  s.onboarded = true; s.coach_done = true;
  s.stocks = [{ stock_code: "000660", hold: "보유", added_at: ago(50), order: 0 }, { stock_code: "005930", hold: "관심", added_at: ago(50), order: 1 }, { stock_code: "035420", hold: "관심", added_at: ago(40), order: 2 }];
  let id = 1;
  const M = (code: string, days: number, title: string, body: string, color: ColorKey, ai: boolean, pinned: boolean, col: number, aiDays?: number, edits: Memo["edits"] = []): Memo => {
    const text = title + " " + body;
    return { id: id++, stock_code: code, title, body, color, created_at: ago(days), updated_at: ago(edits.length ? days - 4 : days), ai, ai_since: ai ? ago(aiDays ?? days) : undefined, tracks: ai ? findItems(text, code) : undefined, pinned, pinned_at: undefined, col, seen_at: ai ? ago(9) : undefined, edits };
  };
  s.memos = [
    M("000660", 47, "실적 나오면 다시 보기", "다음 분기 실적 확인하고\n추가 매수 생각해보기.", "yellow", true, true, 0, 45),
    M("000660", 45, "요즘 반도체 분위기 좋아 보여", "HBM 수요 이야기 계속 나와서\n기대감 있는 것 같음.", "blue", true, false, 1, 44),
    M("000660", 53, "15만원 밑으로 오면 다시 생각", "지지선 근처 오면\n분할 매수 고민해보기.", "green", true, true, 2, 52, [{ at: ago(42, 21, 14), title: "15만원 밑으로 오면 다시 생각", body: "지지선 근처 오면 다시 보기." }]),
    M("000660", 39, "삼성전자랑 같이 비교해보기", "두 종목 주가 흐름 비교해서\n판단하기.", "purple", false, false, 1),
    M("000660", 43, "너무 급하게 따라 사지 말기", "지금은 좀 지켜보고\n조금 더 확인한 뒤에 들어가기.", "pink", false, false, 2),
    M("005930", 36, "자사주 매입 나오면 다시 보기", "주주환원 나오는지 확인하고 판단하기.", "yellow", true, true, 0, 30),
    M("005930", 28, "파운드리 수주 소식 지켜보기", "대형 고객 수주 나오면 다시 보기.", "blue", false, false, 1),
    M("035420", 30, "AI 검색 반응 보기", "서비스 개편 후 이용자 반응 확인.", "green", true, false, 0, 30),
  ];
  const cl = (code: string, title: string, items: [string, boolean][]) => { s.checklists[code] = { stock_code: code, title, items: items.map(([t, d], i) => ({ id: i + 1, t, d })), updated_at: ago(10) }; };
  cl("000660", "체크리스트", [["실적 발표 전 확인", false], ["관련 뉴스 다시 확인", true], ["가격 떨어지면 다시 보기", false], ["삼성전자랑 같이 비교해보기", false]]);
  cl("005930", "매수 전 확인", [["배당 기준일 확인", true], ["파운드리 수주 공시 보기", false]]);
  const J = (days: number, title: string, body: string[], todo: [string, boolean][] = []) => ({ id: id++, title, created_at: ago(days, 18, 20), updated_at: ago(days, 18, 20), body, todo: todo.map(([t, d]) => ({ t, d })) });
  s.journal = [
    J(3, "투자 복기", ["오늘 반도체 업종이 강세를 보였다. SK하이닉스는 HBM 공급 확대 기대감에 상승했고, 삼성전자는 장 초반 약세 뒤 회복했다.", "잘한 점: 급등 구간에서 추격 매수를 하지 않았다.", "아쉬운 점: 실적 발표 전에 체크리스트를 다시 확인하지 못했다."], [["실적 발표일 확인하기", false], ["분할 매수 계획 세우기", false]]),
    J(8, "실적 발표 전 점검", ["발표일 확인하고 체크리스트 정리.", "컨센서스 대비 가이던스 문구를 꼭 볼 것."], [["가이던스 문구 확인", true]]),
    J(15, "매수 전략 메모", ["급하게 따라 사지 않기.", "15만원 근처에서만 분할로 접근."]),
    J(22, "손절 기준 정리", ["지지선 근처에서 분할 매수 고민.", "-10%면 이유를 다시 적고 판단하기."]),
  ].map((j) => { const d = new Date(j.created_at); return { ...j, title: `${String(d.getMonth() + 1).padStart(2, "0")}/${String(d.getDate()).padStart(2, "0")} ${j.title}` }; });
  const codes = s.stocks.map((x) => x.stock_code);
  const td = tradingDays(8);
  s.made = [
    (() => { const data = makeAudio(codes, 1, true, s.memos); return { id: id++, kind: "audio" as const, title: `${md(td[6])} 내 종목 라디오`, stock_codes: codes, created_at: ago(1, 8, 2), meta: `오디오 · ${codes.length}종목 · 전날 · ${Math.floor(data.dur / 60)}:${String(data.dur % 60).padStart(2, "0")}`, data }; })(),
    { id: id++, kind: "report", title: "이번 주 내 종목 보고서", stock_codes: codes, created_at: ago(4, 9, 0), meta: `주간보고서 · ${codes.length}종목`, data: makeReport(codes, s.memos, true) },
  ];
  /* 최근 3거래일 연속 퀴즈 참여 (답한 날 = 문제 날짜 다음 거래일) */
  s.quiz = [3, 2, 1].map((n) => { const day = td[td.length - 1 - n], q = quizFor(day, "ox"); return { quiz_id: q.id, picked: q.answer, correct: true, at: td[td.length - n] + "T10:30:00+09:00" }; });
  s.usage = { pct: 38, reset_at: s.usage.reset_at };
  s.recent = ["SK하이닉스", "삼성전자"];
  return s;
}
const md = (d: string) => `${+d.slice(5, 7)}.${d.slice(8, 10)}`;
