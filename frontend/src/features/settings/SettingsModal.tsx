import React, { useState } from 'react';
import { Linking, Platform, Pressable, ScrollView, View } from 'react-native';
import { useRouter } from 'expo-router';
import { env } from '@/config/env';
import { GoogleLogo, Icon, KakaoLogo, type IconName } from '@/components/icons/Icon';
import { Sheet } from '@/components/ui/Modal';
import { Avatar, Button, Hoverable, IconButton, LabeledCheck, Loading, MiniSegmented, Select, Switch, TextField } from '@/components/ui/primitives';
import { T } from '@/components/ui/Text';
import { useAiStats, useDataStats, useDisconnectMcpApp, useSettings, useUpdateMe, useUpdateSettings } from '@/hooks/queries';
import { useBreakpoint } from '@/hooks/useLayout';
import { relative } from '@/lib/format';
import { useAuth } from '@/store/auth';
import { useUI, type SettingsSection } from '@/store/ui';
import { colors } from '@/theme/tokens';
import type { Settings } from '@/types/models';
import { api } from '@/api';

const NAV: { group: string; items: { key: SettingsSection; label: string; icon: IconName }[] }[] = [
  {
    group: '계정',
    items: [
      { key: 'profile', label: '내 프로필', icon: 'user' },
      { key: 'display', label: '화면', icon: 'monitor' },
      { key: 'notifications', label: '알림', icon: 'bell' },
    ],
  },
  {
    group: '서비스',
    items: [
      { key: 'ai', label: 'AI 연결', icon: 'sparkles' },
      { key: 'usage', label: '사용량', icon: 'barChart' },
      { key: 'mcp', label: 'MCP 연결', icon: 'plug' },
    ],
  },
  {
    group: '기타',
    items: [
      { key: 'data', label: '데이터', icon: 'database' },
      { key: 'about', label: '정보', icon: 'info' },
    ],
  },
];

/** 8-1 ~ 8-7 설정 */
export function SettingsModal({ onClose, initial = 'display' }: { onClose: () => void; initial?: SettingsSection }) {
  const [section, setSection] = useState<SettingsSection>(initial);
  const user = useAuth((s) => s.user);
  const { data: settings } = useSettings();
  const upd = useUpdateSettings();
  const { isMobile } = useBreakpoint();
  const patch = (p: Parameters<typeof upd.mutate>[0]) => upd.mutate(p);

  const nav = isMobile ? (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6, padding: 12 }} style={{ flexGrow: 0, borderBottomWidth: 1, borderColor: colors.borderSoft }}>
      {NAV.flatMap((g) => g.items).map((it) => (
        <Hoverable key={it.key} onPress={() => setSection(it.key)} style={{ height: 34, paddingHorizontal: 12, borderRadius: 17, justifyContent: 'center', backgroundColor: section === it.key ? colors.brandSoft : '#F5F6F8' }}>
          <T size={13} weight={section === it.key ? 'semibold' : 'regular'} color={section === it.key ? colors.brand : colors.textBody}>
            {it.label}
          </T>
        </Hoverable>
      ))}
    </ScrollView>
  ) : (
    <View style={{ width: 250, borderRightWidth: 1, borderColor: colors.borderSoft, padding: 16, paddingTop: 28 }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 12, marginBottom: 20 }}>
        <Avatar name={user?.name ?? '?'} size={36} />
        <View>
          <T size={15} weight="medium">
            {user?.name}
          </T>
          <T size={11} color={colors.textSub}>
            설정
          </T>
        </View>
      </View>
      {NAV.map((g) => (
        <View key={g.group} style={{ marginBottom: 12 }}>
          <T size={11} color={colors.textSub} style={{ paddingHorizontal: 12, marginBottom: 8 }}>
            {g.group}
          </T>
          {g.items.map((it) => {
            const on = section === it.key;
            return (
              <Hoverable
                key={it.key}
                onPress={() => setSection(it.key)}
                style={[{ height: 42, flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 12, borderRadius: 8, marginBottom: 4 }, on && { backgroundColor: colors.brandSoft }]}
                hoverStyle={!on && { backgroundColor: '#F7F7F9' }}
              >
                <Icon name={it.icon} size={16} color={on ? colors.brand : colors.text} />
                <T size={14} weight={on ? 'semibold' : 'regular'} color={on ? colors.brand : colors.text}>
                  {it.label}
                </T>
              </Hoverable>
            );
          })}
        </View>
      ))}
    </View>
  );

  return (
    <Sheet visible onClose={onClose} width={1040} padding={0} radius={24} scroll={false}>
      <View style={{ flex: 1, flexDirection: isMobile ? 'column' : 'row' }}>
        {nav}
        <View style={{ flex: 1 }}>
          <IconButton name="x" label="닫기" onPress={onClose} size={20} color={colors.text} box={36} style={{ position: 'absolute', top: 28, right: 28, zIndex: 5 }} />
          <ScrollView contentContainerStyle={{ padding: isMobile ? 20 : 36, paddingRight: isMobile ? 20 : 36 }}>
            {!settings ? (
              <Loading height={300} />
            ) : (
              <>
                {section === 'profile' && <ProfilePanel onClose={onClose} />}
                {section === 'display' && <DisplayPanel s={settings} patch={patch} />}
                {section === 'notifications' && <NotificationsPanel s={settings} patch={patch} />}
                {section === 'ai' && <AiPanel s={settings} patch={patch} onClose={onClose} />}
                {section === 'usage' && <UsagePanel />}
                {section === 'mcp' && <McpPanel s={settings} patch={patch} />}
                {section === 'data' && <DataPanel onClose={onClose} />}
                {section === 'about' && <AboutPanel onClose={onClose} />}
              </>
            )}
          </ScrollView>
        </View>
      </View>
    </Sheet>
  );
}

