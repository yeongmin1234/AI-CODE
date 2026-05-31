# AI API 사용량 대시보드

개인용 AI API 사용량 대시보드입니다. OpenAI, Claude, Gemini 사용량을 로컬에서 한눈에 보기 위한 FastAPI + SQLite 기반 프로젝트입니다.

현재 버전은 dry-run 기반 1차 안정화 버전입니다. 실제 OpenAI, Claude, Gemini API 연동은 아직 활성화하지 않고, 세 제공사의 샘플 데이터를 저장해 대시보드 흐름을 확인합니다. 이 대시보드는 비용이나 청구 금액이 아니라 토큰 사용량 중심으로 표시합니다.

## 주요 기능

- OpenAI / Claude / Gemini dry-run 샘플 데이터 생성
- 이번 달 총 토큰, 요청 수, 입력 토큰, 출력 토큰, 캐시 토큰 표시
- 제공사별 사용 비중 진행바
- 월간 사용량 한도 진행바
- 제공사·모델별 요약
- 날짜별 사용량 요약
- 전체 / OpenAI / Claude / Gemini 제공사 필터
- SQLite `usage_records` 저장
- `collector_runs` 수집 성공/실패 이력 저장
- 중복 저장 방지를 위한 upsert 처리
- API 키와 로컬 DB 파일을 Git에서 제외

## 기술 스택

- Windows 로컬 실행 기준
- Python
- FastAPI
- SQLite
- Jinja2 템플릿
- HTML/CSS

## 폴더 구조

```text
app/
  collectors/
    base.py
    openai_collector.py
    claude_collector.py
    gemini_collector.py
  services/
    calculation_service.py
    collector_run_service.py
    collector_service.py
    usage_service.py
  static/
    styles.css
  templates/
    dashboard.html
  config.py
  db.py
  main.py
  models.py
  schemas.py
.env.example
.gitignore
requirements.txt
README.md
```

## 설치 방법

PowerShell에서 프로젝트 폴더로 이동한 뒤 실행합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

## 실행 방법

기본 실행 명령어는 다음과 같습니다.

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

브라우저에서 `http://127.0.0.1:8001`을 열면 됩니다.

Windows에서 `[WinError 10013]` 또는 포트 충돌이 발생하면 8081 또는 5000 포트로 바꿔 실행해 보세요.

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8081
uvicorn app.main:app --reload --host 127.0.0.1 --port 5000
```

설정값을 읽어서 실행하려면 아래 명령도 사용할 수 있습니다.

```powershell
python -m app.main
```

## .env 설정

`.env.example`을 복사한 `.env`에서 로컬 설정을 관리합니다.

```env
APP_HOST=127.0.0.1
APP_PORT=8001
DEFAULT_DRY_RUN=true
DEFAULT_PROVIDER_FILTER=all
MONTHLY_TOKEN_LIMIT=1000000

OPENAI_API_KEY=
OPENAI_ADMIN_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
```

설정 설명:

- `APP_HOST`: 로컬 서버 host, 기본값 `127.0.0.1`
- `APP_PORT`: 로컬 서버 port, 기본값 `8001`
- `DEFAULT_DRY_RUN`: 기본 테스트 모드 여부, 기본값 `true`
- `DEFAULT_PROVIDER_FILTER`: 기본 제공사 필터, 기본값 `all`
- `MONTHLY_TOKEN_LIMIT`: 월간 토큰 사용량 한도, 기본값 `1000000`

`.env.example`에는 실제 API 키를 넣지 않습니다.

## 테스트 모드

테스트 모드가 켜진 상태에서 `사용량 수집` 버튼을 누르면 이번 달 1일부터 오늘까지의 샘플 데이터가 SQLite에 저장됩니다.

제공사를 `전체`로 선택하면 다음 샘플 데이터가 함께 생성됩니다.

- OpenAI / `gpt-4o-mini`
- Claude / `claude-3-5-sonnet`
- Gemini / `gemini-1.5-flash`

실제 API 호출은 하지 않습니다.

## 계산 방식

총 토큰:

```text
total_tokens = input_tokens + output_tokens + cached_tokens
```

제공사별 사용 비중:

```text
제공사별 사용 비중 = 해당 제공사의 total_tokens / 전체 total_tokens * 100
```

월간 사용량 한도:

```text
월간 사용률 = 이번 달 total_tokens / MONTHLY_TOKEN_LIMIT * 100
```

전체 토큰이 0이면 사용 비중은 0%로 처리합니다. 월간 토큰 한도가 0이면 월간 사용률도 0%로 처리합니다.

## 중복 저장 방지

`usage_records`는 다음 unique key를 사용합니다.

```text
provider + model + usage_date + source
```

같은 날짜, 제공사, 모델, source의 데이터가 이미 있으면 새 row를 계속 추가하지 않고 기존 row를 업데이트합니다. 따라서 `사용량 수집` 버튼을 여러 번 눌러도 대시보드 숫자가 비정상적으로 누적되지 않습니다.

수집 실행 이력은 `collector_runs` 테이블에 별도로 저장합니다.

## 보안

- `.env`는 `.gitignore`에 포함되어 있습니다.
- SQLite DB 파일은 `*.db`, `data/*.db` 규칙으로 Git에서 제외합니다.
- `.venv`, `venv`, `__pycache__`, `*.pyc`도 Git에서 제외합니다.
- API 키는 서버 설정에서만 읽고 HTML에 출력하지 않습니다.
- 오류 메시지에는 API 키나 민감정보를 포함하지 않도록 처리합니다.

## 실제 API 연동

이번 1차 안정화 단계에서는 실제 OpenAI / Claude / Gemini API 연동을 하지 않습니다.

추후 실제 OpenAI 사용량 수집을 활성화할 때는 `OPENAI_ADMIN_KEY`를 사용하고, Claude/Gemini는 각각 collector 파일에 실제 API 호출 로직을 추가하면 됩니다.

## 문제 해결 FAQ

### 서버가 실행되지 않습니다.

먼저 가상환경이 활성화되어 있는지 확인하세요.

```powershell
.\.venv\Scripts\Activate.ps1
```

### 8001 포트가 막혀 있습니다.

8081 또는 5000 포트로 바꿔 실행하세요.

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8081
```

### 데이터가 표시되지 않습니다.

대시보드에서 `테스트 모드`가 체크된 상태로 `사용량 수집`을 누르세요.

### 버튼을 여러 번 눌러도 괜찮나요?

괜찮습니다. 같은 날짜 + 제공사 + 모델 + source 기준으로 upsert되므로 같은 dry-run 데이터가 무한히 중복 저장되지 않습니다.

### 월간 사용량 한도를 바꾸고 싶습니다.

`.env`의 `MONTHLY_TOKEN_LIMIT` 값을 변경한 뒤 서버를 재시작하세요.
