# Security Notes

이 저장소에는 실제 API 키, 텔레그램 봇 토큰, 계좌 관련 값을 커밋하지 않습니다.

## 로컬 비밀값 관리

실제 값은 반드시 `.env`에만 저장합니다.

```env
TELEGRAM_BOT_TOKEN=<your_telegram_bot_token>
TELEGRAM_ALLOWED_CHAT_ID=<your_chat_id>
TELEGRAM_AUTH_KEY=<your_telegram_auth_key>
TOSS_APPKEY=<your_toss_app_key>
TOSS_SECRETKEY=<your_toss_secret_key>
```

`.env`, `.env.*`, SQLite 데이터베이스, 로그 파일은 `.gitignore`로 제외됩니다.
가상환경 `.venv`와 로컬 SSH 키 폴더도 Git에 포함하지 않습니다.

## 커밋 전 점검

아래 명령으로 저장소에 실수로 들어간 토큰 패턴이 있는지 확인합니다.

```powershell
py -3.9 scripts/check_secrets.py
```

검사가 실패하면 커밋하거나 push하지 말고 해당 값을 제거한 뒤, 이미 커밋된 경우에는 토큰을 즉시 폐기하고 새로 발급합니다.

## GitHub에 올라가면 안 되는 것

- `.env`
- 텔레그램 봇 토큰
- 토스증권 App Key / Secret
- GitHub Personal Access Token
- 계좌번호, 계좌 비밀번호, 인증 관련 값
- SQLite 데이터베이스
- 로그 파일

## 토큰이 노출됐을 때

1. 해당 토큰을 즉시 폐기합니다.
2. 새 토큰을 발급합니다.
3. Git 기록에 남았다면 저장소를 비공개로 전환하거나 기록 정리를 검토합니다.
4. 봇/계정 접근 내역을 확인합니다.
