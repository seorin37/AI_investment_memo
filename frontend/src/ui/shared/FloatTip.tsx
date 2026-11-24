import type { ComponentRef, RefObject } from 'react';
import type { View } from 'react-native';

export type TipTarget = ComponentRef<typeof View>;

export type FloatTipProps = {
  text: string;
  /** 툴팁을 붙일 버튼 */
  anchor: RefObject<TipTarget | null>;
  /** 툴팁이 벗어나면 안 되는 패널 */
  bounds?: RefObject<TipTarget | null>;
  /** 스크롤·창 크기 변경 때 숨김 */
  onDismiss: () => void;
};

/* 앱에는 마우스 툴팁이 없음. 실제 웹 구현은 FloatTip.web.tsx */
export function FloatTip(_props: FloatTipProps) {
  return null;
}
