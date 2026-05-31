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

이 시스템은 시장의 바닥을 맞히려 하지 않습니다. 대신 최근 평균가, 이동평균, 단기 조정, 가격 변동률 같은 지표를 바탕으로 오늘의 상태를 설명하고, 매수할지 기다릴지 판단을 도와줍니다.

## 현재 상태

현재 구현된 것은 `sample` 브로커 기반의 리포트/승인 시스템입니다.

| 영역 | 상태 |
| --- | --- |
| 일일 리포트 | 구현 |
| 샘플 일봉 데이터 | 구현 |
| 3개월 평균 계산 | 구현 |
| 20일/60일 이동평균 | 구현 |
| 시장 라벨 | 구현 |
| 매수 점수 | 구현 |
| 매수 제안 | 구현 |
| 승인/거절 기록 | 구현 |
| 텔레그램 버튼 UI | 구현 |
| SQLite 저장 | 구현 |
| 토스 Open API 연결 | 대기 |
| 실제 주문 전송 | 미구현 |

## 작동 방식

1. ETF 일봉 데이터를 가져옵니다.
2. 3개월 평균, 20일선, 60일선, 최근 5거래일 수익률을 계산합니다.
3. 현재 시장 상태를 라벨로 분류합니다.
4. 0~100점 사이의 매수 점수를 계산합니다.
5. 전술 자금 중 사용할 비율과 예상 수량을 제안합니다.
6. 제안은 `pending` 상태로 저장됩니다.
7. 사용자가 승인하거나 거절합니다.
8. 현재 버전은 승인 기록까지만 남기고 주문은 보내지 않습니다.

## 브로커 구조

증권사 연결부는 분리되어 있습니다.

```text
app/brokers/
  base.py          공통 인터페이스
  sample_client.py API 없이 샘플 데이터로 실행
  toss_client.py   토스 Open API 연결 예정
  factory.py       BROKER 설정에 따라 클라이언트 선택
```

지금은 API 없이도 개발과 테스트가 가능하도록 `BROKER=sample`을 사용합니다. 토스증권 Open API 문서와 키가 준비되면 `BROKER=toss` 구현을 채워 연결할 예정입니다.

## 빠른 실행

```powershell
cd C:\dev\etf
py -3.9 -m app.main init
py -3.9 -m app.main report
```

승인 대기 중인 제안을 확인합니다.

```powershell
py -3.9 -m app.main pending
```

제안을 승인하거나 거절합니다.

```powershell
py -3.9 -m app.main approve 1
py -3.9 -m app.main reject 1
```

일부 Windows 환경에서 `python` 명령이 Anaconda를 가리키며 SQLite DLL 오류가 날 수 있습니다. 이 경우 위 예시처럼 `py -3.9`를 사용합니다.

## 텔레그램 버튼 UI

텔레그램으로 운영하려면 BotFather에서 봇을 만들고 토큰을 `.env`에 넣습니다.

```env
TELEGRAM_BOT_TOKEN=<your_telegram_bot_token>
TELEGRAM_ALLOWED_CHAT_ID=
```

처음에는 `TELEGRAM_ALLOWED_CHAT_ID`를 비워두고 봇을 실행한 뒤, 텔레그램에서 `/start`를 보내면 봇이 현재 `chat_id`를 알려줍니다. 그 값을 `.env`에 넣으면 해당 채팅방에서만 봇을 사용할 수 있습니다.

```powershell
py -3.9 -m app.main telegram
```

텔레그램 UI에서 사용할 수 있는 버튼은 다음과 같습니다.

- 일일 리포트
- 승인 대기
- 승인
- 거절
- 시스템 상태

현재 텔레그램 승인은 주문을 보내지 않고 승인 기록만 저장합니다.

## 설정

`.env.example`을 참고해 `.env`를 만들 수 있습니다.

```env
BROKER=sample
TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_CHAT_ID=
TOSS_APPKEY=
TOSS_SECRETKEY=
TOSS_MOCK=true
ETF_SYMBOL=360750
ETF_NAME=TIGER 미국S&P500
BASE_BUDGET=1000000
TACTICAL_BUDGET=500000
CYCLE_DAY=21
HOLIDAY_POLICY=next_business_day
APPROVAL_MAX_PRICE_DRIFT_PCT=0.3
DAILY_MAX_ORDER_AMOUNT=300000
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
