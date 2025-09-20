#!/usr/bin/env python3
"""
환경변수 로딩 테스트
"""

from dotenv import load_dotenv
import os

# .env 파일 로딩
load_dotenv("../.env")

print("🔍 환경변수 테스트")
print(f"📋 TAVILY_API_KEY: {'설정됨' if os.getenv('TAVILY_API_KEY') else '설정되지 않음'}")
print(f"📋 API 키 길이: {len(os.getenv('TAVILY_API_KEY', ''))}")

if os.getenv('TAVILY_API_KEY'):
    print("✅ API 키가 정상적으로 로딩되었습니다!")
else:
    print("❌ API 키를 찾을 수 없습니다.")
