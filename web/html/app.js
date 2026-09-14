/* Web client cho phân hệ thanh toán học phí.
   Chỉ nói chuyện với API Gateway qua /api/v1/* (nginx proxy sang gateway). */
"use strict";

const $ = (id) => document.getElementById(id);
const money = (v) => new Intl.NumberFormat("vi-VN").format(Math.round(Number(v || 0))) + " ₫";
const when = (iso) => (iso ? new Date(iso).toLocaleString("vi-VN") : "—");

const state = {
  token: sessionStorage.getItem("token") || null,
  user: JSON.parse(sessionStorage.getItem("user") || "null"),
  balance: 0,
  lookup: null,     // kết quả tra cứu MSSV
  payment: null,    // giao dịch đang chờ OTP
  countdown: null,
};

/* ------------------------------------------------------------------ API */
async function api(path, { method = "GET", body, headers = {} } = {}) {
  const res = await fetch("/api/v1" + path, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(state.token ? { Authorization: "Bearer " + state.token } : {}),
      ...headers,
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  let data = null;
  try { data = await res.json(); } catch (_) { /* 204 hoặc body rỗng */ }

  if (!res.ok) {
    if (res.status === 401 && state.token) { logout(); }
    const err = data && data.error ? data.error : {};
    throw Object.assign(new Error(err.message || `Lỗi ${res.status}`), {
      code: err.code || "UNKNOWN", details: err.details || {}, status: res.status,
    });
  }
  return data;
}

function showError(el, message) { el.textContent = message; el.classList.remove("hidden"); }
function hide(el) { el.classList.add("hidden"); }

let toastTimer;
function toast(message) {
  const t = $("toast");
  t.textContent = message;
  t.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.add("hidden"), 3200);
}

/* ------------------------------------------------------------ ĐĂNG NHẬP */
$("form-login").addEventListener("submit", async (e) => {
  e.preventDefault();
  hide($("login-error"));
  const btn = $("btn-login");
  btn.disabled = true; btn.textContent = "Đang đăng nhập…";
  try {
    const data = await api("/auth/login", {
      method: "POST",
      body: { username: $("login-username").value.trim(), password: $("login-password").value },
    });
    state.token = data.access_token;
    state.user = data.user;
    sessionStorage.setItem("token", state.token);
    sessionStorage.setItem("user", JSON.stringify(state.user));
    await enterApp();
  } catch (err) {
    showError($("login-error"), err.message);
  } finally {
    btn.disabled = false; btn.textContent = "Đăng nhập";
  }
});

function logout() {
  sessionStorage.clear();
  state.token = null; state.user = null; state.payment = null; state.lookup = null;
  $("view-app").classList.add("hidden");
  $("view-login").classList.remove("hidden");
  hide($("modal-otp")); hide($("modal-result"));
}
$("btn-logout").addEventListener("click", logout);

async function enterApp() {
  $("view-login").classList.add("hidden");
  $("view-app").classList.remove("hidden");
  $("hdr-name").textContent = state.user.full_name;
  $("payer-name").textContent = state.user.full_name;
  $("payer-phone").textContent = state.user.phone;
  $("payer-email").textContent = state.user.email;
  await refreshAccount();
  await refreshHistory();
}

async function refreshAccount() {
  const acc = await api("/accounts/me");
  state.balance = Number(acc.balance);
  $("hdr-balance").textContent = money(state.balance);
  $("pay-balance").textContent = money(state.balance);
  updateConfirmButton();
}

/* ------------------------------------------------------------- TRA CỨU */
$("btn-lookup").addEventListener("click", lookupTuition);
$("mssv").addEventListener("keydown", (e) => { if (e.key === "Enter") lookupTuition(); });

