/* 가상 서버 저장소 — 브라우저 localStorage에 사용자별로 저장해요. 백엔드 연결 후 삭제
   계정 = 로그인한 소셜 제공자 하나 (같은 제공자로 다시 들어오면 내 데이터가 그대로 있어요) */
import type { Profile, UserState } from "../types";
import { now } from "./market";

const KEY = "memos.mock.v2"; // v2 (11.18): 데이터 필드 snake_case
type DB = { accounts: Partial<Record<Profile["provider"], UserState>>; current: Profile["provider"] | null };
const read = (): DB => { try { const v = localStorage.getItem(KEY); if (v) return JSON.parse(v) as DB; } catch { /* 저장소를 못 쓰면 메모리로 */ } return mem; };
let mem: DB = { accounts: {}, current: null };
const write = (db: DB) => { mem = db; try { localStorage.setItem(KEY, JSON.stringify(db)); } catch { /* 가득 찼거나 막힘 — 메모리에만 */ } };

export const emptyState = (profile: Profile | null): UserState => ({
  profile, settings: { noti_upd: true, noti_studio: true, dark: false },
  stocks: [], memos: [], checklists: {}, journal: [], trash: [], made: [], quiz: [], notifs: [],
  usage: { pct: 0, reset_at: nextMonth() }, onboarded: false, coach_done: false,
  home: { mode: "template", widgets: ["market", "updates", "news"], board: [] }, recent: [], boards: {},
});
export const nextMonth = () => { const d = now(); return new Date(d.getFullYear(), d.getMonth() + 1, 1).toISOString(); };
const PROFILES: Record<Profile["provider"], Omit<Profile, "joined_at">> = {
  kakao: { name: "김나라", job: "대학생", email: "nara.kim@kakao.example", provider: "kakao" },
  naver: { name: "김나라", job: "대학생", email: "narakim@naver.example", provider: "naver" },
  google: { name: "Nara Kim", job: "대학생", email: "nara.kim@gmail.example", provider: "google" },
};

export const db = {
  current(): UserState | null { const d = read(); return d.current ? d.accounts[d.current] ?? null : null; },
  login(p: Profile["provider"]): { state: UserState; is_new: boolean } {
    const d = read(); let s = d.accounts[p]; const isNew = !s;
    if (!s) s = emptyState({ ...PROFILES[p], joined_at: now().toISOString() });
    d.accounts[p] = s; d.current = p; write(d);
    return { state: s, is_new: isNew };
  },
  logout() { const d = read(); d.current = null; write(d); },
  save(s: UserState) { const d = read(); const p = s.profile?.provider ?? d.current; if (!p) return; d.accounts[p] = s; d.current = p; write(d); },
  withdraw() { const d = read(); if (d.current) delete d.accounts[d.current]; d.current = null; write(d); },
  wipeAll() { try { localStorage.removeItem(KEY); } catch { /* 무시 */ } mem = { accounts: {}, current: null }; },
};
