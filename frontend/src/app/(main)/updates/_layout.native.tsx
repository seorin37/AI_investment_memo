import { Stack } from 'expo-router';
import { PUSH_SCREEN_OPTIONS } from '@/components/motion/Navigation';

/** 앱: 업데이트 탭 안에서 종목별 화면이 오른쪽에서 밀려 들어옴 (탭바는 그대로) */
export default function UpdatesStack() {
  return <Stack screenOptions={PUSH_SCREEN_OPTIONS} />;
}
