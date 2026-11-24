import * as Clipboard from 'expo-clipboard';
import { Share } from 'react-native';
import { ON_DOM } from '@/ui/shared/onDom';

/** 글 복사 (앱 · expo-clipboard) */
export function copyText(text: string): void {
  void Clipboard.setStringAsync(text).catch(() => undefined);
}

/** 글 공유: 기기는 공유 창, 공유 창이 없는 미리보기(브라우저)는 웹처럼 복사 → 복사했으면 true */
export async function shareText(text: string): Promise<boolean> {
  if (ON_DOM) {
    copyText(text);
    return true;
  }
  await Share.share({ message: text }).catch(() => undefined);
  return false;
}

/** 메모 글: 제목 다음 줄부터 본문 */
export const memoText = (m: { title: string; body: string }) => [m.title, m.body].filter(Boolean).join('\n');
