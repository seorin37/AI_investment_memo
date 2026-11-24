import React, { useCallback, useRef, useState, type RefObject } from 'react';
import { Pressable, ScrollView, StyleSheet, View, useWindowDimensions } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { Text, TextInput } from '@/components/ui/AppText';
import { ConfirmDialog } from '@/ui/shared/ConfirmDialog';
import { FloatTip, type TipTarget } from '@/ui/shared/FloatTip';
import { Sheet } from '@/ui/shared/Sheet';
import type { TrashItem } from '../My.mock';
import type { TrashProps } from '../My.types';
import { CloseX, type Hover } from './parts';

/**
 * 웹 휴지통 = 원본 overlays.tsx Trash (680×660 · 라운드 20 · 안쪽 23 · 사이 16)
 * 머리(22 · 17) · 검색 48 · [유형 ⌄] 고르기(전체·메모·투자 기록·종목·체크리스트) · '삭제한 항목 N' · 줄 72(아이콘 24 · 제목 17 · 'sub · 언제 삭제' · 복원 · 영구 삭제)
 * 아래: '휴지통 항목은 직접 지우기 전까지 보관돼요.' · [휴지통 비우기] — 영구 삭제·비우기는 확인창까지만
 */
const TYPES = ['전체', '메모', '투자 기록', '종목', '체크리스트'] as const;
type Ty = (typeof TYPES)[number];

