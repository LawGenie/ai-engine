# LawGenie AI Engine

AI-powered legal and trade analysis engine for LawGenie platform.

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   SpringBoot    │    │   FastAPI       │    │   LangGraph     │
│   (메인 서버)    │    │   (AI 엔진)      │    │   (AI 오케스트레이션)│
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ • 비즈니스 로직  │    │ • AI 모델 실행   │    │ • Tool 관리      │
│ • DB 관리       │    │ • 웹 스크래핑    │    │ • 워크플로우     │
│ • 사용자 인증   │    │ • 데이터 처리    │    │ • 결과 통합      │
│ • API 게이트웨이│    │ • 결과 반환      │    │ • 에러 처리      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │   External APIs │
                    │ • FDA, FCC, CBP │
                    │ • 웹 스크래핑    │
                    └─────────────────┘
```

## Features

### HS Code Recommendation
- 상품명 기반 HS코드 추천
- AI 모델을 통한 정확도 향상
- 다중 후보 코드 제공

### Tariff Calculation
- HS코드 기반 관세율 계산
- 국가별 관세 정책 반영
- 실시간 관세 정보 업데이트

### Requirements Analysis
- HS코드 기반 미국 수입요건 분석
- FDA, USDA, EPA, FCC 등 규제기관 데이터 통합
- 실시간 API 호출 및 데이터 수집
- 구조화된 응답 형식 제공

### Precedents Analysis
- 판례 데이터 수집 및 분석
- AI 기반 패턴 인식
- 리스크 요인 식별

## API Endpoints

### HS Code
- `POST /hs-code/recommend` - HS코드 추천
- `GET /hs-code/health` - HS코드 서비스 상태 확인

### Tariff
- `POST /tariff/calculate` - 관세 계산
- `GET /tariff/health` - 관세 서비스 상태 확인

### Requirements
- `POST /requirements/analyze` - HS코드 기반 요건 분석
- `GET /requirements/health` - 요건 분석 서비스 상태 확인

### Precedents
- `POST /precedents/analyze` - 판례 분석
- `GET /precedents/health` - 판례 분석 서비스 상태 확인

### General
- `GET /` - 서비스 정보
- `GET /health` - 전체 서비스 상태 확인

## Installation

가상환경(Venv) 설치

```
# ai-engine 디렉토리로 이동
cd ai-engine

# 가상환경 생성 (Python 3.11+ 필요)
python -m venv venv

# 가상환경 활성화 (Windows)
. venv/Scripts/activate

# 가상환경 활성화 (macOS/Linux)
source venv/bin/activate
```


```bash
# 가상환경이 활성화된 상태에서
pip install -r requirements.txt

# AI 엔진 서버 시작
python main.py
```

## Usage

### 요건건 분석 API 호출 예시

```bash
curl -X POST "http://localhost:8000/requirements/analyze" \
     -H "Content-Type: application/json" \
     -d '{
       "hs_code": "8471.30.01",
       "product_name": "노트북 컴퓨터",
       "product_description": "개인용 노트북 컴퓨터",
       "target_country": "US"
     }'
```

### 응답 형식

```json
{
  "answer": "HS코드 8471.30.01에 대한 미국 수입요건 분석 결과입니다.",
  "reasoning": "분석 근거 설명...",
  "requirements": {
    "certifications": [
      {
        "name": "FCC 인증",
        "required": true,
        "description": "전자제품의 경우 FCC 인증 필요",
        "agency": "FCC",
        "url": "https://www.fcc.gov/device-authorization"
      }
    ],
    "documents": [],
    "labeling": []
  },
  "sources": [
    {
      "title": "FCC Device Authorization",
      "url": "https://www.fcc.gov/device-authorization",
      "type": "공식 데이터베이스",
      "relevance": "high"
    }
  ],
  "metadata": {
    "from_cache": false,
    "confidence": 0.85,
    "response_time_ms": 1200
  }
}
```

## Development

### 프로젝트 구조
```
ai-engine/
├── main.py                          # FastAPI 진입점
├── requirements.txt                 # 의존성 관리
├── .env                            # 환경 변수
│
├── app/
│   ├── __init__.py
│   │
│   ├── schemas/                     # API 스키마
│   │   ├── __init__.py
│   │   ├── common.py
│   │   ├── hs_code.py
│   │   ├── tariff.py
│   │   ├── requirements.py
│   │   └── precedents.py
│   │
│   ├── services/                    # AI 서비스
│   │   ├── __init__.py
│   │   ├── hs_code/                # HS코드 관련 서비스
│   │   │   ├── __init__.py
│   │   │   ├── recommendation.py
│   │   │   ├── validation.py
│   │   │   └── analysis.py
│   │   ├── tariff/                 # 관세 관련 서비스
│   │   │   ├── __init__.py
│   │   │   ├── calculation.py
│   │   │   ├── rate_lookup.py
│   │   │   └── policy_analysis.py
│   │   ├── requirements/           # 요구사항 관련 서비스
│   │   │   ├── __init__.py
│   │   │   ├── analyzer.py
│   │   │   ├── web_scraper.py
│   │   │   └── data_processor.py
│   │   ├── precedents/             # 판례 관련 서비스
│   │   │   ├── __init__.py
│   │   │   ├── collector.py
│   │   │   ├── analyzer.py
│   │   │   └── pattern_matcher.py
│   │   └── common/                 # 공통 서비스
│   │       ├── __init__.py
│   │       ├── config.py
│   │       ├── utils.py
│   │       └── exceptions.py
│   │
│   ├── routers/                     # API 엔드포인트
│   │   ├── __init__.py
│   │   ├── hs_code_router.py
│   │   ├── tariff_router.py
│   │   ├── requirements_router.py
│   │   └── precedents_router.py
│   │
│   └── tools/                       # LangGraph Tools
│       ├── __init__.py
│       ├── hs_code_tools.py
│       ├── tariff_tools.py
│       ├── requirements_tools.py
│       └── precedents_tools.py
│
└── langgraph/                       # LangGraph 워크플로우
    ├── __init__.py
    ├── workflow.py
    └── tools/
        └── __init__.py
```

### LangGraph Tool 역할

LangGraph Tool은 FastAPI 서비스를 LangGraph에서 사용할 수 있게 래핑하는 역할을 합니다:

1. **API 래핑**: FastAPI 서비스를 LangGraph에서 사용할 수 있게 래핑
2. **데이터 변환**: LangGraph 형식 ↔ FastAPI 형식 변환
3. **에러 처리**: Tool 실행 중 에러 처리 및 fallback
4. **로깅**: Tool 실행 로그 및 모니터링

### 팀원별 작업 영역

- **팀원 A (HS코드)**: `schemas/hs_code.py`, `services/hs_code/`, `routers/hs_code_router.py`, `tools/hs_code_tools.py`
- **팀원 B (관세)**: `schemas/tariff.py`, `services/tariff/`, `routers/tariff_router.py`, `tools/tariff_tools.py`
- **팀원 C (요구사항)**: `schemas/requirements.py`, `services/requirements/`, `routers/requirements_router.py`, `tools/requirements_tools.py`
- **팀원 D (판례)**: `schemas/precedents.py`, `services/precedents/`, `routers/precedents_router.py`, `tools/precedents_tools.py`

### 새로운 서비스 추가
1. `app/schemas/`에 해당 모듈 스키마 정의
2. `app/services/`에 해당 모듈 비즈니스 로직 구현
3. `app/routers/`에 해당 모듈 API 엔드포인트 정의
4. `app/tools/`에 해당 모듈 LangGraph Tool 구현
5. `main.py`에 라우터 등록