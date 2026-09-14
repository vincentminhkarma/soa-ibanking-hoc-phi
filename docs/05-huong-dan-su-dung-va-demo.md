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

**Sinh viên và học phí** — học kỳ `HK1/2026-2027`

| MSSV | Họ tên sinh viên | Học phí | Trạng thái | Dùng để demo |
|---|---|---|---|---|
| `522H0001` | Nguyễn Văn Minh | 9.500.000 ₫ | UNPAID | Luồng thành công |
| `522H0002` | Trần Thu Hà | 8.750.000 ₫ | UNPAID | Thanh toán cho người khác |
| `522H0003` | Phạm Minh Tuấn | 10.200.000 ₫ | UNPAID | Dự phòng |
| `522H0004` | Lê Thị Lan | 7.300.000 ₫ | **PAID** | Học phí đã đóng |
| `522H0005` | Võ Quốc Bảo | 11.000.000 ₫ | UNPAID | Hai người cùng đóng |

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
Chỉ ra 6 microservice + gateway + database riêng + MailHog đang chạy, và sơ đồ kiến trúc ở [02-kien-truc-microservices.md](02-kien-truc-microservices.md).

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

### Màn 7 — Tài liệu API (1 phút)
Mở <http://localhost:8004/docs> (payment-service) — Swagger sinh tự động, có request/response model, mã lỗi và mô tả từng endpoint.

---

## 5.4. Câu hỏi thường gặp khi bảo vệ

**Hỏi: Vì sao không dùng một transaction duy nhất cho cả hệ thống?**
Mỗi service có database riêng nên không thể dùng một transaction ACID xuyên service. Hệ thống dùng saga có bù trừ: mỗi bước là một transaction cục bộ ACID, nếu bước sau hỏng thì hoàn tác bước trước bằng nghiệp vụ nghịch đảo (hoàn tiền). Xem [04-transaction-concurrency.md](04-transaction-concurrency.md).

**Hỏi: Nếu hệ thống sập ngay sau khi trừ tiền thì sao?**
Giao dịch nằm lại ở trạng thái `PROCESSING` với bút toán `DEBIT` đã ghi. Vì mọi bước idempotent theo `payment_id`, một job đối soát có thể chạy tiếp hoặc bù trừ an toàn. Bảng `payment_events` chỉ rõ giao dịch dừng ở bước nào. (Job đối soát tự động là phần mở rộng ngoài phạm vi đồ án.)

**Hỏi: OTP có an toàn không?**
Mã không lưu dạng plaintext (SHA-256 kèm pepper), gắn cứng với `payment_id`, có partial unique index đảm bảo không trùng mã giữa các giao dịch còn hiệu lực, hết hạn sau 5 phút, chỉ dùng được một lần, và bị khoá sau 5 lần nhập sai.

**Hỏi: Tại sao trừ tiền trước rồi mới gạch nợ?**
Tiền có thể hoàn lại an toàn, còn trạng thái học phí không nên nhấp nháy PAID → UNPAID. Thứ tự này khiến mọi kịch bản lỗi đều kết thúc ở trạng thái an toàn cho người dùng.

**Hỏi: Đây có thực sự là microservices không, hay chỉ là monolith chia thư mục?**
Mỗi service là một container riêng, một database riêng, một tiến trình riêng, chỉ giao tiếp qua REST; có thể tắt một service và thấy đúng service phụ thuộc trả `503 SERVICE_UNAVAILABLE`:
```bash
docker compose stop tuition-service
curl -i http://localhost:8080/api/v1/tuitions/522H0001 -H "Authorization: Bearer <token>"
docker compose start tuition-service
```
