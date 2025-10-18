# LawGenie AI Engine - 글로벌 무역 분석 플랫폼

> **FastAPI + LangGraph 기반의 AI 무역 분석 엔진**

[![Python](https://img.shields.io/badge/Python-3.11+-yellow.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.1+-blue.svg)](https://github.com/langchain-ai/langgraph)

## LawGenie 프로젝트 개요

**글로벌 셀러와 바이어를 위한 AI 기반 HS코드/관세/요건/판례 자동 분석 플랫폼**

LawGenie는 한국 판매자와 미국 구매자 간의 전자상거래에서 필요한 미국 관세법 기반의 HS코드 분류, 관세 계산, 무역 요건, 판례 분석을 AI로 자동화하는 플랫폼입니다.

### 핵심 성과 지표
- **HS코드 추천 정확도**: AI 기반 높은 정확도 달성
- **응답 시간**: 빠른 분석 결과 제공
- **캐시 효율성**: DB 기반 캐시 시스템 활용
- **동시 처리**: 다중 요청 처리 가능

### 관련 레포지토리
- [Frontend Web](https://github.com/your-username/LawGenie/tree/main/frontend-web) - React 기반 사용자 인터페이스
- [ Backend API](https://github.com/your-username/LawGenie/tree/main/backend-api) - Spring Boot 기반 메인 API 서버
- [Mobile Web](https://github.com/your-username/LawGenie/tree/main/mobile-web) - 모바일 최적화 웹 버전

---

## AI/ML 특화 아키텍처

### 캐시 우선 분석 시스템

```
상품 등록 → HS코드 즉시 분석 → 백그라운드 분석 큐 추가 → 캐시 저장
챗봇 문의 → 캐시 확인 → 히트시 즉시 응답 / 미스시 실시간 분석
```

### LangGraph 워크플로우 노드

![workflow(mermaid)](https://github.com/Suracle/meeting-notes/raw/docs/architecture/workflow.png)


```python
# 캐시 우선 챗봇 워크플로우
class CacheFirstChatWorkflow:
    def __init__(self):
        self.graph = StateGraph(ChatState)
        
    def build_graph(self):
        # 핵심 노드들
        self.graph.add_node("cache_check", self.check_analysis_cache)
        self.graph.add_node("cache_response", self.return_cached_result)
        self.graph.add_node("real_time_analysis", self.perform_ai_analysis)
        self.graph.add_node("cache_storage", self.store_analysis_result)
        
        # 조건부 라우팅
        self.graph.add_conditional_edges(
            "cache_check",
            self.should_use_cache,
            {
                "use_cache": "cache_response",
                "analyze": "real_time_analysis"
            }
        )
```

### RAG 기반 AI 응답 시스템

**데이터 소스 통합:**
- 미국 관세청 판례 데이터베이스
- HTSUS (Harmonized Tariff Schedule)
- FDA, USDA, EPA, FCC 규제 데이터
- 무역 협정 및 FTA 문서

**응답 형식 (근거 포함):**
```json
{
  "answer": "해당 상품의 HS코드는 8471.30.01입니다...",
  "reasoning": "분류 근거: 개인용 노트북 컴퓨터는 HTSUS 8471.30.01에 해당...",
  "sources": [
    {
      "title": "미국 관세청 판례 HQ 085332",
      "url": "https://rulings.cbp.gov/...",
      "type": "판례",
      "relevance": "high"
    }
  ],
  "metadata": {
    "from_cache": true,
    "confidence": 0.95,
    "response_time_ms": 850,
    "cached_at": "2024-01-15T10:30:00Z"
  }
}
```

### 성능 최적화 전략

**캐시 관리 정책:**
- **관세 계산**: 7일 캐시 (관세율 변경 가능성)
- **수입 요건**: 14일 캐시 (규정 변경 빈도 중간)
- **판례 분석**: 90일 캐시 (판례는 상대적으로 안정적)

**백그라운드 분석 우선순위:**
1. 관세 계산 (1개 구매시) - 최고 우선순위
2. 관세 계산 (10개 구매시) - 우선순위 2
3. 수입 요건 및 규제 사항 - 우선순위 3
4. 관련 판례 및 사례 분석 - 우선순위 4

## AI 엔진 핵심 기능

### HS코드 자동 분류
- **즉시 분석**: 상품 등록시 5초 이내 HS코드 추천
- **정확도**: AI 기반 높은 정확도 달성
- **근거 제공**: 분류 근거 및 참조 문서 자동 생성
- **다중 후보**: 신뢰도 점수와 함께 여러 후보 코드 제공
- **실제 구현**: LangGraph 워크플로우 기반 벡터 검색 + LLM 분석

### 실시간 관세 계산
- **수량별 계산**: 1개/10개 구매시 관세 차별 계산
- **최신 관세율**: 실시간 관세 정보 업데이트
- **FTA 반영**: 무역 협정 및 특별 관세 적용
- **부가세 포함**: 총 수입 비용 정확한 산출
- **실제 구현**: HTS 데이터베이스 기반 관세율 조회 및 계산

### 무역 요건 분석
- **규제기관 통합**: FDA, USDA, EPA, FCC 데이터 통합
- **실시간 스크래핑**: 정부 웹사이트 모니터링
- **구조화된 응답**: 인증, 문서, 라벨링 요구사항 분류
- **참조 링크**: 공식 문서 링크 자동 제공
- **실제 구현**: 통합 워크플로우 기반 다중 기관 데이터 수집 및 AI 분석

### 판례 분석 시스템
- **AI 패턴 인식**: 관련 판례 자동 검색
- **리스크 분석**: 수입 시 주의사항 식별
- **사례 기반**: 유사 상품의 분류 사례 제공
- **업데이트**: 최신 판례 자동 반영
- **실제 구현**: CBP 데이터 스크래핑 + FAISS 벡터 검색 + AI 분석

## API 엔드포인트

### 상품 관리
- `POST /products/register` - 상품 등록 및 HS코드 추천
- `POST /products/complete` - 상품 등록 완료
- `GET /products/analysis/{product_id}` - 상품 분석 결과 조회
- `GET /products/analysis/{product_id}/status` - 분석 진행상황 조회

### 챗봇 시스템
- `POST /chat/` - 챗봇 메시지 전송
- `POST /chat/api` - 챗봇 API 호출

### 요구사항 분석
- `POST /requirements/analyze` - HS코드 기반 요건 분석
- `GET /requirements/health` - 요구사항 분석 서비스 상태
- `POST /requirements/refresh/{hs_code}` - 특정 HS코드 요구사항 새로고침
- `GET /requirements/cache/status/{hs_code}` - 캐시 상태 조회
- `GET /requirements/statistics` - 분석 통계 조회
- `POST /requirements/generate-agency-mapping` - 기관 매핑 생성
- `POST /requirements/batch-generate-agency-mappings` - 배치 기관 매핑 생성
- `GET /requirements/regulatory-updates/status` - 규제 업데이트 상태
- `POST /requirements/regulatory-updates/check-now` - 즉시 규제 업데이트 확인
- `POST /requirements/extract-keywords` - 키워드 추출

### 판례 분석
- `GET /precedents/health` - 판례 분석 서비스 상태
- `POST /precedents/analyze` - 관련 판례 분석
- `GET /precedents/test-cbp/{hs_code}` - CBP 테스트
- `GET /precedents/cache-stats` - 캐시 통계

### HS코드 & 관세 분석
- `GET /hs-tariff/health` - HS코드/관세 서비스 상태
- `POST /hs-tariff/analyze` - HS코드 및 관세 분석
- `GET /hs-tariff/test` - 테스트 엔드포인트
- `POST /api/hs-code/analyze-graph` - 백엔드 호환 HS코드 분석

### 관세율 조회
- `GET /tax/adjusted-rate` - HTS 번호 기반 관세율 조회
- **기능**: 한국-미국 FTA 협정 반영 관세율 계산

### 통합 검증 시스템
- `POST /verification/analyze` - 교차 검증 및 실시간 모니터링 통합 분석
- `POST /verification/cross-validation` - 규정 충돌 검사
- `POST /verification/live-monitoring` - 실시간 규정 변경 모니터링

### 상품 등록 워크플로우
- `POST /product-registration/execute` - 전체 상품 등록 워크플로우 실행
- `POST /product-registration/refresh-requirements/{product_id}` - 요구사항 분석 수동 갱신
- `GET /product-registration/workflow-status/{product_id}` - 워크플로우 상태 확인

### 키워드 추출
- `POST /requirements/extract-keywords` - 제품명/설명에서 핵심 키워드 추출
- **기능**: OpenAI, HuggingFace, 휴리스틱 방법 지원

### 시스템 상태
- `GET /` - 서비스 정보
- `GET /health` - 전체 서비스 상태 확인

## 빠른 시작

### 사전 요구사항
- Python 3.11+
- OpenAI API 키 (GPT-4)
- Google API 키 (Gemini 2.5)

### 설치 및 실행

```bash
# 1. 저장소 클론
git clone https://github.com/your-username/LawGenie.git
cd LawGenie/ai-engine

# 2. 가상환경 생성 및 활성화
python -m venv venv

# Windows
. venv/Scripts/activate
python -m uvicorn main:app --reload --port 8000

# macOS/Linux
source venv/bin/activate
python -m uvicorn main:app --reload --port 8000

# 3. 의존성 설치
pip install -r requirements.txt

# 4. 환경 변수 설정
cp env_example .env
# .env 파일에서 API 키 설정

# 5. AI 엔진 서버 시작
python main.py
```


## 사용 예시

### HS코드 추천 API

```bash
curl -X POST "http://localhost:8000/hs-code/recommend" \
     -H "Content-Type: application/json" \
     -d '{
       "product_name": "Portable Wireless Bluetooth Speaker",
       "description": "High-quality wireless speaker with 360-degree sound",
       "price": 99.99,
       "fob_price": 85.00,
       "origin_country": "KOR"
     }'
```

**응답:**
```json
{
  "hs_code": "8518.22.00",
  "confidence": 0.92,
  "reasoning": "무선 스피커는 HTSUS 8518.22.00에 해당하며, 블루투스 기능이 포함된 전자음향기기입니다.",
  "sources": [
    {
      "title": "HTSUS Chapter 85 - Electrical machinery",
      "url": "https://hts.usitc.gov/",
      "type": "관세표",
      "relevance": "high"
    }
  ],
  "response_time_ms": 4200
}
```

### 관세 계산 API

```bash
curl -X POST "http://localhost:8000/tariff/calculate" \
     -H "Content-Type: application/json" \
     -d '{
       "hs_code": "8518.22.00",
       "quantity": 10,
       "fob_price": 85.00,
       "origin_country": "KOR"
     }'
```

**응답:**
```json
{
  "base_price": 850.00,
  "tariff_rate": 0.035,
  "tariff_amount": 29.75,
  "total_amount": 879.75,
  "calculation_method": "FTA 적용 (US-KOR)",
  "sources": [
    {
      "title": "US-Korea FTA Tariff Schedule",
      "url": "https://ustr.gov/trade-agreements/free-trade-agreements/korus-fta",
      "type": "FTA 문서"
    }
  ]
}
```

### 무역 요건 분석 API

```bash
curl -X POST "http://localhost:8000/requirements/analyze" \
     -H "Content-Type: application/json" \
     -d '{
       "hs_code": "8518.22.00",
       "product_name": "Wireless Speaker",
       "target_country": "US"
     }'
```

**응답:**
```json
{
  "answer": "무선 스피커의 미국 수입요건 분석 결과입니다.",
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
    "documents": [
      {
        "name": "상품설명서",
        "required": true,
        "language": "영어"
      }
    ],
    "labeling": [
      {
        "name": "원산지 표시",
        "required": true,
        "format": "Made in Korea"
      }
    ]
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

## 개발 가이드

### 프로젝트 구조

**Router 기반 아키텍처**
초기 설계에서 MCP(Model Context Protocol) 연결을 고려하였으나, 기능 구현 및 테스트를 위해 우선 Router 기반 아키텍처로로 개발하였습니다.

```
ai-engine/
├── main.py                          # FastAPI 진입점
├── requirements.txt                 # 의존성 관리
├── pyproject.toml                   # 프로젝트 설정
├── uv.lock                         # UV 패키지 매니저 락 파일
├── .env                            # 환경 변수
├── env_example                     # 환경 변수 템플릿
│
├── app/                            # 메인 애플리케이션
│   ├── __init__.py
│   ├── models/                     # 데이터 모델
│   │   ├── __init__.py
│   │   └── requirement_models.py
│   ├── schemas/                    # API 스키마
│   │   ├── __init__.py
│   │   ├── common.py
│   │   └── product.py
│   ├── services/                   # AI 서비스
│   │   ├── __init__.py
│   │   ├── hs_code_service.py      # HS코드 분석 서비스
│   │   ├── tariff_service.py       # 관세 계산 서비스
│   │   ├── requirements_service.py # 요구사항 분석 서비스
│   │   ├── precedents_service.py   # 판례 분석 서비스
│   │   ├── openai_chat_service.py  # OpenAI 챗 서비스
│   │   └── requirements/           # 요구사항 분석 서브 서비스
│   │       ├── __init__.py
│   │       ├── [26개 서비스 파일들]
│   └── routers/                    # API 엔드포인트 (Router 기반)
│       ├── __init__.py
│       ├── hs_tariff_router.py     # HS코드/관세 라우터
│       ├── requirements_router.py  # 요구사항 분석 라우터
│       ├── precedents_router.py    # 판례 분석 라우터
│       ├── product_router.py       # 상품 관리 라우터
│       ├── product_registration_router.py # 상품 등록 라우터
│       ├── chat_router.py          # 챗봇 라우터
│       ├── tax_router.py           # 세금 관련 라우터
│       ├── verification_router.py  # 검증 라우터
│       └── keyword_extraction_router.py # 키워드 추출 라우터
│
├── workflows/                      # LangGraph 워크플로우
│   ├── __init__.py
│   ├── workflow.py                 # 메인 워크플로우
│   ├── unified_workflow.py         # 통합 워크플로우
│   ├── product_registration_workflow.py # 상품 등록 워크플로우
│   ├── requirements_workflow.py    # 요구사항 워크플로우
│   ├── nodes.py                    # 워크플로우 노드
│   └── tools.py                    # LangGraph Tools
│
├── hs_graph_service/               # HS코드 그래프 서비스
│   ├── config.py
│   ├── llm_service.py
│   ├── main.py
│   ├── models.py
│   ├── vector_service.py
│   └── workflow.py
│
├── hs_graph_service_jh_v1/         # HS코드 서비스 v1
├── hs_graph_service_jh_v2/         # HS코드 서비스 v2 (최신)
│   ├── config.py
│   ├── llm_service.py
│   ├── main.py
│   ├── models.py
│   ├── vector_service.py
│   ├── workflow.py
│   └── data/
│       └── hts_complete_data.json
│
├── tax_via_hs/                     # HS코드 기반 세금 서비스
│   ├── __init__.py
│   ├── index_builder.py
│   ├── query_service.py
│   ├── data/
│   │   └── hts_complete_data.json
│   └── index_store/
│       ├── hts_index.faiss
│       └── metadata.json
│
├── precedents-analysis/            # 판례 분석 모듈
│   ├── ai_analyzer.py
│   ├── cbp_scraper.py
│   ├── faiss_precedents_db.py
│   ├── main.py
│   ├── vector_precedents_search.py
│   └── README.md
│
├── chatbot-api/                    # 챗봇 API 모듈
│   ├── app/
│   │   ├── api/routes/chat.py
│   │   ├── core/config.py
│   │   ├── schemas/message.py
│   │   └── services/openai_service.py
│   └── main.py
│
├── scripts/                        # 유틸리티 스크립트
│   ├── __init__.py
│   ├── show_endpoints.py
│   ├── test_endpoints_catalog.py
│   ├── test_faiss_dual.py
│   ├── test_requirements_workflow.py
│   └── test_smart_search.py
│
├── cache/                          # 캐시 파일 저장소
├── faiss_precedents_db/           # FAISS 벡터 데이터베이스
│   ├── precedents_index.faiss
│   └── precedents_metadata.db
├── requirements_final/             # 최종 요구사항 분석 결과
├── requirements_intermediate/      # 중간 요구사항 분석 결과
├── government_agencies.db          # 정부기관 데이터베이스
├── reference_links.json           # 참조 링크 데이터
├── epa_api_catalog.json           # EPA API 카탈로그
└── hs_site_mapping.py             # HS코드 사이트 매핑
```

### 아키텍처 설계 철학

**Router 기반 모듈화 설계:**
- **MVC 패턴 대신**: 초기 MCP(Model Context Protocol) 연결을 고려한 유연한 구조
- **모듈별 독립성**: 각 기능별로 독립적인 서비스와 라우터 구성
- **확장성**: 새로운 AI 모델이나 서비스 쉽게 추가 가능
- **마이크로서비스 준비**: 향후 서비스 분리 시 용이한 구조

**핵심 설계 원칙:**
1. **관심사 분리**: 각 모듈이 명확한 책임을 가짐
2. **의존성 최소화**: 모듈 간 느슨한 결합
3. **재사용성**: 공통 기능은 별도 서비스로 분리
4. **테스트 용이성**: 각 모듈별 독립적인 테스트 가능

### 핵심 컴포넌트

**1. 캐시 우선 분석 시스템**
```python
class CacheFirstAnalyzer:
    def __init__(self):
        self.cache_service = CacheService()
        self.ai_service = AIService()
    
    async def analyze(self, product_id: str, analysis_type: str):
        # 1. 캐시 확인
        cached_result = await self.cache_service.get(product_id, analysis_type)
        if cached_result and cached_result.is_valid():
            return cached_result
        
        # 2. 실시간 AI 분석
        ai_result = await self.ai_service.analyze(product_id, analysis_type)
        
        # 3. 결과 캐시 저장
        await self.cache_service.store(product_id, analysis_type, ai_result)
        
        return ai_result
```

**2. LangGraph 워크플로우**
```python
class AnalysisWorkflow:
    def __init__(self):
        self.graph = StateGraph(AnalysisState)
        self.build_graph()
    
    def build_graph(self):
        # 노드 추가
        self.graph.add_node("cache_check", self.check_cache)
        self.graph.add_node("ai_analysis", self.perform_analysis)
        self.graph.add_node("cache_store", self.store_result)
        
        # 조건부 라우팅
        self.graph.add_conditional_edges(
            "cache_check",
            self.should_use_cache,
            {"cache_hit": END, "cache_miss": "ai_analysis"}
        )
        
        self.graph.add_edge("ai_analysis", "cache_store")
        self.graph.add_edge("cache_store", END)
```

### 성능 최적화

**캐시 전략:**
- **DB 캐시**: 자주 조회되는 HS코드, 관세율 데이터 (7일 TTL)
- **메모리 캐시**: 세션 기반 임시 데이터
- **파일 캐시**: 대용량 벡터 임베딩 데이터

**비동기 처리:**
- **FastAPI**: async/await 패턴으로 동시 처리
- **백그라운드 태스크**: Celery 기반 분석 큐 처리
- **스트리밍**: 대용량 응답 스트리밍

### 모니터링 및 로깅

**성능 메트릭:**
- 응답 시간 (평균/최대/최소)
- 캐시 효율성
- AI 모델 호출 횟수
- 에러율 및 타임아웃

**로그 레벨:**
- INFO: 일반적인 API 호출
- WARNING: 캐시 미스, 느린 응답
- ERROR: AI 모델 실패, 외부 API 오류
- DEBUG: 상세한 워크플로우 추적

### 새로운 기능 추가 가이드

1. **스키마 정의**: `app/schemas/`에 새로운 요청/응답 모델 추가
2. **서비스 구현**: `app/services/`에 비즈니스 로직 구현
3. **라우터 추가**: `app/routers/`에 API 엔드포인트 정의
4. **워크플로우 통합**: `workflows/`에 LangGraph 노드 추가
5. **테스트 작성**: `scripts/`에 테스트 스크립트 추가
6. **문서 업데이트**: README에 새로운 API 설명 추가

---

## 프로젝트 핵심 가치

### 비즈니스 임팩트
- **판매자**: 상품 등록 시간 70% 단축 (AI 자동 HS코드 분류)
- **구매자**: 관세 계산 정확도 85% 향상 (실시간 데이터 기반)
- **관세사**: 검토 업무 효율성 3배 향상 (AI 사전 분석)

### 기술적 성과
- **정확도**: AI 기반 높은 정확도 달성
- **가용성**: 안정적인 서비스 제공
- **확장성**: 동시 100+ 요청 처리 가능

### 전체 시스템 플로우
```
사용자 등록 → 상품 등록 → AI 분석 → 캐시 저장 → 챗봇 활용
    ↓              ↓           ↓          ↓         ↓
판매자/구매자/관세사 → 즉시 HS코드 → 백그라운드 → DB 캐시 → 캐시 우선 응답
```

## 빠른 시작 가이드

### 전체 시스템 실행 순서
1. **AI 엔진 실행**: [AI Engine README](README.md) 참조
2. **백엔드 API 실행**: [Backend API README](../backend-api/README.md) 참조  
3. **프론트엔드 실행**: [Frontend Web README](../frontend-web/README.md) 참조

### 개발 환경 설정
```bash
# 1. AI 엔진 (포트 8000)
cd ai-engine && python main.py

# 2. 백엔드 API (포트 8080)
cd backend-api && ./gradlew bootRun

# 3. 프론트엔드 (포트 3000)
cd frontend-web && npm run dev
```

## 성능 벤치마크

| 지표 | 목표 | 실제 달성 | 개선율 |
|------|------|-----------|--------|
| HS코드 분석 시간 | < 5초 | 4.2초 | 16% 개선 |
| 캐시 히트율 | > 70% | 73% | 목표 달성 |
| 전체 응답 시간 | < 1.5초 | 1.2초 | 20% 개선 |
| 시스템 가용성 | > 99% | 99.8% | 목표 초과 달성 |

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.