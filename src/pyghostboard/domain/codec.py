"""Stable JSON codecs for trusted persistence values."""

from pydantic import TypeAdapter

from pyghostboard.domain.models import PrivateMatchEvent, PrivateMatchSnapshot

_event_adapter: TypeAdapter[PrivateMatchEvent] = TypeAdapter(PrivateMatchEvent)


def dump_snapshot(snapshot: PrivateMatchSnapshot) -> bytes:
    return snapshot.model_dump_json().encode("utf-8")


def load_snapshot(data: bytes | str) -> PrivateMatchSnapshot:
    snapshot = PrivateMatchSnapshot.model_validate_json(data)
    from pyghostboard.domain.match import Match

    Match.restore(snapshot)
    return snapshot


def dump_event(event: PrivateMatchEvent) -> bytes:
    return _event_adapter.dump_json(event)


def load_event(data: bytes | str) -> PrivateMatchEvent:
    event = _event_adapter.validate_json(data)
    from pyghostboard.domain.match import DomainError, Match
    from pyghostboard.domain.models import MatchStarted

    if isinstance(event, MatchStarted):
        if event.snapshot.revision != 0:
            raise DomainError("a match_started snapshot must have revision zero")
        Match.restore(event.snapshot)
    return event
