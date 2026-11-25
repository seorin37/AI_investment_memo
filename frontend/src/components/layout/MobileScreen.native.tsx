/**
 * (앱 전용 — MobileScreen.tsx 와 같고, MobileToast 만 아래 버튼 줄이 있는 화면에서 그 위 8 에 뜸)
 * 앱(안드로이드·iOS) 화면 공통 틀 — 위 상단 바(TopBar) + 화면 본문 (11.18).
 * - useProfileAction(): 상단 바 오른쪽 프로필 → MY (/my)
 * - useMockNotice(): mock 단계에서 아직 연결하지 않은 동작을 누르면 짧은 알림
 * - MobileToast: useUI().showToast 알림을 앱 상세 화면((detail)) 아래에 띄움 (탭 화면은 (main)/_layout.native 의 TabToast)
 */
import type { ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Text } from '@/components/ui/AppText';
import { useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import type { TopBarAction } from '@/components/layout/TopBar';
import { useAuth } from '@/store/auth';
import { useUI } from '@/store/ui';
import { useBottomBar } from '@/ui/shared/app/BottomBar';

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
  const bar = useBottomBar((s) => s.bar);
  if (!toast) return null;
  return (
    <View pointerEvents={toast.action ? 'box-none' : 'none'} style={[st.wrap, { bottom: bar ? bar.top + 8 : bottom + insets.bottom }]}>
      <View style={st.toast}>
        <Text style={st.text}>{toast.message}</Text>
        {toast.action ? (
          <Pressable
            onPress={() => {
              useUI.setState({ toast: null });
              toast.action?.onPress();
            }}
            hitSlop={12}
            accessibilityRole="button"
          >
            <Text style={st.action}>{toast.action.label}</Text>
          </Pressable>
        ) : null}
      </View>
    </View>
  );
}

const st = StyleSheet.create({
  wrap: { position: 'absolute', left: 16, right: 16, alignItems: 'center', zIndex: 1000 },
  toast: { flexDirection: 'row', alignItems: 'center', gap: 14, backgroundColor: '#1F2228', paddingHorizontal: 18, paddingVertical: 12, borderRadius: 12, elevation: 8 },
  action: { color: '#CDBBFF', fontSize: 14, fontWeight: '800' },
  text: { flexShrink: 1, color: '#FFFFFF', fontSize: 14 },
});
