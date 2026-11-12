"""
Protecting the live demo from abuse and surprise bills.

Every live question costs a little money (Claude Haiku) and some server time
(the embedding model). Three limits keep that bounded:

  1. Per visitor, per minute  - stops one person hammering the button.
  2. Per visitor, per day     - stops one person (or script) running all day.
  3. Whole site, per day      - a hard cap on paid AI calls, whatever happens.

"Visitor" means IP address (see visitor_id). The counts live in this process's memory, so they
reset when the server restarts and each replica counts on its own. That is
fine for a single small container; a bigger deployment would keep them in a
shared store such as Redis.

The example questions are pre-computed (see baked.py) and never count.
"""

import ipaddress
import os
import threading
import time
from collections import OrderedDict, defaultdict, deque


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


PER_MINUTE = _env_int("RATE_PER_MINUTE", 4)
PER_DAY = _env_int("RATE_PER_DAY", 30)
DAILY_AI_BUDGET = _env_int("DAILY_AI_BUDGET", 500)  # paid generations per day, whole site
TRUSTED_PROXIES = _env_int("TRUSTED_PROXIES", 0)    # proxies we run in front of the API (Azure: 1; locally: 0)


def visitor_id(peer: str | None, forwarded_for: str | None, proxies: int = TRUSTED_PROXIES) -> str:
    """Who is asking, for the limits.

    With no proxy, that is the address the connection came from (`peer`).
    Behind a proxy every connection comes from the proxy, and the proxy adds the
    real address to the END of the X-Forwarded-For header. Everything before that
    was written by the sender and can be a lie, so we count `proxies` entries back
    from the end and never read further. With proxies = 0 the header is ignored.

    An IPv6 visitor usually owns a whole /64 block of addresses, so the block is
    the visitor: changing address inside it does not give a fresh allowance.
    """
    ip = peer or "unknown"
    if proxies > 0 and forwarded_for:
        hops = [h.strip() for h in forwarded_for.split(",") if h.strip()]
        if hops:
            ip = hops[-min(proxies, len(hops))]
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return ip
    if address.version == 4:
        return str(address)
    if address.ipv4_mapped:
        return str(address.ipv4_mapped)
    return str(ipaddress.ip_network((address, 64), strict=False))


class Limited(Exception):
    def __init__(self, message: str, retry_after: int) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class Guard:
    def __init__(self, per_minute: int = PER_MINUTE, per_day: int = PER_DAY,
                 daily_budget: int = DAILY_AI_BUDGET, clock=time.time) -> None:
        self.per_minute, self.per_day, self.daily_budget = per_minute, per_day, daily_budget
        self.clock = clock
        self.hits: dict[str, deque] = defaultdict(deque)  # visitor -> times of their recent questions
        self.day = self._today()
        self.spent = 0
        self.lock = threading.Lock()

    def _today(self) -> int:
        return int(self.clock() // 86400)

    def check(self, visitor: str) -> None:
        """Raise Limited if this visitor (or the whole site) may not ask now. Otherwise count it."""
        with self.lock:
            now = self.clock()
            if self._today() != self.day:  # a new day: everyone starts again
                self.day, self.spent = self._today(), 0
                self.hits.clear()
            if self.spent >= self.daily_budget:
                raise Limited("The live demo has reached today's limit. The example questions still work.",
                              retry_after=int(86400 - now % 86400))
            q = self.hits[visitor]
            while q and now - q[0] > 86400:
                q.popleft()
            if len(q) >= self.per_day:
                raise Limited("You've asked a lot of questions today. Try the examples, or come back tomorrow.",
                              retry_after=int(86400 - (now - q[0])))
            recent = [t for t in q if now - t < 60]
            if len(recent) >= self.per_minute:
                raise Limited("That's quick! Wait a few seconds before asking again.",
                              retry_after=max(1, int(60 - (now - recent[0])) + 1))
            q.append(now)

    def left(self, visitor: str) -> dict:
        """How many more questions this visitor may ask: this minute, and today. Shown in the Journey."""
        with self.lock:
            now = self.clock()
            q = [t for t in self.hits.get(visitor, ()) if now - t <= 86400]
            return {"this_minute": max(0, self.per_minute - sum(now - t < 60 for t in q)),
                    "today": max(0, self.per_day - len(q))}

    def spend(self) -> None:
        """Count one paid AI call against the site-wide budget."""
        with self.lock:
            self.spent += 1


class AnswerCache:
    """Recent answers by question, so a repeated question costs nothing.
    Questions are compared after lower-casing and squashing spaces."""

    def __init__(self, size: int = 256) -> None:
        self.size, self.items, self.lock = size, OrderedDict(), threading.Lock()

    @staticmethod
    def key(question: str) -> str:
        return " ".join(question.lower().split()).rstrip("?!. ")

    def get(self, question: str):
        with self.lock:
            k = self.key(question)
            if k in self.items:
                self.items.move_to_end(k)
                return self.items[k]
        return None

    def put(self, question: str, trace: dict) -> None:
        with self.lock:
            self.items[self.key(question)] = trace
            self.items.move_to_end(self.key(question))
            while len(self.items) > self.size:
                self.items.popitem(last=False)