type PatchFn = (p: Parameters<ReturnType<typeof useUpdateSettings>['mutate']>[0]) => void;

function PanelTitle({ title, desc, badge }: { title: string; desc?: string; badge?: string }) {
  return (
    <View style={{ marginBottom: 32, gap: 6, paddingRight: 48 }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <T size={26} weight="bold">
          {title}
        </T>
        {badge && (
          <View style={{ backgroundColor: '#F3F4F6', borderRadius: 4, paddingHorizontal: 6, height: 20, justifyContent: 'center' }}>
            <T size={10} color={colors.textSub} lh={1}>
              {badge}
            </T>
          </View>
        )}
      </View>
      {desc && (
        <T size={14} color={colors.textSub}>
          {desc}
        </T>
      )}
    </View>
  );
}

function Row({ title, desc, right, last }: { title: string; desc?: string; right?: React.ReactNode; last?: boolean }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 16, paddingVertical: 18, borderBottomWidth: last ? 0 : 1, borderColor: colors.borderSoft, zIndex: 1 }}>
      <View style={{ flex: 1, gap: 4 }}>
        <T size={15} weight="medium">
          {title}
        </T>
        {desc && (
          <T size={13} color={colors.textSub}>
            {desc}
          </T>
        )}
      </View>
      {right}
    </View>
  );
}

function SectionLabel({ children }: { children: string }) {
  return (
    <T size={16} weight="bold" style={{ marginTop: 20, marginBottom: 4 }}>
      {children}
    </T>
  );
}

