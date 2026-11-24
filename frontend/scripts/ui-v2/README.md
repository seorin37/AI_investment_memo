# UI v2 아이콘 생성기

원본UI(앱 HTML · 웹 tsx)의 SVG를 `src/ui/icons/*.data.ts`(react-native-svg 노드)로 바꿉니다.
결과 파일(`appIcons.data.ts` · `webIcons.data.ts` · `logo.data.ts` · `wordmark-web.png`)은 손으로 고치지 않습니다.

## 다시 돌리기

```bash
cd frontend
export UI_V2_ORIG="/mnt/c/Users/<사용자>/Desktop/memos_받은코드/원본UI"   # app/ · web/ 이 있는 폴더
node scripts/ui-v2/extract-app-svgs.mjs    # 1) 앱 svg → 임시 폴더 svgs.json · svgs.html
node scripts/ui-v2/extract-web-svgs.mjs    # 2) 웹 svg → websvgs.json · websvgs.html
node scripts/ui-v2/gen-icons.mjs           # 3) src/ui/icons/*.data.ts 생성
```

- 임시 폴더는 기본 `$TMPDIR/ui-v2-icons`, 바꾸려면 `UI_V2_WORK`.
- 이름은 추출 번호로 붙입니다(`gen-icons.mjs`의 `APP_NAMES` · `WEB_NAMES`). 원본이 바뀌어 번호가 밀리면
  `svgs.html` · `websvgs.html` 갤러리를 브라우저로 열어 번호를 확인하고 이름표를 고칩니다.
- 모양이 같은 svg는 하나로 묶으므로, 쓰는 곳의 원본 색·크기가 다르면 `size` · `color`를 넘깁니다.
- 끝나면 `npm run typecheck`로 확인합니다.
