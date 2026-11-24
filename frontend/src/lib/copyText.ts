import { Clipboard, Share } from 'react-native';
import { ON_DOM } from '@/ui/shared/onDom';

/** 글 복사 (앱). 따로 설치한 클립보드 패키지가 없어 RN 기본 Clipboard 를 씀 */
export function copyText(text: string): void {
  Clipboard.setString(text);
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
