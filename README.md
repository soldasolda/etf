# ETF DCA Assistant

Python으로 만드는 ETF 적립 매수 보조 시스템입니다.

이 프로젝트는 단기 자동매매 봇이 아니라, 장기 ETF 적립 투자를 더 일관되게 운영하기 위한 개인용 투자 루틴 도구입니다. 매일 ETF 상태를 리포트하고, 전술 자금의 분할 매수 여부를 제안하며, 사용자의 승인/거절 기록을 남깁니다.

현재는 토스증권 Open API 승인을 기다리는 단계이므로 실제 주문은 전송하지 않습니다.

## 방향성

핵심 철학은 단순합니다.

```text
어차피 장기적으로 넣을 돈이라면,
조금 더 나은 구간에서,
감정 개입을 줄이고,
규칙에 따라 나누어 넣자.
```

이 시스템은 시장의 바닥을 맞히려 하지 않습니다. 기본 적립금은 매월 정해진 날 반드시 집행하고, 나머지 전술 자금만 가격 매력과 추세를 보며 월 안에서 나누어 쓰는 Dynamic DCA 방식을 따릅니다.

## 현재 상태

현재 구현된 것은 FinanceDataReader 기반 시세 조회와 시뮬레이션 계좌 모드입니다. 시세 제공자와 계좌 제공자를 분리해, 토스 Open API가 준비되면 시세/계좌를 API 기반으로 교체할 수 있게 설계합니다.

| 영역 | 상태 |
| --- | --- |
| 일일 리포트 | 구현 |
| 샘플 일봉 데이터 | 구현 |
| FinanceDataReader 시세 조회 | 구현 |
| 가격/이동평균 차트 | 구현 |
| 3개월 평균 계산 | 구현 |
| 20일/60일 이동평균 | 구현 |
| 시장 라벨 | 구현 |
| 매수 점수 | 구현 |
| 매수 제안 | 구현 |
| 승인/거절 기록 | 구현 |
| 시뮬레이션 계좌 원장 | 구현 |
| 기본 DCA/전술 자금 분리 | 구현 |
| 월간 투자 설정 텔레그램 변경 | 구현 |
| 전액 즉시 매수 벤치마크 | 구현 |
| 텔레그램 버튼 UI | 구현 |
| SQLite 저장 | 구현 |
| 토스 Open API 연결 | 대기 |
| 실제 주문 전송 | 미구현 |

## 작동 방식

1. ETF 일봉 데이터를 가져옵니다.
2. 3개월 평균, 20일선, 60일선, 최근 5거래일 수익률을 계산합니다.
3. 현재 시장 상태를 라벨로 분류합니다.
4. ETF 건강도와 전술 매수 매력도를 따로 계산합니다.
5. 매월 정기 매수일이 지나면 기본 DCA 제안을 생성합니다.
6. 전술 자금 중 사용할 비율과 예상 수량을 제안합니다.
7. 월말에는 남은 전술 자금을 소진하는 방향으로 제안합니다.
8. 제안은 `pending` 상태로 저장됩니다.
9. 사용자가 승인하거나 거절합니다.
10. `ACCOUNT_PROVIDER=simulation`이면 SQLite 시뮬레이션 계좌에 가짜 매수 체결을 기록합니다.
11. 같은 달에 전액을 정기 매수일에 샀을 때와 Dynamic DCA 결과를 벤치마크로 비교합니다.

## Dynamic DCA 운영 원칙

이 프로젝트의 기준은 장기 투자입니다. 점수는 "살지 말지"가 아니라 전술 자금을 얼마나 적극적으로 쓸지 판단하는 보조 지표입니다.

