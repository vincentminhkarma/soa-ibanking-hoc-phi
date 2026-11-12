# 5. Hướng dẫn sử dụng và kịch bản demo

---

## 5.1. Tài khoản và dữ liệu mẫu

**Người dùng iBanking** — mật khẩu chung `123456`

| Username | Họ tên | SĐT | Email | Số dư ban đầu |
|---|---|---|---|---|
| `minhnguyen` | Nguyễn Văn Minh | 0901234567 | minhnguyen@tdtu.edu.vn | 50.000.000 ₫ |
| `thuha` | Trần Thu Hà | 0912345678 | thuha@tdtu.edu.vn | 20.000.000 ₫ |
| `quocbao` | Võ Quốc Bảo | 0923456789 | quocbao@tdtu.edu.vn | 15.000.000 ₫ |
| `itdu` | Lê Ít Dư | 0934567890 | itdu@tdtu.edu.vn | 1.000.000 ₫ |
| `ngoclan` | Phạm Ngọc Lan | 0945678901 | ngoclan@tdtu.edu.vn | 30.000.000 ₫ |
| `ducthinh` | Hoàng Đức Thịnh | 0956789012 | ducthinh@tdtu.edu.vn | 25.000.000 ₫ |
| `hoangyen` | Đỗ Hoàng Yến | 0967890123 | hoangyen@tdtu.edu.vn | 18.000.000 ₫ |
| `giahan` | Lý Gia Hân | 0978901234 | giahan@tdtu.edu.vn | 40.000.000 ₫ |
| `tuananh` | Bùi Tuấn Anh | 0989012345 | tuananh@tdtu.edu.vn | 22.000.000 ₫ |
| `camtu` | Trịnh Cẩm Tú | 0990123456 | camtu@tdtu.edu.vn | 12.000.000 ₫ |

**Sinh viên và học phí** — học kỳ `HK1/2026-2027`

| MSSV | Họ tên sinh viên | Học phí | Trạng thái | Dùng để demo |
|---|---|---|---|---|
| `522H0001` | Nguyễn Văn Minh | 9.500.000 ₫ | UNPAID | Luồng thành công |
| `522H0002` | Trần Thu Hà | 8.750.000 ₫ | UNPAID | Thanh toán cho người khác |
| `522H0003` | Phạm Minh Tuấn | 10.200.000 ₫ | UNPAID | Dự phòng |
| `522H0004` | Lê Thị Lan | 7.300.000 ₫ | **PAID** | Học phí đã đóng |
| `522H0005` | Võ Quốc Bảo | 11.000.000 ₫ | UNPAID | Hai người cùng đóng |

Dữ liệu gốc còn 25 sinh viên khác (`522H0006` – `522L0030`, 7 khoa; 16 UNPAID, 9 PAID) khai báo trong `services/tuition-service/app/seed.py`. `./setup.sh` chạy thêm `scripts/seed_demo.py`: sáu tài khoản phụ thanh toán 9 khoản trong số này qua luồng thật để có sẵn lịch sử giao dịch, còn lại 7 khoản UNPAID.

---

## 5.2. Hướng dẫn sử dụng hệ thống

### Bước 1 — Đăng nhập
Mở <http://localhost:3000>, nhập username/password. Sau khi đăng nhập, thanh trên cùng hiển thị họ tên và **số dư khả dụng**.

### Bước 2 — Thông tin người nộp tiền
Khối **(a) Người nộp tiền** tự động điền họ tên, số điện thoại, email từ tài khoản đang đăng nhập và **không cho chỉnh sửa** — đúng yêu cầu đề bài.

### Bước 3 — Tra cứu học phí
Nhập MSSV vào khối **(b) Thông tin học phí** rồi bấm **Tra cứu** (hoặc Enter). Hệ thống hiển thị họ tên sinh viên, ngành/khoa, học kỳ và **số tiền học phí còn phải thanh toán**.
Nếu MSSV không tồn tại → thông báo lỗi; nếu đã đóng đủ → cảnh báo "không còn khoản học phí cần thanh toán".

