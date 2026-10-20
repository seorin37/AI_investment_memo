# 개발 환경 설정 가이드

memo's(메모스) 개발 환경을 처음 만드는 팀원을 위한 문서다. 위에서부터 순서대로 따라 하면 된다.

- 대상: Windows + VS Code + WSL(Ubuntu 24.04). Mac은 맨 아래를 참고한다.
- 소요 시간: 처음 설치 기준 40분~1시간
- 구조: DB는 Docker 컨테이너로, 백엔드는 conda 환경(`ai_memo`)에서 로컬로 실행한다. 모든 작업은 WSL 안에서 한다.
- 막히면 에러 메시지 전체를 복사해 팀 채팅에 올린다. 혼자 오래 붙잡지 않는다.

## 1. Windows 준비 (한 번만)

### 1-0. 가상화 확인
작업 관리자(`Ctrl+Shift+Esc`) → 성능 → CPU에서 "가상화"가 "사용"인지 확인한다. "사용 안 함"이면 BIOS에서 가상화(Intel VT-x 또는 AMD SVM)를 켜야 WSL과 Docker가 동작한다.

### 1-1. WSL2 + Ubuntu 24.04 설치
PowerShell을 관리자 권한으로 열고 실행한다.

~~~powershell
wsl --install -d Ubuntu-24.04
~~~

재부팅 후 Ubuntu 창이 열리면 사용자 이름과 비밀번호를 만든다. 확인은 PowerShell에서 한다.

~~~powershell
wsl -l -v
~~~

Ubuntu-24.04의 VERSION이 2이면 된다.

### 1-2. VS Code
VS Code를 설치하고 확장 프로그램 "WSL"(Microsoft)을 설치한다. 권장 확장: Python, Docker.

### 1-3. Docker Desktop
Docker Desktop을 설치한다. 설치 후 설정을 확인한다.

- Settings → General → "Use the WSL 2 based engine" 체크
- Settings → Resources → WSL Integration → Ubuntu-24.04 켜기 → Apply & restart

Docker Desktop은 실행 중이어야 한다(작업표시줄 트레이에 고래 아이콘).

## 2. WSL(Ubuntu) 준비

이 장부터는 모두 Ubuntu 터미널에서 실행한다. 시작 메뉴에서 Ubuntu를 열거나 VS Code에서 연결한다.

### 2-1. 기본 패키지

~~~bash
sudo apt update && sudo apt install -y git curl build-essential
~~~

### 2-2. Git 설정
이름과 이메일은 GitHub 계정과 같게 쓴다.

~~~bash
git config --global user.name "이름"
git config --global user.email "GitHub 이메일"
git config --global core.autocrlf input
git config --global pull.rebase false
~~~

### 2-3. GitHub 인증 (SSH)

~~~bash
ssh-keygen -t ed25519 -C "GitHub 이메일"
cat ~/.ssh/id_ed25519.pub
~~~

출력된 한 줄을 복사해 GitHub → Settings → SSH and GPG keys → New SSH key에 붙여넣는다. 확인:

~~~bash
ssh -T git@github.com
~~~

"Hi 아이디!" 메시지가 나오면 성공이다. 레포 초대(이메일 또는 GitHub 알림)는 미리 수락해 둔다.

### 2-4. conda (Miniforge)
이미 conda가 있으면 이 단계는 건너뛴다.

~~~bash
curl -L -O "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"
bash Miniforge3-$(uname)-$(uname -m).sh
~~~

설치 중 마지막 질문(conda init)에는 yes로 답한다. 이후 터미널을 다시 열거나 아래를 실행한다.

~~~bash
source ~/.bashrc
conda --version
~~~

## 3. 프로젝트 받기

~~~bash
mkdir -p ~/projects && cd ~/projects
git clone git@github.com:seorin37/AI_investment_memo.git
cd AI_investment_memo
git checkout dev
code .
~~~

- 프로젝트는 반드시 WSL 홈(`~/projects`) 아래에 둔다. `/mnt/c/...` 아래에 두면 느리고 줄바꿈·권한 문제가 생긴다.
- VS Code 왼쪽 아래에 "WSL: Ubuntu-24.04"가 보이면 WSL에 연결된 것이다.

## 4. 환경변수(.env)

~~~bash
cp .env.example .env
~~~

`.env`를 열어 값을 채운다.

