"""PostgreSQL/HTTP thật; chỉ chèn mất phản hồi sau khi thao tác remote đã commit."""
import importlib
import importlib.util
import logging
import os
import sys
import threading
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from conftest import ACCOUNT_URL, INTERNAL_HEADERS, TUITION_URL, Client, fee_state, new_fee, read_otp, top_up
from common.errors import APIError
from common.security import CurrentUser


@pytest.fixture(scope="module", autouse=True)
def payment_runtime():
    global payment_main, payment_reconcile, ConfirmPaymentRequest, IsolatedSession
    from sqlalchemy.orm import sessionmaker
    from common import config, http

    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    dsn = os.getenv("PAYMENT_DSN", "postgresql://ibanking:ibanking@localhost:5433/paymentdb")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(config, "DATABASE_URL", dsn.replace("postgresql://", "postgresql+psycopg://"))
        patch.setattr(config, "ACCOUNT_SERVICE_URL", ACCOUNT_URL)
        patch.setattr(config, "TUITION_SERVICE_URL", TUITION_URL)
        patch.setattr(config, "OTP_SERVICE_URL", os.getenv("OTP_URL", "http://localhost:8005"))
        patch.setattr(config, "NOTIFICATION_SERVICE_URL", os.getenv("NOTIFICATION_URL", "http://localhost:8006"))
        patch.setattr(http, "INTERNAL_TOKEN", INTERNAL_HEADERS["X-Internal-Token"])
        patch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        directory = Path(__file__).resolve().parents[1] / "services/payment-service/app"
        name = "isolated_payment_saga"
        spec = importlib.util.spec_from_file_location(name, directory / "__init__.py", submodule_search_locations=[str(directory)])
        package = importlib.util.module_from_spec(spec)
        patch.setitem(sys.modules, name, package)
        spec.loader.exec_module(package)
        payment_main = importlib.import_module(f"{name}.main")
        payment_reconcile = importlib.import_module(f"{name}.reconciliation")
        ConfirmPaymentRequest = payment_main.ConfirmPaymentRequest
        from common.db import engine
        IsolatedSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        root.handlers, root.level = handlers, level
        yield
        engine.dispose()


def _as_current_user(client: Client) -> CurrentUser:
    u = client.user
    return CurrentUser(
        user_id=u["id"],
        username=u.get("username", ""),
        full_name=u.get("full_name", ""),
        email=u.get("email", ""),
        phone=u.get("phone", ""),
    )


@pytest.fixture
def pending_payment(alice: Client):
    """Tạo khoản học phí và giao dịch PENDING_OTP qua API thông thường."""
    fee = new_fee("750000.00", prefix="SG")
    top_up(alice.user["id"], "1500000.00", f"topup-saga-{fee['id']}")
    payment = alice.create_payment(fee["student_code"]).json()["payment"]
    otp = read_otp(payment["id"])
    return fee, payment, otp


def test_loss_after_debit_recovery_refunds(alice: Client, pending_payment, monkeypatch):
    """Mất kết nối sau khi trừ tiền thành công: giao dịch giữ PROCESSING -> đối soát hoàn tiền."""
    fee, payment, otp = pending_payment
    so_du_ban_dau = alice.balance()
    real_call_service = payment_main.call_service

    def mock_call_service(method, url, **kwargs):
        res = real_call_service(method, url, **kwargs)
        if "/debit" in url:
            raise APIError(503, "SERVICE_UNAVAILABLE", "Gián đoạn mạng sau khi tài khoản đã bị trừ tiền")
        return res

    monkeypatch.setattr(payment_main, "call_service", mock_call_service)

    user = _as_current_user(alice)
    req = ConfirmPaymentRequest(otp_code=otp)
    with pytest.raises(APIError) as exc_info:
        with IsolatedSession() as db:
            payment_main.confirm_payment(payment["id"], req, user=user, db=db)

    assert exc_info.value.code == "SERVICE_UNAVAILABLE"
    # Tiền đã trừ nhưng payment giữ PROCESSING
    assert alice.balance() == so_du_ban_dau - Decimal("750000.00")
    p_state = alice.http.get(f"/payments/{payment['id']}").json()
    assert p_state["status"] == "PROCESSING"

    # Chạy đối soát: nhận diện giao dịch treo và hoàn tiền
    with IsolatedSession() as db:
        rep = payment_reconcile.reconcile_once(db, stuck_after_seconds=0)

    act = next((r["action"] for r in rep.resolved if r["payment_id"] == payment["id"]), None)
    assert act == "REFUND_AND_FAIL"
    assert alice.balance() == so_du_ban_dau
    p_final = alice.http.get(f"/payments/{payment['id']}").json()
    assert p_final["status"] == "FAILED"
    assert p_final["failure_code"] == "RECONCILED_REFUND"
    assert fee_state(fee["id"])["status"] == "UNPAID"


