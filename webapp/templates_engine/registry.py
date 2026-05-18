"""Template registry."""
from __future__ import annotations
import importlib
import os
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Template:
    id: str
    name: str
    description: str
    slide_count_default: int
    slide_count_min: int
    slide_count_max: int
    schema_fields: list[dict]
    system_prompt: str
    user_template: str
    # Module reference so the engine can call module-specific helpers if needed
    module: Any = None


_REGISTRY: dict[str, Template] = {}


def register(tpl: Template):
    _REGISTRY[tpl.id] = tpl


def list_templates() -> list[Template]:
    return sorted(_REGISTRY.values(), key=lambda t: t.id)


def get_template(template_id: str) -> Optional[Template]:
    return _REGISTRY.get(template_id)


# ---- Auto-discover templates in this folder ----

def _discover():
    """Auto-load every template file in this package using relative imports.
    Relative imports guarantee we always hit the same module instance no matter
    how the caller imported the registry (`templates_engine` vs
    `webapp.templates_engine`)."""
    here = os.path.dirname(os.path.abspath(__file__))
    for fn in os.listdir(here):
        if not fn.endswith(".py") or fn.startswith("_"):
            continue
        if fn in ("registry.py", "compositor.py", "generator.py",
                  "image_gen.py", "zip_export.py"):
            continue
        mod_name = fn[:-3]
        try:
            mod = importlib.import_module(f".{mod_name}", package=__package__)
        except Exception as e:
            print(f"  template '{mod_name}' load error: {e}")
            continue
        tpl = getattr(mod, "TEMPLATE", None)
        if isinstance(tpl, Template):
            tpl.module = mod
            register(tpl)


_discover()