export function WebTrash({ open, items, onClose, onRestore, onPurge }: TrashProps & { open: boolean; onClose: () => void }) {
  const { height } = useWindowDimensions();
  const [q, setQ] = useState('');
  const [type, setType] = useState<Ty | null>(null);
  const [menu, setMenu] = useState(false);
  const [ask, setAsk] = useState<TrashItem | 'all' | null>(null);
  const panel = useRef<TipTarget>(null);
  const t0 = type ?? '전체';
  const list = items.filter((t) => (t0 === '전체' || t.kind === t0) && (!q.trim() || t.title.includes(q.trim()) || t.sub.includes(q.trim())));
  return (
    <Sheet open={open} onClose={onClose} width={680} scrim="rgba(0,0,0,0.32)" label="휴지통">
      <View ref={panel} style={[st.box, { height: Math.min(660, height - 32) }]}>
        <View style={st.head}>
          <View style={{ flex: 1, gap: 4 }}>
            <Text style={st.title}>휴지통</Text>
            <Text style={st.sub}>삭제한 항목을 확인하고 복원할 수 있어요.</Text>
          </View>
          <CloseX onPress={onClose} />
        </View>
        <TextInput value={q} onChangeText={setQ} placeholder="휴지통에서 항목 검색" placeholderTextColor="#747D8D" accessibilityLabel="휴지통에서 항목 검색" style={st.search} />
        <View style={st.typeRow}>
          <Pressable onPress={() => setMenu(!menu)} accessibilityRole="button" accessibilityState={{ expanded: menu }} style={({ hovered }: Hover) => [st.typeBtn, menu ? st.typeOn : hovered && { backgroundColor: '#F6F6F6' }]}>
            <Text style={st.typeT}>{type ?? '유형'}</Text>
            <Svg width={14} height={14} viewBox="0 0 14 14" fill="none"><Path d="M3.11133 5.44531L7.00022 9.3342L10.8891 5.44531" stroke="#333333" strokeWidth={1.24444} strokeLinecap="round" strokeLinejoin="round" /></Svg>
          </Pressable>
          {menu ? (
            <View style={st.menu} accessibilityRole="menu">
              {TYPES.map((t) => {
                const on = t === t0;
                return (
                  <Pressable key={t} onPress={() => { setType(t); setMenu(false); }} accessibilityRole="menuitem" style={({ hovered }: Hover) => [st.opt, (on || hovered) && { backgroundColor: '#F8F7F5' }]}>
                    <Text style={[st.typeT, { flex: 1 }]}>{t}</Text>
                    {on ? <Svg width={16} height={16} viewBox="0 0 16 16" fill="none"><Path d="M3.11133 8.44531L6.66688 12.0009L12.8891 4.44531" stroke="#333333" strokeWidth={1.42222} strokeLinecap="round" strokeLinejoin="round" /></Svg> : null}
                  </Pressable>
                );
              })}
            </View>
          ) : null}
        </View>
        <View style={{ flex: 1, minHeight: 0, gap: 8, zIndex: -1 }}>
          <View style={st.cntRow}><Text style={st.cntL}>삭제한 항목</Text><Text style={[st.cntL, { color: '#333333' }]}>{list.length}</Text></View>
          <ScrollView style={{ flex: 1 }}>
            {!list.length ? (
              <View style={st.empty}>
                <Text style={st.emptyB}>{items.length ? '찾는 항목이 없어요' : '휴지통이 비어 있어요'}</Text>
                <Text style={st.emptyS}>{items.length ? '다른 말로 찾아보세요' : '지운 메모·기록·종목이 여기에 모여요'}</Text>
              </View>
            ) : (
              list.map((t) => (
                <View key={t.id} style={st.row}>
                  <KindIcon kind={t.kind} />
                  <View style={{ flex: 1, minWidth: 0, gap: 2 }}>
                    <Text style={st.rowT} numberOfLines={1}>{t.title}</Text>
                    <Text style={st.rowS} numberOfLines={1}>{t.sub} · {t.ago} 삭제</Text>
                  </View>
                  <View style={st.acts}>
                    <TipBtn tip="복원" open={open} bounds={panel} onPress={() => onRestore(t)}>
                      {(c) => <Svg width={22} height={22} viewBox="0 0 20 20" fill="none"><Path d="M7.22226 5L3.33337 8.88889L7.22226 12.7778" stroke={c} strokeWidth={1.77778} strokeLinecap="round" strokeLinejoin="round" /><Path d="M3.33337 8.89062H11.6667C15 8.89062 16.6667 10.5573 16.6667 13.8906V15.0017" stroke={c} strokeWidth={1.77778} strokeLinecap="round" strokeLinejoin="round" /></Svg>}
                    </TipBtn>
                    <TipBtn tip="영구 삭제" danger open={open} bounds={panel} onPress={() => setAsk(t)}>
                      {(c) => <Svg width={22} height={22} viewBox="0 0 20 20" fill="none" stroke={c} strokeWidth={1.77778} strokeLinecap="round" strokeLinejoin="round"><Path d="M3.33337 5H16.6667" /><Path d="M7.77783 4.9987V3.33203H12.2223V4.9987" /><Path d="M5 5L5.88889 17.2222H14.1111L15 5" /><Path d="M8.33337 8.89062V13.8906" /><Path d="M11.6666 8.89062V13.8906" /></Svg>}
                    </TipBtn>
                  </View>
                </View>
              ))
            )}
          </ScrollView>
        </View>
        <View style={st.foot}>
          <Text style={[st.cntL, { flex: 1, fontWeight: '400' }]}>휴지통 항목은 직접 지우기 전까지 보관돼요.</Text>
          <Pressable disabled={!items.length} onPress={() => setAsk('all')} accessibilityRole="button" style={({ hovered }: Hover) => [st.emptyAll, !items.length && { opacity: 0.4 }, hovered && !!items.length && { backgroundColor: '#FDF0F1' }]}>
            <Text style={st.emptyAllT}>휴지통 비우기</Text>
          </Pressable>
        </View>
      </View>
      <ConfirmDialog
        variant="web"
        danger
        open={!!ask}
        title={ask === 'all' ? '휴지통을 비울까요?' : '영구 삭제할까요?'}
        body={ask === 'all' ? `${items.length}개 항목이 영구 삭제돼요. 되돌릴 수 없어요.` : ask ? `'${ask.title}'을(를) 영구 삭제하면 되돌릴 수 없어요.` : ''}
        confirmLabel={ask === 'all' ? '비우기' : '영구 삭제'}
        onCancel={() => setAsk(null)}
        onConfirm={() => { const a = ask; setAsk(null); onPurge(a === 'all' ? null : a); }}
      />
    </Sheet>
  );
}

/* TipBtn: 40 · 라운드 8 · hover #F8F7F5 (위험은 #FBEFEF · 아이콘 빨강) · 검정 말풍선은 목록에 잘리지 않게 body에 (FloatTip) */
function TipBtn({ tip, danger, open, bounds, onPress, children }: { tip: string; danger?: boolean; open: boolean; bounds: RefObject<TipTarget | null>; onPress: () => void; children: (c: string) => React.ReactNode }) {
  const [h, setH] = useState(false);
  const btn = useRef<TipTarget>(null);
  const hide = useCallback(() => setH(false), []);
  return (
    <>
      <Pressable
        ref={btn}
        onPress={() => {
          hide();
          onPress();
        }}
        onHoverIn={() => setH(true)}
        onHoverOut={hide}
        /* 마우스로 누를 때의 focus로 다시 뜨지 않게 키보드 focus만 */
        onFocus={(e) => {
          if ((e.target as unknown as Element).matches?.(':focus-visible')) setH(true);
        }}
        onBlur={hide}
        accessibilityRole="button"
        accessibilityLabel={tip}
        style={[st.tip, h && { backgroundColor: danger ? '#FBEFEF' : '#F8F7F5' }]}
      >
        {children(h && danger ? '#E45D6A' : '#333333')}
      </Pressable>
      {h && open ? <FloatTip text={tip} anchor={btn} bounds={bounds} onDismiss={hide} /> : null}
    </>
  );
}