// ─── 8-3 내 프로필
function ProfilePanel({ onClose }: { onClose: () => void }) {
  const user = useAuth((s) => s.user);
  const setUser = useAuth((s) => s.setUser);
  const signOut = useAuth((s) => s.signOut);
  const upd = useUpdateMe();
  const toast = useUI((s) => s.showToast);
  const [name, setName] = useState(user?.name ?? '');
  const [bio, setBio] = useState(user?.bio ?? '');
  if (!user) return null;
  const save = () => upd.mutate({ name, bio }, { onSuccess: (u) => (setUser(u), toast('프로필을 저장했어요')) });
  const logos: Record<string, React.ReactNode> = { kakao: <KakaoLogo size={16} />, naver: <T size={13} weight="bold" color="#03A94D">N</T>, google: <GoogleLogo size={16} /> };
  const label: Record<string, string> = { kakao: '카카오', naver: '네이버', google: '구글', email: '이메일' };
  return (
    <View>
      <PanelTitle title="내 프로필" />
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 18, marginBottom: 24 }}>
        <Avatar name={user.name} size={64} />
        <View style={{ gap: 8 }}>
          <T size={14} weight="medium">
            프로필 사진
          </T>
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <Button label="사진 변경" variant="outline" size="sm" />
            <Button label="삭제" variant="outline" size="sm" />
          </View>
        </View>
      </View>
      <View style={{ flexDirection: 'row', gap: 12, flexWrap: 'wrap' }}>
        <View style={{ flex: 1, minWidth: 200, gap: 6 }}>
          <T size={12} color={colors.textSub}>
            이름
          </T>
          <TextField value={name} onChangeText={setName} onBlur={save} />
        </View>
        <View style={{ flex: 1, minWidth: 200, gap: 6 }}>
          <T size={12} color={colors.textSub}>
            한 줄 소개
          </T>
          <TextField value={bio} onChangeText={setBio} onBlur={save} />
        </View>
      </View>
      <SectionLabel>연결된 로그인</SectionLabel>
      <T size={13} color={colors.textSub} style={{ marginBottom: 12 }}>
        연결한 계정으로 메모스톡에 로그인할 수 있어요.
      </T>
      <View style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 14, paddingHorizontal: 16 }}>
        {user.providers.map((p, i) => (
          <View key={p.provider} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 16, borderTopWidth: i ? 1 : 0, borderColor: colors.borderSoft }}>
            <View style={{ width: 32, height: 32, borderRadius: 8, backgroundColor: '#F5F6F8', alignItems: 'center', justifyContent: 'center' }}>{logos[p.provider]}</View>
            <View style={{ flex: 1 }}>
              <T size={14} weight="medium">
                {label[p.provider]}
              </T>
              <T size={11} color={colors.textSub}>
                {p.connected ? `${p.email ?? ''}${p.current ? ' · 현재 로그인 중' : ''}` : '연결되지 않음'}
              </T>
            </View>
            {p.current ? (
              <T size={12} color={colors.brand}>
                사용 중
              </T>
            ) : (
              <Button label={p.connected ? '해제' : '연결'} variant="outline" size="sm" />
            )}
          </View>
        ))}
      </View>
      <Row
        title="로그아웃"
        desc="이 기기에서 로그아웃해요."
        last
        right={
          <Button
            label="로그아웃"
            variant="outline"
            size="sm"
            onPress={() => {
              onClose();
              void signOut();
            }}
          />
        }
      />
    </View>
  );
}

// ─── 8-1 화면
function DisplayPanel({ s, patch }: { s: Settings; patch: PatchFn }) {
  return (
    <View>
      <PanelTitle title="화면" />
      <View style={{ zIndex: 3 }}>
        <Row
          title="테마"
          desc="이 기기에서 메모스톡 테마를 선택하세요. (다크 테마는 준비 중이에요)"
          right={
            <Select
              width={194}
              value={s.theme}
              options={[
                { key: 'system', label: '시스템 설정 사용' },
                { key: 'light', label: '라이트' },
                { key: 'dark', label: '다크 (준비 중)', disabled: true },
              ]}
              onChange={(theme) => patch({ theme })}
            />
          }
        />
      </View>
      <SectionLabel>언어 및 지역</SectionLabel>
      <View style={{ zIndex: 2 }}>
        <Row title="언어" desc="메모스톡에서 사용할 언어를 선택하세요. 지금은 한국어만 지원하고, 다른 언어는 준비 중이에요." right={<Select width={120} value="ko" options={[{ key: 'ko', label: '한국어' }]} onChange={() => {}} />} />
      </View>
      <View style={{ zIndex: 1 }}>
        <Row
          title="등락 색상"
          desc="주가가 오르거나 내릴 때 표시할 색을 선택하세요."
          last
          right={
            <Select
              width={218}
              value={s.updown_color}
              options={[
                { key: 'red_up', label: '상승 빨강 · 하락 파랑' },
                { key: 'green_up', label: '상승 초록 · 하락 빨강' },
              ]}
              onChange={(updown_color) => patch({ updown_color })}
            />
          }
        />
      </View>
    </View>
  );
}

