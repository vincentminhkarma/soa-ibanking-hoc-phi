"""Unit test JWT và bảo vệ endpoint nội bộ (services/common/security.py)."""
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from common import security
from common.config import JWT_ALG, JWT_SECRET
from common.errors import APIError

USER = ("11111111-1111-1111-1111-111111111111", "minhnguyen", "Nguyễn Văn Minh",
        "minhnguyen@tdtu.edu.vn", "0901234567")


def test_token_chua_du_thong_tin_nguoi_nop_tien():
    """Claim mang sẵn họ tên/email/SĐT nên payment-service không phải gọi lại auth-service."""
    token, expires_in = security.create_access_token(*USER)
    claims = security.decode_token(token)
    assert claims["sub"] == USER[0]
    assert claims["username"] == "minhnguyen"
    assert claims["full_name"] == "Nguyễn Văn Minh"
    assert claims["email"] == "minhnguyen@tdtu.edu.vn"
    assert claims["phone"] == "0901234567"
    assert expires_in > 0


def test_token_bi_sua_thi_bi_tu_choi():
    token, _ = security.create_access_token(*USER)
    hong = token[:-3] + ("aaa" if not token.endswith("aaa") else "bbb")
    with pytest.raises(APIError) as err:
        security.decode_token(hong)
    assert err.value.status_code == 401
    assert err.value.code == "INVALID_TOKEN"


def test_token_ky_bang_secret_khac_bi_tu_choi():
    gia_mao = jwt.encode({"sub": "hacker", "exp": datetime.now(UTC) + timedelta(minutes=5)},
                         "secret-khac", algorithm=JWT_ALG)
    with pytest.raises(APIError) as err:
        security.decode_token(gia_mao)
    assert err.value.code == "INVALID_TOKEN"


def test_token_het_han_bao_dung_ma_loi():
    het_han = jwt.encode(
        {"sub": USER[0], "exp": datetime.now(UTC) - timedelta(seconds=1)}, JWT_SECRET, algorithm=JWT_ALG
    )
    with pytest.raises(APIError) as err:
        security.decode_token(het_han)
    assert err.value.code == "TOKEN_EXPIRED"


@pytest.mark.parametrize("header", [None, "", "Basic abc", "token abc", "Bearer"])
def test_thieu_hoac_sai_dinh_dang_authorization(header):
    with pytest.raises(APIError) as err:
        security.current_user(authorization=header)
    assert err.value.status_code == 401


def test_current_user_doc_dung_tu_token_hop_le():
    token, _ = security.create_access_token(*USER)
    user = security.current_user(authorization=f"Bearer {token}")
    assert user.user_id == USER[0]
    assert user.email == "minhnguyen@tdtu.edu.vn"


def test_endpoint_noi_bo_tu_choi_token_sai():
    with pytest.raises(APIError) as err:
        security.require_internal(x_internal_token="token-bay-ba")
    assert err.value.status_code == 403
    assert err.value.code == "FORBIDDEN"


def test_endpoint_noi_bo_chap_nhan_token_dung():
    assert security.require_internal(x_internal_token=security.INTERNAL_TOKEN) is None
