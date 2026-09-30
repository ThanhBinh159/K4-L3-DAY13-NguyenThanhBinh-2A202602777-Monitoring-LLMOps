from __future__ import annotations

from contextlib import contextmanager

from app import agent as agent_module


class ManagedPrompt:
    version = 3

    def compile(self, **variables: str) -> str:
        return (
            f"Feature={variables['feature']}\n"
            f"Docs={variables['docs']}\n"
            f"Question={variables['message']}"
        )


class RecordedObservation:
    def __init__(self, **params) -> None:
        self.params = params
        self.updates: list[dict] = []

    def update(self, **kwargs) -> None:
        self.updates.append(kwargs)


class RecordingLangfuseClient:
    def __init__(self) -> None:
        self.prompt = ManagedPrompt()
        self.span_updates: list[dict] = []
        self.observations: list[RecordedObservation] = []

    def get_prompt(self, name: str, **kwargs):
        return self.prompt

    def update_current_span(self, **kwargs) -> None:
        self.span_updates.append(kwargs)

    @contextmanager
    def start_as_current_observation(self, **kwargs):
        observation = RecordedObservation(**kwargs)
        self.observations.append(observation)
        yield observation


def test_agent_records_prompt_version_with_v4_observation_api(monkeypatch) -> None:
    monkeypatch.setenv("LANGFUSE_PROMPT_NAME", "day13-chat")
    monkeypatch.setenv("LANGFUSE_PROMPT_LABEL", "production")
    client = RecordingLangfuseClient()
    monkeypatch.setattr(agent_module, "get_langfuse_client", lambda: client)
    monkeypatch.setattr(agent_module, "tracing_enabled", lambda: True)

    propagated: list[dict] = []

    @contextmanager
    def record_attributes(**kwargs):
        propagated.append(kwargs)
        yield

    monkeypatch.setattr(agent_module, "propagate_attributes", record_attributes)

    agent = agent_module.LabAgent()
    agent_module.LabAgent.run.__wrapped__(
        agent,
        user_id="student-01",
        feature="qa",
        session_id="session-01",
        message="Explain traces",
        correlation_id="req-12345678",
    )

    span_update = client.span_updates[-1]
    assert span_update["metadata"] == {
        "doc_count": 1,
        "query_preview": "Explain traces",
        "prompt_name": "day13-chat",
        "prompt_label": "production",
        "prompt_version": "3",
        "prompt_source": "langfuse",
        "prompt_fetch_error": "",
    }
    assert span_update["version"] == "3"
    assert propagated[0]["metadata"]["correlation_id"] == "req-12345678"
    assert propagated[-1]["prompt"] is client.prompt


def test_agent_records_safe_retrieval_and_generation_children(monkeypatch) -> None:
    monkeypatch.setenv("LANGFUSE_PROMPT_NAME", "day13-chat")
    monkeypatch.setenv("LANGFUSE_PROMPT_LABEL", "candidate")
    client = RecordingLangfuseClient()
    monkeypatch.setattr(agent_module, "get_langfuse_client", lambda: client)
    monkeypatch.setattr(agent_module, "tracing_enabled", lambda: True)

    @contextmanager
    def pass_attributes(**kwargs):
        yield

    monkeypatch.setattr(agent_module, "propagate_attributes", pass_attributes)
    agent = agent_module.LabAgent()
    agent.llm.generate = lambda _prompt: type(
        "Response",
        (),
        {
            "text": "A safe answer without user data.",
            "usage": type("Usage", (), {"input_tokens": 40, "output_tokens": 20})(),
            "model": agent.model,
            "ttft_ms": 55,
        },
    )()

    agent_module.LabAgent.run.__wrapped__(
        agent,
        user_id="student-01",
        feature="qa",
        session_id="session-01",
        message="How do I ask about learner@example.edu?",
        correlation_id="req-87654321",
    )

    assert [item.params["as_type"] for item in client.observations] == [
        "retriever",
        "generation",
    ]
    retrieval, generation = client.observations
    assert retrieval.params["name"] == "retrieval"
    assert retrieval.updates == [{"metadata": {"doc_count": 1}}]
    assert generation.params["name"] == "llm-generate"
    assert generation.params["model"] == agent.model
    assert generation.params["prompt"] is client.prompt
    assert generation.params["metadata"] == {
        "prompt_name": "day13-chat",
        "prompt_label": "candidate",
        "prompt_version": "3",
        "prompt_source": "langfuse",
    }
    assert generation.updates == [
        {
            "usage_details": {"input": 40, "output": 20},
            "cost_details": {"input": 0.00012, "output": 0.0003, "total": 0.00042},
            "metadata": {"ttft_ms": 55},
        }
    ]
    assert all("input" not in item.params and "output" not in item.params for item in client.observations)
    assert all(
        "input" not in update and "output" not in update
        for item in client.observations
        for update in item.updates
    )
