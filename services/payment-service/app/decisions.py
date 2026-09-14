"""Bảng quyết định của job đối soát — logic thuần, không phụ thuộc DB/HTTP.

Tách riêng để unit-test trực tiếp mà không cần dựng cả hệ thống.
"""

COMPLETE = "COMPLETE"                  # học phí đã gạch nợ bởi chính giao dịch này
REFUND_AND_FAIL = "REFUND_AND_FAIL"    # đã trừ tiền nhưng chưa gạch nợ được
REVERT_AND_FAIL = "REVERT_AND_FAIL"    # đã gạch nợ nhưng không tìm thấy bút toán trừ tiền
FAIL = "FAIL"                          # chưa làm gì cả, chỉ cần đóng giao dịch


def decide(
    payment_id: str, fee_status: str, fee_payment_ref: str | None,
    debit_found: bool, refund_found: bool,
) -> str:
    owns_fee = fee_status == "PAID" and fee_payment_ref == payment_id
    paid = debit_found and not refund_found
    if owns_fee:
        return COMPLETE if paid else REVERT_AND_FAIL
    return REFUND_AND_FAIL if paid else FAIL
