# Precedents Analysis AI Engine

미국 수입 규제 관련 판례 분석을 위한 AI 엔진입니다.

## 기능

- CBP (Customs and Border Protection) 데이터 수집
- GPT-4o-mini를 활용한 판례 분석
- 상품별 성공/실패 사례 분석
- 실행 가능한 인사이트 및 권장 조치 제공

## 설치 및 실행

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. 환경변수 설정
`.env` 파일을 생성하고 다음 내용을 추가하세요:

```bash
# .env 파일 생성
touch .env

# .env 파일 편집
nano .env
```

`.env` 파일 내용:
```env
# OpenAI API Key (필수)
OPENAI_API_KEY=your-actual-openai-api-key-here

# AI Engine 설정
AI_ENGINE_HOST=0.0.0.0
AI_ENGINE_PORT=8000

# 로깅 레벨
LOG_LEVEL=INFO
```

**중요**: `your-actual-openai-api-key-here`를 실제 OpenAI API 키로 교체하세요.

### 3. 서버 실행
```bash
python main.py
```

서버는 `http://localhost:8000`에서 실행됩니다.

## API 엔드포인트

### POST /analyze-precedents
상품 정보를 받아서 판례 분석을 수행합니다.

**요청 예시:**
```json
{
  "product_id": "PROD-2024-001",
  "product_name": "Premium Vitamin C Serum",
  "description": "High-concentration Vitamin C serum",
  "hs_code": "3304.99.50.00",
  "origin_country": "KOR",
  "price": 29.99,
  "fob_price": 25.00
}
```

**응답 예시:**
```json
{
  "success_cases": ["2024년 4월 레티놀 세럼 승인 - 농도 검증 및 안정성 테스트 완료로 통과"],
  "failure_cases": ["2024년 2월 비타민C 세럼 거부 - 농도 검증 부족으로 반송"],
  "actionable_insights": ["비타민C 농도는 반드시 HPLC 분석법으로 검증"],
  "risk_factors": ["농도 검증 문서 부족", "FDA 인증서 미비"],
  "recommended_action": "농도 검증서 및 FDA 인증서를 준비하여 재신청",
  "confidence_score": 0.85,
  "is_valid": true
}
```

### GET /test-cbp/{hs_code}
CBP 데이터 수집을 테스트합니다.

### GET /health
서비스 헬스체크

## 테스트

```bash
# API 테스트 실행
python test_api.py
```

## 개발 계획

- [ ] 실제 CBP CROSS 데이터베이스 스크래핑 구현
- [ ] Customs Bulletin 자동 수집
- [ ] FOIA Reading Room 데이터 수집
- [ ] 더 정교한 AI 분석 프롬프트 개발
- [ ] 분석 결과 캐싱 시스템
