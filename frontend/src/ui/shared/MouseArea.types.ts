/** 마우스 위치를 알려 주는 투명 칸 (웹 전용 · 앱에서는 아무것도 그리지 않음) */
export interface MouseAreaProps {
  width: number;
  height: number;
  /** FixedFrame 배율 (원본 860 px 로 돌려 줌) */
  scale?: number;
  onMove: (x: number, y: number) => void;
  onLeave: () => void;
  /** left · top 등 (px) */
  style?: { left?: number; top?: number };
  cursor?: 'crosshair' | 'pointer' | 'default';
}
