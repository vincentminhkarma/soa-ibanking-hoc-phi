# 3. Thiết kế REST API

Tài liệu tương tác (OpenAPI/Swagger) được sinh tự động cho từng service:

| Service | Swagger UI | OpenAPI JSON |
|---|---|---|
| API Gateway | <http://localhost:8080/docs> | `/openapi.json` |
| auth-service | <http://localhost:8001/docs> | `/openapi.json` |
| account-service | <http://localhost:8002/docs> | `/openapi.json` |
| tuition-service | <http://localhost:8003/docs> | `/openapi.json` |
| payment-service | <http://localhost:8004/docs> | `/openapi.json` |
| otp-service | <http://localhost:8005/docs> | `/openapi.json` |
| notification-service | <http://localhost:8006/docs> | `/openapi.json` |

`GET http://localhost:8080/services` trả về danh sách toàn bộ service kèm link tài liệu.

---

## 3.1. Quy ước chung

| Hạng mục | Quy ước |
|---|---|
| Base URL | `http://localhost:8080/api/v1` (qua API Gateway) |
| Versioning | Trên URI: `/api/v1/...` |
| Định dạng | JSON, `Content-Type: application/json`, UTF-8 |
| Xác thực | `Authorization: Bearer <JWT>` cho mọi API trừ `POST /auth/login` |
| Idempotency | Header `Idempotency-Key` (UUID) ở `POST /payments` |
| Truy vết | `X-Request-Id` trong response; OpenTelemetry truyền W3C `traceparent` giữa các service, JSON log có `trace_id`/`span_id` |
| Tài nguyên | Danh từ số nhiều: `/accounts`, `/tuitions`, `/payments` |
| Phân trang | `?limit=n` (mặc định 20–50, trần 100–200) |
| Nội bộ | `/internal/*` — chỉ service gọi nhau, yêu cầu `X-Internal-Token`, gateway chặn |

### Mẫu lỗi thống nhất

```json
{
  "error": {
    "code": "INSUFFICIENT_FUNDS",
    "message": "Số dư khả dụng không đủ để thực hiện giao dịch.",
    "details": { "balance": "500000.00", "required": "9500000.00" },
    "request_id": "3f9a1c2b7d4e5a60"
  }
}
```

### Quy ước HTTP Status Code

| Code | Dùng khi |
|---|---|
| `200 OK` | Đọc/ghi thành công |
| `201 Created` | Tạo giao dịch, tạo khoản học phí |
| `400 Bad Request` | OTP sai/hết hạn/bị khoá, chưa đồng ý điều khoản |
| `401 Unauthorized` | Thiếu token, token sai hoặc hết hạn, sai mật khẩu |
| `403 Forbidden` | Truy cập giao dịch của người khác, gọi `/internal/*` từ ngoài |
| `404 Not Found` | MSSV/giao dịch/tài khoản không tồn tại |
| `409 Conflict` | Xung đột trạng thái: hết số dư, học phí đã thanh toán, không còn công nợ |
| `422 Unprocessable Entity` | Sai kiểu/định dạng dữ liệu (validation của schema) |
| `502 Bad Gateway` | Gửi email thất bại |
| `503 Service Unavailable` | Service phụ thuộc không phản hồi |

---

## 3.2. API công khai (qua API Gateway)

### 3.2.1. Authentication — `auth-service`

| # | Method | URI | Mô tả | Auth |
|---|---|---|---|---|
| A1 | `POST` | `/api/v1/auth/login` | Đăng nhập | ❌ |
| A2 | `GET` | `/api/v1/auth/me` | Thông tin người dùng đang đăng nhập | ✔ |

**A1 · POST /api/v1/auth/login**

Request
```json
{ "username": "minhnguyen", "password": "123456" }
```

