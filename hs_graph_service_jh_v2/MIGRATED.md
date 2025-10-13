# 📌 통합 안내

**이 디렉토리의 코드는 메인 AI Engine에 통합되었습니다.**

---

## 🔗 통합 위치

### **라우터 파일**
`ai-engine/app/routers/hs_tariff_router.py`

### **실행 방법**
```bash
# 이전 방식 (더 이상 사용 안 함)
cd hs_graph_service_jh_v2
python -m uvicorn main:app

# 새로운 방식 (권장)
cd ai-engine
python -m uvicorn main:app --reload --port 8000
```

---

## 🎯 API 엔드포인트 변경

### **Before (별도 서버)**
```
POST http://localhost:[PORT]/api/hs-code/analyze-graph
GET  http://localhost:[PORT]/health
```

### **After (통합 서버)**
```
POST http://localhost:8000/hs-tariff/analyze
GET  http://localhost:8000/hs-tariff/health
GET  http://localhost:8000/hs-tariff/test
```

---

## 📂 원본 코드 보존

### **이 디렉토리의 파일들**
- `workflow.py` - LangGraph 기반 HS 코드 분석 워크플로우
- `llm_service.py` - LLM 서비스 (GPT 활용)
- `vector_service.py` - 벡터 검색 서비스 (FAISS)
- `models.py` - Pydantic 모델 정의
- `config.py` - 설정 파일
- `main.py` - FastAPI 서버 (참조용으로 유지)

### **Git 이력 확인**
```bash
# 각 파일의 작성자 확인
git log --follow hs_graph_service_jh_v2/workflow.py

# 라인별 작성자 확인
git blame hs_graph_service_jh_v2/workflow.py

# 모든 기여자 목록
git log --pretty=format:"%an" hs_graph_service_jh_v2/ | sort -u
```

---

## 🔧 통합 방식

### **통합 레이어 패턴**
`hs_tariff_router.py`는 이 디렉토리의 모듈을 **import**하여 사용합니다:

```python
# ai-engine/app/routers/hs_tariff_router.py

# Python path 추가
hs_graph_path = project_root / "hs_graph_service_jh_v2"
sys.path.insert(0, str(hs_graph_path))

# 원본 코드 import
from models import HsCodeAnalysisRequest, HsCodeAnalysisResponse
from workflow import run_hs_analysis_workflow
from config import settings

# FastAPI 라우터로 제공
@router.post("/analyze")
async def analyze_hs_code(request: HsCodeAnalysisRequest):
    # 원본 워크플로우 실행
    result = await run_hs_analysis_workflow(...)
    return result
```

### **장점**
1. ✅ **원본 코드 보존**: 이 디렉토리 파일들은 수정 없음
2. ✅ **Git 이력 유지**: 팀원 기여도 그대로 보존
3. ✅ **코드 재사용**: DRY 원칙 준수
4. ✅ **유지보수 용이**: 원본 참조 가능

---

## 📖 관련 문서

- `ai-engine/PRECEDENTS_INTEGRATION.md` - 통합 가이드
- `ai-engine/INTEGRATION_COMPLETE.md` - 통합 완료 보고서
- `ai-engine/GIT_INTEGRATION_STRATEGY.md` - Git 전략 가이드

---

## 👥 기여자

이 디렉토리의 모든 파일은 팀원이 작성했습니다.

Git 이력을 통해 각 파일의 작성자를 확인할 수 있습니다:
```bash
git log hs_graph_service_jh_v2/
```

---

**통합일**: 2025-10-12  
**통합 방식**: 원본 유지 + 라우터 레이어 추가  
**원본 상태**: 보존됨 (변경 없음)