def test_loss_after_pay_recovery_completes(alice: Client, pending_payment, monkeypatch):
    """Mất kết nối sau khi gạch nợ học phí: giao dịch giữ PROCESSING -> đối soát hoàn tất SUCCESS."""
    fee, payment, otp = pending_payment
    so_du_ban_dau = alice.balance()
    real_call_service = payment_main.call_service

    def mock_call_service(method, url, **kwargs):
        res = real_call_service(method, url, **kwargs)
        if "/pay" in url:
            raise APIError(503, "NETWORK_TIMEOUT", "Mất phản hồi mạng sau khi gạch nợ học phí thành công")
        return res

    monkeypatch.setattr(payment_main, "call_service", mock_call_service)

    user = _as_current_user(alice)
    req = ConfirmPaymentRequest(otp_code=otp)
    with pytest.raises(APIError) as exc_info:
        with IsolatedSession() as db:
            payment_main.confirm_payment(payment["id"], req, user=user, db=db)

    assert exc_info.value.code == "NETWORK_TIMEOUT"
    p_state = alice.http.get(f"/payments/{payment['id']}").json()
    assert p_state["status"] == "PROCESSING"

    # Chạy đối soát: nhận diện cả hai bước đã xong -> hoàn tất giao dịch
    with IsolatedSession() as db:
        rep = payment_reconcile.reconcile_once(db, stuck_after_seconds=0)

    act = next((r["action"] for r in rep.resolved if r["payment_id"] == payment["id"]), None)
    assert act == "COMPLETE"
    assert alice.balance() == so_du_ban_dau - Decimal("750000.00")
    p_final = alice.http.get(f"/payments/{payment['id']}").json()
    assert p_final["status"] == "SUCCESS"
    assert fee_state(fee["id"])["status"] == "PAID"
    assert fee_state(fee["id"])["payment_ref"] == payment["id"]


def test_loss_after_refund_recovery(alice: Client, pending_payment, monkeypatch):
    """Gạch nợ thất bại, bù trừ hoàn tiền thành công nhưng mất mạng -> đối soát không hoàn tiền 2 lần."""
    fee, payment, otp = pending_payment
    so_du_ban_dau = alice.balance()

    # Làm cho gạch nợ bị từ chối bằng cách cho bên khác gạch nợ trước
    other_ref = f"other-payer-{fee['id']}"
    httpx.post(
        f"{TUITION_URL}/internal/tuitions/fees/{fee['id']}/pay",
        json={"payment_ref": other_ref},
        headers=INTERNAL_HEADERS,
        timeout=15,
    ).raise_for_status()

    real_call_service = payment_main.call_service

    def mock_call_service(method, url, **kwargs):
        res = real_call_service(method, url, **kwargs)
        if "/credit" in url and f"{payment['id']}:refund" in str(kwargs.get("json", {})):
            raise APIError(503, "CRASH_AFTER_REFUND", "Sập kết nối ngay sau khi bút toán hoàn tiền đã commit")
        return res

    monkeypatch.setattr(payment_main, "call_service", mock_call_service)

    user = _as_current_user(alice)
    req = ConfirmPaymentRequest(otp_code=otp)
    with pytest.raises(APIError) as exc_info:
        with IsolatedSession() as db:
            payment_main.confirm_payment(payment["id"], req, user=user, db=db)

    assert exc_info.value.code == "CRASH_AFTER_REFUND"
    # Tiền đã được hoàn về tài khoản
    assert alice.balance() == so_du_ban_dau
    p_state = alice.http.get(f"/payments/{payment['id']}").json()
    assert p_state["status"] == "PROCESSING"

    # Chạy đối soát: phát hiện đã có bút toán refund -> đóng thất bại an toàn, không hoàn thêm
    with IsolatedSession() as db:
        rep = payment_reconcile.reconcile_once(db, stuck_after_seconds=0)

    act = next((r["action"] for r in rep.resolved if r["payment_id"] == payment["id"]), None)
    assert act == "FAIL"
    assert alice.balance() == so_du_ban_dau
    ledger = alice.http.get("/accounts/me/transactions").json()["items"]
    assert sum(1 for i in ledger if i["reference"] == f"{payment['id']}:refund") == 1
    p_final = alice.http.get(f"/payments/{payment['id']}").json()
    assert p_final["status"] == "FAILED"
    assert p_final["failure_code"] == "RECONCILED_REFUND"