Response `200 OK`
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "user": {
    "id": "11111111-1111-1111-1111-111111111111",
    "username": "minhnguyen",
    "full_name": "Nguyễn Văn Minh",
    "phone": "0901234567",
    "email": "minhnguyen@tdtu.edu.vn"
  }
}
```

| Status | Code | Tình huống |
|---|---|---|
| 401 | `INVALID_CREDENTIALS` | Sai username hoặc password |
| 422 | `VALIDATION_ERROR` | Thiếu trường, password < 6 ký tự |

---

### 3.2.2. Account — `account-service`

| # | Method | URI | Mô tả | Auth |
|---|---|---|---|---|
| B1 | `GET` | `/api/v1/accounts/me` | Số dư khả dụng | ✔ |
| B2 | `GET` | `/api/v1/accounts/me/transactions?limit=50` | Lịch sử biến động số dư | ✔ |

**B1** → `200 OK`
```json
{ "account_id": "a0000001-...", "user_id": "11111111-...", "balance": "50000000.00", "currency": "VND" }
```

**B2** → `200 OK`
```json
{
  "items": [{
    "id": "9c1f...", "direction": "DEBIT", "amount": "9500000.00",
    "balance_after": "40500000.00", "reference": "4b2e-...",
    "description": "Thanh toán học phí HK1/2026-2027 - MSSV 522H0001",
    "created_at": "2026-09-14T08:12:31.442Z"
  }],
  "total": 1
}
```

| Status | Code | Tình huống |
|---|---|---|
| 401 | `UNAUTHORIZED` / `TOKEN_EXPIRED` | Không có/hết hạn token |
| 404 | `ACCOUNT_NOT_FOUND` | Người dùng chưa có tài khoản thanh toán |

---

### 3.2.3. Tuition — `tuition-service`

| # | Method | URI | Mô tả | Auth |
|---|---|---|---|---|
| C1 | `GET` | `/api/v1/tuitions/{student_code}` | Tra cứu sinh viên + công nợ học phí | ✔ |

**C1** → `200 OK`
```json
{
  "student": {
    "student_code": "522H0001", "full_name": "Nguyễn Văn Minh",
    "program": "Kỹ thuật phần mềm", "faculty": "Công nghệ thông tin"
  },
  "outstanding_fee": {
    "id": "f0000001-...", "student_code": "522H0001", "semester": "HK1/2026-2027",
    "amount": "9500000.00", "status": "UNPAID", "payment_ref": null, "paid_at": null
  },
  "fees": [ "... toàn bộ khoản học phí của sinh viên ..." ]
}
```
`outstanding_fee = null` nghĩa là sinh viên không còn khoản phải đóng.

| Status | Code | Tình huống |
|---|---|---|
| 404 | `STUDENT_NOT_FOUND` | MSSV không tồn tại |

---

### 3.2.4. Payment — `payment-service`

| # | Method | URI | Mô tả | Auth |
|---|---|---|---|---|
| D1 | `POST` | `/api/v1/payments` | Khởi tạo giao dịch + gửi OTP | ✔ |
| D2 | `POST` | `/api/v1/payments/{id}/confirm` | Xác thực OTP và hoàn tất giao dịch | ✔ |
| D3 | `POST` | `/api/v1/payments/{id}/otp/resend` | Gửi lại mã OTP | ✔ |
| D4 | `GET` | `/api/v1/payments/{id}` | Chi tiết giao dịch | ✔ |
| D5 | `GET` | `/api/v1/payments/{id}/events` | Nhật ký các bước xử lý (saga trace) | ✔ |
| D6 | `GET` | `/api/v1/payments?limit=20` | Lịch sử giao dịch của người dùng | ✔ |

**D1 · POST /api/v1/payments**

Headers: `Authorization: Bearer <JWT>`, `Idempotency-Key: <uuid>` *(khuyến nghị)*

Request
```json
{ "student_code": "522H0001", "accept_terms": true }
```

Response `201 Created`
```json
{
  "payment": {
    "id": "4b2e8f11-...", "status": "PENDING_OTP",
    "payer": { "name": "Nguyễn Văn Minh", "email": "minhnguyen@tdtu.edu.vn", "phone": "0901234567" },
    "student_code": "522H0001", "student_name": "Nguyễn Văn Minh",
    "fee_id": "f0000001-...", "semester": "HK1/2026-2027", "amount": "9500000.00",
    "otp_expires_at": "2026-09-14T08:17:31.442Z", "created_at": "2026-09-14T08:12:31.442Z"
  },
  "otp_sent_to": "mi*******@tdtu.edu.vn",
  "otp_ttl_seconds": 300
}
```

| Status | Code | Tình huống |
|---|---|---|
| 400 | `TERMS_NOT_ACCEPTED` | Chưa đồng ý điều khoản |
| 404 | `STUDENT_NOT_FOUND` | MSSV không tồn tại |
| 409 | `NO_OUTSTANDING_TUITION` | Học phí đã đóng / không có công nợ |
| 409 | `INSUFFICIENT_FUNDS` | Số dư < số tiền cần thanh toán |
| 503 | `SERVICE_UNAVAILABLE` | Không gọi được tuition/account/otp service |

**D2 · POST /api/v1/payments/{id}/confirm**

Request
```json
{ "otp_code": "482913" }
```

Response `200 OK` — giao dịch hoàn tất
```json
{
  "id": "4b2e8f11-...", "status": "SUCCESS",
  "payer": { "name": "Nguyễn Văn Minh", "email": "minhnguyen@tdtu.edu.vn", "phone": "0901234567" },
  "student_code": "522H0001", "student_name": "Nguyễn Văn Minh",
  "semester": "HK1/2026-2027", "amount": "9500000.00", "balance_after": "40500000.00",
  "completed_at": "2026-09-14T08:13:02.887Z"
}
```

| Status | Code | Tình huống |
|---|---|---|
| 400 | `OTP_INVALID` | Sai mã (kèm `details.remaining_attempts`) |
| 400 | `OTP_EXPIRED` | Quá 5 phút |
| 400 | `OTP_NOT_FOUND` | Không có mã hiệu lực (đã dùng / đã thu hồi) |
| 400 | `OTP_LOCKED` | Nhập sai quá 5 lần |
| 403 | `FORBIDDEN` | Giao dịch không thuộc người dùng hiện tại |
| 404 | `PAYMENT_NOT_FOUND` | Giao dịch không tồn tại |
| 409 | `INSUFFICIENT_FUNDS` | Số dư không đủ tại thời điểm trừ tiền (giao dịch song song) |
| 409 | `TUITION_ALREADY_PAID` | Học phí vừa được người khác thanh toán — **đã tự động hoàn tiền** |
| 409 | `PAYMENT_IN_PROGRESS` | Giao dịch đang xử lý |
| 422 | `VALIDATION_ERROR` | `otp_code` không phải 6 chữ số |
| 503 | `SERVICE_UNAVAILABLE` | Mất kết nối/phản hồi; giao dịch có thể vẫn `PROCESSING` để đối soát |

Lỗi kỹ thuật hoặc mã lỗi upstream chưa xác định không được hiểu là "chưa trừ tiền". Client cần đọc `GET /payments/{id}` hoặc lịch sử để lấy kết quả cuối, không tạo payment mới chỉ vì timeout. Nếu thao tác hoàn tiền cũng lỗi, payment giữ `PROCESSING` thay vì giả báo đã hoàn.

Gọi lại `confirm` cho giao dịch đã `SUCCESS` trả về `200` với chính giao dịch đó (idempotent), không trừ tiền lần hai.

**D5** → `200 OK`
```json
[
  { "step": "PAYMENT_CREATED",    "status": "OK", "detail": "fee=f000... amount=9500000.00" },
  { "step": "OTP_ISSUED",         "status": "OK", "detail": "hết hạn 2026-09-14T08:17:31Z" },
  { "step": "OTP_VERIFIED",       "status": "OK", "detail": null },
  { "step": "DEBIT",              "status": "OK", "detail": "số dư còn 40500000.00" },
  { "step": "MARK_TUITION_PAID",  "status": "OK", "detail": null },
  { "step": "PAYMENT_COMPLETED",  "status": "OK", "detail": null },
  { "step": "RECEIPT_EMAIL",      "status": "OK", "detail": null }
]
```

---

### 3.2.5. Hệ thống

| Method | URI | Mô tả |
|---|---|---|
| `GET` | `/health` | Liveness của gateway |
| `GET` | `/health/services` | Health tổng hợp; `503` nếu có service DOWN |
| `GET` | `/services` | Danh sách service + link Swagger |

---

## 3.3. API nội bộ (service-to-service)

Yêu cầu header `X-Internal-Token`. **Không** truy cập được qua gateway.

| Service | Method | URI | Mục đích |
|---|---|---|---|
| account | `GET` | `/internal/accounts/{user_id}` | Đọc số dư |
| account | `GET` | `/internal/accounts/{user_id}/entries/{reference}` | Đọc bút toán đúng tài khoản; 404 nếu không có hoặc thuộc tài khoản khác |
| payment | `POST` | `/internal/payments/reconcile?stuck_after_seconds=60` | Đối soát một lượt; ngưỡng ≥ 0, mặc định lấy cấu hình; trả `scanned` và `resolved` |
| account | `POST` | `/internal/accounts/{user_id}/debit` | Trừ tiền (idempotent theo `reference`) |
| account | `POST` | `/internal/accounts/{user_id}/credit` | Hoàn tiền — bù trừ saga |
| tuition | `GET` | `/internal/tuitions/students/{student_code}` | Đọc công nợ theo MSSV |
| tuition | `GET` | `/internal/tuitions/fees/{fee_id}` | Đọc một khoản học phí |
| tuition | `POST` | `/internal/tuitions/fees` | Tạo sinh viên/khoản học phí (admin, phục vụ test) |
| tuition | `POST` | `/internal/tuitions/fees/{fee_id}/pay` | Gạch nợ — chỉ thành công một lần |
| tuition | `POST` | `/internal/tuitions/fees/{fee_id}/revert` | Huỷ gạch nợ — bù trừ saga |
| otp | `POST` | `/internal/otp/issue` | Phát hành OTP + gửi email |
| otp | `POST` | `/internal/otp/verify` | Xác thực OTP (một lần duy nhất) |
| otp | `GET` | `/internal/otp/{payment_id}/status` | Trạng thái/hạn dùng của OTP |
| notification | `POST` | `/internal/notifications/email` | Gửi email theo template `OTP`/`RECEIPT` |
| notification | `GET` | `/internal/notifications` | Nhật ký email đã gửi |
| auth | `GET` | `/internal/users/{user_id}` | Hồ sơ người dùng |

**Ví dụ `POST /internal/accounts/{user_id}/debit`**

```json
{ "amount": "9500000.00", "reference": "4b2e8f11-...", "description": "Thanh toán học phí HK1/2026-2027 - MSSV 522H0001" }
```
```json
{ "ledger_id": "9c1f...", "balance_after": "40500000.00", "idempotent_replay": false }
```
`409 INSUFFICIENT_FUNDS` nếu số dư không đủ. Gọi lại cùng `reference` trả `idempotent_replay: true` và **không** trừ tiền thêm. Replay chỉ được công nhận khi trùng cả tài khoản, chiều và số tiền; `reference` đã thuộc về bút toán khác trả `409 REFERENCE_CONFLICT` (áp dụng cho cả `debit` lẫn `credit`).

---

## 3.4. Validation và error handling

| Tầng | Kiểm tra | Ví dụ |
|---|---|---|
| Schema (Pydantic) | Kiểu, độ dài, regex, số dương | `otp_code` khớp `^\d{6}$`; `amount > 0`, 2 chữ số thập phân |
| Nghiệp vụ (service) | Trạng thái hợp lệ | Học phí `UNPAID`, giao dịch `PENDING_OTP`, OTP còn hạn |
| Quyền | Chủ sở hữu tài nguyên | Chỉ người tạo giao dịch mới xem/xác nhận được |
| Cơ sở dữ liệu | CHECK / UNIQUE / partial index | `balance >= 0`, một `SUCCESS` cho mỗi `fee_id` |

Mọi ngoại lệ đều đi qua `install_error_handlers()` (`services/common/errors.py`) nên client **luôn** nhận đúng một cấu trúc lỗi, kể cả lỗi validation của framework hay lỗi 500 ngoài dự kiến. Lỗi nghiệp vụ từ service nội bộ được `call_service()` giữ nguyên mã lỗi khi truyền ngược lên client — ví dụ `INSUFFICIENT_FUNDS` của account-service tới thẳng trình duyệt thay vì biến thành `500`.
