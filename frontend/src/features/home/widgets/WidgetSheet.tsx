import React from 'react';
import { View } from 'react-native';
import { Icon } from '@/components/icons/Icon';
import { Sheet } from '@/components/ui/Modal';
import { IconButton } from '@/components/ui/primitives';
import { T } from '@/components/ui/Text';
import { colors } from '@/theme/tokens';

/** 위젯 세부 화면 공통 팝업 (이상규의 위젯 아이디어 · 세부 화면) */
export function WidgetSheet({
  title,
  subtitle,
  onClose,
  children,
  footer,
}: {
  title: string;
  subtitle?: string;
  onClose: () => void;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  return (
    <Sheet visible onClose={onClose} width={440} padding={20} radius={20}>
      <View style={{ flexDirection: 'row', alignItems: 'flex-start', marginBottom: 14 }}>
        <View style={{ flex: 1 }}>
          <T size={16} weight="bold">
            {title}
          </T>
          {subtitle && (
            <T size={11} color={colors.textSub}>
              {subtitle}
            </T>
          )}
        </View>
        <IconButton name="x" label="닫기" onPress={onClose} size={16} color={colors.text} />
      </View>
      <View style={{ gap: 10, minHeight: 300 }}>{children}</View>
      {footer && <View style={{ gap: 8, marginTop: 18 }}>{footer}</View>}
    </Sheet>
  );
}

export function SuccessBox({ message }: { message: string }) {
  return (
    <View style={{ backgroundColor: colors.greenSoft, borderRadius: 12, padding: 16, gap: 10 }}>
      <Icon name="check" size={16} color={colors.greenText} strokeWidth={2.4} />
      <T size={14} weight="semibold" color={colors.greenText}>
        {message}
      </T>
    </View>
  );
}

export function FieldLabel({ children }: { children: string }) {
  return (
    <T size={11} color={colors.textBody} weight="medium">
      {children}
    </T>
  );
}
