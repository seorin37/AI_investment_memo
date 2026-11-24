import React, { useState } from 'react';
import { View, type StyleProp, type ViewStyle } from 'react-native';
import { PaperFace } from './MemoPaper';

/**
 * 크기가 내용에 따라 바뀌는 메모지 (원본 .paper · .mver · .mnote: 라운드 r r 0 r · 오른쪽 아래 cut 만큼 잘리고 접힌 부분 색).
 * 크기를 재서 PaperFace 를 뒤에 그림 (RN 에는 clip-path 가 없음).
 */
export function PaperBox({ bg, accent, radius, cut, variant = 'app', style, children }: { bg: string; accent: string; radius: number; cut: number; variant?: 'app' | 'web'; style?: StyleProp<ViewStyle>; children: React.ReactNode }) {
  const [box, setBox] = useState<{ w: number; h: number } | null>(null);
  return (
    <View style={style} onLayout={(e) => setBox({ w: e.nativeEvent.layout.width, h: e.nativeEvent.layout.height })}>
      {box ? <PaperFace width={box.w} height={box.h} bg={bg} accent={accent} variant={variant} radius={radius} cut={cut} /> : null}
      {children}
    </View>
  );
}
