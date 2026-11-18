/* 1. 로그인 · 2.0 홈 시작 설정 — Figma 그대로 */
import { useApp } from "../store";
import { useState } from "react";
import { cx } from "../kit";
import { API_MODE } from "../api/config";
import { api } from "../api/client";
const LAST: { p: string | null } = { p: null }; /* 최근 로그인 (로그아웃 뒤에도 남음) */
import { LOGIN_LOGO } from "../assets_wm";

export const KakaoLogo = ({ size = 24 }: { size?: number }) => <svg width={size} height={size} viewBox="0 0 24 24" fill="none"><path d="M12 3C6.48 3 2 6.49 2 10.8C2 13.57 3.85 16 6.63 17.38L5.46 21.68C5.36 22.02 5.75 22.28 6.04 22.1L11.12 18.62C11.41 18.64 11.7 18.65 12 18.65C17.52 18.65 22 15.15 22 10.8C22 6.45 17.52 3 12 3Z" fill="#191919" /></svg>;
export const NaverLogo = ({ size = 24 }: { size?: number }) => <svg width={size} height={size} viewBox="0 0 24 24" fill="none"><path d="M3 3H9.2L14.8 11.2V3H21V21H14.8L9.2 12.8V21H3V3Z" fill="white" /></svg>;
export const GoogleLogo = ({ size = 24 }: { size?: number }) => <svg width={size} height={size} viewBox="0 0 24 24" fill="none"><path d="M21.8 10.25H21V10H12V14H17.65C17.0846 15.131 16.1763 16.0546 15.0548 16.6387C13.9333 17.2228 12.6559 17.4376 11.405 17.2525C10.1541 17.0675 8.9937 16.4919 8.08939 15.6081C7.18508 14.7242 6.58313 13.5773 6.36947 12.3309C6.15582 11.0846 6.34138 9.80266 6.89968 8.66809C7.45797 7.53351 8.36045 6.60432 9.47826 6.01317C10.5961 5.42203 11.8721 5.19916 13.1241 5.37638C14.3761 5.5536 15.5402 6.12185 16.45 7L19.3 4.15C17.7282 2.49391 15.637 1.42557 13.3739 1.12254C11.1109 0.819508 8.81229 1.30004 6.86015 2.48427C4.90802 3.6685 3.41993 5.4851 2.64319 7.63217C1.86645 9.77923 1.84784 12.1275 2.59047 14.2866C3.33309 16.4457 4.79221 18.2856 6.72533 19.5006C8.65846 20.7156 10.9492 21.2325 13.2167 20.9654C15.4843 20.6983 17.5922 19.6632 19.19 18.0322C20.7879 16.4012 21.7794 14.2726 22 12C22 11.4 21.95 10.8 21.8 10.25Z" fill="#FBBC05" /><path d="M3.15002 7.35002L6.45002 9.75002C6.71859 8.7353 7.24865 7.80878 7.98729 7.063C8.72592 6.31721 9.64729 5.77825 10.6594 5.49992C11.6715 5.2216 12.7389 5.21366 13.755 5.47689C14.7711 5.74011 15.7004 6.26531 16.45 7.00002L19.3 4.15002C18.1389 3.02091 16.7209 2.19073 15.1679 1.73086C13.615 1.27099 11.9736 1.19519 10.3849 1.50998C8.79618 1.82477 7.3077 2.52073 6.04745 3.53802C4.78719 4.5553 3.79289 5.86347 3.15002 7.35002Z" fill="#EA4335" /><path d="M12 22C14.6 22 16.95 21 18.7 19.4L15.6 16.8C14.8469 17.3635 13.9718 17.7421 13.0454 17.9051C12.1191 18.0682 11.1673 18.0111 10.2671 17.7386C9.36682 17.4661 8.54323 16.9857 7.8628 16.3363C7.18237 15.6869 6.66416 14.8866 6.34999 14L3.04999 16.55C3.8917 18.1974 5.1739 19.579 6.75397 20.5412C8.33404 21.5033 10.15 22.0083 12 22Z" fill="#34A853" /><path d="M21.8 10.25H21V10H12V14H17.65C17.2574 15.1149 16.5442 16.089 15.6 16.8L18.7 19.4C19.7359 18.4651 20.5647 17.3237 21.133 16.0492C21.7014 14.7747 21.9967 13.3954 22 12C22 11.4 21.95 10.8 21.8 10.25Z" fill="#92B5D3" /></svg>;

