import { Slot } from 'expo-router';

/** 웹: 그대로 바깥 (main) Stack 이 처리 (Slot). 앱은 _layout.native.tsx 의 Stack(밀려 들어오기) */
export default function UpdatesLayout() {
  return <Slot />;
}