async function lookupTuition() {
  const code = $("mssv").value.trim().toUpperCase();
  hide($("lookup-error")); hide($("fee-status")); hide($("pay-error"));
  state.lookup = null;
  $("fee-box").classList.add("hidden");
  updateConfirmButton();
  if (!code) { showError($("lookup-error"), "Vui lòng nhập MSSV."); return; }

  const btn = $("btn-lookup");
  btn.disabled = true; btn.textContent = "Đang tra…";
  try {
    const data = await api("/tuitions/" + encodeURIComponent(code));
    state.lookup = data;
    $("fee-student").textContent = data.student.full_name;
    $("fee-program").textContent = `${data.student.program} — ${data.student.faculty}`;
    $("fee-box").classList.remove("hidden");

    if (data.outstanding_fee) {
      $("fee-semester").textContent = data.outstanding_fee.semester;
      $("fee-amount").textContent = money(data.outstanding_fee.amount);
      $("pay-amount").textContent = money(data.outstanding_fee.amount);
      $("pay-after").textContent = money(state.balance - Number(data.outstanding_fee.amount));
    } else {
      const paid = data.fees[data.fees.length - 1];
      $("fee-semester").textContent = paid ? paid.semester : "—";
      $("fee-amount").textContent = "0 ₫";
      $("pay-amount").textContent = "0 ₫";
      $("pay-after").textContent = money(state.balance);
      showError($("fee-status"), "Sinh viên này không còn khoản học phí cần thanh toán.");
      $("fee-status").className = "alert alert-warn";
    }
  } catch (err) {
    showError($("lookup-error"), err.message);
  } finally {
    btn.disabled = false; btn.textContent = "Tra cứu";
    updateConfirmButton();
  }
}

/* ------------------------------------------- ĐIỀU KIỆN BẬT NÚT XÁC NHẬN */
$("chk-terms").addEventListener("change", updateConfirmButton);
$("link-terms").addEventListener("click", (e) => {
  e.preventDefault();
  alert(
    "THỎA THUẬN VÀ ĐIỀU KHOẢN\n\n" +
    "1. Giao dịch thanh toán toàn bộ khoản học phí, không hỗ trợ thanh toán một phần.\n" +
    "2. Giao dịch cần được xác thực bằng mã OTP gửi qua email, hiệu lực 5 phút và chỉ dùng một lần.\n" +
    "3. Số tiền được trừ trực tiếp từ số dư khả dụng của tài khoản đang đăng nhập.\n" +
    "4. Giao dịch đã thành công không thể hoàn tác trên hệ thống iBanking."
  );
});

function confirmBlocker() {
  if (!state.lookup) return "Chưa tra cứu MSSV.";
  if (!state.lookup.outstanding_fee) return "Sinh viên không còn khoản học phí cần thanh toán.";
  if (state.balance < Number(state.lookup.outstanding_fee.amount)) return "Số dư khả dụng không đủ.";
  if (!$("chk-terms").checked) return "Bạn cần đồng ý với điều khoản giao dịch.";
  return null;
}

function updateConfirmButton() {
  const blocker = confirmBlocker();
  $("btn-confirm").disabled = blocker !== null;
  $("confirm-hint").textContent =
    blocker || "Thông tin hợp lệ. Bấm “Xác nhận giao dịch” để nhận mã OTP qua email.";
}

/* ------------------------------------------------------- TẠO GIAO DỊCH */
$("btn-confirm").addEventListener("click", async () => {
  hide($("pay-error"));
  const btn = $("btn-confirm");
  btn.disabled = true; btn.textContent = "Đang tạo giao dịch…";
  try {
    const data = await api("/payments", {
      method: "POST",
      // Idempotency-Key: bấm hai lần / mạng chập chờn cũng chỉ tạo một giao dịch.
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: { student_code: state.lookup.student.student_code, accept_terms: true },
    });
    state.payment = data.payment;
    openOtpModal(data);
  } catch (err) {
    showError($("pay-error"), err.message);
    if (err.code === "TUITION_ALREADY_PAID" || err.code === "NO_OUTSTANDING_TUITION") lookupTuition();
  } finally {
    btn.textContent = "Xác nhận giao dịch";
    updateConfirmButton();
  }
});