function KindIcon({ kind }: { kind: TrashItem['kind'] }) {
  const p = { stroke: '#333333', strokeWidth: 1.95556, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const };
  return (
    <Svg width={24} height={24} viewBox="0 0 22 22" fill="none">
      {kind === '메모' ? (
        <><Path d="M4.39984 14.1768L3.6665 18.3324L7.82206 17.599L18.0887 7.33238L14.6665 3.91016L4.39984 14.1768Z" {...p} /><Path d="M12.7109 5.86719L16.1332 9.28941" {...p} /></>
      ) : kind === '종목' ? (
        <><Path d="M18.9446 7.33203H3.05566V18.332H18.9446V7.33203Z" {...p} /><Path d="M7.94434 7.33507V4.89062H14.0554V7.33507" {...p} /><Path d="M3.05566 12.2227H18.9446" {...p} /></>
      ) : (
        <><Path d="M13.4442 2.44531H4.88867V19.5564H17.722V6.72309L13.4442 2.44531Z" {...p} /><Path d="M13.4443 2.44531V6.72309H17.7221" {...p} /><Path d="M7.94434 11.6094H14.6666" {...p} /><Path d="M7.94434 15.2773H14.6666" {...p} /></>
      )}
    </Svg>
  );
}

const st = StyleSheet.create({
  box: { width: 680, maxWidth: '100%', gap: 16, borderRadius: 20, borderWidth: 1, borderColor: '#E8EAED', backgroundColor: '#FFFFFF', padding: 23 },
  head: { height: 56, flexDirection: 'row', alignItems: 'center', gap: 16 },
  title: { fontSize: 22, lineHeight: 31, fontWeight: '700', color: '#15171A' },
  sub: { fontSize: 17, lineHeight: 26, color: '#747D8D' },
  search: { height: 48, borderRadius: 12, backgroundColor: '#F8F7F5', paddingHorizontal: 16, fontSize: 17, lineHeight: 26, color: '#15171A', borderWidth: 1, borderColor: 'transparent' },
  typeRow: { height: 36, flexDirection: 'row', alignItems: 'center', gap: 8, zIndex: 5 },
  typeBtn: { height: 36, flexDirection: 'row', alignItems: 'center', gap: 8, borderRadius: 8, paddingHorizontal: 13, backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#E8EAED' },
  typeOn: { borderWidth: 1.5, borderColor: '#15171A' },
  typeT: { fontSize: 15, lineHeight: 23, fontWeight: '500', color: '#333333' },
  menu: { position: 'absolute', left: 0, top: 44, width: 180, borderRadius: 12, borderWidth: 1, borderColor: '#E8EAED', backgroundColor: '#FFFFFF', padding: 8, shadowColor: '#1C2940', shadowOpacity: 0.08, shadowRadius: 32, shadowOffset: { width: 0, height: 12 } },
  opt: { height: 40, flexDirection: 'row', alignItems: 'center', gap: 8, borderRadius: 8, paddingHorizontal: 12 },
  cntRow: { height: 22, flexDirection: 'row', alignItems: 'center', gap: 8 },
  cntL: { fontSize: 14, lineHeight: 21, fontWeight: '500', color: '#747D8D' },
  empty: { alignItems: 'center', gap: 4, paddingVertical: 64 },
  emptyB: { fontSize: 17, lineHeight: 26, fontWeight: '700', color: '#333D4B' },
  emptyS: { fontSize: 14, lineHeight: 21, color: '#8B95A1' },
  row: { height: 72, flexDirection: 'row', alignItems: 'center', gap: 12, borderBottomWidth: 1, borderBottomColor: '#E8EAED', paddingVertical: 8, paddingLeft: 8, paddingRight: 4 },
  rowT: { fontSize: 17, lineHeight: 26, fontWeight: '500', color: '#15171A' },
  rowS: { fontSize: 14, lineHeight: 21, color: '#747D8D' },
  acts: { width: 88, height: 40, flexDirection: 'row', alignItems: 'center', gap: 8 },
  tip: { width: 40, height: 40, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  foot: { height: 36, flexDirection: 'row', alignItems: 'center', gap: 8 },
  emptyAll: { height: 36, borderRadius: 10, paddingHorizontal: 12, justifyContent: 'center' },
  emptyAllT: { fontSize: 14, lineHeight: 21, fontWeight: '700', color: '#E45D6A' },
});
