import React from 'react';
import { Image, Platform, Pressable, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { IconButton } from '@/components/ui/primitives';
import { T } from '@/components/ui/Text';
import { useBreakpoint } from '@/hooks/useLayout';
import { useUI } from '@/store/ui';
import { colors, shadow } from '@/theme/tokens';
import { ModalHost } from './ModalHost';
import { Sidebar } from './Sidebar';

/**
 * 앱 골격 — 데스크톱/태블릿: 고정 사이드바 · 모바일: 상단 바 + 드로어
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  const { isMobile, isTablet } = useBreakpoint();
  const { sidebarCollapsed, drawerOpen, setDrawer } = useUI();
  const router = useRouter();
  const collapsed = isTablet ? true : sidebarCollapsed;

  const Wrapper = Platform.OS === 'web' ? View : SafeAreaView;

  if (isMobile) {
    return (
      <Wrapper style={{ flex: 1, backgroundColor: colors.page }} {...(Platform.OS === 'web' ? {} : { edges: ['top', 'left', 'right'] as const })}>
        <View style={styles.mobileBar}>
          <IconButton name="menu" label="메뉴 열기" onPress={() => setDrawer(true)} color={colors.text} size={22} box={40} />
          <Pressable onPress={() => router.navigate('/')} accessibilityLabel="홈으로">
            <Image source={require('../../../assets/images/logo-wordmark.png')} style={{ width: 96, height: 32 }} resizeMode="contain" />
          </Pressable>
          <IconButton name="refresh" label="최신 업데이트" onPress={() => router.navigate('/updates')} color={colors.text} size={20} box={40} />
        </View>
        <View style={{ flex: 1 }}>{children}</View>
        {drawerOpen && (
          <View style={StyleSheet.absoluteFill}>
            <Pressable style={[StyleSheet.absoluteFill, { backgroundColor: colors.overlay }]} onPress={() => setDrawer(false)} accessibilityLabel="메뉴 닫기" />
            <View style={{ width: 280, height: '100%', ...shadow.modal }}>
              <Sidebar collapsed={false} onNavigate={() => setDrawer(false)} />
            </View>
          </View>
        )}
        <ModalHost />
        <Toast />
      </Wrapper>
    );
  }

  return (
    <View style={{ flex: 1, flexDirection: 'row', backgroundColor: colors.page }}>
      <Sidebar collapsed={collapsed} />
      <View style={{ flex: 1, minWidth: 0 }}>{children}</View>
      <ModalHost />
      <Toast />
    </View>
  );
}

function Toast() {
  const toast = useUI((s) => s.toast);
  if (!toast) return null;
  return (
    <View pointerEvents="none" style={styles.toastWrap}>
      <View style={styles.toast}>
        <T size={14} weight="medium" color="#FFF">
          {toast.message}
        </T>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  mobileBar: {
    height: 56,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 8,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderSoft,
  },
  toastWrap: { position: 'absolute', left: 0, right: 0, bottom: 32, alignItems: 'center', zIndex: 1000 },
  toast: { backgroundColor: '#1F2228', paddingHorizontal: 18, paddingVertical: 12, borderRadius: 12, ...shadow.pop },
});
