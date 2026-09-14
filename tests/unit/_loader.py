"""Nạp module logic thuần theo đường dẫn file.

Các service đều có package tên `app`, nên không thể import kiểu thông thường cho
nhiều service trong cùng một phiên pytest. Các module được nạp ở đây đều **không
có import tương đối** và không phụ thuộc database, nên nạp theo file là đủ.
"""
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

SERVICES = Path(__file__).resolve().parents[2] / "services"


def load_module(relative_path: str) -> ModuleType:
    """Ví dụ: load_module('otp-service/app/codes.py')."""
    path = SERVICES / relative_path
    name = "unit_" + relative_path.replace("/", "_").removesuffix(".py")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