- 기본 DCA는 매월 정기 매수일 이후 반드시 제안합니다.
- ETF 건강도와 전술 매수 매력도는 분리해서 봅니다.
- 장기 상승 추세가 건강하면 전술 자금 0%를 피합니다.
- 가격이 고점권이고 RSI가 높으면 전술 자금을 한 번에 많이 쓰지 않습니다.
- 월초와 중순에는 더 나은 가격을 기다립니다.
- 월말에는 남은 전술 자금을 소진하는 제안을 우선합니다.
- 기본 DCA 승인과 전술 매수 제안은 서로 다른 절차로 봅니다.
- 벤치마크는 "정기 매수일에 월 총액을 전액 매수했을 때"와 비교합니다.

점수의 의미는 다음처럼 나뉩니다.

| 점수 | 의미 |
| --- | --- |
| ETF 건강도 | 장기 추세, 120일선/200일선, 이동평균 정배열 |
| 전술 매수 매력도 | RSI, 고점 대비 눌림, 최근 위치, 가격 매력 |
| 최종 DCA 제안 | 건강도, 전술 매력도, 월말 소진 원칙을 합친 실제 제안 |

## 브로커 구조

시세 제공자와 계좌 모드는 분리되어 있습니다.

```text
app/brokers/
  base.py          공통 인터페이스
  sample_client.py API 없이 샘플 데이터로 실행
  fdr_client.py    FinanceDataReader 기반 시세 조회
  toss_client.py   토스 Open API 연결 예정
  factory.py       BROKER 설정에 따라 클라이언트 선택
```

API 없이 개발과 테스트만 할 때는 `MARKET_DATA_PROVIDER=sample`을 사용합니다. 실제 시세 기반 리포트는 `MARKET_DATA_PROVIDER=fdr`을 사용합니다. 토스증권 Open API 문서와 키가 준비되면 `MARKET_DATA_PROVIDER=toss`, `ACCOUNT_PROVIDER=api` 구현을 채워 연결할 예정입니다.

| 시세 제공자 | 계좌 모드 | 의미 |
| --- | --- | --- |
| `sample` | `simulation` | 샘플 가격 + 가짜 계좌 |
| `fdr` | `simulation` | FinanceDataReader 실제 시세 + 가짜 계좌 |
| `toss` | `api` | 토스 Open API 시세/주문/잔고 |

## 빠른 실행

```powershell
cd C:\dev\etf
py -3.9 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
py -3.9 -m app.main init
py -3.9 -m app.main report
```

FinanceDataReader를 쓰는 `MARKET_DATA_PROVIDER=fdr` 모드에서는 가상환경 Python으로 실행하는 편이 가장 깔끔합니다.

```powershell
.\.venv\Scripts\python.exe -m app.main report
.\.venv\Scripts\python.exe -m app.main telegram
```

차트 이미지는 `matplotlib`으로 생성됩니다. `requirements.txt` 설치 후 자동으로 활성화되며, 생성된 PNG는 `data/charts/` 아래에 저장됩니다.

텔레그램 봇은 실행 중일 때 자동 감시도 수행합니다. 기본값은 15분마다 시장을 재평가하고, 점수가 기준 이상이면 승인 가능한 매수 제안을 먼저 보냅니다.

```env
MONITOR_ENABLED=true
MONITOR_INTERVAL_SECONDS=900
MONITOR_MIN_SCORE=60
MONITOR_COOLDOWN_MINUTES=180
```

텔레그램 없이 CLI에서 감시 루프만 돌릴 수도 있습니다.

```powershell
.\.venv\Scripts\python.exe -m app.main monitor
```

승인 대기 중인 제안을 확인합니다.

```powershell
py -3.9 -m app.main pending
```

제안을 승인하거나 거절합니다.

```powershell
py -3.9 -m app.main approve 1
py -3.9 -m app.main reject 1
py -3.9 -m app.main portfolio
```

일부 Windows 환경에서 `python` 명령이 Anaconda를 가리키며 SQLite DLL 오류가 날 수 있습니다. 이 경우 위 예시처럼 `py -3.9`를 사용합니다.

## 텔레그램 버튼 UI

텔레그램으로 운영하려면 BotFather에서 봇을 만들고 토큰을 `.env`에 넣습니다.

