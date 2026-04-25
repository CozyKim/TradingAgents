"""Tests for in-memory analysis event bus."""
import asyncio

import pytest

from tradingagents_web.services.event_bus import AnalysisEvent, EventBus


@pytest.mark.asyncio
async def test_publish_then_subscribe_replays_history():
    bus = EventBus()
    bus.publish("run-1", AnalysisEvent(type="agent_message", data={"text": "hello"}))
    bus.publish("run-1", AnalysisEvent(type="progress", data={"step": 1, "total": 5}))

    received: list[AnalysisEvent] = []
    async with bus.subscribe("run-1") as queue:
        for _ in range(2):
            ev = await asyncio.wait_for(queue.get(), 0.5)
            received.append(ev)
    assert [e.type for e in received] == ["agent_message", "progress"]


@pytest.mark.asyncio
async def test_subscribe_receives_live_events():
    bus = EventBus()

    async with bus.subscribe("run-2") as queue:
        bus.publish("run-2", AnalysisEvent(type="agent_message", data={"text": "live"}))
        ev = await asyncio.wait_for(queue.get(), 0.5)
        assert ev.data["text"] == "live"


@pytest.mark.asyncio
async def test_finish_marks_run_done_and_closes_subs():
    bus = EventBus()
    bus.publish("run-3", AnalysisEvent(type="agent_message", data={}))
    async with bus.subscribe("run-3") as queue:
        await asyncio.wait_for(queue.get(), 0.5)
        bus.finish("run-3")
        sentinel = await asyncio.wait_for(queue.get(), 0.5)
        assert sentinel is None  # closed sentinel


def test_publish_caps_history_per_run():
    bus = EventBus(max_buffer=3)
    for i in range(5):
        bus.publish("run-4", AnalysisEvent(type="agent_message", data={"i": i}))
    history = bus.history("run-4")
    assert [e.data["i"] for e in history] == [2, 3, 4]


def test_publish_isolates_caller_dict_mutation():
    bus = EventBus()
    payload = {"step": 1}
    bus.publish("run-x", AnalysisEvent(type="progress", data=payload))
    payload["step"] = 999
    history = bus.history("run-x")
    assert history[0].data == {"step": 1}
