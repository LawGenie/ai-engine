#!/bin/bash

echo "�� Precedents Analysis AI Engine 시작 중..."

# 환경변수 확인
if [ -z "$OPENAI_API_KEY" ]; then
    echo "❌ OPENAI_API_KEY 환경변수가 설정되지 않았습니다."
    echo "다음 명령어로 설정해주세요:"
    echo "export OPENAI_API_KEY='your-openai-api-key-here'"
    echo "또는 .env 파일에 설정해주세요."
    exit 1
fi

# 의존성 설치
echo "📦 의존성 설치 중..."
pip install -r requirements.txt

# 서버 시작
echo "🌐 AI Engine 서버 시작 중... (포트: 8000)"
python main.py