def test_dependency_unavailable_during_reconciliation_then_retries(alice: Client, pending_payment, monkeypatch):
    """Khi service phụ thuộc tạm thời không liên lạc được, reconciler bỏ qua và xử lý thành công ở lần sau."""
    fee, payment, otp = pending_payment
    so_du_ban_dau = alice.balance()
    real_call_service = payment_main.call_service

    # Cho trừ tiền thành công rồi làm đứt mạng
    def mock_call_service_confirm(method, url, **kwargs):
        res = real_call_service(method, url, **kwargs)
        if "/debit" in url:
            raise APIError(503, "DEBIT_COMMITTED_BUT_DROPPED", "Trừ tiền xong rớt mạng")
        return res

    monkeypatch.setattr(payment_main, "call_service", mock_call_service_confirm)
    user = _as_current_user(alice)
    with pytest.raises(APIError):
        with IsolatedSession() as db:
            payment_main.confirm_payment(payment["id"], ConfirmPaymentRequest(otp_code=otp), user=user, db=db)

    # Lần 1: đối soát gọi tuition-service bị lỗi
    def mock_reconcile_down(method, url, **kwargs):
        if "/internal/tuitions/fees" in url:
            raise APIError(503, "SERVICE_UNAVAILABLE", "Tuition service tạm thời chết")
        return real_call_service(method, url, **kwargs)

    monkeypatch.setattr(payment_reconcile, "call_service", mock_reconcile_down)
    with IsolatedSession() as db:
        rep1 = payment_reconcile.reconcile_once(db, stuck_after_seconds=0)
    assert not any(r["payment_id"] == payment["id"] for r in rep1.resolved)
    assert alice.http.get(f"/payments/{payment['id']}").json()["status"] == "PROCESSING"

    # Lần 2: dịch vụ phục hồi, đối soát thành công
    monkeypatch.setattr(payment_reconcile, "call_service", real_call_service)
    with IsolatedSession() as db:
        rep2 = payment_reconcile.reconcile_once(db, stuck_after_seconds=0)
    act = next((r["action"] for r in rep2.resolved if r["payment_id"] == payment["id"]), None)
    assert act == "REFUND_AND_FAIL"
    assert alice.balance() == so_du_ban_dau


def test_foreground_exclusion_skips_concurrent_sweep(alice: Client, pending_payment, monkeypatch):
    """Trong lúc luồng chính đang giữ khoá xử lý thanh toán, luồng quét đối soát phải bỏ qua dòng đó."""
    fee, payment, otp = pending_payment
    real_call_service = payment_main.call_service
    in_saga_event = threading.Event()
    release_saga_event = threading.Event()

    def mock_call_service_blocking(method, url, **kwargs):
        res = real_call_service(method, url, **kwargs)
        if "/debit" in url:
            in_saga_event.set()
            # Tạm dừng luồng chính trong lúc đang giữ khoá dòng payment
            assert release_saga_event.wait(timeout=10), "Không nhả khóa saga đúng hạn"
        return res

    monkeypatch.setattr(payment_main, "call_service", mock_call_service_blocking)

    user = _as_current_user(alice)
    confirm_thread_error = []

    def run_confirm():
        try:
            with IsolatedSession() as db:
                payment_main.confirm_payment(
                    payment["id"],
                    ConfirmPaymentRequest(otp_code=otp),
                    user=user,
                    db=db,
                )
        except Exception as e:
            confirm_thread_error.append(e)

    th = threading.Thread(target=run_confirm)
    th.start()

    try:
        assert in_saga_event.wait(timeout=10), "Luồng chính không vào bước debit"
        with IsolatedSession() as db_sweep:
            rep = payment_reconcile.reconcile_once(db_sweep, stuck_after_seconds=0)
        assert not any(r["payment_id"] == payment["id"] for r in rep.resolved)
    finally:
        release_saga_event.set()
        th.join(timeout=10)
    assert not th.is_alive()
    assert not confirm_thread_error, f"Lỗi luồng chính: {confirm_thread_error}"
    assert alice.http.get(f"/payments/{payment['id']}").json()["status"] == "SUCCESS"
