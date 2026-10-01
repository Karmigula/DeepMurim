"""FakeClaude (phase 6 spec 11): the bridge's interface, answering from a script, so tests need no network."""

from collections import deque

from ai.bridge import Exchange, Job, conforms


class FakeClaude:
    """Each call takes the next scripted reply: a dict (checked against the job's schema like a real reply),
    None (a failure), or a callable of (job, prompt) returning either. With the script empty it fails."""

    def __init__(self, *replies, available: bool = True) -> None:
        self.script = deque(replies)
        self.calls: list[tuple[str, str]] = []
        self.exchanges: deque[Exchange] = deque(maxlen=20)
        self._available = available
        self.just_paused = False

    def available(self) -> tuple[bool, str]:
        return (True, "") if self._available else (False, "the claude command is not installed")

    def paused(self) -> bool:
        return False

    def add(self, *replies) -> None:
        self.script.extend(replies)

    def call(self, job: Job, prompt: str) -> dict | None:
        self.calls.append((job.name, prompt))
        if not self._available:
            return None
        reply = self.script.popleft() if self.script else None
        if callable(reply):
            reply = reply(job, prompt)
        if reply is not None and not conforms(job.schema, reply):
            reply = None
        self.exchanges.append(Exchange(job.name, prompt, reply, "" if reply is not None else "scripted failure"))
        return reply