// ─── 8-4 알림
function NotificationsPanel({ s, patch }: { s: Settings; patch: PatchFn }) {
  const n = s.notifications;
  return (
    <View>
      <PanelTitle title="알림" desc="내 메모와 연결된 새 소식을 어떻게 받을지 정해요." />
      <SectionLabel>받을 알림</SectionLabel>
      <Row title="공시 알림" desc="내 종목의 새 공시가 올라오면 알려줘요." right={<Switch value={n.disclosure} onChange={(v) => patch({ notifications: { disclosure: v } })} />} />
      <Row title="뉴스 알림" desc="AI 연결 메모와 관련된 뉴스를 알려줘요." right={<Switch value={n.news} onChange={(v) => patch({ notifications: { news: v } })} />} />
      <Row title="가격 조건 알림" desc="메모에 적은 가격 조건에 도달하면 알려줘요." right={<Switch value={n.price_condition} onChange={(v) => patch({ notifications: { price_condition: v } })} />} />
      <View style={{ zIndex: 3 }}>
        <Row
          title="주가 급변 알림"
          desc="하루 등락폭이 큰 종목을 알려줘요."
          right={
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
              <Select
                width={104}
                value={String(n.price_spike_threshold) as '3' | '5' | '10'}
                options={[
                  { key: '3', label: '±3% 이상' },
                  { key: '5', label: '±5% 이상' },
                  { key: '10', label: '±10% 이상' },
                ]}
                onChange={(k) => patch({ notifications: { price_spike_threshold: Number(k) as 3 | 5 | 10 } })}
              />
              <Switch value={n.price_spike} onChange={(v) => patch({ notifications: { price_spike: v } })} />
            </View>
          }
        />
      </View>
      <SectionLabel>받는 방식</SectionLabel>
      <View style={{ flexDirection: 'row', gap: 22, paddingVertical: 14, borderBottomWidth: 1, borderColor: colors.borderSoft }}>
        <LabeledCheck label="앱 내 알림" checked={n.channels.in_app} onChange={(v) => patch({ notifications: { channels: { in_app: v } } })} />
        <LabeledCheck label="이메일" checked={n.channels.email} onChange={(v) => patch({ notifications: { channels: { email: v } } })} />
        <LabeledCheck label="푸시 알림" checked={n.channels.push} onChange={(v) => patch({ notifications: { channels: { push: v } } })} />
      </View>
      <View style={{ zIndex: 2 }}>
        <Row
          title="받는 주기"
          desc="알림을 바로 받을지, 모아서 받을지 선택하세요."
          right={
            <Select
              width={120}
              value={n.frequency}
              options={[
                { key: 'realtime', label: '실시간' },
                { key: 'hourly', label: '1시간마다' },
                { key: 'daily', label: '하루 한 번' },
              ]}
              onChange={(frequency) => patch({ notifications: { frequency } })}
            />
          }
        />
      </View>
      <View style={{ zIndex: 1 }}>
        <Row
          title="방해 금지 시간"
          desc="설정한 시간에는 알림을 보내지 않아요."
          last
          right={
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
              <Select
                width={168}
                value={`${n.quiet_hours.from}-${n.quiet_hours.to}`}
                options={[
                  { key: '22:00-07:00', label: '오후 10:00 ~ 오전 7:00' },
                  { key: '23:00-08:00', label: '오후 11:00 ~ 오전 8:00' },
                  { key: '00:00-09:00', label: '오전 12:00 ~ 오전 9:00' },
                ]}
                onChange={(k) => {
                  const [from, to] = k.split('-');
                  patch({ notifications: { quiet_hours: { from, to } } });
                }}
              />
              <Switch value={n.quiet_hours.enabled} onChange={(v) => patch({ notifications: { quiet_hours: { enabled: v } } })} />
            </View>
          }
        />
      </View>
    </View>
  );
}