- DB 값(`POSTGRES_*`)은 내 컴퓨터에서만 쓰므로 기본값을 써도 된다. 비밀번호만 아무 값으로 바꾼다.
- 외부 API 키(DART, 네이버, 토스증권, LLM)는 각자 발급하거나 팀에서 따로 전달받은 값을 넣는다.
- `.env`는 절대 커밋하지 않는다. `git status`에 `.env`가 보이지 않으면 정상이다.
- 내 컴퓨터에 이미 PostgreSQL이 설치되어 있으면 5432번 포트가 겹친다. 이 경우 `POSTGRES_PORT=5433`으로 바꾼다(9장 참고).

## 5. DB 실행 (Docker)

~~~bash
docker compose up -d --wait
docker compose ps
~~~

처음에는 이미지를 받느라 1~2분 걸린다. `memos-db`의 상태가 healthy이면 된다. pgvector 확장을 확인한다.

~~~bash
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\dx"'
~~~

목록에 `vector`가 보이면 성공이다.

자주 쓰는 명령:

| 하려는 일 | 명령 |
|---|---|
| DB 중지 | `docker compose stop` |
| DB 다시 시작 | `docker compose start` |
| 로그 보기 | `docker compose logs -f db` |
| DB 완전 초기화 (데이터 삭제됨) | `docker compose down -v` |

## 6. Python 환경 (conda)

~~~bash
conda env create -f environment.yml
conda activate ai_memo
~~~

- 환경 이름은 `environment.yml`에 적힌 `ai_memo`다. 같은 이름의 환경이 이미 있으면 `conda env update -f environment.yml --prune`을 쓴다.
- VS Code에서 `Ctrl+Shift+P` → "Python: Select Interpreter" → `ai_memo`를 선택한다.
- 패키지를 추가할 때는 `environment.yml`의 pip 목록에 한 줄 추가하고 아래를 실행한 뒤 커밋한다(`chore: 패키지 추가`).

~~~bash
conda env update -f environment.yml --prune
~~~

### 6-1. DB 테이블 만들기 (Alembic)
DB 구조(테이블)와 기초 데이터(코스피 종목, 뉴스 매체, 요금제 한도)는 마이그레이션 파일(`alembic/versions/`)로 관리한다. 5장에서 DB를 띄운 뒤, 프로젝트 루트에서 실행한다.

~~~bash
alembic upgrade head
alembic current
~~~

`0002 (head)`가 나오면 성공이다. DB에 들어간 테이블은 다음으로 확인한다.

~~~bash
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\dt"'
~~~

`memos`, `tracking_items`, `stocks` 등이 보이면 된다(`alembic_version` 포함 40개).

- 예전에 `.env`를 만든 사람은 `.env.example`의 `DATABASE_URL=` 줄을 `.env`에도 붙여 넣는다. 값은 `${POSTGRES_*}` 변수를 쓰므로 따로 고칠 것이 없다.
- 테이블 구조는 DBeaver 등에서 직접 고치지 않는다. 바꿀 일이 있으면 `alembic revision -m "설명"`으로 새 파일을 만들어 PR로 올린다.
- 이미 올라간 마이그레이션 파일(0001, 0002 등)은 수정하지 않는다.
- 누군가 새 마이그레이션을 올렸으면 `git pull` 후 `alembic upgrade head`를 다시 실행한다.
- 개발은 각자 내 컴퓨터의 DB로 한다. 강의실 PC의 DB는 수집된 데이터가 쌓이는 곳이라 직접 접속하지 않는다.

## 7. 백엔드 실행과 DB 연결 확인

~~~bash
cd backend
uvicorn app.main:app --reload
~~~

- 반드시 `backend` 폴더에서 실행한다. 다른 폴더에서 실행하면 `No module named 'app'` 에러가 난다.
- 8000번 포트를 다른 프로그램이 쓰고 있으면 `--port 8001`을 붙여 실행한다.
- `.env`를 바꾼 뒤에는 서버를 `Ctrl+C`로 끄고 다시 실행한다.

Windows 브라우저에서 확인한다. 포트를 바꿨다면 주소의 숫자도 바꾼다.

| 주소 | 정상 결과 |
|---|---|
| `http://localhost:8000/health` | `{"status":"ok"}` |
| `http://localhost:8000/health/db` | `{"status":"ok","pgvector":true}` |
| `http://localhost:8000/docs` | API 문서(Swagger) 화면 |

