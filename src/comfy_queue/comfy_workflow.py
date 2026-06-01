from __future__ import annotations

import copy
import json
import random
from pathlib import Path
from typing import Any


def load_workflow(path: str | Path) -> dict[str, Any]:
    """Read a workflow JSON file off disk."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def clone(workflow: dict[str, Any]) -> dict[str, Any]:
    """Deep copy — mutating helpers always return a fresh dict to avoid shared state."""
    return copy.deepcopy(workflow)


def find_nodes(workflow: dict[str, Any], class_type: str) -> list[str]:
    """Return every node id matching ``class_type``."""
    return [nid for nid, node in workflow.items() if node.get("class_type") == class_type]


def set_input(workflow: dict[str, Any], node_id: str, key: str, value: Any) -> dict[str, Any]:
    """Set ``workflow[node_id]["inputs"][key] = value``. Returns a *new* dict."""
    w = clone(workflow)
    node = w.get(node_id)
    if node is None:
        raise KeyError(f"node {node_id!r} not found in workflow")
    node.setdefault("inputs", {})[key] = value
    return w


def set_prompt(workflow: dict[str, Any], text: str, *, class_type: str = "CLIPTextEncode") -> dict[str, Any]:
    """Replace the ``text`` input on every node of ``class_type``."""
    w = clone(workflow)
    for nid in find_nodes(w, class_type):
        w[nid].setdefault("inputs", {})["text"] = text
    return w


def randomize_seeds(workflow: dict[str, Any], *, rng: random.Random | None = None) -> dict[str, Any]:
    """Replace every ``inputs.seed`` and ``inputs.noise_seed`` with fresh randoms."""
    r = rng or random.Random()
    w = clone(workflow)
    for node in w.values():
        inputs = node.get("inputs") or {}
        if "seed" in inputs and isinstance(inputs["seed"], int):
            inputs["seed"] = r.randint(0, 2**63 - 1)
        if "noise_seed" in inputs and isinstance(inputs["noise_seed"], int):
            inputs["noise_seed"] = r.randint(0, 2**63 - 1)
    return w