// ─── 8-5 AI 연결
function AiPanel({ s, patch, onClose }: { s: Settings; patch: PatchFn; onClose: () => void }) {
  const { data: stats } = useAiStats();
  const router = useRouter();
  return (
    <View>
      <PanelTitle title="AI 연결" desc="AI가 내 메모와 관련된 공시·뉴스·주가 변화를 찾아 연결해줘요." />
      <Row title="새 메모에 AI 연결 기본 적용" desc="끄면 새 메모는 AI 연결 없이 만들어지고, 메모마다 직접 켤 수 있어요." right={<Switch value={s.ai.default_link_new_memo} onChange={(v) => patch({ ai: { default_link_new_memo: v } })} />} />
      <SectionLabel>추적할 소스</SectionLabel>
      <T size={13} color={colors.textSub} style={{ marginTop: 8 }}>
        선택한 소스에서만 새 소식을 찾아요.
      </T>
      <View style={{ flexDirection: 'row', gap: 22, paddingVertical: 16 }}>
        <LabeledCheck label="공시 (DART)" checked={s.ai.sources.disclosure} onChange={(v) => patch({ ai: { sources: { disclosure: v } } })} />
        <LabeledCheck label="뉴스" checked={s.ai.sources.news} onChange={(v) => patch({ ai: { sources: { news: v } } })} />
        <LabeledCheck label="주가 변동" checked={s.ai.sources.price} onChange={(v) => patch({ ai: { sources: { price: v } } })} />
      </View>
      <Row
        title="업데이트 민감도"
        desc="높을수록 메모와 관련 깊은 소식만 보여줘요."
        last
        right={
          <MiniSegmented
            items={[
              { key: 'strict', label: '관련 높은 것만' },
              { key: 'balanced', label: '균형' },
              { key: 'broad', label: '폭넓게' },
            ]}
            value={s.ai.sensitivity}
            onChange={(sensitivity) => patch({ ai: { sensitivity } })}
          />
        }
      />
      <View style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 14, padding: 20, gap: 18, marginTop: 12 }}>
        <T size={16} weight="semibold">
          AI 연결 현황
        </T>
        <StatRow items={[['AI 연결 메모', `${stats?.linked_memos ?? '–'}개`], ['이번 달 업데이트', `${stats?.updates_this_month ?? '–'}건`], ['연결된 종목', `${stats?.linked_stocks ?? '–'}개`]]} />
        <Button
          label="연결 메모 관리"
          variant="outline"
          size="sm"
          style={{ alignSelf: 'flex-start' }}
          onPress={() => {
            onClose();
            router.navigate('/updates');
          }}
        />
      </View>
      <T size={13} color={colors.textSub} style={{ marginTop: 24 }}>
        AI 연결을 켠 메모만 분석하고, 연결하지 않은 메모는 분석하지 않아요. 업데이트는 참고용 정보이며 투자 권유가 아니에요.
      </T>
    </View>
  );
}

function StatRow({ items }: { items: [string, string][] }) {
  return (
    <View style={{ flexDirection: 'row' }}>
      {items.map(([k, v]) => (
        <View key={k} style={{ flex: 1, gap: 6 }}>
          <T size={11} color={colors.textSub}>
            {k}
          </T>
          <T size={24} weight="bold">
            {v}
          </T>
        </View>
      ))}
    </View>
  );
}

// ─── 사용량 (시안 없음 — 최소 구성)
function UsagePanel() {
  const { data: stats } = useAiStats();
  return (
    <View>
      <PanelTitle title="사용량" desc="이번 달 AI 연결과 업데이트 사용 현황이에요." />
      <View style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 14, padding: 20 }}>
        <StatRow items={[['AI 연결 메모', `${stats?.linked_memos ?? '–'}개`], ['이번 달 업데이트', `${stats?.updates_this_month ?? '–'}건`], ['연결된 종목', `${stats?.linked_stocks ?? '–'}개`]]} />
      </View>
      <T size={13} color={colors.textSub} style={{ marginTop: 20 }} lh={1.6}>
        모든 메모를 매일 AI에 넣지 않아요. 임베딩 검색과 코드로 후보를 먼저 좁히고, 관련성이 높을 때만 AI 판단을 사용해요. 가격 조건은 AI 없이 종가로 계산해요.
      </T>
    </View>
  );
}

