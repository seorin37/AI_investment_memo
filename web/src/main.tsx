import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

/* Pretendard: 같은 곳에 올린 서체 파일을 불러와 등록 (CDN 스타일시트를 쓸 수 없는 곳에서도 동작) */
fetch('PretendardVariable.woff2').then((r) => (r.ok ? r.arrayBuffer() : null)).then(async (b) => {
  if (!b) return;
  const f = new FontFace('Pretendard Variable', b, { weight: '45 920' });
  await f.load(); document.fonts.add(f);
}).catch(() => {});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
