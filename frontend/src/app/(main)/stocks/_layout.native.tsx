import { Stack } from 'expo-router';
import { PUSH_SCREEN_OPTIONS } from '@/components/motion/Navigation';

/** 앱: 내 종목 → 종목 상세(메모 보드 · 기업정보)가 오른쪽에서 밀려 들어옴 (탭바는 그대로) */
export default function StocksStack() {
  return <Stack screenOptions={PUSH_SCREEN_OPTIONS} />;
}
