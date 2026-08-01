import time as _real_time

import pytest


class _FastTime:
    """Delegates to the real time module for everything except sleep.

    A naive monkeypatch.setattr("openai._base_client.time.sleep", ...)
    mutates the actual stdlib time module, since openai._base_client.time
    IS that module, not a copy. That silently defeats any other test
    (e.g. LatencyFault's "did it actually sleep" test) that depends on a
    real time.sleep. This wraps the module instead of mutating it.
    """

    def __getattr__(self, name):
        return getattr(_real_time, name)

    def sleep(self, seconds):
        pass


@pytest.fixture(autouse=True)
def fast_openai_retries(monkeypatch):
    """The OpenAI SDK sleeps between retries using time.sleep. Faults fire
    in microseconds; nothing in this test suite should be slowed down by
    the SDK's own backoff. Applies to every test in the suite, not just
    test_transport.py, since test_cli.py and test_runner.py can also
    trigger real SDK retry paths through examples/01-hello-agent.
    """
    monkeypatch.setattr("openai._base_client.time", _FastTime())
