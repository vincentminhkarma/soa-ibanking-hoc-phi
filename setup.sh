#!/usr/bin/env bash
# Cài đặt và khởi chạy toàn bộ hệ thống bằng MỘT lệnh:
#     ./setup.sh
# Yêu cầu duy nhất: Docker Desktop (hoặc Docker Engine + Compose v2).
# Python 3.11+ là tuỳ chọn, chỉ để chạy bộ kiểm thử tự động.
# Windows: chạy trong Git Bash hoặc WSL.
set -euo pipefail
cd "$(dirname "$0")"

step() { printf '\n\033[1;35m==> %s\033[0m\n' "$1"; }
fail() { printf '\033[1;31mLỖI: %s\033[0m\n' "$1" >&2; exit 1; }

step "1/4 Kiểm tra Docker"
command -v docker >/dev/null || fail "Chưa cài Docker. Tải Docker Desktop: https://www.docker.com/products/docker-desktop/"
docker compose version >/dev/null 2>&1 || fail "Cần Docker Compose v2 (lệnh 'docker compose')."
if ! docker info >/dev/null 2>&1; then
  if [ "$(uname)" = "Darwin" ]; then
    echo "Docker chưa chạy, đang mở Docker Desktop…"
    open -a Docker
    for _ in $(seq 60); do docker info >/dev/null 2>&1 && break; sleep 2; done
  fi
  docker info >/dev/null 2>&1 || fail "Docker daemon chưa chạy. Mở Docker Desktop rồi chạy lại ./setup.sh"
fi
docker compose version

step "2/4 Cấu hình"
if [ -f .env ]; then
  echo ".env đã có, giữ nguyên."
else
  cp .env.example .env
  echo "Đã tạo .env từ .env.example (giá trị mặc định chạy được ngay)."
fi

step "3/4 Build 7 image và khởi chạy 11 container (lần đầu ~2–4 phút)"
# Tải gói pip qua mạng chập chờn có thể hỏng file (pip báo sai hash) → thử lại; phần đã build nằm trong cache.
for i in 1 2 3; do
  docker compose up -d --build --wait && break
  [ "$i" = 3 ] && fail "Build/khởi chạy thất bại sau 3 lần. Xem log: docker compose logs"
  echo "Lần $i lỗi (thường do mạng khi tải thư viện), thử lại…"
done
docker compose ps --format 'table {{.Service}}\t{{.Status}}'

step "4/4 Môi trường kiểm thử Python và giao dịch mẫu (tuỳ chọn)"
PY=""
for c in python3.11 python3 python; do
  if command -v "$c" >/dev/null && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then PY=$c; break; fi
done
if [ -z "$PY" ]; then
  echo "Không thấy Python ≥ 3.11 → bỏ qua (hệ thống vẫn chạy đầy đủ trong Docker)."
else
  "$PY" -m venv .venv
  VPY=.venv/bin/python; [ -x "$VPY" ] || VPY=.venv/Scripts/python.exe
  "$VPY" -m pip install -q --upgrade pip
  "$VPY" -m pip install -q -r tests/requirements.txt
  echo "Đã cài thư viện kiểm thử vào .venv ($("$VPY" --version))."
  echo "Chạy test: $VPY -m pytest"
  echo "Tạo lịch sử giao dịch mẫu (bỏ qua nếu đã có)…"
  "$VPY" scripts/seed_demo.py || echo "Chưa tạo được giao dịch mẫu; chạy lại sau: $VPY scripts/seed_demo.py"
fi

curl -fsS http://localhost:8080/health/services >/dev/null && HEALTH="UP" || HEALTH="chưa sẵn sàng, xem: docker compose logs"
cat <<EOF

✅ Hệ thống: $HEALTH
   Giao diện web      http://localhost:3000   (tài khoản minhnguyen / 123456)
   Hộp thư OTP        http://localhost:8025
   API Gateway        http://localhost:8080/docs
   Jaeger tracing     http://localhost:16686
   Dừng hệ thống      docker compose stop   ·   Xoá sạch dữ liệu: docker compose down -v
EOF
