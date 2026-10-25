import asyncio
import types

from stockboard_backend import request_limiter


async def answer_ok(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


def collect_response_start_list(middleware, request_count):
    response_start_list = []

    async def send_all_requests():
        for _ in range(request_count):
            sent_message_list = []

            async def send(message):
                sent_message_list.append(message)

            await middleware({"type": "http"}, None, send)
            response_start_list.append(sent_message_list[0])

    asyncio.run(send_all_requests())
    return response_start_list


def test_requests_within_the_burst_are_answered():
    middleware = request_limiter.RequestLimiterMiddleware(answer_ok, requests_per_second=10)
    assert {start["status"] for start in collect_response_start_list(middleware, 30)} == {200}


def test_requests_beyond_the_burst_get_429_with_retry_after():
    middleware = request_limiter.RequestLimiterMiddleware(answer_ok, requests_per_second=1)
    response_start_list = collect_response_start_list(middleware, 5)
    assert [start["status"] for start in response_start_list[:3]] == [200, 200, 200]
    assert response_start_list[4]["status"] == 429
    assert (b"retry-after", b"5") in response_start_list[4]["headers"]


def test_budget_comes_back_over_time(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(request_limiter, "time", types.SimpleNamespace(monotonic=lambda: clock[0]))
    middleware = request_limiter.RequestLimiterMiddleware(answer_ok, requests_per_second=1)
    assert [start["status"] for start in collect_response_start_list(middleware, 4)] == [200, 200, 200, 429]
    clock[0] += 2
    assert [start["status"] for start in collect_response_start_list(middleware, 3)] == [200, 200, 429]
