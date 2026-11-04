# Windows 네이티브 실행 (Git Bash)

이 문서는 WSL이 아니라 Windows용 Python과 CUDA를 사용해 파이프라인을 실행하는 절차다.
Git Bash는 셸만 Bash이며, 아래 구성에서 Python 프로세스는 Windows 네이티브로 실행된다.

## 1. 준비

Windows에 Git for Windows, Miniforge, VS Code, Docker Desktop, NVIDIA 드라이버를 설치한다.
프로젝트는 `C:\projects\AI_investment_memo`처럼 Windows 파일시스템에 둔다.

기존 WSL 작업 폴더를 복사하는 예시(PowerShell):

```powershell
New-Item -ItemType Directory -Force C:\projects
robocopy "\\wsl.localhost\Ubuntu-24.04\home\sd1-03\projects\AI_investment_memo" "C:\projects\AI_investment_memo" /E /XD .venv __pycache__ .pytest_cache
```

배포판 이름은 `wsl -l -q`로 확인하고 실제 이름에 맞춘다. Windows 실행이 검증될 때까지
WSL 원본을 삭제하지 않는다.

## 2. Conda와 CUDA

Git Bash에서 Miniforge의 Conda 초기화 스크립트를 불러온다. 설치 경로가 다르면 경로를 맞춘다.

```bash
source ~/miniforge3/etc/profile.d/conda.sh
cd /c/projects/AI_investment_memo
conda env create -f environment.yml
conda activate ai_memo
```

`FlagEmbedding`의 전이 의존성인 `datasets`와 `pyarrow`는 `environment.yml`에 고정되어 있다.
최신 `pyarrow`가 NumPy 2 전용 wheel을 설치하면 이 프로젝트의 고정 NumPy 1.26과 호환되지
않으므로 임의로 업그레이드하지 않는다.

PyTorch CUDA 빌드는 `environment.yml`에서 고정하지 않는다. PyTorch 공식 설치 선택기에서
Windows / Pip / Python과 NVIDIA 드라이버에 맞는 CUDA 빌드 명령을 받아 설치한다.

Windows Python과 GPU가 선택됐는지 확인한다.

```bash
python -c "import platform,sys; print(platform.system()); print(sys.executable)"
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NO GPU')"
```

첫 명령은 `Windows`와 `C:\...\python.exe`, 두 번째 명령은 `True`와 NVIDIA GPU 이름을
출력해야 한다. `Linux`가 출력되면 WSL Python이므로 본 실행을 시작하지 않는다.

## 3. DB와 환경변수

Docker Desktop을 시작하고 기존 DB 컨테이너를 확인한다.

```bash
docker ps
docker compose up -d --wait
```

기존 `memos-db`가 이미 실행 중이면 두 번째 명령은 생략할 수 있다. 기존 데이터가 필요할 때
`docker compose down -v`를 실행하면 안 된다. 저장소 루트의 `.env`에서 `DATABASE_URL`의
호스트는 `localhost`로 둔다.

```bash
alembic current
python -m pytest -q backend/tests/test_file_lock.py backend/tests/test_run_all.py backend/tests/test_run_financials_all.py backend/tests/test_kis_market.py
```

## 4. VS Code

Git Bash에서 `code .`로 Windows 폴더를 연다. VS Code 왼쪽 아래에 `WSL: Ubuntu`가 없어야
하며, Python 인터프리터는 Windows Miniforge의 `ai_memo` 환경을 선택한다. 통합 터미널의
기본 프로필은 Git Bash로 설정한다.

## 5. 파이프라인 실행

저장소 루트에서 상태와 소규모 실행을 먼저 확인한다.

```bash
PYTHONPATH=backend python -m pipelines.disclosures.run_all --status
PYTHONPATH=backend python -m pipelines.disclosures.run_all --max-companies 1 --batch-size 1
```

정상 동작 후 작업 관리자의 메모리를 보며 묶음을 늘린다.

```bash
PYTHONPATH=backend python -m pipelines.disclosures.run_all --batch-size 5
```

Windows 네이티브 실행도 운영체제와 VS Code가 사용할 RAM을 남겨야 한다. 처음부터
`--batch-size 20`으로 실행하지 말고 5, 10 순서로 확인한다.

재무 파이프라인도 같은 방식으로 실행한다.

```bash
PYTHONPATH=backend python -m pipelines.disclosures.run_financials_all --status
PYTHONPATH=backend python -m pipelines.disclosures.run_financials_all
```
