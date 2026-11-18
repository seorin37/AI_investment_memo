import React, { useState } from 'react';
import { Linking, Pressable, View } from 'react-native';
import { Icon, type IconName } from '@/components/icons/Icon';
import { Hoverable } from '@/components/ui/primitives';
import { T } from '@/components/ui/Text';
import { dotDateTime, korMonthDay, korMonthDayTime, mmdd } from '@/lib/format';
import { colors, timelineTone } from '@/theme/tokens';
import type { MemoVersion, TimelineEntry, UpdateType } from '@/types/models';

const typeIcon: Record<UpdateType, IconName> = { news: 'newspaper', price: 'candle', disclosure: 'fileText' };
const sourceLabel = (t: UpdateType, source: string) => (t === 'price' ? `시세 ${source}` : t === 'disclosure' ? `DART` : source);

/**
 * 메모 팝업 'AI 업데이트' 탭 — 시계열 타임라인.
 * 각 소식에 '당시 메모(버전)'를 함께 보여줘 메모를 수정해도 어떤 생각에 대한 업데이트였는지 알 수 있어요.
 */
export function AiTimeline({ entries, order }: { entries: TimelineEntry[]; order: 'desc' | 'asc' }) {
  const [open, setOpen] = useState<string | null>(null);
  const list = order === 'desc' ? entries : [...entries].reverse();
  const key = (e: TimelineEntry, i: number) => (e.kind === 'update' ? e.update.id : `${e.kind}-${i}`);

  return (
    <View style={{ gap: 8 }}>
      {list.map((e, i) => {
        const k = key(e, i);
        const expanded = open === k;
        const toggle = () => setOpen(expanded ? null : k);
        if (e.kind === 'update') return <UpdateCard key={k} entry={e} expanded={expanded} onToggle={toggle} />;
        if (e.kind === 'memo_edit' || e.kind === 'memo_created')
          return <MemoHistoryRow key={k} version={e.version} created={e.kind === 'memo_created'} expanded={expanded} onToggle={toggle} />;
        return (
          <View key={k} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingLeft: 24, paddingVertical: 8 }}>
            <View style={{ width: 5, height: 5, borderRadius: 3, backgroundColor: colors.greenText }} />
            <T size={12} color={colors.textBody}>
              {korMonthDay(e.at)} · AI 연결 시작
            </T>
          </View>
        );
      })}
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 4 }}>
        <Icon name="sparkles" size={13} color={colors.greenText} />
        <T size={12} color={colors.textBody}>
          뉴스·공시는 AI가 요약했어요. 자세히에서 메모와 출처를 볼 수 있어요.
        </T>
      </View>
    </View>
  );
}

function UpdateCard({ entry, expanded, onToggle }: { entry: Extract<TimelineEntry, { kind: 'update' }>; expanded: boolean; onToggle: () => void }) {
  const u = entry.update;
  const tone = timelineTone[u.type];
  const snap = entry.memo_snapshot;
  return (
    <View style={{ backgroundColor: tone.bg, borderRadius: 16, overflow: 'hidden' }}>
      <View style={{ position: 'absolute', left: 0, top: 16, bottom: expanded ? undefined : 16, height: expanded ? 40 : undefined, width: 3, backgroundColor: tone.bar, borderRadius: 2 }} />
      <Pressable onPress={onToggle} accessibilityRole="button" accessibilityState={{ expanded }} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 16, paddingLeft: 16, paddingRight: 16 }}>
        <View style={{ width: 32, height: 32, borderRadius: 10, backgroundColor: tone.iconBg, alignItems: 'center', justifyContent: 'center' }}>
          <Icon name={typeIcon[u.type]} size={16} color={tone.icon} />
        </View>
        <View style={{ flex: 1 }}>
          <T size={12} color={colors.textWarm}>
            {tone.label} · {korMonthDay(u.published_at)}
          </T>
          <T size={16} weight="bold" numberOfLines={expanded ? undefined : 1}>
            {u.headline}
          </T>
        </View>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
          <T size={12} color={colors.textWarm}>
            {expanded ? '접기' : '자세히'}
          </T>
          <Icon name={expanded ? 'chevronUp' : 'chevronDown'} size={14} color={colors.textWarm} />
        </View>
      </Pressable>
      {expanded && (
        <View style={{ paddingLeft: 60, paddingRight: 20, paddingBottom: 18, gap: 12 }}>
          <T size={13} color={colors.textWarm} lh={1.6}>
            {u.summary}
          </T>
          <View style={{ borderLeftWidth: 2, borderLeftColor: tone.bar, paddingLeft: 12, gap: 2 }}>
            <T size={11} color={colors.textWarm}>
              연결된 내 메모 · {korMonthDay(snap.saved_at)} {snap.version > 1 ? '수정' : '작성'}
            </T>
            <T size={13} weight="semibold">
              {snap.title}
            </T>
            <T size={12} color={colors.textWarm}>
              {snap.body.replace(/\n/g, ' ')}
            </T>
          </View>
          <View style={{ gap: 2 }}>
            <Pressable disabled={!u.url} onPress={() => u.url && void Linking.openURL(u.url)}>
              <T size={11} color={u.url ? colors.textBody : colors.textWarm} style={u.url ? { textDecorationLine: 'underline' } : undefined}>
                출처 {sourceLabel(u.type, u.source)} · {dotDateTime(u.published_at)}
              </T>
            </Pressable>
            {u.type === 'price' && (
              <T size={11} color={colors.textWarm}>
                설정한 가격 조건과 비교해 자동 계산했어요.
              </T>
            )}
          </View>
        </View>
      )}
    </View>
  );
}

function MemoHistoryRow({ version, created, expanded, onToggle }: { version: MemoVersion; created: boolean; expanded: boolean; onToggle: () => void }) {
  return (
    <View>
      <Hoverable onPress={onToggle} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 16, height: 48, borderRadius: 12 }} hoverStyle={{ backgroundColor: '#FAFAF9' }}>
        <View style={{ width: 32, height: 22, borderRadius: 6, backgroundColor: colors.greenSoft, alignItems: 'center', justifyContent: 'center' }}>
          <Icon name={created ? 'file' : 'edit'} size={13} color={colors.greenText} strokeWidth={2} />
        </View>
        <T size={14} color={colors.textWarm} style={{ flex: 1 }}>
          {mmdd(version.saved_at)} · {created ? '첫 메모를 남겼어요' : '메모를 수정했어요'}
        </T>
        <Icon name={expanded ? 'chevronUp' : 'chevronDown'} size={14} color={colors.textWarm} />
      </Hoverable>
      {expanded && (
        <View style={{ marginLeft: 60, marginRight: 16, marginBottom: 8, backgroundColor: '#E2F5E9', borderRadius: 12, padding: 14, gap: 2 }}>
          <T size={11} color={colors.textWarm}>
            {korMonthDayTime(version.saved_at)} · {created ? '처음 작성한 메모' : '수정 당시 메모'}
          </T>
          <T size={13} weight="semibold">
            {version.title}
          </T>
          <T size={12} color={colors.textWarm}>
            {version.body}
          </T>
        </View>
      )}
    </View>
  );
}