export function Login() {
  const { go, x, setX, auth, authError } = useApp();
  const [err, setErr] = useState(false), [shake, setShake] = useState(0);
  const busy = auth === "checking" || auth === "loading";
  /* 11.16 앱 통일: 최근 로그인 표시 · 로그인 실패 안내 · 인터넷 끊김 */
  const start = (p: "kakao" | "naver" | "google") => () => {
    if (x.offline) { setShake((n) => n + 1); return; }
    /* API 모드: 백엔드 소셜 로그인으로 이동 → 돌아오면 쿠키 세션으로 /auth/me 확인 (store.tsx) */
    if (API_MODE) { if (busy) return; LAST.p = p; window.location.assign(api.loginUrl(p, window.location.origin)); return; }
    if (x.loginFail) { setErr(true); setShake((n) => n + 1); return; }
    LAST.p = p; go({ name: "terms" });
  };
  const Recent = ({ p }: { p: string }) => LAST.p === p ? <span className="absolute -top-2 right-3 rounded-full bg-[#15171a] px-2 py-[2px] text-[12px] font-bold leading-[16px] text-white">최근 로그인</span> : null;
  return (
    <div className="flex h-full min-h-[600px] w-full flex-col items-center justify-center overflow-auto bg-[#fdfdfd]">
      <div key={shake} className={cx("m-pop flex w-[480px] max-w-[calc(100vw-32px)] flex-col items-center gap-7 overflow-hidden rounded-[24px] border border-[#e5e8eb] bg-white px-12 py-10", shake > 0 && "x-shake")}>
        {API_MODE && busy && !x.offline && <div data-login-notice className="m-pop -mb-3 flex w-full items-center gap-2 rounded-[12px] bg-[#f3f4f6] px-4 py-3 text-[14px] font-bold text-[#575b63]"><span className="flex-1">{auth === "loading" ? "내 종목과 메모를 불러오고 있어요…" : "로그인 상태를 확인하고 있어요…"}</span></div>}
        {(x.offline || err || (API_MODE && !busy && authError)) && <div data-login-notice className="m-pop -mb-3 flex w-full items-center gap-2 rounded-[12px] bg-[#fdf0f1] px-4 py-3 text-[14px] font-bold text-[#c0392b]"><span className="flex-1">{x.offline ? "인터넷에 연결되어 있지 않아요" : API_MODE && authError ? authError : "로그인을 마치지 못했어요. 다시 시도해 주세요."}</span>{x.offline && <button onClick={() => setX((v) => ({ ...v, offline: false }))} className="h-8 rounded-[8px] px-2 text-[#c0392b] hover:bg-white/60">다시 시도</button>}</div>}
        <div className="flex w-full flex-col items-center gap-3">
          <img src={LOGIN_LOGO} alt="MEMO'S" className="h-[50px] w-[150px]" draggable={false} />
          <p className="w-full text-center text-[26px] font-bold leading-[35px] text-[#191f28]">내 생각에서 시작하는 투자 소식</p>
          <p className="w-full text-center text-[14px] leading-[21px] text-[#8f8f8f]">소셜 계정으로 간편하게 시작하세요</p>
        </div>
        <div className="flex w-full flex-col items-start gap-3">
          <button onClick={start("kakao")} className="relative flex h-14 w-full items-center justify-center gap-3 rounded-[12px] bg-[#fee500] px-6 hover:brightness-[.98]">
            <KakaoLogo />
            <span className="min-w-0 flex-1 text-center text-[17px] font-bold leading-[26px] text-[#191f28]">카카오로 로그인</span><span className="h-6 w-6" /><Recent p="kakao" />
          </button>
          <button onClick={start("naver")} className="relative flex h-14 w-full items-center justify-center gap-3 rounded-[12px] bg-[#03a94d] px-6 hover:brightness-[.98]">
            <NaverLogo />
            <span className="min-w-0 flex-1 text-center text-[17px] font-bold leading-[26px] text-white">네이버로 로그인</span><span className="h-6 w-6" /><Recent p="naver" />
          </button>
          <button onClick={start("google")} className="relative flex h-14 w-full items-center justify-center gap-3 rounded-[12px] border border-[#e8ecf3] bg-white px-6 hover:bg-[#f9f9f9]">
            <GoogleLogo />
            <span className="min-w-0 flex-1 text-center text-[17px] font-bold leading-[26px] text-[#191f28]">구글로 로그인</span><span className="h-6 w-6" /><Recent p="google" />
          </button>
        </div>
        <button onClick={() => go({ name: "intro" })} className="-mt-2 text-[14px] leading-[21px] text-[#8f8f8f] underline-offset-2 hover:text-[#191f28] hover:underline">MEMO'S가 처음이라면 · 서비스 소개 보기</button>
      </div>
    </div>
  );
}

