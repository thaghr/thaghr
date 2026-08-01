from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import httpx

# httpx recomputes these on response construction; keeping recorded values
# causes mismatched content-length or outright construction errors on replay.
_STRIPPED_RESPONSE_HEADERS = {"content-length", "content-encoding", "transfer-encoding"}


@dataclass
class Interaction:
    """One recorded real (non-faulted) request/response pair."""

    method: str
    url: str
    request_body: str
    status_code: int
    response_headers: dict[str, str]
    response_body: str

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "url": self.url,
            "request_body": self.request_body,
            "status_code": self.status_code,
            "response_headers": self.response_headers,
            "response_body": self.response_body,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Interaction":
        return cls(**d)


class CassetteMissError(LookupError):
    """Raised in replay mode when no recorded interaction matches a request.

    Means the cassette is stale relative to the code driving it: the agent's
    call pattern changed since the recording was made. Re-record rather than
    trying to hand-edit the cassette file.
    """


class Cassette:
    """Records and replays the real, non-faulted portion of a campaign.

    Faults are already deterministic under a seed (Fault.reset() rewinds
    the RNG). Without this class, every re-run of a mixed real+fault
    campaign still calls the live backend for the calls that weren't
    faulted, so the campaign as a whole is never byte-identical across
    runs. Record mode calls through to the real backend and saves the
    response; replay mode never touches the network and returns exactly
    what was saved, in the order it was saved.

    Matching key: (method, url, request_body). Retries commonly repeat an
    identical key more than once in a single run, so matches are consumed
    in recorded order via a per-key position counter rather than matched
    by content alone, preserving call order even when requests are
    indistinguishable by content.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.interactions: list[Interaction] = []
        self._replay_position: dict[tuple[str, str, str], int] = defaultdict(int)
        if self.path.exists():
            self._load()

    def _load(self) -> None:
        raw = json.loads(self.path.read_text())
        self.interactions = [Interaction.from_dict(d) for d in raw]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps([i.to_dict() for i in self.interactions], indent=2))

    @staticmethod
    def _body_str(request: httpx.Request) -> str:
        return request.content.decode("utf-8") if request.content else ""

    def _key(self, request: httpx.Request) -> tuple[str, str, str]:
        return (request.method, str(request.url), self._body_str(request))

    def record(self, request: httpx.Request, response: httpx.Response) -> None:
        self.interactions.append(
            Interaction(
                method=request.method,
                url=str(request.url),
                request_body=self._body_str(request),
                status_code=response.status_code,
                response_headers=dict(response.headers),
                response_body=response.text,
            )
        )

    def replay(self, request: httpx.Request) -> httpx.Response:
        key = self._key(request)
        matches = [i for i in self.interactions if (i.method, i.url, i.request_body) == key]
        position = self._replay_position[key]
        if position >= len(matches):
            raise CassetteMissError(
                f"No recorded interaction #{position} for {key[0]} {key[1]} "
                f"({len(matches)} recorded match(es) for this request key)"
            )
        self._replay_position[key] += 1
        interaction = matches[position]
        headers = {
            k: v
            for k, v in interaction.response_headers.items()
            if k.lower() not in _STRIPPED_RESPONSE_HEADERS
        }
        return httpx.Response(
            status_code=interaction.status_code,
            headers=headers,
            content=interaction.response_body.encode("utf-8"),
            request=request,
        )

    def reset_replay_position(self) -> None:
        """Rewind to the start, for re-running a campaign against the same cassette."""
        self._replay_position.clear()