/* ------------------------------------------------------------ MODAL OTP */
function openOtpModal(data) {
  $("otp-email").textContent = data.otp_sent_to || state.user.email;
  $("otp-student").textContent = `${state.payment.student_name} (${state.payment.student_code})`;
  $("otp-amount").textContent = money(state.payment.amount);
  $("otp-payment-id").textContent = state.payment.id;
  $("otp-code").value = "";
  hide($("otp-error"));
  $("modal-otp").classList.remove("hidden");
  $("otp-code").focus();
  startCountdown(state.payment.otp_expires_at);
}

function startCountdown(expiresAt) {
  clearInterval(state.countdown);
  const end = new Date(expiresAt).getTime();
  const tick = () => {
    const left = Math.max(0, Math.floor((end - Date.now()) / 1000));
    const mm = String(Math.floor(left / 60)).padStart(2, "0");
    const ss = String(left % 60).padStart(2, "0");
    $("otp-countdown").textContent = `${mm}:${ss}`;
    if (left <= 0) {
      clearInterval(state.countdown);
      showError($("otp-error"), "Mã OTP đã hết hạn. Vui lòng bấm “Gửi lại mã”.");
    }
  };
  tick();
  state.countdown = setInterval(tick, 1000);
}

$("btn-otp-cancel").addEventListener("click", () => {
  clearInterval(state.countdown);
  hide($("modal-otp"));
  toast("Đã huỷ xác thực. Giao dịch vẫn ở trạng thái chờ OTP trong lịch sử.");
  refreshHistory();
});

$("btn-otp-resend").addEventListener("click", async () => {
  const btn = $("btn-otp-resend");
  btn.disabled = true;
  hide($("otp-error"));
  try {
    const data = await api(`/payments/${state.payment.id}/otp/resend`, { method: "POST" });
    state.payment = data.payment;
    $("otp-email").textContent = data.otp_sent_to;
    $("otp-code").value = "";
    startCountdown(state.payment.otp_expires_at);
    toast("Đã gửi lại mã OTP mới. Mã cũ không còn hiệu lực.");
  } catch (err) {
    showError($("otp-error"), err.message);
  } finally {
    btn.disabled = false;
  }
});

$("otp-code").addEventListener("input", (e) => {
  e.target.value = e.target.value.replace(/\D/g, "").slice(0, 6);
});
$("otp-code").addEventListener("keydown", (e) => { if (e.key === "Enter") $("btn-otp-submit").click(); });

$("btn-otp-submit").addEventListener("click", async () => {
  const code = $("otp-code").value.trim();
  hide($("otp-error"));
  if (!/^\d{6}$/.test(code)) { showError($("otp-error"), "Mã OTP gồm đúng 6 chữ số."); return; }

  const btn = $("btn-otp-submit");
  btn.disabled = true; btn.textContent = "Đang xử lý…";
  try {
    const payment = await api(`/payments/${state.payment.id}/confirm`, {
      method: "POST", body: { otp_code: code },
    });
    clearInterval(state.countdown);
    hide($("modal-otp"));
    await showResult(payment, true);
  } catch (err) {
    // Lỗi nghiệp vụ chặn hẳn giao dịch thì đóng modal và hiện kết quả thất bại.
    const fatal = ["INSUFFICIENT_FUNDS", "TUITION_ALREADY_PAID", "PAYMENT_FAILED", "OTP_LOCKED"];
    if (fatal.includes(err.code)) {
      clearInterval(state.countdown);
      hide($("modal-otp"));
      await showResult({ ...state.payment, status: "FAILED", failure_reason: err.message }, false);
    } else {
      showError($("otp-error"), err.message +
        (err.details && err.details.remaining_attempts !== undefined
          ? ` (còn ${err.details.remaining_attempts} lần thử)` : ""));
    }
  } finally {
    btn.disabled = false; btn.textContent = "Xác nhận";
  }
});

