#!/usr/bin/env python3
"""
정부 기관 정보 데이터베이스 시스템
- 모든 정부 기관의 정보를 DB에 저장
- HS 코드별 자동 기관 매칭
- LangGraph 워크플로우와 통합
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

@dataclass
class GovernmentAgency:
    """정부 기관 정보"""
    agency_id: str
    name: str
    short_name: str
    description: str
    website: str
    api_endpoints: List[str]
    categories: List[str]
    hs_chapters: List[str]
    priority: int  # 우선순위 (1-10, 높을수록 우선)
    is_active: bool
    last_updated: datetime

class GovernmentAgenciesDB:
    """정부 기관 데이터베이스 관리자"""
    
    def __init__(self, db_path: str = "government_agencies.db"):
        self.db_path = db_path
        self.init_database()
        self.load_default_agencies()
    
    def init_database(self):
        """데이터베이스 초기화"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 정부 기관 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS government_agencies (
                agency_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                short_name TEXT NOT NULL,
                description TEXT,
                website TEXT,
                api_endpoints TEXT,  -- JSON
                categories TEXT,     -- JSON
                hs_chapters TEXT,    -- JSON
                priority INTEGER DEFAULT 5,
                is_active BOOLEAN DEFAULT TRUE,
                last_updated TEXT
            )
        ''')
        
        # HS 코드별 기관 매핑 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hs_agency_mappings (
                hs_chapter TEXT,
                agency_id TEXT,
                priority INTEGER DEFAULT 5,
                PRIMARY KEY (hs_chapter, agency_id),
                FOREIGN KEY (agency_id) REFERENCES government_agencies (agency_id)
            )
        ''')
        
        # API 엔드포인트 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_endpoints (
                endpoint_id TEXT PRIMARY KEY,
                agency_id TEXT NOT NULL,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                method TEXT DEFAULT 'GET',
                params TEXT,  -- JSON
                headers TEXT, -- JSON
                success_rate REAL DEFAULT 0.0,
                last_success TEXT,
                last_failure TEXT,
                failure_count INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                FOREIGN KEY (agency_id) REFERENCES government_agencies (agency_id)
            )
        ''')
        
        conn.commit()
        conn.close()
        print("✅ 정부 기관 데이터베이스 초기화 완료")
    
    def load_default_agencies(self):
        """기본 정부 기관 정보 로드"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 기존 데이터 확인
        cursor.execute('SELECT COUNT(*) FROM government_agencies')
        count = cursor.fetchone()[0]
        
        if count > 0:
            conn.close()
            print(f"✅ 기존 {count}개 기관 데이터 로드됨")
            return
        
        # 기본 기관 데이터
        default_agencies = [
            # 식품/농산물 관련 (HS 01-24장)
            {
                "agency_id": "usda",
                "name": "U.S. Department of Agriculture",
                "short_name": "USDA",
                "description": "농산물 수입요건, 검역요구사항",
                "website": "https://www.usda.gov",
                "api_endpoints": [
                    "https://api.nal.usda.gov/fdc/v1/foods/search",
                    "https://api.nal.usda.gov/fdc/v1/foods",
                    "https://api.nal.usda.gov/fdc/v1/nutrients"
                ],
                "categories": ["agricultural", "food"],
                "hs_chapters": ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24"],
                "priority": 9
            },
            {
                "agency_id": "fda",
                "name": "Food and Drug Administration",
                "short_name": "FDA",
                "description": "식품 안전기준, 라벨링 규정, 의약품, 의료기기",
                "website": "https://www.fda.gov",
                "api_endpoints": [
                    "https://api.fda.gov/food/enforcement.json",
                    "https://api.fda.gov/drug/event.json",
                    "https://api.fda.gov/device/event.json",
                    "https://api.fda.gov/cosmetic/event.json"
                ],
                "categories": ["food", "drug", "device", "cosmetic"],
                "hs_chapters": ["09", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24", "30", "31", "32", "33", "34", "84", "85", "90", "91", "92", "93", "94", "95", "96"],
                "priority": 10
            },
            {
                "agency_id": "fsis",
                "name": "Food Safety and Inspection Service",
                "short_name": "FSIS",
                "description": "육류/가금류 검사요구사항",
                "website": "https://www.fsis.usda.gov",
                "api_endpoints": [],
                "categories": ["agricultural", "meat"],
                "hs_chapters": ["01", "02", "03", "04", "16"],
                "priority": 8
            },
            {
                "agency_id": "aphis",
                "name": "Animal and Plant Health Inspection Service",
                "short_name": "APHIS",
                "description": "동식물 검역요구사항",
                "website": "https://www.aphis.usda.gov",
                "api_endpoints": [],
                "categories": ["agricultural", "quarantine"],
                "hs_chapters": ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24"],
                "priority": 7
            },
            
            # 화학물질 관련 (HS 28-38장)
            {
                "agency_id": "epa",
                "name": "Environmental Protection Agency",
                "short_name": "EPA",
                "description": "화학물질 등록요구사항, 환경규제",
                "website": "https://www.epa.gov",
                "api_endpoints": [
                    "https://comptox.epa.gov/dashboard/api/chemical/search",
                    "https://aqs.epa.gov/data/api/sampleData/byState"
                ],
                "categories": ["chemical", "environmental"],
                "hs_chapters": ["28", "29", "30", "31", "32", "33", "34", "35", "36", "37", "38"],
                "priority": 8
            },
            {
                "agency_id": "osha",
                "name": "Occupational Safety and Health Administration",
                "short_name": "OSHA",
                "description": "작업장 안전기준",
                "website": "https://www.osha.gov",
                "api_endpoints": [],
                "categories": ["chemical", "safety"],
                "hs_chapters": ["28", "29", "30", "31", "32", "33", "34", "35", "36", "37", "38"],
                "priority": 6
            },
            {
                "agency_id": "cpsc",
                "name": "Consumer Product Safety Commission",
                "short_name": "CPSC",
                "description": "소비자제품 안전기준",
                "website": "https://www.cpsc.gov",
                "api_endpoints": [
                    "https://www.cpsc.gov/Recalls/CPSC-Recalls-API/recalls"
                ],
                "categories": ["consumer", "safety"],
                "hs_chapters": ["84", "85", "94", "95", "96"],
                "priority": 7
            },
            
            # 전자제품 관련 (HS 84-85장)
            {
                "agency_id": "fcc",
                "name": "Federal Communications Commission",
                "short_name": "FCC",
                "description": "무선통신 인증요구사항",
                "website": "https://www.fcc.gov",
                "api_endpoints": [
                    "https://api.fcc.gov/device/authorization/grants"
                ],
                "categories": ["electronics", "telecommunications"],
                "hs_chapters": ["84", "85"],
                "priority": 8
            },
            {
                "agency_id": "ntia",
                "name": "National Telecommunications and Information Administration",
                "short_name": "NTIA",
                "description": "통신기기 규제",
                "website": "https://www.ntia.gov",
                "api_endpoints": [],
                "categories": ["electronics", "telecommunications"],
                "hs_chapters": ["84", "85"],
                "priority": 6
            },
            
            # 의료기기 관련 (HS 90-96장)
            {
                "agency_id": "cdc",
                "name": "Centers for Disease Control and Prevention",
                "short_name": "CDC",
                "description": "감염방지기준",
                "website": "https://www.cdc.gov",
                "api_endpoints": [],
                "categories": ["medical", "health"],
                "hs_chapters": ["90", "91", "92", "93", "94", "95", "96"],
                "priority": 7
            },
            {
                "agency_id": "nih",
                "name": "National Institutes of Health",
                "short_name": "NIH",
                "description": "연구용 의료기기 기준",
                "website": "https://www.nih.gov",
                "api_endpoints": [],
                "categories": ["medical", "research"],
                "hs_chapters": ["90", "91", "92", "93", "94", "95", "96"],
                "priority": 6
            },
            {
                "agency_id": "cms",
                "name": "Centers for Medicare & Medicaid Services",
                "short_name": "CMS",
                "description": "의료기기 보상기준",
                "website": "https://www.cms.gov",
                "api_endpoints": [],
                "categories": ["medical", "insurance"],
                "hs_chapters": ["90", "91", "92", "93", "94", "95", "96"],
                "priority": 5
            },
            
            # 일반 상품/통관 관련
            {
                "agency_id": "cbp",
                "name": "Customs and Border Protection",
                "short_name": "CBP",
                "description": "수입요구사항, 관세율",
                "website": "https://www.cbp.gov",
                "api_endpoints": [
                    "https://api.cbp.gov/trade/statistics/imports"
                ],
                "categories": ["trade", "customs"],
                "hs_chapters": ["99"],  # 모든 HS 코드
                "priority": 9
            },
            {
                "agency_id": "ftc",
                "name": "Federal Trade Commission",
                "short_name": "FTC",
                "description": "상품표시기준",
                "website": "https://www.ftc.gov",
                "api_endpoints": [],
                "categories": ["consumer", "labeling"],
                "hs_chapters": ["99"],  # 모든 HS 코드
                "priority": 6
            },
            {
                "agency_id": "commerce",
                "name": "Department of Commerce",
                "short_name": "Commerce",
                "description": "수출입 통계, 무역정책",
                "website": "https://www.commerce.gov",
                "api_endpoints": [],
                "categories": ["trade", "statistics"],
                "hs_chapters": ["99"],  # 모든 HS 코드
                "priority": 5
            }
        ]
        
        # 기관 데이터 삽입
        for agency_data in default_agencies:
            cursor.execute('''
                INSERT INTO government_agencies 
                (agency_id, name, short_name, description, website, api_endpoints, categories, hs_chapters, priority, is_active, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                agency_data["agency_id"],
                agency_data["name"],
                agency_data["short_name"],
                agency_data["description"],
                agency_data["website"],
                json.dumps(agency_data["api_endpoints"]),
                json.dumps(agency_data["categories"]),
                json.dumps(agency_data["hs_chapters"]),
                agency_data["priority"],
                True,
                datetime.now().isoformat()
            ))
            
            # HS 코드별 매핑 생성
            for hs_chapter in agency_data["hs_chapters"]:
                cursor.execute('''
                    INSERT OR REPLACE INTO hs_agency_mappings (hs_chapter, agency_id, priority)
                    VALUES (?, ?, ?)
                ''', (hs_chapter, agency_data["agency_id"], agency_data["priority"]))
        
        conn.commit()
        conn.close()
        print(f"✅ {len(default_agencies)}개 기본 기관 데이터 로드됨")
    
    def get_agencies_for_hs_code(self, hs_code: str) -> List[Dict[str, Any]]:
        """HS 코드에 적합한 기관 목록 반환 (우선순위 순)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        hs_chapter = hs_code[:2]
        
        # 해당 HS 챕터에 매핑된 기관들 조회
        cursor.execute('''
            SELECT ga.*, ham.priority
            FROM government_agencies ga
            JOIN hs_agency_mappings ham ON ga.agency_id = ham.agency_id
            WHERE ham.hs_chapter = ? AND ga.is_active = TRUE
            ORDER BY ham.priority DESC, ga.priority DESC
        ''', (hs_chapter,))
        
        agencies = []
        for row in cursor.fetchall():
            agency_data = {
                "agency_id": row[0],
                "name": row[1],
                "short_name": row[2],
                "description": row[3],
                "website": row[4],
                "api_endpoints": json.loads(row[5]) if row[5] else [],
                "categories": json.loads(row[6]) if row[6] else [],
                "hs_chapters": json.loads(row[7]) if row[7] else [],
                "priority": row[8],
                "is_active": bool(row[9]),
                "last_updated": row[10],
                "mapping_priority": row[11]
            }
            agencies.append(agency_data)
        
        conn.close()
        return agencies
    
    def get_all_agencies(self) -> List[Dict[str, Any]]:
        """모든 기관 목록 반환"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM government_agencies WHERE is_active = TRUE ORDER BY priority DESC')
        
        agencies = []
        for row in cursor.fetchall():
            agency_data = {
                "agency_id": row[0],
                "name": row[1],
                "short_name": row[2],
                "description": row[3],
                "website": row[4],
                "api_endpoints": json.loads(row[5]) if row[5] else [],
                "categories": json.loads(row[6]) if row[6] else [],
                "hs_chapters": json.loads(row[7]) if row[7] else [],
                "priority": row[8],
                "is_active": bool(row[9]),
                "last_updated": row[10]
            }
            agencies.append(agency_data)
        
        conn.close()
        return agencies
    
    def add_agency(self, agency_data: Dict[str, Any]):
        """새 기관 추가"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO government_agencies 
            (agency_id, name, short_name, description, website, api_endpoints, categories, hs_chapters, priority, is_active, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            agency_data["agency_id"],
            agency_data["name"],
            agency_data["short_name"],
            agency_data["description"],
            agency_data["website"],
            json.dumps(agency_data["api_endpoints"]),
            json.dumps(agency_data["categories"]),
            json.dumps(agency_data["hs_chapters"]),
            agency_data["priority"],
            True,
            datetime.now().isoformat()
        ))
        
        # HS 코드별 매핑 생성
        for hs_chapter in agency_data["hs_chapters"]:
            cursor.execute('''
                INSERT OR REPLACE INTO hs_agency_mappings (hs_chapter, agency_id, priority)
                VALUES (?, ?, ?)
            ''', (hs_chapter, agency_data["agency_id"], agency_data["priority"]))
        
        conn.commit()
        conn.close()
        print(f"✅ 기관 추가됨: {agency_data['name']}")
    
    def update_agency_priority(self, agency_id: str, new_priority: int):
        """기관 우선순위 업데이트"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE government_agencies 
            SET priority = ?, last_updated = ?
            WHERE agency_id = ?
        ''', (new_priority, datetime.now().isoformat(), agency_id))
        
        cursor.execute('''
            UPDATE hs_agency_mappings 
            SET priority = ?
            WHERE agency_id = ?
        ''', (new_priority, agency_id))
        
        conn.commit()
        conn.close()
        print(f"✅ {agency_id} 우선순위 업데이트: {new_priority}")

# 전역 인스턴스
agencies_db = GovernmentAgenciesDB()

def get_agencies_for_product(hs_code: str, product_name: str = "") -> List[Dict[str, Any]]:
    """상품에 적합한 기관 목록 반환 (LangGraph 워크플로우용)"""
    return agencies_db.get_agencies_for_hs_code(hs_code)

def get_agency_info(agency_id: str) -> Optional[Dict[str, Any]]:
    """특정 기관 정보 반환"""
    agencies = agencies_db.get_all_agencies()
    for agency in agencies:
        if agency["agency_id"] == agency_id:
            return agency
    return None

if __name__ == "__main__":
    # 테스트 실행
    db = GovernmentAgenciesDB()
    
    # 테스트 상품들
    test_products = [
        ("8471.30.01", "노트북 컴퓨터"),
        ("3304.99.00", "비타민C 세럼"),
        ("0101.21.00", "소고기"),
        ("9018.90.00", "의료기기")
    ]
    
    print("🔍 HS 코드별 적합한 기관 테스트")
    print("=" * 60)
    
    for hs_code, product_name in test_products:
        agencies = db.get_agencies_for_hs_code(hs_code)
        print(f"\n{product_name} (HS: {hs_code}):")
        
        if agencies:
            for agency in agencies[:3]:  # 상위 3개만
                print(f"  - {agency['name']} ({agency['short_name']})")
                print(f"    우선순위: {agency['mapping_priority']}")
                print(f"    설명: {agency['description']}")
                print(f"    API: {len(agency['api_endpoints'])}개")
        else:
            print("  적합한 기관 없음")
