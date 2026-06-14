from __future__ import annotations


def test_llm_categorize_prefers_flm_startup_before_fallback(fresh_modules, monkeypatch):
    notes = fresh_modules("notes")
    calls: list[bool] = []

    monkeypatch.setattr(notes.engine, "is_flm_server_reachable", lambda: False)
    monkeypatch.setattr(notes.engine, "start_flm_server", lambda force_restart=False: calls.append(force_restart))

    def fail_call(*_args, **_kwargs):
        raise AssertionError("call_flm_simple should not be reached when FLM stays down")

    monkeypatch.setattr(notes.engine, "call_flm_simple", fail_call)

    out = notes._llm_categorize("hello", "foot", "", "", "")

    assert calls == [False]
    assert out["category"] == notes.INBOX
    assert out["summary"] == "(LLM unavailable; left in inbox)"
