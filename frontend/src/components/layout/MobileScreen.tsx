/**
 * 앱(안드로이드·iOS) 화면 공통 틀 — 위 상단 바(TopBar) + 화면 본문. 웹용 AppShell 과 따로 쓴다 (11.18).
 * - useProfileAction(): 상단 바 오른쪽 프로필 → MY (/my)
 * - useMockNotice(): mock 단계에서 아직 연결하지 않은 동작을 누르면 짧은 알림
 * - MobileToast: useUI().showToast 알림을 앱 화면 아래에 띄움 (웹은 AppShell 의 Toast)
 */
import type { ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';
import { Text } from '@/components/ui/AppText';
import { useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import type { TopBarAction } from '@/components/layout/TopBar';
import { useAuth } from '@/store/auth';
import { useUI } from '@/store/ui';

export const APP_BG = '#F3F4F6';

export function MobileScreen({ bar, children, bg = APP_BG }: { bar?: ReactNode; children: ReactNode; bg?: string }) {
  return (
    <View style={{ flex: 1, backgroundColor: bg }}>
      {bar}
      <View style={{ flex: 1 }}>{children}</View>
    </View>
  );
}

export function useProfileAction(): TopBarAction {
  const router = useRouter();
  const name = useAuth((s) => s.user?.name) ?? '';
  return { kind: 'profile', initial: name.trim().slice(0, 1) || 'M', onPress: () => router.push('/my') };
}

/** mock 단계: 아직 연결하지 않은 동작 */
export function useMockNotice() {
  const toast = useUI((s) => s.showToast);
  return (what: string) => toast(`${what}은(는) 다음 단계에서 연결해요`);
}

export function MobileToast({ bottom = 96 }: { bottom?: number }) {
  const toast = useUI((s) => s.toast);
  const insets = useSafeAreaInsets();
  if (!toast) return null;
  return (
    <View pointerEvents="none" style={[st.wrap, { bottom: bottom + insets.bottom }]}>
      <View style={st.toast}>
        <Text style={st.text}>{toast.message}</Text>
      </View>
    </View>
  );
}

const st = StyleSheet.create({
  wrap: { position: 'absolute', left: 16, right: 16, alignItems: 'center', zIndex: 1000 },
  toast: { backgroundColor: '#1F2228', paddingHorizontal: 18, paddingVertical: 12, borderRadius: 12, elevation: 8 },
  text: { color: '#FFFFFF', fontSize: 14 },
});
