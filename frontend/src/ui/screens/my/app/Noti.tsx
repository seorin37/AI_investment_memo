import React from 'react';
import { Toggle } from '@/ui/shared/Toggle';
import type { NotiProps } from '../My.types';
import { Foot, Grp, Item, Page, Rv } from './parts';

/**
 * 앱 알림 = 원본 app/my.html openNoti() (11.13: AI 업데이트 알림 · 스튜디오 알림 두 개만)
 * 화면 상태만 바꿈 — OS 알림 권한은 묻지 않음.
 */
export function AppNoti({ noti, onBack, onChange }: NotiProps) {
  return (
    <Page title="알림" lead="알림을 받을지 정해요." onBack={onBack}>
      <Rv i={0}>
        <Grp>
          <Item two title="AI 업데이트 알림" sub="AI 연결한 메모에 새 공시·뉴스·가격 소식이 오면 알려 줘요" right={<Toggle variant="app" on={noti.ai} onChange={(v) => onChange({ ...noti, ai: v })} label="AI 업데이트 알림" />} />
          <Item two last title="스튜디오 알림" sub="오디오·주간보고서·실험 결과가 다 만들어지면 알려 줘요" right={<Toggle variant="app" on={noti.studio} onChange={(v) => onChange({ ...noti, studio: v })} label="스튜디오 알림" />} />
        </Grp>
      </Rv>
      <Rv i={1}><Foot>여기서 켠 알림만 위쪽 종(🔔) 알림함에 쌓여요. 휴대폰 설정에서 memo&apos;s 알림을 꺼 두면 휴대폰 알림은 오지 않아요.</Foot></Rv>
    </Page>
  );
}
