import React, { useEffect, useLayoutEffect, useRef, type CSSProperties, type ReactNode, type ReactPortal } from 'react';
// @ts-expect-error 프로젝트에 @types/react-dom 이 없음 (패키지를 늘리지 않고 아래에서 쓰는 모양만 지정)
import { createPortal } from 'react-dom';
import type { TextStyle } from 'react-native';
import { Text } from '@/components/ui/AppText';
import type { FloatTipProps } from './FloatTip';

const portal = createPortal as (children: ReactNode, container: Element) => ReactPortal;

/* react-native-web Modal(z-index 9999) 위에 보이도록 원본의 100보다 높임 */
const BOX: CSSProperties = { position: 'fixed', left: 0, top: 0, zIndex: 10000, display: 'flex', width: 'max-content', transform: 'translateX(-50%)', borderRadius: 6, backgroundColor: '#111111', padding: '5px 8px', pointerEvents: 'none', visibility: 'hidden' };
const LABEL = { fontSize: 13, lineHeight: 20, fontWeight: '500', color: '#FFFFFF', whiteSpace: 'nowrap' } as TextStyle;
const rectOf = (r?: FloatTipProps['anchor']) => (r?.current as unknown as HTMLElement | null)?.getBoundingClientRect();

/** 원본 overlays.tsx TipBtn: 스크롤 칸에 잘리지 않게 body에 띄우는 한 줄 툴팁 */
export function FloatTip({ text, anchor, bounds, onDismiss }: FloatTipProps) {
  const box = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const a = rectOf(anchor);
    const el = box.current;
    if (!a || !el) return;
    const b = rectOf(bounds);
    const half = el.offsetWidth / 2;
    const minX = Math.max(b?.left ?? 0, 0) + 8 + half;
    const maxX = Math.min(b?.right ?? innerWidth, innerWidth) - 8 - half;
    const minY = Math.max(b?.top ?? 0, 0) + 8;
    const above = a.top - 34;
    el.style.left = `${Math.max(minX, Math.min(maxX, a.left + a.width / 2))}px`;
    el.style.top = `${above < minY ? a.bottom + 6 : above}px`;
    el.style.visibility = 'visible';
  }, [text, anchor, bounds]);
  useEffect(() => {
    window.addEventListener('scroll', onDismiss, true);
    window.addEventListener('resize', onDismiss);
    return () => {
      window.removeEventListener('scroll', onDismiss, true);
      window.removeEventListener('resize', onDismiss);
    };
  }, [onDismiss]);
  return portal(
    <div ref={box} role="tooltip" style={BOX}>
      <Text style={LABEL}>{text}</Text>
    </div>,
    document.body,
  );
}
