import React from 'react';
import { StyleSheet, View } from 'react-native';
import { webColor } from '@/ui/theme';
import { Sidebar } from './Sidebar';
import { StudioColumnFrame } from './StudioColumnFrame';
import type { SidebarProps, StudioColumnFrameProps } from './WebShell.types';

/**
 * 웹 3단 (원본 App.tsx Shell): 사이드바(250/72) · 가운데(#FDFDFD, 스크롤은 각 화면) · 스튜디오 열(436/96)
 * 전체 바탕은 원본 html,body #F6F6F6 대신 가운데 #FDFDFD 와 같은 줄 바탕(원본 Shell 의 bg-[#FDFDFD]).
 */
export function WebShell({ sidebar, studio, children }: { sidebar: SidebarProps; studio: Omit<StudioColumnFrameProps, 'children'> & { content?: React.ReactNode }; children: React.ReactNode }) {
  const { content, ...frame } = studio;
  return (
    <View style={st.shell}>
      <Sidebar {...sidebar} />
      <View style={st.main}>{children}</View>
      <StudioColumnFrame {...frame}>{content}</StudioColumnFrame>
    </View>
  );
}

const st = StyleSheet.create({
  shell: { flex: 1, flexDirection: 'row', backgroundColor: webColor.page },
  main: { flex: 1, minWidth: 0, backgroundColor: webColor.page },
});
