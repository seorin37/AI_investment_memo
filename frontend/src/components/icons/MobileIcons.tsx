/**
 * 모바일 앱 화면 공용 선 아이콘 (react-native-svg).
 * 체험판(memo's 앱 최종본)의 SVG 경로를 그대로 옮김. 색은 color prop으로만 받음.
 */
import Svg, { Circle, Path, Rect } from 'react-native-svg';

export type MobileIconName =
  | 'search' | 'bell' | 'back' | 'more' | 'more_h' | 'plus' | 'check' | 'close'
  | 'grid' | 'list' | 'plug' | 'pin' | 'mic' | 'edit' | 'trash' | 'copy' | 'palette'
  | 'home' | 'updates' | 'stocks' | 'journal' | 'studio' | 'check_all' | 'chevron_right'
  | 'audio' | 'report' | 'lab' | 'quiz' | 'play' | 'memo' | 'checklist' | 'news'
  | 'chart' | 'sun' | 'moon' | 'holding' | 'watching' | 'info'
  | 'refresh' | 'drag' | 'arrow_right';

export interface MobileIconProps {
  name: MobileIconName;
  size?: number;
  color: string;
  strokeWidth?: number;
}

export function MobileIcon({ name, size = 22, color, strokeWidth = 2 }: MobileIconProps) {
  const s = { stroke: color, strokeWidth, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, fill: 'none' };
  const body = (() => {
    switch (name) {
      case 'search': return <><Circle cx={11} cy={11} r={7} {...s} /><Path d="M20 20l-4-4" {...s} /></>;
      case 'bell': return <><Path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15z" {...s} /><Path d="M10 20.5a2 2 0 0 0 4 0" {...s} /></>;
      case 'back': return <Path d="M15 5l-7 7 7 7" {...s} />;
      case 'more': return <><Circle cx={12} cy={5} r={1.8} fill={color} /><Circle cx={12} cy={12} r={1.8} fill={color} /><Circle cx={12} cy={19} r={1.8} fill={color} /></>;
      case 'more_h': return <><Circle cx={5} cy={12} r={1.7} fill={color} /><Circle cx={12} cy={12} r={1.7} fill={color} /><Circle cx={19} cy={12} r={1.7} fill={color} /></>;
      case 'plus': return <Path d="M12 5v14M5 12h14" {...s} />;
      case 'check': return <Path d="M5 12.5l4.5 4.5L19 7.5" {...s} />;
      case 'close': return <Path d="M6 6l12 12M18 6 6 18" {...s} />;
      case 'grid': return <><Rect x={4} y={4} width={7} height={7} rx={1.6} {...s} /><Rect x={13} y={4} width={7} height={7} rx={1.6} {...s} /><Rect x={4} y={13} width={7} height={7} rx={1.6} {...s} /><Rect x={13} y={13} width={7} height={7} rx={1.6} {...s} /></>;
      case 'list': return <Path d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01" {...s} />;
      case 'plug': return <><Path d="M9 3v4M15 3v4M12 16.5V21" {...s} /><Path d="M6.5 7h11v4a5.5 5.5 0 0 1-11 0z" fill={color} stroke="none" /></>;
      case 'pin': return <Path d="M9 3h6l-1 6 4 4H6l4-4zM12 13v8" {...s} />;
      case 'mic': return <><Rect x={9} y={3} width={6} height={11} rx={3} {...s} /><Path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21" {...s} /></>;
      case 'edit': return <><Path d="M4 20h4L19 9l-4-4L4 16z" {...s} /><Path d="M13.5 6.5l4 4" {...s} /></>;
      case 'trash': return <Path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13" {...s} />;
      case 'copy': return <><Rect x={8} y={8} width={12} height={12} rx={2} {...s} /><Path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3" {...s} /></>;
      case 'palette': return <><Circle cx={12} cy={12} r={9} {...s} /><Circle cx={8.5} cy={10} r={1.3} fill={color} /><Circle cx={12} cy={7.5} r={1.3} fill={color} /><Circle cx={15.5} cy={10} r={1.3} fill={color} /></>;
      case 'home': return <Path d="M3 11 12 4l9 7v9h-6v-6H9v6H3z" {...s} />;
      case 'updates': return <Path d="M20 12a8 8 0 0 1-14 5.3M4 12a8 8 0 0 1 14-5.3M18 3v4h-4M6 21v-4h4" {...s} />;
      case 'stocks': return <><Rect x={3} y={7} width={18} height={13} rx={2.5} {...s} /><Path d="M9 7V5h6v2M8 16v-3M12 16v-5M16 16v-2" {...s} /></>;
      case 'journal': return <><Path d="M6 3h8l4 4v14H6z" {...s} /><Path d="M9 12h6M9 16h6" {...s} /></>;
      case 'studio': return <><Path d="M12 4l1.6 4.4L18 10l-4.4 1.6L12 16l-1.6-4.4L6 10l4.4-1.6z" fill={color} stroke="none" /><Path d="M18.5 15l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z" fill={color} stroke="none" /></>;
      case 'check_all': return <Path d="M2 12.5l4.5 4.5L15 8.5M10 16l1 1L21.5 6.5" {...s} />;
      case 'chevron_right': return <Path d="M9 5l7 7-7 7" {...s} />;
      case 'audio': return <Path d="M4 10v4M8 7v10M12 4v16M16 8v8M20 11v2" {...s} />;
      case 'report': return <><Path d="M7 3h7l5 5v12a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z" {...s} /><Path d="M14 3v5h5M9.5 17v-2M12.5 17v-4M15.5 17v-3" {...s} /></>;
      case 'lab': return <><Path d="M9 3h6M10 3v6l-5 9.5A1.7 1.7 0 0 0 6.5 21h11a1.7 1.7 0 0 0 1.5-2.5L14 9V3" {...s} /><Path d="M7.5 15h9" {...s} /></>;
      case 'quiz': return <><Circle cx={12} cy={12} r={9} {...s} /><Path d="M9.6 9.3a2.4 2.4 0 0 1 4.8.9c0 1.7-2.4 2.2-2.4 3.6M12 17.2h.01" {...s} /></>;
      case 'play': return <Path d="M8 5v14l11-7z" fill={color} stroke="none" />;
      case 'memo': return <><Path d="M5 4.5h14v10l-5 5H5z" {...s} /><Path d="M14 19.5v-5h5M8.5 9h7M8.5 12.5h4" {...s} /></>;
      case 'checklist': return <><Rect x={4} y={4} width={16} height={16} rx={4} {...s} /><Path d="M8 12.3l2.6 2.6L16 9.5" {...s} /></>;
      case 'news': return <><Rect x={4} y={4} width={16} height={16} rx={3} {...s} /><Path d="M8 9h8M8 13h8M8 17h5" {...s} /></>;
      case 'chart': return <Path d="M4 18l5-6 4 3 7-8M15 7h5v5" {...s} />;
      case 'sun': return <><Circle cx={12} cy={12} r={4} {...s} /><Path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" {...s} /></>;
      case 'moon': return <Path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" {...s} />;
      case 'holding': return <><Rect x={3.5} y={7} width={17} height={12} rx={2.5} {...s} /><Path d="M9 7V5h6v2M3.5 12h17" {...s} /></>;
      case 'watching': return <><Path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15z" {...s} /><Path d="M10 20.5a2 2 0 0 0 4 0" {...s} /></>;
      case 'info': return <><Circle cx={12} cy={12} r={9} {...s} /><Path d="M12 11v5M12 8h.01" {...s} /></>;
      case 'refresh': return <><Path d="M20 11a8 8 0 1 0-2.3 5.7" {...s} /><Path d="M20 4v7h-7" {...s} /></>;
      case 'drag': return <><Circle cx={9} cy={6} r={1.6} fill={color} /><Circle cx={15} cy={6} r={1.6} fill={color} /><Circle cx={9} cy={12} r={1.6} fill={color} /><Circle cx={15} cy={12} r={1.6} fill={color} /><Circle cx={9} cy={18} r={1.6} fill={color} /><Circle cx={15} cy={18} r={1.6} fill={color} /></>;
      case 'arrow_right': return <Path d="M5 12h14M13 6l6 6-6 6" {...s} />;
    }
  })();
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24">
      {body}
    </Svg>
  );
}