`/health/db`가 위와 같이 나오면 conda 환경, Docker DB, `.env`가 모두 연결된 것이다. 루트 주소(`/`)는 화면이 없어서 `Not Found`가 나오는 게 정상이다.

## 8. 작업 시작

Git 협업 지침을 따른다. 시작할 때마다 최신 dev를 받고 기능 브랜치를 만든다.

~~~bash
git checkout dev
git pull origin dev
git checkout -b feature/브랜치-이름
~~~

## 9. 문제 해결

| 증상 | 원인과 해결 |
|---|---|
| `docker: command not found` | Docker Desktop이 실행 중인지, WSL Integration에서 Ubuntu-24.04가 켜져 있는지 확인한 뒤 터미널을 새로 연다. |
| `Cannot connect to the Docker daemon` | Docker Desktop을 켠다. |
| `port is already allocated` (5432) | 이미 쓰는 포트다. `.env`의 `POSTGRES_PORT`를 5433으로 바꾸고 `docker compose up -d --wait`를 다시 실행한다. 서버도 다시 시작한다. |
| `/health/db`에서 `password authentication failed`가 나오는데 비밀번호는 맞음 | 5432번 포트에서 내 DB가 아닌 다른 PostgreSQL(예: Windows에 설치된 것)이 응답하는 경우다. `POSTGRES_PORT=5433`으로 바꾸고 DB와 서버를 다시 시작한다. |
| uvicorn에서 `Address already in use` | 8000번 포트를 다른 프로그램이 쓰고 있다. `--port 8001`로 실행한다. |
| `ModuleNotFoundError: No module named 'app'` | `backend` 폴더에서 실행해야 한다. `cd backend` 후 다시 실행한다. |
| `.env`를 바꿨는데 반영이 안 됨 | `--reload`는 파이썬 파일 변경만 감지한다. 서버를 `Ctrl+C`로 끄고 다시 실행한다. |
| DB 컨테이너가 바로 종료됨 | `.env`가 없거나 `POSTGRES_PASSWORD`가 비어 있다. `cp .env.example .env` 후 값을 채운다. |
| `\dx`에 `vector`가 없음 | 예전에 만든 DB 볼륨이 남아 있는 경우다. `docker compose down -v` 후 `docker compose up -d --wait` (DB 데이터가 삭제된다). |
| 비밀번호를 바꿨는데 접속이 안 됨 | 비밀번호는 DB를 처음 만들 때만 적용된다. `docker compose down -v` 후 다시 실행한다. |
| `Permission denied (publickey)` | SSH 키가 GitHub에 등록됐는지(`ssh -T git@github.com`), 레포 초대를 수락했는지 확인한다. |
| `conda: command not found` | `source ~/.bashrc` 또는 터미널을 다시 연다. |
| 파일이 느리거나 변경 감지가 안 됨 | 프로젝트가 `/mnt/c` 아래에 있는지 확인하고 `~/projects`로 옮긴다. |
| `alembic: command not found` | `conda activate ai_memo`를 먼저 실행한다. |
| `DATABASE_URL이 없습니다` | `.env`에 `DATABASE_URL` 줄이 없다. `.env.example`의 해당 줄을 `.env`에 붙여 넣는다. |
| `alembic upgrade head`에서 `already exists` | 예전에 직접 만든 테이블이 있다. `docker compose down -v` 후 `docker compose up -d --wait`로 DB를 비우고 다시 실행한다(DB 데이터가 삭제된다). |

## 10. 완료 체크리스트

모두 되면 개발을 시작할 수 있다.

- [ ] `docker compose ps`에서 `memos-db`가 healthy
- [ ] `\dx` 결과에 `vector`가 보임
- [ ] `alembic upgrade head` 후 `alembic current`가 `0002 (head)`
- [ ] `conda activate ai_memo` 후 `uvicorn`이 실행됨
- [ ] `/health/db` 결과가 `{"status":"ok","pgvector":true}`
- [ ] `git status`에 `.env`가 보이지 않음

완료하면 `/health/db` 결과 화면을 캡처해 팀 채팅에 올린다.

## Mac / Linux 참고

1~2장 대신 Docker Desktop(Mac) 또는 Docker Engine, VS Code, Git, Miniforge를 설치한다. 3장부터는 터미널에서 같은 명령을 쓴다.