/* --------------------------------------------------------- MODAL KẾT QUẢ */
async function showResult(payment, ok) {
  $("result-icon").textContent = ok ? "✓" : "✕";
  $("result-icon").className = "result-icon" + (ok ? "" : " fail");
  $("result-title").textContent = ok ? "Giao dịch thành công" : "Giao dịch không thành công";
  $("result-message").textContent = ok
    ? "Học phí đã được gạch nợ và biên lai đã gửi tới email của bạn."
    : (payment.failure_reason || "Giao dịch đã bị từ chối.");

  const rows = [
    ["Mã giao dịch", payment.id],
    ["MSSV", payment.student_code],
    ["Sinh viên", payment.student_name],
    ["Số tiền", money(payment.amount)],
  ];
  if (ok) {
    rows.push(["Số dư còn lại", money(payment.balance_after)]);
    rows.push(["Thời gian", when(payment.completed_at)]);
  }
  $("result-details").innerHTML = rows
    .map(([k, v]) => `<div><span>${k}</span><b>${v}</b></div>`).join("");

  try {
    const events = await api(`/payments/${payment.id}/events`);
    $("trace-body").innerHTML = events.map((e) => `
      <div class="trace-item ${e.status.toLowerCase()}">
        <div class="dot"></div>
        <div><b>${e.step}</b> — ${e.status}
          ${e.detail ? `<div class="muted small">${e.detail}</div>` : ""}
          <div class="muted small">${when(e.created_at)}</div>
        </div>
      </div>`).join("");
    $("result-trace").classList.remove("hidden");
  } catch (_) {
    $("result-trace").classList.add("hidden");
  }

  $("modal-result").classList.remove("hidden");
  await refreshAccount();
  await refreshHistory();
}

$("btn-result-close").addEventListener("click", async () => {
  hide($("modal-result"));
  state.payment = null;
  $("chk-terms").checked = false;
  if (state.lookup) await lookupTuition();
  updateConfirmButton();
});

/* ------------------------------------------------------------- LỊCH SỬ */
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    const pay = tab.dataset.tab === "pay";
    $("tab-pay").classList.toggle("hidden", !pay);
    $("tab-history").classList.toggle("hidden", pay);
    if (!pay) refreshHistory();
  });
});

const BADGE = { SUCCESS: "badge-success", FAILED: "badge-failed", PENDING_OTP: "badge-pending", PROCESSING: "badge-pending" };
const LABEL = { SUCCESS: "Thành công", FAILED: "Thất bại", PENDING_OTP: "Chờ OTP", PROCESSING: "Đang xử lý" };

async function refreshHistory() {
  const [payments, ledger] = await Promise.all([
    api("/payments?limit=50"),
    api("/accounts/me/transactions?limit=50"),
  ]);

  const pbody = document.querySelector("#tbl-payments tbody");
  pbody.innerHTML = payments.items.length
    ? payments.items.map((p) => `
        <tr>
          <td>${when(p.created_at)}</td>
          <td class="mono">${p.student_code}</td>
          <td>${p.student_name}</td>
          <td class="right">${money(p.amount)}</td>
          <td><span class="badge ${BADGE[p.status] || ""}">${LABEL[p.status] || p.status}</span></td>
          <td class="right"><button class="btn-link" data-payment="${p.id}">Chi tiết</button></td>
        </tr>`).join("")
    : `<tr><td colspan="6" class="empty">Chưa có giao dịch nào.</td></tr>`;

  pbody.querySelectorAll("[data-payment]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const p = await api("/payments/" + btn.dataset.payment);
      await showResult(p, p.status === "SUCCESS");
    });
  });

  const lbody = document.querySelector("#tbl-ledger tbody");
  lbody.innerHTML = ledger.items.length
    ? ledger.items.map((t) => `
        <tr>
          <td>${when(t.created_at)}</td>
          <td>${t.description}</td>
          <td class="right ${t.direction === "DEBIT" ? "amount-out" : "amount-in"}">
            ${t.direction === "DEBIT" ? "−" : "+"}${money(t.amount)}
          </td>
          <td class="right">${money(t.balance_after)}</td>
        </tr>`).join("")
    : `<tr><td colspan="4" class="empty">Chưa có biến động số dư.</td></tr>`;
}

/* ------------------------------------------------------------ KHỞI ĐỘNG */
if (state.token && state.user) {
  enterApp().catch(logout);
}
