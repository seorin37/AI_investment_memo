import React from 'react';
import { RefreshControl, ScrollView, View, type StyleProp, type ViewStyle } from 'react-native';
import { T } from '@/components/ui/Text';
import { useBreakpoint } from '@/hooks/useLayout';
import { colors } from '@/theme/tokens';

/** 화면 공통 스크롤 컨테이너 — 시안 기준 좌우 32 · 상단 48 여백 */
export function Page({
  children,
  scroll = true,
  maxWidth,
  style,
  refreshing,
  onRefresh,
  top = 48,
}: {
  children: React.ReactNode;
  scroll?: boolean;
  maxWidth?: number;
  style?: StyleProp<ViewStyle>;
  refreshing?: boolean;
  onRefresh?: () => void;
  top?: number;
}) {
  const { isMobile } = useBreakpoint();
  const pad = { paddingHorizontal: isMobile ? 16 : 32, paddingTop: isMobile ? 20 : top, paddingBottom: 48 };
  const inner = <View style={[{ width: '100%', maxWidth, alignSelf: maxWidth ? 'flex-start' : undefined }, style]}>{children}</View>;
  if (!scroll) return <View style={[{ flex: 1 }, pad]}>{inner}</View>;
  return (
    <ScrollView
      style={{ flex: 1 }}
      contentContainerStyle={pad}
      refreshControl={onRefresh ? <RefreshControl refreshing={!!refreshing} onRefresh={onRefresh} /> : undefined}
    >
      {inner}
    </ScrollView>
  );
}

export function PageHeader({ title, subtitle, right, size = 26 }: { title: string; subtitle?: string; right?: React.ReactNode; size?: number }) {
  const { isMobile } = useBreakpoint();
  return (
    <View style={{ flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, marginBottom: isMobile ? 16 : 24 }}>
      <View style={{ flex: 1, gap: 4 }}>
        <T size={isMobile ? 22 : size} weight="bold">
          {title}
        </T>
        {subtitle ? (
          <T size={14} color={colors.textSub}>
            {subtitle}
          </T>
        ) : null}
      </View>
      {right}
    </View>
  );
}
