"""Agent names must not replace the harness's scoring callable."""

import math
from types import SimpleNamespace

import pytest

from fle.env import lua_manager
from fle.env.namespace import FactorioNamespace


@pytest.fixture
def scoring_namespaces(tmp_path, monkeypatch):
    tool_dir = tmp_path / "agent" / "score"
    tool_dir.mkdir(parents=True)
    (tool_dir / "server.lua").write_text("-- No server needed for this test.\n")
    (tool_dir / "client.py").write_text(
        "class Reward:\n"
        "    def __init__(self, manager, namespace):\n"
        "        self.agent_index = namespace.agent_index\n"
        "    def __call__(self):\n"
        "        return 100 + self.agent_index, 20 + self.agent_index\n"
    )
    monkeypatch.setattr(lua_manager, "_get_dir", lambda _: str(tmp_path))
    calls = []
    instance = SimpleNamespace(
        tcp_port=0,
        num_agents=2,
        pre_tool_hooks={
            "score": [lambda tool: calls.append(("pre", tool.agent_index))]
        },
        post_tool_hooks={
            "score": [lambda tool, result: calls.append(("post", result))]
        },
    )
    instance.namespaces = [FactorioNamespace(instance, i) for i in range(2)]
    manager = lua_manager.LuaScriptManager.__new__(lua_manager.LuaScriptManager)
    manager.setup_tools(instance)
    for namespace in instance.namespaces:
        namespace._freeze_protected_names()
    return instance.namespaces, calls


def test_import_alias_cannot_break_internal_scoring(scoring_namespaces):
    namespaces, calls = scoring_namespaces
    for index, namespace in enumerate(namespaces):
        expected = (100 + index, 20 + index)
        score, automated, output = namespace.eval_with_timeout(
            "from math import pi as score\nprint(score)"
        )
        assert (score, automated) == expected
        assert namespace.score == math.pi
        assert str(math.pi) in output
        assert calls[-2:] == [("pre", index), ("post", expected)]

        # The next evaluation must also complete with the shadowed name persisted.
        assert namespace.eval_with_timeout("print(score)")[:2] == expected


def test_existing_assignment_protection_is_preserved(scoring_namespaces):
    namespaces, _ = scoring_namespaces
    namespace = namespaces[0]
    score, automated, output = namespace.eval_with_timeout("score = 1.5")
    assert "Cannot redefine 'score'" in output
    assert callable(namespace.score)
    assert (score, automated) == (100, 20)


def test_internal_score_matches_public_tool_before_shadowing(scoring_namespaces):
    namespaces, _ = scoring_namespaces
    for namespace in namespaces:
        assert namespace._score is namespace.score
        assert namespace._score() == namespace.score()