```env
TELEGRAM_BOT_TOKEN=<your_telegram_bot_token>
TELEGRAM_ALLOWED_CHAT_ID=
TELEGRAM_AUTH_KEY=<your_telegram_auth_key>
```

처음에는 `TELEGRAM_ALLOWED_CHAT_ID`를 비워두고, `TELEGRAM_AUTH_KEY`만 설정해도 됩니다. 봇에게 `/start`를 보내면 인증키 입력을 요청하고, 올바른 인증키를 보낸 채팅방만 메뉴를 사용할 수 있습니다. 인증된 채팅방은 SQLite에 저장됩니다.

```powershell
py -3.9 -m app.main telegram
```

텔레그램 UI에서 사용할 수 있는 버튼은 다음과 같습니다.

- 일일 리포트
- 승인 대기
- 월간 설정
- 승인
- 거절
- 시스템 상태
- 시뮬 계좌

월간 설정에서는 월 총액, 기본 DCA/전술 자금 비율, 정기 매수일, 감시 주기를 버튼으로 바꿀 수 있습니다. 일일 리포트에는 종가, 20일선, 60일선, 3개월 평균, 현재 위치가 포함된 차트 이미지가 함께 전송됩니다. 현재 텔레그램 승인은 `ACCOUNT_PROVIDER=simulation`일 때 SQLite 시뮬레이션 계좌에 가짜 매수 체결을 기록합니다. 실전 주문은 보내지 않습니다.

## 설정

`.env.example`을 참고해 `.env`를 만들 수 있습니다.

```env
MARKET_DATA_PROVIDER=fdr
ACCOUNT_PROVIDER=simulation
TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_CHAT_ID=
TELEGRAM_AUTH_KEY=
TOSS_APPKEY=
TOSS_SECRETKEY=
TOSS_MOCK=true
ETF_SYMBOL=360750
ETF_NAME=TIGER 미국S&P500
BASE_BUDGET=1000000
TACTICAL_BUDGET=500000
SIMULATION_INITIAL_CASH=5000000
CYCLE_DAY=22
HOLIDAY_POLICY=next_business_day
APPROVAL_MAX_PRICE_DRIFT_PCT=0.3
DAILY_MAX_ORDER_AMOUNT=1500000
MONITOR_ENABLED=true
MONITOR_INTERVAL_SECONDS=900
MONITOR_MIN_SCORE=60
MONITOR_COOLDOWN_MINUTES=180
```

`.env`, SQLite 데이터베이스, 로그 파일은 Git에 포함하지 않습니다.

커밋 전에는 비밀값 점검을 실행할 수 있습니다.

```powershell
py -3.9 scripts/check_secrets.py
```

## 시장 라벨

리포트는 숫자만 보여주지 않고 현재 구간을 사람이 읽기 쉬운 라벨로 설명합니다.

- 상승 추세
- 상승 추세 중 단기 조정
- 횡보 구간
- 저가 매수 구간
- 공포 구간
- 과열 구간
- 관망 구간

## 안전 원칙

초기 버전부터 실제 주문보다 안전한 운영 흐름을 우선합니다.

- 기본값은 샘플 브로커
- 실전 주문 전송 없음
- 승인/거절 기록 저장
- 승인 전 가격 변동률 검증 구조
- `.env`와 데이터베이스 Git 제외
- 토스 API 문서 확인 전 주문 기능 보류

## 다음 개발 계획

1. 리포트 히스토리 조회 기능
2. 승인/거절 내역 요약
3. 토스 Open API 문서 반영
4. `TossBrokerClient` 시세 조회 연결
5. 승인된 제안의 주문 전송 연결
6. 주문번호와 체결 결과 저장

## 유의사항

이 프로젝트는 개인용 투자 보조 도구이며 투자 권유가 아닙니다. 실제 주문 기능을 연결할 경우, 주문 전 사용자 승인과 금액 제한을 유지하는 방향으로 개발합니다.
