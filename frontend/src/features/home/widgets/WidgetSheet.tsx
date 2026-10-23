import React from 'react';
import { View } from 'react-native';
import { Icon } from '@/components/icons/Icon';
import { Sheet, SheetHeader } from '@/components/ui/Modal';
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
    <Sheet visible onClose={onClose} width={440} radius={20}>
      <SheetHeader title={title} description={subtitle} onClose={onClose} />
      <View style={{ gap: 10, minHeight: 300 }}>{children}</View>
      {footer && <View style={{ gap: 8, marginTop: 20, paddingTop: 16, borderTopWidth: 1, borderColor: colors.borderSoft }}>{footer}</View>}
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
