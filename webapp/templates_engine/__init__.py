"""Template engine — generic carousel templates for any niche.

Each template is a Python file in this folder that exports:
  - id (slug)
  - name (display)
  - description
  - slide_count_default / slide_count_min / slide_count_max
  - schema_fields (list of {key, label, type, placeholder, optional})
  - SYSTEM_PROMPT / USER_TEMPLATE (Gemini prompts)
  - SLIDE_LAYOUT (list of slide-type names — driven by the JSON Gemini returns)

The registry auto-discovers templates by walking this folder.
"""
from .registry import (
    Template,
    list_templates,
    get_template,
)
