"""Reads and checks config.yaml (SRG-17, D11, D14, D23).

The tool stops with a ConfigError when the file has an error.
Each message names the line in config.yaml where the error is.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

PRIORITY_LEVELS = ("P1", "P2", "P3", "P4", "P5")
UNMAPPED = "Unmapped"
BLOCKED_METHODS = {"status", "flag", "label"}
OUTPUT_FORMATS = {"markdown", "html"}


class ConfigError(Exception):
    """config.yaml has an error. The message tells the user how to correct it."""


@dataclass(frozen=True)
class Config:
    project_key: str
    timezone: str
    work_types: tuple[str, ...]
    priority_map: dict[str, str]  # Jira priority name -> P1 to P5
    blocked_methods: tuple[str, ...]
    blocked_status_name: str | None
    blocked_label: str | None
    amber_window_days: int
    amber_only_status: str
    high_priorities: tuple[str, ...]
    ai_enabled: bool
    ai_model: str
    max_tokens_per_run: int
    hide_titles_from_ai: bool
    output_folder: str
    output_formats: tuple[str, ...]
    warnings: list[str] = field(default_factory=list, compare=False)

    def priority_level(self, jira_priority: str | None) -> str:
        """Return P1 to P5 for a Jira priority name, or "Unmapped" (decision A)."""
        if jira_priority is None:
            return UNMAPPED
        return self.priority_map.get(jira_priority.strip().lower(), UNMAPPED)

    def unmapped_warning(self, ticket_key: str, jira_priority: str | None) -> str:
        """Warning text for a ticket whose priority is not in priority_map."""
        name = jira_priority if jira_priority else "(no priority)"
        return (
            f"{ticket_key}: priority '{name}' is not in priority_map in config.yaml. "
            f"The ticket is in the '{UNMAPPED}' row."
        )


def load_config(path: str | Path = "config.yaml") -> Config:
    """Read config.yaml, check each setting, and return a Config."""
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"{path}: file not found. Copy config.yaml from the repository.")

    text = path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(text)
        root = yaml.compose(text)
    except yaml.YAMLError as error:
        line = _error_line(error)
        where = f"{path.name} line {line}" if line else path.name
        raise ConfigError(f"{where}: the file is not valid YAML. {_problem(error)}") from None

    if not isinstance(data, dict):
        raise ConfigError(f"{path.name}: the file must contain settings in the form 'name: value'.")

    return _Checker(path.name, data, root).build()


class _Checker:
    """Checks each setting and gives an error message with the line number."""

    def __init__(self, file_name: str, data: dict, root: yaml.Node):
        self.file_name = file_name
        self.data = data
        self.root = root

    # --- helpers -------------------------------------------------------

    def line_of(self, *keys: str) -> int | None:
        node = self.root
        for key in keys:
            if not isinstance(node, yaml.MappingNode):
                return None
            for key_node, value_node in node.value:
                if key_node.value == key:
                    node = value_node
                    break
            else:
                return self.line_of(*keys[:-1]) if len(keys) > 1 else None
        return node.start_mark.line + 1

    def fail(self, keys: tuple[str, ...], message: str) -> ConfigError:
        line = self.line_of(*keys)
        where = f"{self.file_name} line {line}" if line else self.file_name
        return ConfigError(f"{where}: {'.'.join(keys)}: {message}")

    def get(self, *keys: str, required: bool = True, default=None):
        value = self.data
        for key in keys:
            if not isinstance(value, dict) or key not in value:
                if required:
                    raise self.fail(keys, "this setting is missing.")
                return default
            value = value[key]
        return value

    def text(self, *keys: str, required: bool = True, default=None) -> str | None:
        value = self.get(*keys, required=required, default=default)
        if value is None and not required:
            return None
        if not isinstance(value, str) or not value.strip():
            raise self.fail(keys, "must be a text value.")
        return value.strip()

    def text_list(self, *keys: str) -> tuple[str, ...]:
        value = self.get(*keys)
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list) or not value:
            raise self.fail(keys, "must be a list with one or more items.")
        if not all(isinstance(item, str) and item.strip() for item in value):
            raise self.fail(keys, "each item must be a text value.")
        return tuple(item.strip() for item in value)

    def integer(self, *keys: str, minimum: int) -> int:
        value = self.get(*keys)
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise self.fail(keys, f"must be a whole number of {minimum} or more.")
        return value

    def boolean(self, *keys: str) -> bool:
        value = self.get(*keys)
        if not isinstance(value, bool):
            raise self.fail(keys, "must be true or false.")
        return value

    # --- checks --------------------------------------------------------

    def priority_map(self) -> dict[str, str]:
        raw = self.get("priority_map")
        if not isinstance(raw, dict):
            raise self.fail(("priority_map",), "must give a Jira priority name for P1 to P5.")
        for level in raw:
            if level not in PRIORITY_LEVELS:
                raise self.fail(
                    ("priority_map", str(level)),
                    f"'{level}' is not valid. Use P1, P2, P3, P4, and P5 only.",
                )
        result: dict[str, str] = {}
        for level in PRIORITY_LEVELS:
            for name in self.text_list("priority_map", level):
                key = name.lower()
                if key in result:
                    raise self.fail(
                        ("priority_map", level),
                        f"'{name}' is also in {result[key]}. Each Jira name can have one level only.",
                    )
                result[key] = level
        return result

    def blocked(self) -> tuple[tuple[str, ...], str | None, str | None]:
        methods = self.text_list("blocked_method")
        for method in methods:
            if method not in BLOCKED_METHODS:
                raise self.fail(
                    ("blocked_method",),
                    f"'{method}' is not valid. Use status, flag, or label.",
                )
        status_name = self.text("blocked_status_name", required="status" in methods)
        label = self.text("blocked_label", required="label" in methods)
        return methods, status_name, label

    def work_types(self) -> tuple[str, ...]:
        types = self.text_list("work_types")
        for name in types:
            if name.lower() in {"epic", "subtask", "sub-task"}:
                raise self.fail(
                    ("work_types",),
                    f"'{name}' cannot be counted. Epics and subtasks are not counted (D23).",
                )
        return types

    def high_priorities(self) -> tuple[str, ...]:
        levels = self.text_list("project_status", "high_priorities")
        for level in levels:
            if level not in PRIORITY_LEVELS:
                raise self.fail(
                    ("project_status", "high_priorities"),
                    f"'{level}' is not valid. Use P1 to P5.",
                )
        return levels

    def output_formats(self) -> tuple[str, ...]:
        formats = self.text_list("output", "formats")
        for name in formats:
            if name not in OUTPUT_FORMATS:
                raise self.fail(
                    ("output", "formats"),
                    f"'{name}' is not valid. Use markdown or html.",
                )
        return formats

    def build(self) -> Config:
        methods, status_name, label = self.blocked()
        return Config(
            project_key=self.text("jira", "project_key"),
            timezone=self.text("jira", "timezone"),
            work_types=self.work_types(),
            priority_map=self.priority_map(),
            blocked_methods=methods,
            blocked_status_name=status_name,
            blocked_label=label,
            amber_window_days=self.integer("ticket_status", "amber_window_days", minimum=0),
            amber_only_status=self.text("ticket_status", "amber_only_status"),
            high_priorities=self.high_priorities(),
            ai_enabled=self.boolean("ai", "enabled"),
            ai_model=self.text("ai", "model"),
            max_tokens_per_run=self.integer("ai", "max_tokens_per_run", minimum=1),
            hide_titles_from_ai=self.boolean("ai", "hide_titles_from_ai"),
            output_folder=self.text("output", "folder"),
            output_formats=self.output_formats(),
        )


def _error_line(error: yaml.YAMLError) -> int | None:
    mark = getattr(error, "problem_mark", None)
    return mark.line + 1 if mark else None


def _problem(error: yaml.YAMLError) -> str:
    problem = getattr(error, "problem", None)
    return f"Problem: {problem}." if problem else ""
