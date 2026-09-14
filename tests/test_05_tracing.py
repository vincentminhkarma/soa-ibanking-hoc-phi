import json
import os
import time
import uuid

import httpx
from conftest import Client, new_fee, read_otp, top_up

JAEGER_URL = os.getenv("JAEGER_URL", "http://localhost:16686")


def test_trace_xuyen_service_va_parent_child(alice: Client):
    fee = new_fee("10000", prefix="TR")
    top_up(alice.user["id"], "10000", f"trace-{fee['id']}")
    trace_id = uuid.uuid4().hex
    parent = uuid.uuid4().hex[:16]
    headers = {"traceparent": f"00-{trace_id}-{parent}-01", "X-Request-Id": f"trace-{trace_id[:16]}"}
    created = alice.http.post(
        "/payments", json={"student_code": fee["student_code"], "accept_terms": True}, headers=headers,
    )
    created.raise_for_status()
    assert created.headers["X-Request-Id"] == headers["X-Request-Id"]
    payment_id = created.json()["payment"]["id"]
    confirmed = alice.confirm(payment_id, read_otp(payment_id))
    confirmed.raise_for_status()
    assert confirmed.json()["status"] == "SUCCESS"

    expected = {"api-gateway", "payment-service", "account-service", "tuition-service", "otp-service", "notification-service"}
    deadline = time.monotonic() + 30
    data = None
    while time.monotonic() < deadline:
        response = httpx.get(f"{JAEGER_URL}/api/traces/{trace_id}", timeout=5)
        if response.status_code == 200 and response.json().get("data"):
            data = response.json()["data"][0]
            names = {p["serviceName"] for p in data["processes"].values()}
            if expected <= names:
                break
        time.sleep(0.5)
    assert data is not None, f"Jaeger chưa nhận trace {trace_id}"
    spans = data["spans"]
    names = {p["serviceName"] for p in data["processes"].values()}
    assert expected <= names
    by_id = {s["spanID"]: s for s in spans}
    assert all(s["traceID"] == trace_id and s["duration"] > 0 for s in spans)
    edges = set()
    for span in spans:
        child_service = data["processes"][span["processID"]]["serviceName"]
        for ref in span["references"]:
            ancestor = by_id.get(ref["spanID"])
            if ancestor:
                parent_service = data["processes"][ancestor["processID"]]["serviceName"]
                if parent_service != child_service:
                    edges.add((parent_service, child_service))
    assert {("api-gateway", "payment-service"), ("payment-service", "account-service"),
            ("payment-service", "tuition-service"), ("payment-service", "otp-service"),
            ("otp-service", "notification-service")} <= edges
    attributes = json.dumps([s["tags"] for s in spans])
    assert alice.token not in attributes
    assert not any(tag["key"] == "error" and tag["value"] for s in spans for tag in s["tags"])
    print(f"Jaeger trace: {JAEGER_URL}/trace/{trace_id}")