const Tick = ({ bg }: { bg: string }) => <span className="grid h-[18px] w-[18px] shrink-0 place-items-center rounded-full text-[13px] font-bold leading-[20px] text-black" style={{ background: bg }}>✓</span>;
export function Start() {
  const { go, setHomeMode } = useApp();
  return (
    <div className="flex min-h-full w-full flex-col items-center justify-center px-10 py-[125px]">
      <div className="flex h-[650px] w-full max-w-[674px] flex-col items-center justify-center gap-6">
        <div className="flex h-[125px] w-full flex-col items-center justify-center gap-[10px]">
          <span className="flex h-[30px] w-[104px] items-center justify-center rounded-[15px] bg-[#efefef] text-[13px] font-medium leading-[20px] text-black">처음 시작하기</span>
          <p className="whitespace-nowrap text-[32px] font-bold leading-[40px] text-black">나에게 맞는 홈 화면을 선택해 주세요</p>
          <p className="whitespace-nowrap text-[17px] leading-[26px] text-[#6b7684]">추천 템플릿을 바로 적용하거나, 원하는 정보로 직접 구성할 수 있어요.</p>
        </div>
        <div className="flex h-[380px] w-full items-start gap-6">
          <div className="flex h-[380px] min-w-0 flex-1 flex-col items-start justify-between rounded-[20px] border-2 border-black bg-[#f7f8fa] px-7 py-6">
            <div className="flex h-12 w-full items-center justify-between">
              <span className="grid h-12 w-12 place-items-center rounded-[14px] bg-[#efefef]"><svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M8 3H5C3.89543 3 3 3.89543 3 5V8C3 9.10457 3.89543 10 5 10H8C9.10457 10 10 9.10457 10 8V5C10 3.89543 9.10457 3 8 3Z" stroke="black" strokeWidth="2" /><path d="M19 3H16C14.8954 3 14 3.89543 14 5V8C14 9.10457 14.8954 10 16 10H19C20.1046 10 21 9.10457 21 8V5C21 3.89543 20.1046 3 19 3Z" stroke="black" strokeWidth="2" /><path d="M8 14H5C3.89543 14 3 14.8954 3 16V19C3 20.1046 3.89543 21 5 21H8C9.10457 21 10 20.1046 10 19V16C10 14.8954 9.10457 14 8 14Z" stroke="black" strokeWidth="2" /><path d="M19 14H16C14.8954 14 14 14.8954 14 16V19C14 20.1046 14.8954 21 16 21H19C20.1046 21 21 20.1046 21 19V16C21 14.8954 20.1046 14 19 14Z" stroke="black" strokeWidth="2" /></svg></span>
              <span className="flex h-7 w-14 items-center justify-center rounded-[14px] bg-black text-[13px] font-bold leading-[20px] text-white">추천</span>
            </div>
            <div className="flex h-[78px] w-full flex-col items-start gap-2">
              <p className="whitespace-nowrap text-[22px] font-bold leading-[31px] text-black">기본 템플릿 적용</p>
              <p className="w-full text-[14px] leading-[21px] text-[#6b7684]">시장 흐름과 내 종목 소식을 한눈에 보는 추천 구성을 바로 시작해요.</p>
            </div>
            <div className="flex h-[88px] w-full flex-col items-start gap-2">
              {["시장 지수와 환율", "관심 종목 업데이트", "주요 일정과 뉴스"].map((t) => <div key={t} className="flex h-6 w-full items-center gap-[10px]"><Tick bg="#efefef" /><p className="text-[13px] leading-[20px] text-[#191f28]">{t}</p></div>)}
            </div>
            <button onClick={() => { setHomeMode("template"); go({ name: "home" }); }} className="flex h-12 w-full items-center justify-center rounded-[12px] bg-black text-[15px] font-medium leading-[23px] text-white hover:bg-[#222]">템플릿으로 시작</button>
          </div>
          <div className="flex h-[380px] min-w-0 flex-1 flex-col items-start justify-between rounded-[20px] border border-[#eaecf0] bg-white px-7 py-6">
            <div className="flex h-12 w-full items-center justify-between">
              <span className="grid h-12 w-12 place-items-center rounded-[14px] bg-[#f7f8fa]"><svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M4 7H9M15 7H20M4 17H13M19 17H20" stroke="black" strokeWidth="2" strokeLinecap="round" /><path d="M12 10C13.6569 10 15 8.65685 15 7C15 5.34315 13.6569 4 12 4C10.3431 4 9 5.34315 9 7C9 8.65685 10.3431 10 12 10Z" stroke="black" strokeWidth="2" /><path d="M16 20C17.6569 20 19 18.6569 19 17C19 15.3431 17.6569 14 16 14C14.3431 14 13 15.3431 13 17C13 18.6569 14.3431 20 16 20Z" stroke="black" strokeWidth="2" /></svg></span>
              <span className="h-7 w-14" />
            </div>
            <div className="flex h-[78px] w-full flex-col items-start gap-2">
              <p className="whitespace-nowrap text-[22px] font-bold leading-[31px] text-black">직접 사용자화</p>
              <p className="w-full text-[14px] leading-[21px] text-[#6b7684]">보고 싶은 정보만 골라 나만의 홈 화면을 직접 구성해요.</p>
            </div>
            <div className="flex h-[88px] w-full flex-col items-start gap-2">
              {["원하는 위젯 선택", "위젯 순서와 크기 조정", "언제든 다시 변경"].map((t) => <div key={t} className="flex h-6 w-full items-center gap-[10px]"><Tick bg="#f7f8fa" /><p className="text-[13px] leading-[20px] text-[#191f28]">{t}</p></div>)}
            </div>
            <button onClick={() => go({ name: "custom" })} className="flex h-12 w-full items-center justify-center rounded-[12px] bg-[#f7f8fa] text-[15px] font-medium leading-[23px] text-[#191f28] hover:bg-[#eef0f3]">직접 구성하기</button>
          </div>
        </div>
        <div className="flex h-6 w-full items-center justify-center gap-2">
          <span className="grid h-[18px] w-[18px] place-items-center rounded-full bg-[#f7f8fa] text-[13px] font-bold leading-[20px] text-[#8f8f8f]">i</span>
          <p className="whitespace-nowrap text-[13px] leading-[20px] text-[#8f8f8f]">선택한 설정은 홈 화면에서 언제든 변경할 수 있어요.</p>
        </div>
      </div>
    </div>
  );
}
