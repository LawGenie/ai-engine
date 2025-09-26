"""
미국 정부 기관 API 엔드포인트 관리
각 기관의 공식 API 엔드포인트를 중앙 집중식으로 관리
"""

from typing import Dict, List, Any
from enum import Enum

class AgencyType(Enum):
    """정부 기관 타입"""
    FDA = "fda"
    USDA = "usda"
    EPA = "epa"
    FCC = "fcc"
    CBP = "cbp"
    CPSC = "cpsc"
    KCS = "kcs"
    MFDS = "mfds"
    MOTIE = "motie"

class APIEndpoints:
    """미국 정부 기관 API 엔드포인트 관리 클래스"""
    
    def __init__(self):
        self.endpoints = self._build_endpoints()
    
    def _build_endpoints(self) -> Dict[str, Dict[str, Any]]:
        """모든 기관의 API 엔드포인트를 정의"""
        return {
            # FDA (Food and Drug Administration)
            "fda": {
                "base_url": "https://api.fda.gov",
                "endpoints": {
                    "drug": {
                        "event": "https://api.fda.gov/drug/event.json",
                        "label": "https://api.fda.gov/drug/label.json",
                        "ndc": "https://api.fda.gov/drug/ndc.json",
                        "enforcement": "https://api.fda.gov/drug/enforcement.json",
                        "drugsfda": "https://api.fda.gov/drug/drugsfda.json",
                        "shortages": "https://api.fda.gov/drug/shortages.json"
                    },
                    "device": {
                        "event": "https://api.fda.gov/device/event.json",
                        "510k": "https://api.fda.gov/device/510k.json",
                        "enforcement": "https://api.fda.gov/device/enforcement.json"
                    },
                    "food": {
                        "enforcement": "https://api.fda.gov/food/enforcement.json",
                        "event": "https://api.fda.gov/food/event.json"
                    },
                    "cosmetic": {
                        "event": "https://api.fda.gov/cosmetic/event.json"
                    },
                    "animalandveterinary": {
                        "event": "https://api.fda.gov/animalandveterinary/event.json"
                    }
                },
                "api_key_required": False,
                "rate_limit": "1000/day without key, 120000/day with key"
            },
            
            # USDA (U.S. Department of Agriculture)
            "usda": {
                "base_url": "https://api.nal.usda.gov",
                "endpoints": {
                    "fooddata_central": {
                        "foods": "https://api.nal.usda.gov/fdc/v1/foods",
                        "search": "https://api.nal.usda.gov/fdc/v1/foods/search",
                        "nutrients": "https://api.nal.usda.gov/fdc/v1/nutrients"
                    },
                    "plants": {
                        "plants": "https://plants.usda.gov/api/plants",
                        "search": "https://plants.usda.gov/api/plants/search"
                    },
                    "biopreferred": {
                        "products": "https://www.biopreferred.gov/BioPreferred/faces/pages/ProductCatalog.xhtml"
                    }
                },
                "api_key_required": True,
                "rate_limit": "1000/day"
            },
            
            # EPA (Environmental Protection Agency)
            "epa": {
                "base_url": "https://comptox.epa.gov",
                "endpoints": {
                    "chemicals": {
                        "base": "https://comptox.epa.gov/dashboard/api",
                        "search": "https://comptox.epa.gov/dashboard/api/chemical/search",
                        "details": "https://comptox.epa.gov/dashboard/api/chemical/details",
                        "lists": "https://comptox.epa.gov/dashboard/api/chemical/lists"
                    },
                    "aqs": {
                        "base": "https://aqs.epa.gov/data/api",
                        "sample_data": "https://aqs.epa.gov/data/api/sampleData/byState",
                        "daily_data": "https://aqs.epa.gov/data/api/dailyData/byState",
                        "annual_data": "https://aqs.epa.gov/data/api/annualData/byState"
                    }
                },
                "api_key_required": True,
                "rate_limit": "1000/hour"
            },
            
            # FCC (Federal Communications Commission)
            "fcc": {
                "base_url": "https://api.fcc.gov",
                "endpoints": {
                    "device_authorization": {
                        "base": "https://api.fcc.gov/device/authorization",
                        "grants": "https://api.fcc.gov/device/authorization/grants",
                        "applications": "https://api.fcc.gov/device/authorization/applications"
                    },
                    "ecfs": {
                        "base": "https://api.fcc.gov/ecfs",
                        "proceedings": "https://api.fcc.gov/ecfs/proceedings",
                        "filings": "https://api.fcc.gov/ecfs/filings"
                    },
                    "consumer_help": {
                        "complaints": "https://opendata.fcc.gov/resource/sr6c-syda.json"
                    }
                },
                "api_key_required": False,
                "rate_limit": "1000/hour",
                "retry_enabled": True,
                "max_retries": 3
            },
            
            # CBP (Customs and Border Protection)
            "cbp": {
                "base_url": "https://api.cbp.gov",
                "endpoints": {
                    "trade_statistics": {
                        "base": "https://api.cbp.gov/trade/statistics",
                        "imports": "https://api.cbp.gov/trade/statistics/imports",
                        "exports": "https://api.cbp.gov/trade/statistics/exports",
                        "hs_codes": "https://api.cbp.gov/trade/statistics/hs-codes"
                    },
                    "ace_portal": {
                        "base": "https://api.cbp.gov/ace/",
                        "api": "https://api.cbp.gov/ace/"
                    },
                    "stats": {
                        "base": "https://www.cbp.gov/stats",
                        "portal": "https://www.cbp.gov/stats"
                    },
                    "rules_regulations": {
                        "base": "https://api.cbp.gov/rules-regulations",
                        "tariffs": "https://api.cbp.gov/rules-regulations/tariffs",
                        "requirements": "https://api.cbp.gov/rules-regulations/requirements"
                    },
                    "data": {
                        "base": "https://api.cbp.gov/data",
                        "trade_data": "https://api.cbp.gov/data/trade"
                    }
                },
                "api_key_required": True,
                "rate_limit": "1000/day"
            },
            
            # CPSC (Consumer Product Safety Commission)
            "cpsc": {
                "base_url": "https://www.cpsc.gov",
                "endpoints": {
                    "recalls": {
                        "api": "https://www.cpsc.gov/Recalls/CPSC-Recalls-API",
                        "recalls": "https://www.cpsc.gov/Recalls/CPSC-Recalls-API/recalls",
                        "search": "https://www.cpsc.gov/Recalls/CPSC-Recalls-API/recalls/search",
                        "json": "https://www.cpsc.gov/Recalls/CPSC-Recalls-API/recalls.json"
                    },
                    "saferproducts": {
                        "base": "https://www.cpsc.gov/SaferProducts/",
                        "api": "https://www.cpsc.gov/SaferProducts/"
                    },
                    "penalties": {
                        "base": "https://www.cpsc.gov/",
                        "civil_criminal": "https://www.cpsc.gov/"
                    },
                    "data": {
                        "base": "https://www.cpsc.gov/api",
                        "recalls": "https://www.cpsc.gov/api/recalls",
                        "products": "https://www.cpsc.gov/api/products"
                    }
                },
                "api_key_required": False,
                "rate_limit": "1000/day"
            },
            
            # Commerce (Department of Commerce)
            "commerce": {
                "base_url": "https://api.census.gov",
                "endpoints": {
                    "trade_data": {
                        "base": "https://api.census.gov/data/timeseries/intltrade/",
                        "imports": "https://api.census.gov/data/timeseries/intltrade/imports",
                        "exports": "https://api.census.gov/data/timeseries/intltrade/exports"
                    },
                    "steel_import": {
                        "base": "https://www.trade.gov/steel-import-monitoring-analysis-system-sima",
                        "monitoring": "https://www.trade.gov/steel-import-monitoring-analysis-system-sima"
                    },
                    "aluminum_import": {
                        "base": "https://www.trade.gov/aluminum-import-monitor",
                        "monitoring": "https://www.trade.gov/aluminum-import-monitor"
                    }
                },
                "api_key_required": True,
                "rate_limit": "1000/day"
            },
            
            # 한국 기관들 (추후 확장)
            "kcs": {
                "base_url": "https://www.customs.go.kr",
                "endpoints": {
                    "hs_codes": {
                        "base": "https://www.customs.go.kr/api/hs-codes",
                        "tariffs": "https://www.customs.go.kr/api/hs-codes/tariffs"
                    }
                },
                "api_key_required": False,
                "rate_limit": "1000/day"
            },
            
            "mfds": {
                "base_url": "https://www.mfds.go.kr",
                "endpoints": {
                    "food_safety": {
                        "base": "https://www.mfds.go.kr/api/food-safety",
                        "imports": "https://www.mfds.go.kr/api/food-safety/imports"
                    }
                },
                "api_key_required": False,
                "rate_limit": "1000/day"
            },
            
            "motie": {
                "base_url": "https://www.motie.go.kr",
                "endpoints": {
                    "trade": {
                        "base": "https://www.motie.go.kr/api/trade",
                        "statistics": "https://www.motie.go.kr/api/trade/statistics"
                    }
                },
                "api_key_required": False,
                "rate_limit": "1000/day"
            }
        }
    
    def get_endpoint(self, agency: str, category: str, endpoint: str) -> str:
        """특정 기관의 엔드포인트 URL을 반환"""
        try:
            return self.endpoints[agency]["endpoints"][category][endpoint]
        except KeyError:
            raise ValueError(f"Endpoint not found: {agency}.{category}.{endpoint}")
    
    def get_all_endpoints(self, agency: str) -> Dict[str, Any]:
        """특정 기관의 모든 엔드포인트를 반환"""
        return self.endpoints.get(agency, {})
    
    def is_api_key_required(self, agency: str) -> bool:
        """특정 기관이 API 키를 요구하는지 확인"""
        return self.endpoints.get(agency, {}).get("api_key_required", False)
    
    def get_rate_limit(self, agency: str) -> str:
        """특정 기관의 API 제한 정보를 반환"""
        return self.endpoints.get(agency, {}).get("rate_limit", "Unknown")
    
    def get_base_url(self, agency: str) -> str:
        """특정 기관의 기본 URL을 반환"""
        return self.endpoints.get(agency, {}).get("base_url", "")

# 전역 인스턴스
api_endpoints = APIEndpoints()
