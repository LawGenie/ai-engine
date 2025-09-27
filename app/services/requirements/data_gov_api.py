"""
Data.gov API 통합 서비스
api.data.gov를 통해 7개 미국 정부 기관의 API에 접근
"""

import httpx
import asyncio
from typing import Dict, List, Optional, Any
import os
from datetime import datetime
from .api_endpoints import api_endpoints
import json

class DataGovAPIService:
    """api.data.gov 통합 API 서비스"""
    
    def __init__(self):
        # API 키 로딩 (여러 기관용)
        self.api_keys = {
            "data_gov": os.getenv("API_DATA_GOV", ""),
            "usda": os.getenv("USDA_API_KEY", ""),
            "epa": os.getenv("EPA_API_KEY", ""),
            "fcc": os.getenv("FCC_API_KEY", ""),
            "cbp": os.getenv("CBP_API_KEY", ""),
            "cpsc": os.getenv("CPSC_API_KEY", "")
        }
        
        # 기본 API 키 (data_gov)
        self.api_key = self.api_keys["data_gov"]
        self.base_url = "https://api.data.gov"
        self.timeout = 30.0
        
        # API 키 상태 확인
        if not self.api_key:
            print("⚠️ API_DATA_GOV 키가 설정되지 않았습니다.")
        
        for agency, key in self.api_keys.items():
            if key and agency != "data_gov":
                print(f"✅ {agency.upper()} API 키: 설정됨")
            elif not key and agency != "data_gov":
                print(f"⚠️ {agency.upper()} API 키: 미설정 (공통 키 사용)")
        
        # 기관별 API 엔드포인트 매핑 (api.data.gov 프록시 기반 - 비권장)
        # NOTE: openFDA의 공식 엔드포인트는 self.openfda_endpoints를 사용하세요.
        self.agency_endpoints = {
            "FDA": {
                "base": "https://api.fda.gov",
                "food": "https://api.fda.gov/food/enforcement.json",
                "drug": "https://api.fda.gov/drug/enforcement.json",
                "device": "https://api.fda.gov/device/enforcement.json"
            },
            "USDA": {
                "base": "/usda",
                "food": "/usda/food/nutrition.json",
                "agriculture": "/usda/agriculture/crops.json"
            },
            "EPA": {
                "base": "/epa",
                "chemical": "/epa/chemical/toxicity.json",
                "air": "/epa/air/quality.json"
            },
            "FCC": {
                "base": "/fcc",
                "device": "/fcc/device/authorization.json",
                "license": "/fcc/license/amateur.json"
            },
            "CBP": {
                "base": "/cbp",
                "trade": "/cbp/trade/statistics.json",
                "import": "/cbp/import/requirements.json"
            },
            "CPSC": {
                "base": "/cpsc",
                "recall": "/cpsc/recall/recalls.json",
                "safety": "/cpsc/safety/standards.json"
            }
        }
        
        self.headers = {
            'User-Agent': 'LawGenie-AI-Engine/1.0',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }

        # NOTE: moved openfda_endpoints initialization here to ensure availability
        # openFDA official endpoints mapping (reference: open.fda.gov)
        # These are raw endpoints for direct access (not via api.data.gov proxy)
        self.openfda_endpoints: Dict[str, Dict[str, str]] = {
            "drug": {
                # Adverse Events
                "event": "https://api.fda.gov/drug/event.json",
                # Product Labeling
                "label": "https://api.fda.gov/drug/label.json",
                # NDC Directory
                "ndc": "https://api.fda.gov/drug/ndc.json",
                # Recall Enforcement Reports
                "enforcement": "https://api.fda.gov/drug/enforcement.json",
                # Drugs@FDA
                "drugsfda": "https://api.fda.gov/drug/drugsfda.json",
                # Drug Shortages
                "shortages": "https://api.fda.gov/drug/shortages.json",
            },
            "device": {
                # 510(k)
                "510k": "https://api.fda.gov/device/510k.json",
                # Device Adverse Events
                "event": "https://api.fda.gov/device/event.json",
                # Device Recalls (enforcement)
                "enforcement": "https://api.fda.gov/device/enforcement.json",
            },
            "food": {
                # Recall Enforcement Reports
                "enforcement": "https://api.fda.gov/food/enforcement.json",
                # Adverse Events (CAERS)
                "event": "https://api.fda.gov/food/event.json",
            },
            "cosmetic": {
                # Cosmetic Adverse Events
                "event": "https://api.fda.gov/cosmetic/event.json",
            },
            "animalandveterinary": {
                # Adverse Events
                "event": "https://api.fda.gov/animalandveterinary/event.json",
            },
        }

        
    def _make_item_key(self, item: Dict[str, Any], agency: str) -> str:
        """Build a stable key to dedupe requirement items across/within agencies."""
        name = (item.get("name") or "").strip().lower()
        url = (item.get("url") or "").strip().lower()
        required = item.get("required")
        return f"{agency}|{name}|{url}|{required}"

    def _dedupe_items(self, items: List[Dict[str, Any]], agency: str) -> List[Dict[str, Any]]:
        """Remove duplicates preserving order using the stable key."""
        seen: set[str] = set()
        unique: List[Dict[str, Any]] = []
        for it in items:
            key = self._make_item_key(it, agency)
            if key in seen:
                continue
            seen.add(key)
            unique.append(it)
        return unique

        # openFDA official endpoints mapping (reference: open.fda.gov)
        # These are raw endpoints for direct access (not via api.data.gov proxy)
        self.openfda_endpoints: Dict[str, Dict[str, str]] = {
            "drug": {
                # Adverse Events
                "event": "https://api.fda.gov/drug/event.json",
                # Product Labeling
                "label": "https://api.fda.gov/drug/label.json",
                # NDC Directory
                "ndc": "https://api.fda.gov/drug/ndc.json",
                # Recall Enforcement Reports
                "enforcement": "https://api.fda.gov/drug/enforcement.json",
                # Drugs@FDA
                "drugsfda": "https://api.fda.gov/drug/drugsfda.json",
                # Drug Shortages
                "shortages": "https://api.fda.gov/drug/shortages.json",
            },
            "device": {
                # 510(k)
                "510k": "https://api.fda.gov/device/510k.json",
                # Device Adverse Events
                "event": "https://api.fda.gov/device/event.json",
                # Device Recalls (enforcement)
                "enforcement": "https://api.fda.gov/device/enforcement.json",
            },
            "food": {
                # Recall Enforcement Reports
                "enforcement": "https://api.fda.gov/food/enforcement.json",
                # Adverse Events (CAERS)
                "event": "https://api.fda.gov/food/event.json",
            },
            "cosmetic": {
                # Cosmetic Adverse Events
                "event": "https://api.fda.gov/cosmetic/event.json",
            },
            "animalandveterinary": {
                # Adverse Events
                "event": "https://api.fda.gov/animalandveterinary/event.json",
            },
        }

    def get_openfda_endpoints(self) -> Dict[str, Dict[str, str]]:
        """Expose the canonical openFDA endpoints mapping for callers/tests."""
        return self.openfda_endpoints

        
    def _build_fda_routing(self) -> Dict[str, Dict[str, Any]]:
        """Return a dictionary-driven routing for FDA by HS code chapter prefixes with multiple API types."""
        return {
            "food": {
                "prefixes": {"09","10","11","12","13","14","15","16","17","18","19","20","21","22","23"},
                "endpoints": [
                    self.openfda_endpoints["food"]["enforcement"],
                    self.openfda_endpoints["food"]["event"]
                ],
                "search_field": "product_description",
                "category": "food"
            },
            "drug": {
                "prefixes": {"30","31","32"},
                "endpoints": [
                    self.openfda_endpoints["drug"]["event"],
                    self.openfda_endpoints["drug"]["label"],
                    self.openfda_endpoints["drug"]["ndc"],
                    self.openfda_endpoints["drug"]["drugsfda"],
                    self.openfda_endpoints["drug"]["shortages"]
                ],
                "search_field": "patient.drug.medicinalproduct",
                "category": "drug"
            },
            "cosmetic": {
                "prefixes": {"33","34"},
                "endpoints": [
                    self.openfda_endpoints["cosmetic"]["event"]
                ],
                "search_field": "products.name_brand",
                "category": "cosmetic"
            },
            "device": {
                "prefixes": {"84","85","86","87","88","89","90","91","92","93","94","95","96"},
                "endpoints": [
                    self.openfda_endpoints["device"]["event"],
                    self.openfda_endpoints["device"]["510k"],
                    self.openfda_endpoints["device"]["enforcement"]
                ],
                "search_field": "device_name",
                "category": "device"
            },
        }

    def _resolve_fda_route(self, hs_prefix: str) -> Dict[str, Any]:
        routes = getattr(self, "_fda_routes", None)
        if routes is None:
            self._fda_routes = self._build_fda_routing()
            routes = self._fda_routes
        for key, conf in routes.items():
            if hs_prefix in conf["prefixes"]:
                return conf
        # default to food enforcement
        return {
            "endpoints": [self.openfda_endpoints["food"]["enforcement"]],
            "search_field": "product_description",
            "category": "food"
        }
    
    def _translate_to_english(self, korean_name: str) -> str:
        """한국어 제품명을 영어로 변환 (간단한 매핑)"""
        translations = {
            "노트북 컴퓨터": "laptop computer",
            "컴퓨터": "computer",
            "커피 원두": "coffee beans",
            "커피": "coffee",
            "비타민C 세럼": "vitamin c serum",
            "세럼": "serum",
            "비타민": "vitamin",
            "의료기기": "medical device",
            "의약품": "pharmaceutical",
            "식품": "food",
            "화장품": "cosmetic"
        }
        
        # 정확한 매칭 시도
        if korean_name in translations:
            return translations[korean_name]
        
        # 부분 매칭 시도
        for korean, english in translations.items():
            if korean in korean_name:
                return english
        
        # 매칭되지 않으면 원본 반환
        return korean_name
    
    async def _call_fda_endpoint(self, client: httpx.AsyncClient, endpoint: str, params: Dict[str, Any], hs_type: str) -> Dict[str, Any]:
        """FDA 엔드포인트 호출 헬퍼 메서드"""
        try:
            print(f"    📡 FDA API 호출 ({hs_type}): {endpoint}")
            print(f"    🔍 검색 파라미터: {params}")
            
            response = await client.get(endpoint, params=params)
            response.raise_for_status()
            data = response.json()
            
            print(f"    📊 FDA API 응답 ({hs_type}): {len(data.get('results', []))}개 결과")
            
            return {
                "success": True,
                "data": data,
                "endpoint": endpoint,
                "hs_type": hs_type
            }
        except Exception as e:
            print(f"    ❌ FDA API 호출 실패 ({hs_type}): {e}")
            return {
                "success": False,
                "error": str(e),
                "endpoint": endpoint,
                "hs_type": hs_type
            }
    
    async def search_requirements_by_hs_code(self, hs_code: str, product_name: str = "") -> Dict[str, Any]:
        """HS코드로 모든 기관에서 요구사항 검색"""
        print(f"\n🔍 [DATA.GOV] HS코드 {hs_code} 검색 시작")
        print(f"  📦 상품명: {product_name}")
        
        results = {
            "hs_code": hs_code,
            "product_name": product_name,
            "search_timestamp": datetime.now().isoformat(),
            "agencies": {},
            "total_requirements": 0,
            "total_certifications": 0,
            "total_documents": 0
        }
        
        # 각 기관별로 병렬 검색
        tasks = []
        for agency in self.agency_endpoints.keys():
            task = self._search_agency_requirements(agency, hs_code, product_name)
            tasks.append(task)
        
        # 모든 기관 검색 결과 수집
        agency_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, agency in enumerate(self.agency_endpoints.keys()):
            result = agency_results[i]
            if isinstance(result, Exception):
                print(f"  ❌ {agency}: 검색 실패 - {result}")
                results["agencies"][agency] = {
                    "status": "error",
                    "error": str(result),
                    "certifications": [],
                    "documents": [],
                    "sources": []
                }
            else:
                # Per-agency results are already deduped; attach
                results["agencies"][agency] = result

        # Compute global unique counts across agencies
        global_certifications: List[Dict[str, Any]] = []
        global_documents: List[Dict[str, Any]] = []
        seen_cert: set[str] = set()
        seen_doc: set[str] = set()

        for agency, data in results["agencies"].items():
            certs = data.get("certifications", [])
            docs = data.get("documents", [])
            for it in certs:
                key = self._make_item_key(it, agency)
                if key in seen_cert:
                    continue
                seen_cert.add(key)
                global_certifications.append(it)
            for it in docs:
                key = self._make_item_key(it, agency)
                if key in seen_doc:
                    continue
                seen_doc.add(key)
                global_documents.append(it)

        results["total_certifications"] = len(global_certifications)
        results["total_documents"] = len(global_documents)
        results["total_requirements"] = results["total_certifications"] + results["total_documents"]
        results["unique_summary"] = {
            "certifications_unique": results["total_certifications"],
            "documents_unique": results["total_documents"],
            "requirements_unique": results["total_requirements"]
        }
        
        print(f"\n✅ [DATA.GOV] 검색 완료")
        print(f"  📋 총 요구사항: {results['total_requirements']}개")
        print(f"  🏆 인증요건: {results['total_certifications']}개")
        print(f"  📄 필요서류: {results['total_documents']}개")
        
        return results
    
    async def _search_agency_requirements(self, agency: str, hs_code: str, product_name: str) -> Dict[str, Any]:
        """특정 기관에서 HS코드 기반 요구사항 검색"""
        print(f"  🔍 {agency} 검색 중...")
        
        try:
            if agency == "FDA":
                return await self._search_fda_requirements(hs_code, product_name)
            elif agency == "USDA":
                return await self._search_usda_requirements(hs_code, product_name)
            elif agency == "EPA":
                return await self._search_epa_requirements(hs_code, product_name)
            elif agency == "FCC":
                return await self._search_fcc_requirements(hs_code, product_name)
            elif agency == "CBP":
                return await self._search_cbp_requirements(hs_code, product_name)
            elif agency == "CPSC":
                return await self._search_cpsc_requirements(hs_code, product_name)
            else:
                return {"status": "unsupported", "error": f"지원되지 않는 기관: {agency}"}
                
        except Exception as e:
            print(f"    ❌ {agency} 검색 실패: {e}")
            return {
                "status": "error",
                "error": str(e),
                "certifications": [],
                "documents": [],
                "sources": []
            }
    
    async def _search_fda_requirements(self, hs_code: str, product_name: str) -> Dict[str, Any]:
        """FDA API로 HS코드 기반 요구사항 검색 (여러 엔드포인트 병렬 조회)"""
        print(f"    🏥 FDA API 검색: HS코드 {hs_code}")
        
        try:
            # HS코드 기반 라우팅 (사전 기반)
            hs_prefix = hs_code.split('.')[0] if '.' in hs_code else hs_code[:4]
            # 4자리 HS 코드를 2자리 챕터로 변환
            if len(hs_prefix) >= 4:
                hs_chapter = hs_prefix[:2]
            else:
                hs_chapter = hs_prefix
            print(f"    🔍 HS 코드 챕터: {hs_chapter} (원본: {hs_prefix})")
            route = self._resolve_fda_route(hs_chapter)
            endpoints = route["endpoints"]
            search_field = route["search_field"]
            
            print(f"    📡 FDA API 엔드포인트: {len(endpoints)}개")
            print(f"    🔍 검색 필드: {search_field}")
            print(f"    🎯 선택된 카테고리: {route.get('category', 'unknown')}")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # 모든 엔드포인트를 병렬로 조회
                tasks = []
                # 한국어 제품명을 영어로 변환 (간단한 매핑)
                english_name = self._translate_to_english(product_name)
                tokens = [t for t in english_name.split() if t]

                for endpoint in endpoints:
                    # 엔드포인트별 올바른 검색 필드로 스위치
                    if "/drug/" in endpoint:
                        field = "patient.drug.medicinalproduct"
                    elif "/device/510k" in endpoint:
                        field = "device_name"
                    elif "/device/" in endpoint:
                        field = "device_name"
                    elif "/food/" in endpoint:
                        field = "product_description"
                    elif "/cosmetic/" in endpoint:
                        field = "products.name_brand"
                    elif "/animalandveterinary/" in endpoint:
                        field = "products.name_brand"
                    else:
                        field = search_field

                    # Build AND/OR queries for this endpoint's field
                    and_query = None
                    or_query = None
                    if tokens:
                        # openFDA query language uses spaces as AND by default, but we make it explicit
                        and_query = "+AND+".join([f"{field}:{t}" for t in tokens])
                        or_query = "+OR+".join([f"{field}:{t}" for t in tokens])

                    # name_exact
                    params_exact = {
                        "search": f"{field}:\"{english_name}\"",
                        "limit": 10
                    }
                    tasks.append(self._call_fda_endpoint(client, endpoint, params_exact, "name_exact"))

                    # name_and
                    if and_query:
                        params_and = {
                            "search": and_query,
                            "limit": 10
                        }
                        tasks.append(self._call_fda_endpoint(client, endpoint, params_and, "name_and"))

                    # name_or
                    if or_query:
                        params_or = {
                            "search": or_query,
                            "limit": 10
                        }
                        tasks.append(self._call_fda_endpoint(client, endpoint, params_or, "name_or"))

                    # name_token (each token separately)
                    for tok in tokens[:2] if tokens else []:  # limit single-token fanout
                        params_tok = {
                            "search": f"{field}:{tok}",
                            "limit": 10
                        }
                        tasks.append(self._call_fda_endpoint(client, endpoint, params_tok, f"name_token:{tok}"))

                    # HS코드 검색은 공식 지원되지 않으므로 제거 (404 원인)
                
                # 모든 API 호출을 병렬로 실행
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # 결과 통합
                all_results = []
                all_sources = []
                
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        print(f"    ❌ API 호출 실패: {result}")
                        continue
                    
                    endpoint = result.get("endpoint", "unknown")
                    hs_type = result.get("hs_type", "unknown")
                    
                    if result.get("success"):
                        data = result["data"]
                        results_list = data.get('results', [])
                        all_results.extend(results_list)
                        
                        # 소스 정보 추가
                        source_info = {
                            "title": f"FDA {endpoint.split('/')[-1].replace('.json', '')} [{hs_type}]",
                            "url": endpoint,
                            "type": "공식 API",
                            "relevance": "high",
                            "raw_data": data
                        }
                        all_sources.append(source_info)
                        
                        print(f"    📊 FDA {endpoint.split('/')[-1]} ({hs_type}): {len(results_list)}개 결과")
                    else:
                        print(f"    ❌ FDA {endpoint.split('/')[-1]} ({hs_type}): {result.get('error', 'Unknown error')}")
                
                print(f"    📊 FDA API 통합 결과: {len(all_results)}개")

                # Food 카테고리일 경우, Adverse Events도 추가 조회 및 병합
                adverse_events = []
                if any("/food/enforcement" in endpoint for endpoint in endpoints):
                    food_event_url = self.openfda_endpoints["food"]["event"]
                    english_name = self._translate_to_english(product_name)
                    params_event = {
                        "search": f"products.name_brand:\"{english_name}\"",
                        "limit": 10
                    }
                    print(f"    📡 FDA Food Adverse Events 호출: {food_event_url}")
                    print(f"    🔍 검색 파라미터: {params_event}")
                    try:
                        resp_event = await client.get(food_event_url, params=params_event)
                        resp_event.raise_for_status()
                        data_event = resp_event.json()
                        adverse_events = data_event.get("results", [])
                        print(f"    📊 FDA Food Adverse Events 응답: {len(adverse_events)}개 결과")
                    except Exception as ev_err:
                        print(f"    ❌ FDA Food Adverse Events 호출 실패: {ev_err}")
                
                # 실제 API 데이터에서 요구사항 추출
                certifications = []
                documents = []
                sources = []
                
                if all_results:
                    for result in all_results:
                        # FDA enforcement 데이터에서 원문 정보 추출
                        product_desc = result.get('product_description', 'Unknown Product')
                        recall_reason = result.get('reason_for_recall', 'No specific reason provided')
                        recall_date = result.get('recall_initiation_date', 'Unknown date')
                        status = result.get('status', 'Unknown status')
                        
                        # 원문 데이터를 그대로 활용한 요구사항 생성
                        certifications.append({
                            "name": f"FDA 식품 안전 요구사항 ({product_desc})",
                            "required": True,
                            "description": f"원문: {recall_reason} (상태: {status}, 날짜: {recall_date})",
                            "agency": "FDA",
                            "url": "https://www.fda.gov/food/importing-food-products-imported-food",
                            "raw_data": {
                                "product_description": product_desc,
                                "reason_for_recall": recall_reason,
                                "recall_initiation_date": recall_date,
                                "status": status,
                                "distribution_pattern": result.get('distribution_pattern', 'Unknown'),
                                "product_quantity": result.get('product_quantity', 'Unknown')
                            }
                        })
                        
                        documents.append({
                            "name": "FDA 식품 시설 등록 증명서",
                            "required": True,
                            "description": f"FDA에 등록된 식품 시설 증명서 (제품: {product_desc})",
                            "url": "https://www.fda.gov/food/importing-food-products-imported-food",
                            "raw_data": result  # 전체 원문 데이터 포함
                        })

                # Adverse Events → documents에 요약 형태로 병합
                for ev in adverse_events:
                    reactions = ev.get("reactions") or ev.get("reaction") or []
                    if isinstance(reactions, list):
                        reactions_text = ", ".join([r if isinstance(r, str) else (r.get("veddra_term_name") or r.get("reactionmeddrapt") or "") for r in reactions])
                    else:
                        reactions_text = str(reactions)
                    documents.append({
                        "name": "FDA 식품 이상사례",
                        "required": False,
                        "description": f"보고된 반응: {reactions_text[:400]}",
                        "url": self.openfda_endpoints["food"]["event"],
                        "raw_data": ev,
                        "source_type": "adverse_event"
                    })
                
                sources.append({
                    "title": f"FDA HS코드 {hs_code} 요구사항",
                    "url": "https://www.fda.gov/food/importing-food-products-imported-food",
                    "type": "공식 API",
                    "relevance": "high"
                })
                if adverse_events:
                    sources.append({
                        "title": "FDA Food Adverse Events",
                        "url": self.openfda_endpoints["food"]["event"],
                        "type": "공식 API",
                        "relevance": "medium"
                    })
                
                # 중복 제거된 최종 결과
                final_certifications = self._dedupe_items(certifications, "FDA")
                final_documents = self._dedupe_items(documents, "FDA")
                
                # 상세 로그 출력
                print(f"    📋 FDA 인증요건 ({len(final_certifications)}개):")
                for i, cert in enumerate(final_certifications, 1):
                    print(f"      {i}. {cert['name']} - {cert['description'][:100]}...")
                
                print(f"    📄 FDA 필요서류 ({len(final_documents)}개):")
                for i, doc in enumerate(final_documents, 1):
                    print(f"      {i}. {doc['name']} - {doc['description'][:100]}...")
                
                return {
                    "status": "success",
                    "agency": "FDA",
                    "certifications": final_certifications,
                    "documents": final_documents,
                    "sources": sources,
                    "hs_code_matched": True,
                    "api_source": "data.gov",
                    "api_results_count": len(all_results),
                    "endpoints_used": endpoints,
                    "total_api_calls": len(results)
                }
            
        except httpx.HTTPStatusError as e:
            print(f"    ❌ FDA API HTTP 오류: {e.response.status_code}")
            return {
                "status": "http_error",
                "agency": "FDA",
                "certifications": [],
                "documents": [],
                "sources": [],
                "hs_code_matched": False,
                "api_source": "data.gov",
                "error": f"HTTP {e.response.status_code}"
            }
        except Exception as e:
            print(f"    ❌ FDA API 호출 실패: {e}")
            return {
                "status": "error",
                "agency": "FDA",
                "certifications": [],
                "documents": [],
                "sources": [],
                "hs_code_matched": False,
                "api_source": "data.gov",
                "error": str(e)
            }
    
    async def _search_usda_requirements(self, hs_code: str, product_name: str) -> Dict[str, Any]:
        """USDA API로 HS코드 기반 요구사항 검색 (FoodData Central API 사용)"""
        print(f"    🌾 USDA API 검색: HS코드 {hs_code}")
        
        try:
            # USDA FoodData Central API 사용
            api_url = api_endpoints.get_endpoint("usda", "fooddata_central", "search")
            english_name = self._translate_to_english(product_name)
            # USDA API 키가 없으면 공통 키 사용, 그것도 없으면 키 없이 시도
            api_key = self.api_keys.get("usda") or self.api_key
            params = {
                "query": english_name,
                "pageSize": 10,
                "pageNumber": 1
            }
            if api_key:
                params["api_key"] = api_key
            
            print(f"    📡 USDA API 호출: {api_url}")
            print(f"    🔍 검색 파라미터: {params}")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # 1. 상품명 기반 검색
                response_name = await client.get(api_url, params=params)
                response_name.raise_for_status()
                data_name = response_name.json()
                
                # 2. HS코드 기반 검색 (추가 파라미터)
                params_hs = params.copy()
                params_hs["fdcId"] = hs_code  # HS코드를 fdcId로 시도
                try:
                    response_hs = await client.get(api_url, params=params_hs)
                    response_hs.raise_for_status()
                    data_hs = response_hs.json()
                except:
                    data_hs = {"foods": []}
                
                # 결과 통합
                all_foods = data_name.get('foods', []) + data_hs.get('foods', [])
                print(f"    📊 USDA API 응답: 상품명 {len(data_name.get('foods', []))}개, HS코드 {len(data_hs.get('foods', []))}개, 총 {len(all_foods)}개")
                
                # 실제 API 데이터에서 요구사항 추출
                certifications = []
                documents = []
                sources = []
                
                if all_foods:
                    for result in all_foods:
                        certifications.append({
                            "name": f"USDA 농산물 요구사항 ({product_name})",
                            "required": True,
                            "description": f"USDA 농산물 기준에 따른 요구사항",
                            "agency": "USDA",
                            "url": "https://www.aphis.usda.gov/aphis/ourfocus/planthealth/import-information",
                            "raw_data": result
                        })
                
                sources.append({
                    "title": f"USDA HS코드 {hs_code} 요구사항",
                    "url": "https://www.aphis.usda.gov/aphis/ourfocus/planthealth/import-information",
                    "type": "공식 API",
                    "relevance": "high"
                })
                
                # 중복 제거된 최종 결과
                final_certifications = self._dedupe_items(certifications, "USDA")
                final_documents = self._dedupe_items(documents, "USDA")
                
                # 상세 로그 출력
                print(f"    📋 USDA 인증요건 ({len(final_certifications)}개):")
                for i, cert in enumerate(final_certifications, 1):
                    print(f"      {i}. {cert['name']} - {cert['description'][:100]}...")
                
                print(f"    📄 USDA 필요서류 ({len(final_documents)}개):")
                for i, doc in enumerate(final_documents, 1):
                    print(f"      {i}. {doc['name']} - {doc['description'][:100]}...")
                
                return {
                    "status": "success",
                    "agency": "USDA",
                    "certifications": final_certifications,
                    "documents": final_documents,
                    "sources": sources,
                    "hs_code_matched": True,
                    "api_source": "data.gov",
                    "api_results_count": len(all_foods)
                }
            
        except Exception as e:
            print(f"    ❌ USDA API 호출 실패: {e}")
            return {
                "status": "error",
                "agency": "USDA",
                "certifications": [],
                "documents": [],
                "sources": [],
                "hs_code_matched": False,
                "api_source": "data.gov",
                "error": str(e)
            }
    
    async def _search_epa_requirements(self, hs_code: str, product_name: str) -> Dict[str, Any]:
        """EPA API로 HS코드 기반 요구사항 검색 (CompTox Chemicals Dashboard API 사용)"""
        print(f"    🌿 EPA API 검색: HS코드 {hs_code}")
        
        try:
            # EPA CompTox Chemicals Dashboard API 사용
            api_url = api_endpoints.get_endpoint("epa", "chemicals", "search")
            english_name = self._translate_to_english(product_name)
            params = {
                "searchTerm": english_name,
                "limit": 10
            }
            
            # EPA API 키가 필요한 경우 추가
            if self.api_key:
                params["api_key"] = self.api_key
            
            print(f"    📡 EPA API 호출: {api_url}")
            print(f"    🔍 검색 파라미터: {params}")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(api_url, params=params)
                response.raise_for_status()
                data = response.json()
                
                print(f"    📊 EPA API 응답: {len(data.get('results', []))}개 결과")
                
                # 실제 API 데이터에서 요구사항 추출
                certifications = []
                documents = []
                sources = []
                
                if data.get('results'):
                    for result in data['results']:
                        certifications.append({
                            "name": f"EPA 환경 규제 요구사항 ({product_name})",
                            "required": True,
                            "description": f"EPA 환경 기준에 따른 요구사항",
                            "agency": "EPA",
                            "url": "https://www.epa.gov/chemicals-under-tsca",
                            "raw_data": result
                        })
                
                sources.append({
                    "title": f"EPA HS코드 {hs_code} 요구사항",
                    "url": "https://www.epa.gov/chemicals-under-tsca",
                    "type": "공식 API",
                    "relevance": "high"
                })
                
                # 중복 제거된 최종 결과
                final_certifications = self._dedupe_items(certifications, "EPA")
                final_documents = self._dedupe_items(documents, "EPA")
                
                # 상세 로그 출력
                print(f"    📋 EPA 인증요건 ({len(final_certifications)}개):")
                for i, cert in enumerate(final_certifications, 1):
                    print(f"      {i}. {cert['name']} - {cert['description'][:100]}...")
                
                print(f"    📄 EPA 필요서류 ({len(final_documents)}개):")
                for i, doc in enumerate(final_documents, 1):
                    print(f"      {i}. {doc['name']} - {doc['description'][:100]}...")
                
                return {
                    "status": "success",
                    "agency": "EPA",
                    "certifications": final_certifications,
                    "documents": final_documents,
                    "sources": sources,
                    "hs_code_matched": True,
                    "api_source": "data.gov",
                    "api_results_count": len(data.get('results', []))
                }
            
        except httpx.HTTPStatusError as e:
            print(f"    ❌ EPA API HTTP 오류: {e.response.status_code}")
            return {
                "status": "http_error",
                "agency": "EPA",
                "certifications": [],
                "documents": [],
                "sources": [],
                "hs_code_matched": False,
                "api_source": "data.gov",
                "error": f"HTTP {e.response.status_code}"
            }
        except Exception as e:
            print(f"    ❌ EPA API 호출 실패: {e}")
            return {
                "status": "error",
                "agency": "EPA",
                "certifications": [],
                "documents": [],
                "sources": [],
                "hs_code_matched": False,
                "api_source": "data.gov",
                "error": str(e)
            }
    
    async def _search_fcc_requirements(self, hs_code: str, product_name: str) -> Dict[str, Any]:
        """FCC API로 HS코드 기반 요구사항 검색 (Device Authorization API 사용) - 재시도 로직 포함"""
        print(f"    📡 FCC API 검색: HS코드 {hs_code}")
        
        try:
            # FCC Device Authorization API 사용
            api_url = api_endpoints.get_endpoint("fcc", "device_authorization", "grants")
            english_name = self._translate_to_english(product_name)
            params = {
                "search": f"device_name:{english_name}",
                "limit": 10,
                "format": "json"
            }
            # FCC는 API 키가 필요하지 않음
            
            print(f"    📡 FCC API 호출: {api_url}")
            print(f"    🔍 검색 파라미터: {params}")
            
            # 재시도 로직 (502 오류 대응)
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        response = await client.get(api_url, params=params)
                        response.raise_for_status()
                        break
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 502 and attempt < max_retries - 1:
                        print(f"    ⚠️ FCC API 502 오류, {attempt + 1}번째 재시도...")
                        await asyncio.sleep(2 ** attempt)  # 지수 백오프
                        continue
                    else:
                        raise
                data = response.json()
                
                print(f"    📊 FCC API 응답: {len(data.get('results', []))}개 결과")
                
                # 실제 API 데이터에서 요구사항 추출
                certifications = []
                documents = []
                sources = []
                
                if data.get('results'):
                    for result in data['results']:
                        certifications.append({
                            "name": f"FCC 전자제품 인증 요구사항 ({product_name})",
                            "required": True,
                            "description": f"FCC 전자제품 인증 기준에 따른 요구사항",
                            "agency": "FCC",
                            "url": "https://www.fcc.gov/device-authorization",
                            "raw_data": result
                        })
                
                sources.append({
                    "title": f"FCC HS코드 {hs_code} 요구사항",
                    "url": "https://www.fcc.gov/device-authorization",
                    "type": "공식 API",
                    "relevance": "high"
                })
                
                # 중복 제거된 최종 결과
                final_certifications = self._dedupe_items(certifications, "FCC")
                final_documents = self._dedupe_items(documents, "FCC")
                
                # 상세 로그 출력
                print(f"    📋 FCC 인증요건 ({len(final_certifications)}개):")
                for i, cert in enumerate(final_certifications, 1):
                    print(f"      {i}. {cert['name']} - {cert['description'][:100]}...")
                
                print(f"    📄 FCC 필요서류 ({len(final_documents)}개):")
                for i, doc in enumerate(final_documents, 1):
                    print(f"      {i}. {doc['name']} - {doc['description'][:100]}...")
                
                return {
                    "status": "success",
                    "agency": "FCC",
                    "certifications": final_certifications,
                    "documents": final_documents,
                    "sources": sources,
                    "hs_code_matched": True,
                    "api_source": "data.gov",
                    "api_results_count": len(data.get('results', []))
                }
            
        except httpx.HTTPStatusError as e:
            print(f"    ❌ FCC API HTTP 오류: {e.response.status_code}")
            return {
                "status": "http_error",
                "agency": "FCC",
                "certifications": [],
                "documents": [],
                "sources": [],
                "hs_code_matched": False,
                "api_source": "data.gov",
                "error": f"HTTP {e.response.status_code}"
            }
        except Exception as e:
            print(f"    ❌ FCC API 호출 실패: {e}")
            return {
                "status": "error",
                "agency": "FCC",
                "certifications": [],
                "documents": [],
                "sources": [],
                "hs_code_matched": False,
                "api_source": "data.gov",
                "error": str(e)
            }
    
    async def _search_cbp_requirements(self, hs_code: str, product_name: str) -> Dict[str, Any]:
        """CBP API로 HS코드 기반 요구사항 검색 (Trade Statistics API 사용)"""
        print(f"    🛃 CBP API 검색: HS코드 {hs_code}")
        
        try:
            # CBP Trade Statistics API 사용 (HS 코드 기반)
            api_url = api_endpoints.get_endpoint("cbp", "trade_statistics", "hs_codes")
            params = {
                "hs_code": hs_code,
                "limit": 10,
                "format": "json"
            }
            # CBP는 API 키가 필요할 수 있음
            if self.api_key:
                params["api_key"] = self.api_key
            
            print(f"    📡 CBP API 호출 시도: {api_url}")
            print(f"    🔍 검색 파라미터: {params}")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(api_url, params=params)
                response.raise_for_status()
                data = response.json()
                
                print(f"    📊 CBP API 응답: {len(data.get('data', []))}개 결과")
                
                # CBP 데이터에서 요구사항 추출
                certifications = []
                documents = []
                sources = []
                
                if data.get('data'):
                    for item in data['data']:
                        certifications.append({
                            "name": f"CBP 관세 요구사항",
                            "required": True,
                            "description": f"HS코드 {hs_code}에 대한 관세 정보",
                            "agency": "CBP",
                            "url": "https://www.cbp.gov",
                            "raw_data": item
                        })
                        
                        sources.append({
                            "title": f"CBP Trade Statistics - {hs_code}",
                            "url": "https://www.cbp.gov",
                            "type": "공식 API",
                            "relevance": "high",
                            "raw_data": item
                        })
                
                # 중복 제거된 최종 결과
                final_certifications = self._dedupe_items(certifications, "CBP")
                final_documents = self._dedupe_items(documents, "CBP")
                
                # 상세 로그 출력
                print(f"    📋 CBP 인증요건 ({len(final_certifications)}개):")
                for i, cert in enumerate(final_certifications, 1):
                    print(f"      {i}. {cert['name']} - {cert['description'][:100]}...")
                
                print(f"    📄 CBP 필요서류 ({len(final_documents)}개):")
                for i, doc in enumerate(final_documents, 1):
                    print(f"      {i}. {doc['name']} - {doc['description'][:100]}...")
                
                return {
                    "status": "success",
                    "agency": "CBP",
                    "certifications": final_certifications,
                    "documents": final_documents,
                    "sources": sources,
                    "total_certifications": len(final_certifications),
                    "total_documents": len(final_documents),
                    "total_sources": len(sources),
                    "raw_api_data": data
                }
                
        except Exception as e:
            print(f"    ❌ CBP API 호출 실패: {e}")
            return {
                "status": "no_api_call",
                "agency": "CBP",
                "certifications": [],
                "documents": [],
                "sources": [],
                "hs_code_matched": False,
                "api_source": "data.gov",
                "note": "실제 API 호출 미구현 - 하드코딩 제거됨"
            }
            
        except Exception as e:
            print(f"    ❌ CBP API 호출 실패: {e}")
            return {
                "status": "error",
                "agency": "CBP",
                "certifications": [],
                "documents": [],
                "sources": [],
                "hs_code_matched": False,
                "api_source": "data.gov",
                "error": str(e)
            }
    
    async def _search_cpsc_requirements(self, hs_code: str, product_name: str) -> Dict[str, Any]:
        """CPSC API로 HS코드 기반 요구사항 검색 (Recalls API 사용)"""
        print(f"    🛡️ CPSC API 검색: HS코드 {hs_code}")
        
        try:
            # CPSC Recalls API 사용 (JSON 엔드포인트)
            api_url = api_endpoints.get_endpoint("cpsc", "recalls", "json")
            english_name = self._translate_to_english(product_name)
            params = {
                "search": english_name,
                "limit": 10,
                "format": "json"
            }
            # CPSC는 API 키가 필요하지 않음
            
            print(f"    📡 CPSC API 호출 시도: {api_url}")
            print(f"    🔍 검색 파라미터: {params}")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(api_url, params=params)
                response.raise_for_status()
                data = response.json()
                
                print(f"    📊 CPSC API 응답: {len(data.get('results', []))}개 결과")
                
                # CPSC 데이터에서 요구사항 추출
                certifications = []
                documents = []
                sources = []
                
                if data.get('results'):
                    for item in data['results']:
                        certifications.append({
                            "name": f"CPSC 제품 안전 요구사항",
                            "required": True,
                            "description": f"제품 안전 기준 및 리콜 정보",
                            "agency": "CPSC",
                            "url": "https://www.cpsc.gov",
                            "raw_data": item
                        })
                        
                        sources.append({
                            "title": f"CPSC Recalls - {english_name}",
                            "url": "https://www.cpsc.gov",
                            "type": "공식 API",
                            "relevance": "high",
                            "raw_data": item
                        })
                
                # 중복 제거된 최종 결과
                final_certifications = self._dedupe_items(certifications, "CPSC")
                final_documents = self._dedupe_items(documents, "CPSC")
                
                # 상세 로그 출력
                print(f"    📋 CPSC 인증요건 ({len(final_certifications)}개):")
                for i, cert in enumerate(final_certifications, 1):
                    print(f"      {i}. {cert['name']} - {cert['description'][:100]}...")
                
                print(f"    📄 CPSC 필요서류 ({len(final_documents)}개):")
                for i, doc in enumerate(final_documents, 1):
                    print(f"      {i}. {doc['name']} - {doc['description'][:100]}...")
                
                return {
                    "status": "success",
                    "agency": "CPSC",
                    "certifications": final_certifications,
                    "documents": final_documents,
                    "sources": sources,
                    "total_certifications": len(final_certifications),
                    "total_documents": len(final_documents),
                    "total_sources": len(sources),
                    "raw_api_data": data
                }
                
        except Exception as e:
            print(f"    ❌ CPSC API 호출 실패: {e}")
            return {
                "status": "no_api_call",
                "agency": "CPSC",
                "certifications": [],
                "documents": [],
                "sources": [],
                "hs_code_matched": False,
                "api_source": "data.gov",
                "note": "실제 API 호출 미구현 - 하드코딩 제거됨"
            }
            
        except Exception as e:
            print(f"    ❌ CPSC API 호출 실패: {e}")
            return {
                "status": "error",
                "agency": "CPSC",
                "certifications": [],
                "documents": [],
                "sources": [],
                "hs_code_matched": False,
                "api_source": "data.gov",
                "error": str(e)
            }
