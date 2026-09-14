"""Mẫu email. Giữ ở dạng f-string thuần để không kéo thêm engine template.

Mỗi renderer trả về (subject, html, text). Bản text vừa là fallback cho trình
đọc không hỗ trợ HTML, vừa giúp test tự động bóc mã OTP từ MailHog.
"""


def _money(value) -> str:
    return f"{int(float(value)):,}".replace(",", ".") + " VND"


def _wrap(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="vi"><body style="margin:0;background:#f1f5f9;padding:24px;font-family:Arial,Helvetica,sans-serif">
  <div style="max-width:560px;margin:auto;background:#fff;border-radius:12px;overflow:hidden;border:1px solid #e2e8f0">
    <div style="background:#0f3d75;color:#fff;padding:18px 24px">
      <div style="font-size:18px;font-weight:700">TDTU iBanking</div>
      <div style="font-size:13px;opacity:.85">{title}</div>
    </div>
    <div style="padding:24px;color:#0f172a;font-size:14px;line-height:1.6">{body}</div>
    <div style="padding:16px 24px;background:#f8fafc;color:#64748b;font-size:12px">
      Email tu dong tu he thong mo phong iBanking - Dai hoc Ton Duc Thang. Vui long khong tra loi email nay.
    </div>
  </div>
</body></html>"""


def otp_email(data: dict) -> tuple[str, str, str]:
    subject = f"[TDTU iBanking] Ma OTP xac thuc giao dich {data['payment_id'][:8]}"
    body = f"""
      <p>Xin chào <b>{data.get('recipient_name', '')}</b>,</p>
      <p>Bạn đang thực hiện thanh toán học phí cho sinh viên
         <b>{data.get('student_name', '')}</b> (MSSV <b>{data.get('student_code', '')}</b>)
         với số tiền <b>{_money(data.get('amount', 0))}</b>.</p>
      <p>Mã OTP xác thực giao dịch của bạn là:</p>
      <div style="font-size:32px;font-weight:700;letter-spacing:8px;color:#0f3d75;
                  background:#eff6ff;border-radius:10px;padding:16px;text-align:center">{data['otp_code']}</div>
      <p>Mã có hiệu lực trong <b>{data.get('ttl_minutes', 5)} phút</b> và chỉ sử dụng được <b>một lần</b>
         cho đúng giao dịch <code>{data['payment_id']}</code>.</p>
      <p style="color:#b91c1c">Không chia sẻ mã này cho bất kỳ ai.</p>
    """
    text = (
        f"TDTU iBanking - Xac thuc giao dich\n"
        f"PAYMENT_ID: {data['payment_id']}\n"
        f"OTP: {data['otp_code']}\n"
        f"Hieu luc: {data.get('ttl_minutes', 5)} phut, chi dung mot lan.\n"
    )
    return subject, _wrap("Xác thực giao dịch", body), text


def receipt_email(data: dict) -> tuple[str, str, str]:
    subject = f"[TDTU iBanking] Thanh toan hoc phi thanh cong - {_money(data.get('amount', 0))}"
    rows = [
        ("Mã giao dịch", data.get("payment_id", "")),
        ("Thời gian", data.get("completed_at", "")),
        ("Người nộp tiền", data.get("payer_name", "")),
        ("MSSV", data.get("student_code", "")),
        ("Sinh viên", data.get("student_name", "")),
        ("Học kỳ", data.get("semester", "")),
        ("Số tiền", _money(data.get("amount", 0))),
        ("Số dư còn lại", _money(data.get("balance_after", 0))),
    ]
    table = "".join(
        f"""<tr><td style="padding:8px 0;color:#64748b">{k}</td>
             <td style="padding:8px 0;text-align:right;font-weight:600">{v}</td></tr>"""
        for k, v in rows
    )
    body = f"""
      <p>Xin chào <b>{data.get('payer_name', '')}</b>,</p>
      <p>Giao dịch thanh toán học phí của bạn đã <b style="color:#15803d">THÀNH CÔNG</b>.</p>
      <table style="width:100%;border-collapse:collapse;font-size:14px">{table}</table>
    """
    text = (
        f"TDTU iBanking - Bien lai giao dich\n"
        f"PAYMENT_ID: {data.get('payment_id', '')}\n"
        f"STATUS: SUCCESS\n"
        f"MSSV: {data.get('student_code', '')}\n"
        f"So tien: {_money(data.get('amount', 0))}\n"
        f"So du con lai: {_money(data.get('balance_after', 0))}\n"
    )
    return subject, _wrap("Biên lai giao dịch", body), text


RENDERERS = {"OTP": otp_email, "RECEIPT": receipt_email}
