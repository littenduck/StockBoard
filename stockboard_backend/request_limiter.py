"""Turn away requests above a global rate before they reach the routes.

One token bucket for the whole server: a flood becomes cheap 429 replies instead of work for the app.
It is global because behind a proxy the app may not see the real client address.
"""
import time


class RequestLimiterMiddleware:
    def __init__(self, app, requests_per_second: float):
        self.app = app
        self.refill_per_second = requests_per_second
        self.burst = requests_per_second * 3  # a page load is about 7 requests
        self.token_count = self.burst
        self.last_time = time.monotonic()

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":  # lifespan and other scopes pass through
            now = time.monotonic()
            self.token_count = min(self.burst, self.token_count + (now - self.last_time) * self.refill_per_second)
            self.last_time = now
            if self.token_count < 1:
                await send({"type": "http.response.start", "status": 429,
                            "headers": [(b"retry-after", b"5"), (b"content-length", b"0")]})
                return await send({"type": "http.response.body", "body": b""})
            self.token_count -= 1  # no await since the check above, so concurrent requests cannot interleave here
        await self.app(scope, receive, send)