### Bước 4 — Xác nhận giao dịch
Khối **(c) Thông tin thanh toán** hiển thị số dư khả dụng, số tiền cần thanh toán và số dư dự kiến sau giao dịch. Tick **đồng ý điều khoản** (bấm vào liên kết để đọc). Nút **Xác nhận giao dịch** chỉ bật khi:
1. đã tra cứu được khoản học phí **chưa thanh toán**;
2. **số dư ≥ số tiền** cần thanh toán;
3. đã đồng ý điều khoản.

Dòng gợi ý dưới nút luôn cho biết còn thiếu điều kiện nào.

### Bước 5 — Nhập OTP
Hệ thống gửi **mã OTP 6 chữ số** tới email người nộp tiền và mở hộp thoại xác thực kèm **đồng hồ đếm ngược 5 phút**.
Mở **MailHog** tại <http://localhost:8025> để đọc email và lấy mã. Có thể bấm **Gửi lại mã** — mã cũ lập tức mất hiệu lực.

### Bước 6 — Kết quả
Xác thực đúng → hộp thoại **Giao dịch thành công** hiển thị mã giao dịch, số tiền, số dư còn lại, kèm mục **"Xem các bước xử lý (saga trace)"**.
Email biên lai được gửi ngay sau đó (xem trong MailHog).

### Bước 7 — Lịch sử
Tab **Lịch sử giao dịch** gồm hai bảng: danh sách giao dịch học phí (kèm trạng thái) và biến động số dư (ghi nợ/ghi có). Bấm **Chi tiết** để xem lại saga trace của bất kỳ giao dịch nào.

---

## 5.3. Kịch bản demo trước hội đồng (≈ 10 phút)

### Màn 1 — Kiến trúc (1 phút)
```bash
curl -s http://localhost:8080/health/services | python3 -m json.tool
docker compose ps
```
Chỉ ra 11 container đang chạy: 6 microservice, gateway, PostgreSQL (6 database), MailHog, web và Jaeger; đối chiếu sơ đồ ở [02-kien-truc-microservices.md](02-kien-truc-microservices.md).

### Màn 2 — Luồng thành công (2 phút)
Đăng nhập `minhnguyen` → tra cứu `522H0001` → xác nhận → lấy OTP trong MailHog → hoàn tất.
Nhấn mạnh: số dư giảm đúng 9.500.000 ₫, học phí chuyển **PAID**, lịch sử có bản ghi, email biên lai đã tới.

### Màn 3 — Thanh toán cho sinh viên khác (30 giây)
Vẫn tài khoản `minhnguyen`, tra cứu `522H0002` → thanh toán hộ. Chứng minh yêu cầu "thanh toán cho chính mình hoặc sinh viên khác".

### Màn 4 — Các ràng buộc OTP (1,5 phút)
- Nhập sai mã → `Mã OTP không đúng` kèm số lần thử còn lại.
- Bấm **Gửi lại mã**, dùng mã cũ → bị từ chối.
- Tra cứu `522H0004` (đã đóng) → hệ thống chặn ngay từ bước tra cứu.

### Màn 5 — Concurrency 5.1 và 5.2 (3 phút) ⭐
```bash
pytest tests/test_03_concurrency.py -v
```
Vừa chạy vừa giải thích:
- `test_51...`: hai giao dịch trên cùng tài khoản, số dư chỉ đủ một → 1 SUCCESS, 1 `INSUFFICIENT_FUNDS`, số dư cuối bằng 0.
- `test_52...`: hai người cùng đóng một khoản học phí → 1 SUCCESS, 1 `TUITION_ALREADY_PAID` **và được hoàn tiền**.
- `test_xac_nhan_trung_lap...`: bấm xác nhận 3 lần cùng lúc → chỉ trừ tiền một lần.

Sau đó mở giao diện, xem **saga trace** của giao dịch thất bại để chỉ ra chuỗi `DEBIT → MARK_TUITION_PAID(FAILED) → REFUND(COMPENSATED)` và dòng hoàn tiền trong bảng biến động số dư.

*Làm thủ công nếu muốn:* mở hai trình duyệt (một cửa sổ ẩn danh), đăng nhập `minhnguyen` và `thuha`, cả hai cùng tra cứu `522H0005`, cùng tạo giao dịch, lấy hai mã OTP trong MailHog, rồi bấm **Xác nhận** gần như đồng thời.

### Màn 6 — Toàn bộ test tự động (1 phút)
```bash
pytest -v
```

