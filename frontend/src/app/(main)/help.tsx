import React from 'react';
import { View } from 'react-native';
import { Page, PageHeader } from '@/components/layout/Page';
import { T } from '@/components/ui/Text';
import { colors } from '@/theme/tokens';

const FAQ = [
  { q: 'AI 연결은 무엇인가요?', a: '메모 카드의 토글을 켜면 그 메모와 관련된 공시·뉴스·주가 변화를 AI가 찾아 연결해요. 끈 메모는 분석하지 않아요.' },
  { q: '가격 조건은 어떻게 인식되나요?', a: '“15만원 밑이면 다시 보기”처럼 금액과 방향이 들어간 메모를 코드로 감지해요. AI 없이 매 영업일 종가와 비교해요.' },
  { q: '메모와 투자 기록은 어떻게 다른가요?', a: '메모는 앞으로 확인할 생각, 투자 기록은 이미 지나간 판단을 돌아보는 공간이에요.' },
];

/** 11. 도움말 — 서비스 이용 안내는 준비 중 (시안), 자주 묻는 질문만 우선 제공 */
export default function HelpScreen() {
  return (
    <Page top={80} maxWidth={760}>
      <PageHeader title="도움말" subtitle="서비스 이용 안내는 준비 중입니다." size={28} />
      <View style={{ gap: 12 }}>
        {FAQ.map((f) => (
          <View key={f.q} style={{ backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: 16, padding: 18, gap: 6 }}>
            <T size={15} weight="semibold">
              {f.q}
            </T>
            <T size={14} color={colors.textSub} lh={1.6}>
              {f.a}
            </T>
          </View>
        ))}
      </View>
    </Page>
  );
}