// ─── 8-2 MCP 연결
function McpPanel({ s, patch }: { s: Settings; patch: PatchFn }) {
  const m = s.mcp;
  const disconnect = useDisconnectMcpApp();
  const toast = useUI((st) => st.showToast);
  const copy = async () => {
    if (Platform.OS === 'web' && globalThis.navigator?.clipboard) {
      await globalThis.navigator.clipboard.writeText(m.server_url);
      toast('서버 주소를 복사했어요');
    } else toast(m.server_url);
  };
  return (
    <View>
      <PanelTitle title="MCP 연결" badge="베타" desc="Claude, ChatGPT 같은 외부 AI 앱에서 내 투자 메모를 읽을 수 있도록 메모스톡 MCP 서버를 연결해요." />
      <Row title="MCP 서버 사용" desc="켜면 연결한 AI 앱이 내 메모를 읽을 수 있어요." right={<Switch value={m.enabled} onChange={(v) => patch({ mcp: { enabled: v } })} />} />
      <View style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 14, padding: 18, gap: 12, marginVertical: 16, opacity: m.enabled ? 1 : 0.5 }}>
        <T size={14} weight="medium">
          서버 주소 · 예시
        </T>
        <T size={12} color={colors.textSub}>
          AI 앱의 MCP 설정에 이 주소를 붙여넣으세요.
        </T>
        <View style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: '#F7F8FA', borderRadius: 10, padding: 8, paddingLeft: 12 }}>
          <T size={13} style={{ flex: 1 }} numberOfLines={1}>
            {m.server_url}
          </T>
          <Button label="복사" variant="outline" size="sm" onPress={() => void copy()} />
        </View>
      </View>
      <SectionLabel>공유 범위</SectionLabel>
      <View style={{ flexDirection: 'row', gap: 22, paddingVertical: 14 }}>
        <LabeledCheck label="메모" checked={m.scopes.memo} onChange={(v) => patch({ mcp: { scopes: { memo: v } } })} />
        <LabeledCheck label="투자 기록" checked={m.scopes.journal} onChange={(v) => patch({ mcp: { scopes: { journal: v } } })} />
        <LabeledCheck label="종목 정보" checked={m.scopes.stock} onChange={(v) => patch({ mcp: { scopes: { stock: v } } })} />
      </View>
      <Row
        title="접근 권한"
        right={
          <MiniSegmented
            items={[
              { key: 'read', label: '읽기 전용' },
              { key: 'read_write', label: '읽기·쓰기' },
            ]}
            value={m.access}
            onChange={(access) => patch({ mcp: { access } })}
          />
        }
      />
      <Row title="AI 연결을 켠 메모만 공유" desc="끄면 AI 연결 여부와 상관없이 선택한 범위를 모두 공유해요." right={<Switch value={m.only_ai_linked} onChange={(v) => patch({ mcp: { only_ai_linked: v } })} />} />
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 20, marginBottom: 12 }}>
        <T size={16} weight="bold">
          연결된 앱
        </T>
        <Button label="새 앱 연결" variant="outline" size="sm" onPress={() => void copy()} />
      </View>
      {m.apps.length === 0 && (
        <T size={13} color={colors.textMuted}>
          아직 연결된 앱이 없어요.
        </T>
      )}
      {m.apps.map((a) => (
        <View key={a.id} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, borderWidth: 1, borderColor: colors.border, borderRadius: 14, padding: 16 }}>
          <View style={{ width: 32, height: 32, borderRadius: 8, backgroundColor: '#F5F6F8', alignItems: 'center', justifyContent: 'center' }}>
            <T size={13} weight="bold">
              {a.name[0]}
            </T>
          </View>
          <View style={{ flex: 1 }}>
            <T size={14} weight="medium">
              {a.name}
            </T>
            <T size={11} color={colors.textSub}>
              {a.access === 'read' ? '읽기 전용' : '읽기·쓰기'} · 마지막 사용 {relative(a.last_used_at)}
            </T>
          </View>
          <Button label="연결 해제" variant="outline" size="sm" loading={disconnect.isPending} onPress={() => disconnect.mutate(a.id)} />
        </View>
      ))}
    </View>
  );
}

