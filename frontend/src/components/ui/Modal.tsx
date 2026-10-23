import React from 'react';
import { KeyboardAvoidingView, Modal, Platform, Pressable, ScrollView, StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import { useBreakpoint } from '@/hooks/useLayout';
import { colors, modalLayout, shadow } from '@/theme/tokens';
import { IconButton } from './primitives';
import { T } from './Text';

/**
 * 중앙 팝업 (웹/태블릿) · 하단 시트형 (모바일) 공통 모달.
 * react-native-web 의 Modal 은 body 포털로 렌더되어 사이드바 위를 덮습니다.
 */
export function Sheet({
  visible,
  onClose,
  width = 640,
  children,
  scroll = true,
  padding = modalLayout.padding,
  radius = modalLayout.radius,
  style,
}: {
  visible: boolean;
  onClose: () => void;
  width?: number;
  children: React.ReactNode;
  scroll?: boolean;
  padding?: number;
  radius?: number;
  style?: StyleProp<ViewStyle>;
}) {
  const { isMobile, height } = useBreakpoint();
  const body = scroll ? (
    <ScrollView contentContainerStyle={{ padding }} keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}>
      {children}
    </ScrollView>
  ) : (
    <View style={{ padding, flex: 1 }}>{children}</View>
  );
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose} statusBarTranslucent>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={[styles.backdrop, isMobile && { justifyContent: 'flex-end', padding: 0 }]}>
        <Pressable style={StyleSheet.absoluteFill} onPress={onClose} accessibilityLabel="닫기" />
        <View
          style={[
            styles.panel,
            { width: '100%', maxWidth: width, maxHeight: height * (isMobile ? 0.92 : 0.94), borderRadius: radius },
            isMobile && { borderBottomLeftRadius: 0, borderBottomRightRadius: 0, maxWidth: undefined },
            !scroll && { height: Math.min(height * 0.94, 780) },
            style,
          ]}
        >
          {body}
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

/** 모달 상단: 작은 맥락 라벨 + 제목 + 닫기 */
export function SheetHeader({ eyebrow, title, description, titleSize = modalLayout.titleSize, onClose, right }: { eyebrow?: string; title: string; description?: string; titleSize?: number; onClose: () => void; right?: React.ReactNode }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 20, gap: 12 }}>
      <View style={{ flex: 1, minWidth: 0, gap: 4 }}>
        {eyebrow ? (
          <T size={13} color={colors.textWarm}>
            {eyebrow}
          </T>
        ) : null}
        <T size={titleSize} weight="bold">
          {title}
        </T>
        {!!description && <T size={modalLayout.descriptionSize} color={colors.textSub}>{description}</T>}
      </View>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        {right}
        <IconButton name="x" label="닫기" onPress={onClose} size={modalLayout.closeSize} color={colors.text} box={modalLayout.closeBox} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: colors.overlay,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 20,
  },
  panel: {
    backgroundColor: colors.surface,
    overflow: 'hidden',
    ...shadow.modal,
  },
});
