import React, { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View, useWindowDimensions } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { Text } from '@/components/ui/AppText';
import type { InboxItem } from '../My.mock';
import type { InboxProps } from '../My.types';
import { useEscWhile } from './inboxKeys.web';
import type { Hover } from './parts';

/**
 * 웹 알림함 = 원본 x.tsx InboxPanel (fixed · 위 16 · 왼쪽 사이드바 폭+8 · 380 · 라운드 22)
 * '알림' 20 + [모두 읽음] · 탭(전체·업데이트·스튜디오) · 줄(아이콘 36 · 제목 15 · 설명 14 · 언제 13 · 안 읽음 점) · 아래 [알림 설정]
 * 바깥 누르기·Esc 로 닫힘. 읽음은 화면 상태만 (mock)
 */
type Tab = 'all' | 'ai' | 'studio';

export function WebInbox({ open, left, items, unread, noti, onClose, onOpen, onReadAll, onSettings }: Omit<InboxProps, 'onBack'> & { open: boolean; left: number; onClose: () => void }) {
  const [tab, setTab] = useState<Tab>('all');
  const { height } = useWindowDimensions();
  useEscWhile(open, onClose);
  if (!open) return null;
  const allOff = !noti.ai && !noti.studio;
  const list = items.filter((n) => (n.kind === 'ai' ? noti.ai : noti.studio) && (tab === 'all' || n.kind === tab));
  const nUnread = list.filter((n) => unread.includes(n.id)).length;
  return (
    <>
      <Pressable onPress={onClose} accessible={false} style={StyleSheet.absoluteFill} />
      <View aria-label="알림함" style={[st.pan, { left, maxHeight: height - 32 }]}>
        <View style={st.head}>
          <Text style={st.title}>알림</Text>
          <Pressable disabled={!nUnread} onPress={onReadAll} accessibilityRole="button" style={({ hovered }: Hover) => [st.all, !nUnread && { opacity: 0.4 }, hovered && !!nUnread && { backgroundColor: '#F5F6F8' }]}>
            <Text style={st.allT}>모두 읽음</Text>
          </Pressable>
        </View>
        <View style={st.tabs}>
          {([['all', '전체'], ['ai', '업데이트'], ['studio', '스튜디오']] as const).map(([k, l]) => (
            <Pressable key={k} onPress={() => setTab(k)} accessibilityRole="tab" accessibilityState={{ selected: tab === k }} style={({ hovered }: Hover) => [st.tab, tab === k ? { backgroundColor: '#15171A' } : hovered && { backgroundColor: '#F5F6F8' }]}>
              <Text style={[st.tabT, tab === k && { color: '#FFFFFF' }]}>{l}</Text>
            </Pressable>
          ))}
        </View>
        <ScrollView style={{ flexShrink: 1 }} contentContainerStyle={{ paddingHorizontal: 8, paddingBottom: 8 }}>
          {allOff ? <Empty t="알림을 모두 꺼 두었어요" s="알림에서 켠 알림만 여기에 와요" /> : !list.length ? <Empty t="새 알림이 없어요" s="연결한 메모에 소식이 오면 여기에 모아 드려요" /> : list.map((n) => {
            const read = !unread.includes(n.id);
            return (
              <Pressable key={n.id} onPress={() => onOpen(n)} accessibilityRole="button" style={({ hovered }: Hover) => [st.row, read && { opacity: 0.6 }, hovered && { backgroundColor: '#F5F6F8' }]}>
                <NIcon kind={n.kind} />
                <View style={{ flex: 1, minWidth: 0 }}>
                  <Text style={st.rT} numberOfLines={1}>{n.title}</Text>
                  <Text keepAll style={st.rS}>{n.sub}</Text>
                  <Text style={st.rW}>{n.when}</Text>
                </View>
                {!read ? <View style={st.dot} /> : null}
              </Pressable>
            );
          })}
        </ScrollView>
        <Pressable onPress={onSettings} accessibilityRole="button" style={({ hovered }: Hover) => [st.set, hovered && { backgroundColor: '#F9F9F9' }]}>
          <Text style={st.allT}>알림 설정</Text>
        </Pressable>
      </View>
    </>
  );
}

function NIcon({ kind }: { kind: InboxItem['kind'] }) {
  return (
    <View style={[st.ic, { backgroundColor: kind === 'ai' ? '#F1F2F4' : '#15171A' }]}>
      {kind === 'ai' ? (
        <Svg width={18} height={18} viewBox="0 0 20 20" fill="none" stroke="#15171a" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round"><Path d="M7.5 3.5v3M12.5 3.5v3M5.5 6.5h9v3a4.5 4.5 0 0 1-9 0z" /><Path d="M10 14v3" /></Svg>
      ) : (
        <Svg width={16} height={16} viewBox="0 0 16 16" fill="none"><Path d="M7.33317 2C7.73317 4.86667 9.13317 6.26667 11.9998 6.66667C9.13317 7.06667 7.73317 8.46667 7.33317 11.3333C6.93317 8.46667 5.53317 7.06667 2.6665 6.66667C5.53317 6.26667 6.93317 4.86667 7.33317 2Z" fill="white" /></Svg>
      )}
    </View>
  );
}

const Empty = ({ t, s }: { t: string; s: string }) => (
  <View style={{ alignItems: 'center', gap: 4, paddingHorizontal: 24, paddingVertical: 48 }}>
    <Text style={{ fontSize: 15, lineHeight: 23, fontWeight: '700', color: '#333D4B' }}>{t}</Text>
    <Text keepAll style={{ fontSize: 14, lineHeight: 21, color: '#8B95A1', textAlign: 'center' }}>{s}</Text>
  </View>
);

const st = StyleSheet.create({
  pan: { position: 'absolute', top: 16, zIndex: 60, width: 380,borderRadius: 22, borderWidth: 1, borderColor: '#E5E8EB', backgroundColor: '#FFFFFF', shadowColor: '#111111', shadowOpacity: 0.35, shadowRadius: 30, shadowOffset: { width: 0, height: 30 }, overflow: 'hidden' },
  head: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 20, paddingBottom: 8, paddingTop: 18 },
  title: { flex: 1, fontSize: 20, lineHeight: 29, fontWeight: '700', color: '#15171A' },
  all: { height: 32, borderRadius: 8, paddingHorizontal: 8, justifyContent: 'center' },
  allT: { fontSize: 14, lineHeight: 21, fontWeight: '700', color: '#575B63' },
  tabs: { flexDirection: 'row', gap: 4, paddingHorizontal: 16, paddingBottom: 8 },
  tab: { height: 32, borderRadius: 999, paddingHorizontal: 12, justifyContent: 'center' },
  tabT: { fontSize: 13, lineHeight: 20, fontWeight: '700', color: '#8B95A1' },
  row: { flexDirection: 'row', alignItems: 'flex-start', gap: 12, borderRadius: 14, paddingVertical: 11, paddingLeft: 12, paddingRight: 28 },
  ic: { width: 36, height: 36, borderRadius: 11, alignItems: 'center', justifyContent: 'center' },
  rT: { fontSize: 15, lineHeight: 23, fontWeight: '700', color: '#15171A' },
  rS: { fontSize: 14, lineHeight: 21, color: '#575B63' },
  rW: { fontSize: 13, lineHeight: 20, color: '#9A9EA7' },
  dot: { position: 'absolute', right: 12, top: 18, width: 8, height: 8, borderRadius: 4, backgroundColor: '#E5484D' },
  set: { height: 48, alignItems: 'center', justifyContent: 'center', borderTopWidth: 1, borderTopColor: '#EFEFF2' },
});
