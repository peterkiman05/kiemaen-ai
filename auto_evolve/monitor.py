import asyncio
from pathlib import Path
from auto_evolve.models import Suggestion
from auto_evolve.logger_setup import setup_logger, load_config

SUGGESTION_QUEUE: dict[str, Suggestion] = {}

class Monitor:
    def __init__(self, config=None):
        self.config = config or load_config()
        self.logger = setup_logger(config=self.config)
        self.interval = self.config.get("interval_seconds", 300)
        self.watch_targets = self.config.get("kiemaen_log_sources", [])
        self._running = False
        self._last_sizes = {}

    def _scan_source(self, path: str):
        p = Path(path)
        if not p.exists():
            return []
        try:
            size = p.stat().st_size
            last = self._last_sizes.get(path, 0)
            if size <= last:
                self._last_sizes[path] = size
                return []
            with open(p, "r", errors="ignore") as f:
                f.seek(last)
                new_content = f.read()
            self._last_sizes[path] = size
        except Exception as e:
            self.logger.error(f"Failed reading {path}: {e}")
            return []

        findings = []
        lowered = new_content.lower()
        keyword_actions = {
            "413": "Reduce payload size sent to LLM provider (cap history/content length).",
            "timeout": "Investigate slow upstream calls; consider retries/backoff.",
            "traceback": "Review recent stack trace for an unhandled exception.",
            "rate limit": "Consider backoff/retry logic or user-facing rate-limit messaging.",
        }
        for keyword, action in keyword_actions.items():
            if keyword in lowered:
                findings.append((keyword, action))
        return findings

    async def scan_once(self):
        self.logger.info("Scan cycle started.")
        if not self.watch_targets:
            self.logger.info("No log sources configured — nothing to scan.")
        for source in self.watch_targets:
            for keyword, action in self._scan_source(source):
                s = Suggestion(description=f"Detected '{keyword}' pattern in {source}", action=action)
                SUGGESTION_QUEUE[s.id] = s
                self.logger.info(f"New suggestion [{s.id}]: {s.description}")
        self.logger.info("Scan cycle finished.")

    async def run_forever(self):
        self._running = True
        self.logger.info(f"Monitor loop starting. Interval={self.interval}s")
        while self._running:
            try:
                await self.scan_once()
            except Exception as e:
                self.logger.exception(f"Monitor scan crashed: {e}")
            await asyncio.sleep(self.interval)

    def stop(self):
        self._running = False
        self.logger.info("Monitor loop stopped.")