// ─── 8-6 데이터
function DataPanel({ onClose }: { onClose: () => void }) {
  const { data: stats } = useDataStats();
  const openModal = useUI((s) => s.openModal);
  const toast = useUI((s) => s.showToast);
  const [format, setFormat] = useState<'csv' | 'json'>('csv');
  const [confirm, setConfirm] = useState(false);
  return (
    <View>
      <PanelTitle title="데이터" />
      <View style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 14, padding: 20, marginBottom: 12 }}>
        <StatRow items={[['메모', `${stats?.memos ?? '–'}개`], ['투자 기록', `${stats?.journals ?? '–'}개`], ['종목', `${stats?.stocks ?? '–'}개`]]} />
      </View>
      <View style={{ zIndex: 2 }}>
        <Row
          title="내보내기"
          desc="메모와 투자 기록을 파일로 내려받아요."
          right={
            <View style={{ flexDirection: 'row', gap: 8 }}>
              <Select
                width={96}
                value={format}
                options={[
                  { key: 'csv', label: 'CSV' },
                  { key: 'json', label: 'JSON' },
                ]}
                onChange={setFormat}
              />
              <Button
                label="내보내기"
                variant="outline"
                size="sm"
                style={{ height: 38 }}
                onPress={async () => {
                  const { url } = await api.exportData(format);
                  if (env.useMock) toast('목업 모드에서는 빈 파일이 만들어져요');
                  else void Linking.openURL(url);
                }}
              />
            </View>
          }
        />
      </View>
      <Row title="휴지통" desc="삭제한 항목을 확인하고 복원하거나 영구 삭제할 수 있어요." right={<Button label="휴지통 열기" variant="outline" size="sm" onPress={() => openModal({ type: 'trash' })} />} />
      <View style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 14, padding: 18, marginTop: 16, gap: 10 }}>
        <T size={13} weight="semibold" color={colors.danger}>
          위험 구역
        </T>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
          <View style={{ flex: 1 }}>
            <T size={14} weight="medium">
              모든 데이터 삭제
            </T>
            <T size={12} color={colors.textSub}>
              모든 메모, 기록, 종목이 영구 삭제돼요. 되돌릴 수 없어요.
            </T>
          </View>
          {confirm ? (
            <View style={{ flexDirection: 'row', gap: 6 }}>
              <Button label="취소" variant="outline" size="sm" onPress={() => setConfirm(false)} />
              <Button
                label="정말 삭제"
                variant="danger"
                size="sm"
                onPress={async () => {
                  await api.deleteAllData();
                  toast('모든 데이터를 삭제했어요');
                  onClose();
                }}
              />
            </View>
          ) : (
            <Button label="전체 삭제" variant="dangerOutline" size="sm" onPress={() => setConfirm(true)} />
          )}
        </View>
      </View>
    </View>
  );
}

// ─── 8-7 정보
function AboutPanel({ onClose }: { onClose: () => void }) {
  const openModal = useUI((s) => s.openModal);
  const links: { label: string; run: () => void }[] = [
    { label: '이용약관', run: () => {} },
    { label: '개인정보 처리방침', run: () => {} },
    { label: '오픈소스 라이선스', run: () => {} },
    { label: '피드백 보내기', run: () => openModal({ type: 'feedback' }) },
    { label: '문의하기', run: () => openModal({ type: 'feedback', tab: 'bug' }) },
  ];
  return (
    <View>
      <PanelTitle title="정보" />
      <Row title="버전" desc="메모스톡 v0.1.0 (베타)" right={<T size={12} color={colors.textSub}>최신 버전이에요</T>} />
      {links.map((l) => (
        <Pressable key={l.label} onPress={l.run} style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 16, borderBottomWidth: 1, borderColor: colors.borderSoft }}>
          <T size={14}>{l.label}</T>
          <Icon name="chevronRight" size={14} color={colors.textSub} />
        </Pressable>
      ))}
      <SectionLabel>데이터 출처</SectionLabel>
      <T size={13} color={colors.textSub} style={{ marginTop: 8 }}>
        공시 · 금융감독원 DART{'   '}뉴스 · 네이버 뉴스{'   '}주가 · 한국투자증권 KIS Open API
      </T>
      <View style={{ backgroundColor: '#F7F8FA', borderRadius: 12, padding: 16, marginTop: 16 }}>
        <T size={12} color={colors.textSub} lh={1.6}>
          메모스톡은 투자 권유를 하지 않으며, 제공되는 모든 정보는 참고용이에요. 투자 판단과 그 결과에 대한 책임은 투자자 본인에게 있어요.
        </T>
      </View>
      <T size={11} color={colors.textSub} style={{ marginTop: 20 }}>
        SIG · Saram Is Good
      </T>
    </View>
  );
}
