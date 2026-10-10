"""Give the app's own loggers somewhere to write.

Until 10 October 2026 nothing configured them. `logging.getLogger(__name__)` in
rag.py and files.py had no handler, so Python's last-resort handler printed
WARNING and above to stderr with no timestamp, and every INFO line was dropped.
The INFO lines are the ones that say *which* quote failed the grounding check
and which citations were dropped -- the first thing needed when an answer comes
back UNVERIFIED in production, and on that day there was nothing to read.

Only the `app` namespace gets a handler. uvicorn configures its own loggers and
leaves the root logger bare, so a line from `app.*` is printed once. It still
propagates, so pytest's `caplog` (which listens on the root) keeps seeing it.
"""

import logging

from app.core.config import settings

_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


class _AppHandler(logging.StreamHandler):
    """Marker type, so a second call can tell its own handler from anyone else's."""


def configure_logging() -> None:
    logger = logging.getLogger("app")
    logger.setLevel(settings.LOG_LEVEL.upper())
    if any(isinstance(h, _AppHandler) for h in logger.handlers):
        # uvicorn --reload imports the app again; a second handler would print
        # every line twice.
        return
    handler = _AppHandler()
    handler.setFormatter(logging.Formatter(_FORMAT))
    logger.addHandler(handler)