### Màn 7 — Unit test và test pyramid
```bash
pytest tests/unit -v
pytest -m unit -v
```
Unit test kiểm tra logic thuần (OTP, JWT, email, quyết định đối soát) và tracing in-memory, không cần Docker. Integration test kiểm tra HTTP/PostgreSQL và lỗi giữa saga; E2E đi từ tạo payment qua OTP/email đến số dư/công nợ/biên lai. Concurrency test thuộc tầng integration, không phải một tầng riêng của pyramid. Mục tiêu là nhiều phản hồi nhanh ở tầng unit, giữ test xuyên dịch vụ cho những tính chất không thể chứng minh bằng mock.

### Màn 8 — Jaeger và phục hồi giao dịch treo
1. Mở <http://localhost:16686>, chọn service `api-gateway`, thực hiện một luồng thanh toán mới và tìm trace theo thời gian.
2. Mở waterfall: gateway → payment → account/tuition/otp/notification, kiểm tra cùng trace ID và quan hệ parent-child.
3. Chạy `pytest tests/test_04_reconciliation.py tests/test_06_saga_recovery.py -v` để kiểm tra trạng thái sau crash và mất phản hồi sau commit; test nền chờ job tự xử lý thay vì chỉ gọi API thủ công. `pytest tests/test_05_tracing.py -v` kiểm tra tự động trace xuyên service.
4. Đối chiếu balance, ledger, trạng thái fee/payment và span `payment.reconcile`.

### Màn 9 — Tài liệu API (1 phút)
Mở <http://localhost:8004/docs> (payment-service) — Swagger sinh tự động, có request/response model, mã lỗi và mô tả từng endpoint.

---

## 5.4. Câu hỏi thường gặp khi bảo vệ

**Hỏi: Vì sao không dùng một transaction duy nhất cho cả hệ thống?**
Mỗi service có database riêng nên không thể dùng một transaction ACID xuyên service. Hệ thống dùng saga có bù trừ: mỗi bước là một transaction cục bộ ACID, nếu bước sau hỏng thì hoàn tác bước trước bằng nghiệp vụ nghịch đảo (hoàn tiền). Xem [04-transaction-concurrency.md](04-transaction-concurrency.md).

**Hỏi: Nếu hệ thống sập ngay sau khi trừ tiền thì sao?**
Job đối soát **đã được hiện thực** trong payment-service: mặc định chạy mỗi 30 giây, xét `PROCESSING` cũ hơn 60 giây. Job đọc công nợ và cả bút toán debit/refund: hoàn tất nếu đã gạch nợ và chưa hoàn tiền; hoàn tiền nếu chỉ mới debit; huỷ gạch nợ nếu không còn khoản tiền tương ứng. Mỗi payment được khóa riêng để không tranh chấp với foreground/worker khác. Nếu dependency chưa phục hồi, job giữ trạng thái để thử lại. Xem mục 4.7 về giới hạn RPC đang bay và biên lai best-effort.

**Hỏi: OTP có an toàn không?**
Mã không lưu dạng plaintext (SHA-256 kèm pepper), gắn cứng với `payment_id`, có partial unique index đảm bảo không trùng mã giữa các giao dịch còn hiệu lực, hết hạn sau 5 phút, chỉ dùng được một lần, và bị khoá sau 5 lần nhập sai.

**Hỏi: Tại sao trừ tiền trước rồi mới gạch nợ?**
Debit là thao tác có thể bù trừ bằng credit cùng reference; đặt nó trước giúp tránh gạch nợ khi tài khoản không đủ tiền. Nếu kết quả remote chưa rõ thì giữ `PROCESSING` và đối soát, không khẳng định mọi lỗi đều được xử lý tức thời; xem giới hạn ở mục 4.7.

**Hỏi: Đây có thực sự là microservices không, hay chỉ là monolith chia thư mục?**
Mỗi service là một container riêng, một database riêng, một tiến trình riêng, chỉ giao tiếp qua REST; có thể tắt một service và thấy đúng service phụ thuộc trả `503 SERVICE_UNAVAILABLE`:
```bash
docker compose stop tuition-service
curl -i http://localhost:8080/api/v1/tuitions/522H0001 -H "Authorization: Bearer <token>"
docker compose start tuition-service
```
