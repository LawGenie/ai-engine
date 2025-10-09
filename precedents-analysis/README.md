# Precedents Analysis AI Engine

CBP(미국 세관국경보호청) 판례 데이터를 **Tavily 검색**으로 수집하고 AI로 분석하는 시스템입니다.

## 🚀 주요 기능

1. **Tavily 기반 CBP 판례 검색** 
   - Tavily API를 사용하여 실시간 CBP 판례 검색
   - CBP 공식 사이트(cbp.gov, rulings.cbp.gov) 데이터만 수집

2. **FAISS 벡터 DB**
   - tax_via_hs와 완전히 별개의 독립적인 FAISS 시스템
   - 256차원 해시 기반 임베딩
   - SQLite 메타데이터 관리

3. **메모리 캐싱**
   - 7일 TTL 캐싱으로 중복 검색 방지
   - 동일 HS 코드 재검색 시 캐시 사용

4. **AI 분석**
   - OpenAI GPT-4o-mini를 사용한 판례 분석
   - 성공/실패 사례, 리스크 요인, 실행 가능한 인사이트 제공

## 📋 필수 환경 변수

`.env` 파일에 다음을 설정하세요:

```env
OPENAI_API_KEY=your_openai_api_key
TAVILY_API_KEY=your_tavily_api_key
```

## 🔧 설치

```bash
cd ai-engine/precedents-analysis
pip install -r requirements.txt
```

## 🏃 실행

```bash
python main.py
```

서버가 `http://localhost:8000`에서 실행됩니다.

## 📡 API 엔드포인트

### 1. 헬스체크
```bash
GET /health
```

### 2. 판례 분석
```bash
POST /analyze-precedents
{
  "product_id": "prod-001",
  "product_name": "Medical Stethoscope",
  "description": "Professional acoustic stethoscope",
  "hs_code": "9018.90.60.00",
  "origin_country": "KR",
  "price": 150.00,
  "fob_price": 120.00
}
```

### 3. CBP 데이터 테스트
```bash
GET /test-cbp/{hs_code}
```

### 4. 캐시/벡터 DB 통계
```bash
GET /cache-stats
```

## 🗂️ 시스템 구조

```
precedents-analysis/
├── main.py                      # FastAPI 서버
├── cbp_scraper.py              # Tavily 기반 CBP 데이터 수집
├── ai_analyzer.py              # OpenAI 기반 AI 분석
├── faiss_precedents_db.py      # FAISS 벡터 DB
├── vector_precedents_search.py # 벡터 검색 시스템
└── faiss_precedents_db/        # FAISS 데이터 저장소
    ├── precedents_index.faiss
    └── precedents_metadata.db
```

## 🔍 동작 흐름

1. **HS 코드 요청** → 캐시 확인
2. **캐시 없음** → Tavily로 CBP 데이터 검색
3. **데이터 수집** → 벡터 DB 저장 + 메모리 캐싱
4. **유사 판례 검색** → FAISS 벡터 검색
5. **CBP 데이터 + 유사 판례** → AI 분석
6. **결과 반환** → 성공/실패 사례, 인사이트, 권장 사항

## ⚙️ 주요 특징

- ✅ **실시간 데이터**: Tavily API로 최신 CBP 판례 검색
- ✅ **캐싱 최적화**: 7일 TTL로 중복 검색 방지
- ✅ **벡터 검색**: FAISS로 유사 판례 자동 발견
- ✅ **독립 시스템**: tax_via_hs와 완전히 분리
- ✅ **No 샘플 데이터**: 실제 검색 결과만 사용

## 🛠️ 기술 스택

- **FastAPI**: REST API 서버
- **Tavily API**: 실시간 웹 검색
- **FAISS**: 고속 벡터 검색
- **SQLite**: 메타데이터 저장
- **OpenAI GPT-4o-mini**: AI 분석