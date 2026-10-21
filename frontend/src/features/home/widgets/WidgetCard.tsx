import React from 'react';
import { View, type StyleProp, type ViewStyle } from 'react-native';
import { Icon, type IconName } from '@/components/icons/Icon';
import { Hoverable } from '@/components/ui/primitives';
import { T } from '@/components/ui/Text';
import { colors } from '@/theme/tokens';

/** 홈 위젯 공통 카드 (제목 · 부제 · 우상단 아이콘) */
export function WidgetCard({
  title,
  subtitle,
  icon,
  onIconPress,
  right,
  children,
  style,
  titleSize = 15,
}: {
  title: string;
  subtitle?: string;
  icon?: IconName;
  onIconPress?: () => void;
  right?: React.ReactNode;
  children: React.ReactNode;
  style?: StyleProp<ViewStyle>;
  titleSize?: number;
}) {
  return (
    <View style={[{ backgroundColor: colors.surface, borderRadius: 20, borderWidth: 1, borderColor: '#E8ECF3', padding: 18, gap: 14, flexGrow: 1 }, style]}>
      <View style={{ flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
        <View style={{ flex: 1, gap: 2 }}>
          <T size={titleSize} weight="bold">
            {title}
          </T>
          {subtitle ? (
            <T size={11} color={colors.textSub}>
              {subtitle}
            </T>
          ) : null}
        </View>
        {right}
        {icon && (
          <Hoverable onPress={onIconPress} disabled={!onIconPress} style={{ width: 28, height: 28, alignItems: 'center', justifyContent: 'center', borderRadius: 8 }} hoverStyle={{ backgroundColor: '#F3F4F6' }}>
            <Icon name={icon} size={17} color={colors.textBody} />
          </Hoverable>
        )}
      </View>
      {children}
    </View>
  );
}

export function LinkText({ label, onPress, align = 'center' }: { label: string; onPress: () => void; align?: 'center' | 'left' }) {
  return (
    <Hoverable onPress={onPress} style={{ alignSelf: align === 'center' ? 'center' : 'flex-start', paddingVertical: 4 }} hoverStyle={{ opacity: 0.75 }}>
      <T size={13} color={colors.blue} weight="medium">
        {label}
      </T>
    </Hoverable>
  );
}
