"""Unit test bảng quyết định của job đối soát giao dịch treo (payment-service).

Bốn nhánh này tương ứng bốn khả năng khi tiến trình chết giữa saga; không thể
dựng lại bằng integration test nên phải kiểm tra ở mức hàm thuần.
"""
import pytest
from _loader import load_module

d = load_module("payment-service/app/decisions.py")

PID = "4b2e8f11-0000-0000-0000-000000000001"
OTHER = "aaaaaaaa-0000-0000-0000-000000000002"


@pytest.mark.parametrize(
    "fee_status,fee_ref,debit_found,expected",
    [
        # Đã gạch nợ bởi chính giao dịch này + đã trừ tiền => hoàn tất nốt.
        ("PAID", PID, True, d.COMPLETE),
        # Đã gạch nợ nhưng không có bút toán trừ tiền => huỷ gạch nợ, đóng thất bại.
        ("PAID", PID, False, d.REVERT_AND_FAIL),
        # Học phí do người khác thanh toán, tiền mình đã bị trừ => phải hoàn tiền.
        ("PAID", OTHER, True, d.REFUND_AND_FAIL),
        ("PAID", OTHER, False, d.FAIL),
        # Học phí vẫn còn nợ: chỉ cần hoàn tiền nếu đã trừ.
        ("UNPAID", None, True, d.REFUND_AND_FAIL),
        ("UNPAID", None, False, d.FAIL),
    ],
)
def test_bang_quyet_dinh(fee_status, fee_ref, debit_found, expected):
    assert d.decide(PID, fee_status, fee_ref, debit_found, False) == expected


def test_khong_bao_gio_hoan_tat_khi_hoc_phi_thuoc_giao_dich_khac():
    """Bất biến quan trọng nhất: không tự nhận công của giao dịch khác."""
    for debit in (True, False):
        assert d.decide(PID, "PAID", OTHER, debit, False) != d.COMPLETE


def test_khong_hoan_tien_khi_chua_tung_tru_tien():
    """Không được tạo tiền từ hư không khi đối soát."""
    for status, ref in (("PAID", PID), ("PAID", OTHER), ("UNPAID", None)):
        assert d.decide(PID, status, ref, False, False) != d.REFUND_AND_FAIL


@pytest.mark.parametrize("status,ref,expected", [
    ("PAID", PID, d.REVERT_AND_FAIL),
    ("PAID", OTHER, d.FAIL),
    ("UNPAID", None, d.FAIL),
])
def test_da_hoan_tien_khong_duoc_success_hoac_hoan_them(status, ref, expected):
    assert d.decide(PID, status, ref, True, True) == expected
