# AI API 사용량 대시보드

FastAPI + SQLite 기반 로컬 AI 사용량 대시보드입니다. OpenAI, Claude, Gemini 제공자를 표시하고, dry-run 샘플 데이터, 수동 입력 데이터, 실제 API 테스트 호출의 토큰 사용량을 함께 볼 수 있습니다.

이 프로젝트는 토큰 사용량만 저장하고 표시합니다. 결제, 구독, 청구 기능은 구현하지 않습니다.

## 주요 기능

- OpenAI / Claude / Gemini 제공자 표시
- dry-run 샘플 데이터 생성
- 수동 사용량 입력, 수정, 삭제
- OpenAI / Gemini 실제 API 테스트 호출의 토큰 사용량 저장
- Claude는 현재 실제 수집 비활성 상태로 표시
- `source=dry_run`, `source=manual`, `source=api` 구분 저장
- 제공자별 사용 비중, 모델별 요약, 날짜별 요약 표시
- 월간 토큰 한도 대비 사용률 표시

## 설치

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

## 실행

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

브라우저에서 `http://127.0.0.1:8001`을 엽니다.

## 다른 PC에서 이어서 작업하는 방법

새 PC에서는 저장소를 다시 받은 뒤 로컬 환경을 새로 만듭니다.

```powershell
git clone 저장소주소
cd 프로젝트폴더
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

그 다음 `.env`에 필요한 API 키를 직접 입력하고 서버를 실행합니다.

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

`.env`는 GitHub에 올리지 않습니다. 회사 PC에서는 `.env`를 새로 만들어야 하며, API 키는 캡처하거나 공유하지 마세요.

## .env 설정 예시

`.env.example`에는 실제 키를 넣지 않습니다. 실제 키는 로컬 `.env`에만 입력하세요.

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
OPENAI_MODEL=gpt-4o-mini
CLAUDE_MODEL=claude-3-5-haiku-latest
GEMINI_MODEL=gemini-2.5-flash
```

## OpenAI 연결

`OPENAI_API_KEY`가 설정되어 있으면 대시보드의 `실제 API 테스트 수집` 영역에서 OpenAI 테스트 호출을 실행할 수 있습니다. 짧은 테스트 프롬프트를 보내고 응답의 토큰 사용량을 `provider=openai`, `source=api`로 저장합니다.

`OPENAI_API_KEY`와 `OPENAI_ADMIN_KEY`는 용도가 다릅니다.

- `OPENAI_API_KEY`: 일반 모델 호출에 사용합니다. 이 대시보드의 OpenAI API 테스트 수집은 이 값을 사용합니다.
- `OPENAI_ADMIN_KEY`: 조직 단위 사용량 조회 같은 관리 API에 사용할 수 있는 키입니다. 현재 일반 테스트 호출에는 사용하지 않습니다.

`OPENAI_ADMIN_KEY`가 비어 있어도 OpenAI API 테스트 수집에는 영향이 없습니다.

### OpenAI 429 insufficient_quota

ChatGPT Plus/Pro 구독과 OpenAI API 사용은 별도로 관리됩니다. `OPENAI_API_KEY`가 있어도 API 크레딧, 결제수단, 사용 한도가 준비되어 있지 않으면 OpenAI API가 `429 insufficient_quota`를 반환할 수 있습니다.

이 경우 대시보드는 OpenAI 상태를 `쿼터 부족`으로 표시하고, `usage_records`에는 실패 데이터를 저장하지 않습니다. 토큰 사용량이 없는 호출 실패이므로 `source=api` 행을 만들지 않고, `collector_runs`에 한국어 요약 메시지만 저장합니다.

OpenAI Platform의 Billing/Usage 설정에서 결제수단 또는 사용 한도를 확인하세요.

## Gemini 연결

`GEMINI_API_KEY`가 설정되어 있으면 Gemini 테스트 호출을 실행할 수 있습니다. 응답의 `usage_metadata`에서 입력 토큰, 출력 토큰, 총 토큰을 읽어 `provider=gemini`, `source=api`로 저장합니다. 일부 토큰 값이 비어 있으면 0 또는 계산 가능한 값으로 안전하게 처리합니다.

Gemini는 OpenAI와 별도의 `GEMINI_API_KEY`로 동작합니다.

## Claude 상태

현재 Claude 실제 API 수집은 비활성 상태입니다. `ANTHROPIC_API_KEY`가 비어 있어도 앱은 정상 실행되며, Claude API 테스트 수집을 누르면 실제 호출을 하지 않고 비활성 안내 메시지만 표시합니다.

Claude가 비활성 상태여도 제공자 목록과 필터에는 계속 표시됩니다. 다만 기본 dry-run 샘플 데이터에는 Claude 사용량을 포함하지 않습니다. Claude 사용량을 기록하려면 대시보드의 수동 입력 기능을 사용하세요.

기존 DB에 예전 Claude 샘플 데이터가 남아 있을 수 있어, dry-run 수집을 실행할 때 다음 데이터만 안전하게 정리합니다.

```text
provider = 'claude' AND source = 'dry_run'
```

수동 입력 데이터(`source=manual`)와 API 데이터(`source=api`)는 삭제하지 않습니다.

## 저장 방식

`usage_records`는 다음 기준으로 중복 저장을 방지합니다.

```text
provider + model + usage_date + source
```

총 토큰은 다음 기준을 유지합니다.

```text
total_tokens = input_tokens + output_tokens + cached_tokens
```

API 응답이 별도의 총 토큰 값을 제공하면 해당 값을 안전하게 저장하고, 값이 없으면 위 기준으로 계산합니다.

## 보안

- `.env`는 `.gitignore`에 포함되어 있습니다.
- 실제 API 키를 코드, README, HTML, JavaScript, 로그에 출력하지 않습니다.
- API 호출 실패 시 전체 traceback을 화면에 노출하지 않고 한국어 안내 메시지만 표시합니다.
- 실제 키를 Git에 올리지 마세요.
