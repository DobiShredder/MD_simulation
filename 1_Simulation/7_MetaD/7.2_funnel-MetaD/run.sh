#!/usr/bin/env bash
set -euo pipefail

echo "오류: 3PTB의 alignment group, funnel axis와 wall geometry가 아직 정해지지 않았습니다." >&2
echo "download.sh로 구조를 받은 뒤 README의 geometry 항목을 먼저 결정해야 합니다." >&2
exit 1
