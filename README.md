# ETF 적립 매수 시스템

Python 기반 ETF 적립 매수 보조 도구입니다.

초기 버전은 실전 주문을 하지 않습니다. 일일 리포트를 만들고, 사용자가 승인하면 승인 기록을 남깁니다. 증권사 API 연결부는 브로커 방식으로 분리되어 있어 토스 Open API 문서가 나오면 `TossBrokerClient`를 채우는 식으로 연결할 수 있습니다.

## 빠른 실행

```powershell
python -m app.main init
python -m app.main report
python -m app.main pending
python -m app.main approve 1
```

API 키 없이 실행하면 샘플 가격 데이터로 리포트를 만듭니다.

현재 PC에서 `python`이 Anaconda를 가리키며 SQLite DLL 오류가 나면 아래처럼 설치된 Python 3.9 런타임으로 실행하세요.

```powershell
py -3.9 -m app.main init
py -3.9 -m app.main report
py -3.9 -m app.main approve 1
```

## 설정

`.env.example`을 참고해 `.env`를 만들 수 있습니다.

```env
BROKER=sample
TOSS_APPKEY=...
TOSS_SECRETKEY=...
TOSS_MOCK=true
ETF_SYMBOL=360750
ETF_NAME=TIGER 미국S&P500
BASE_BUDGET=1000000
TACTICAL_BUDGET=500000
```

`BROKER=sample`은 API 없이 샘플 가격으로 리포트를 만드는 대기 모드입니다. 나중에 토스 문서가 준비되면 `BROKER=toss` 구현을 채우면 됩니다.

## 현재 구현 범위

- SQLite 저장소 초기화
- 샘플 일봉 데이터 생성
- 3개월 평균, 20일선, 60일선 계산
- 시장 라벨 및 점수 계산
- 일일 리포트 생성
- 매수 제안 생성
- 승인/거절 기록
- 승인 전 가격 변동률 검증 구조

## 다음 단계

1. 토스 Open API 승인 및 공식 문서 확인
2. `TossBrokerClient`에 시세 조회 연결
3. 승인된 제안의 주문 전송 API 연결
4. 주문번호와 체결 결과 저장
