#!/bin/bash
# 실행 중 오류가 나면 바로 중단
set -e

# 가상환경 이름
VENV_DIR=".venv"

echo "=== Python 가상환경 확인 ==="
if [ ! -d "$VENV_DIR" ]; then
    echo "가상환경이 없으므로 새로 생성합니다."
    python3 -m venv $VENV_DIR
else
    echo "기존 가상환경을 사용합니다."
fi

echo "=== 가상환경 활성화 ==="
source $VENV_DIR/bin/activate

echo "=== pip 업그레이드 ==="
pip install --upgrade pip

echo "=== requirements.txt 설치 ==="
if [ -f requirements.txt ]; then
    pip install -r requirements.txt
else
    echo "requirements.txt 파일이 없습니다."
fi

echo "=== 1_update_docs.py 실행 ==="
python3 1_update_docs.py

echo "=== 2_remove_vs.py 실행 ==="
python3 2_remove_vs.py

echo "=== 3_insert_vs.py 실행 ==="
python3 3_insert_vs.py

echo "=== 4_create_qa_json.py 실행 ==="
python3 4_create_qa_json.py

echo "=== 5_remove_qa_vs.py 실행 ==="
python3 5_remove_qa_vs.py

echo "=== 6_insert_qa_vs.py 실행 ==="
python3 6_insert_qa_vs.py

echo "모든 작업 완료"
