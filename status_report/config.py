"""Reads and checks the settings file, config.yaml (v2 spec SRG-R13.1, SRG-R13.2).

The file lists the teams (one Jira project for each team) and the v1 rule settings.
Each v1 setting is optional and has its v1 default. There are no AI settings.
The tool stops with a ConfigError when the file has an error. Each message says what is
wrong and how to correct it, and names the line in config.yaml where it can.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

PRIORITY_LEVELS = ("P1", "P2", "P3", "P4", "P5")
HIGH_PRIORITIES = ("P1", "P2")  # Spec §4: "High priority" = P1 or P2
UNMAPPED = "Unmapped"
BLOCKED_METHODS = {"status", "flag", "label"}
NOT_STARTED = "To Do"  # Spec §4: "Not started" = status category To Do
PROJECT_KEY = re.compile(r"^[A-Z][A-Z0-9_]{0,19}$")  # Jira project key

DEFAULT_PRIORITY_MAP = {"P1": "Highest", "P2": "High", "P3": "Medium", "P4": "Low", "P5": "Lowest"}
DEFAULTS = {
    "work_types": ["Story", "Task", "Bug"],
    "priority_map": DEFAULT_PRIORITY_MAP,
    "blocked_method": ["status"],
    "blocked_status_name": "Blocked",
    "blocked_label": "blocked",
    "amber_window_days": 2,
    "forecast": True,
    "output_folder": "output",
}
SETTINGS = {"teams", "timezone", *DEFAULTS}

NO_TEAMS = "The settings file has no teams. Add a project key and a team name."


class ConfigError(Exception):
    """The settings file has an error. The message tells the user how to correct it."""


@dataclass(frozen=True)
class Team:
    key: str  # Jira project key, for example ALP
    name: str  # Team name on the page and in the report, for example Alpha


@dataclass(frozen=True)
class Config:
    teams: tuple[Team, ...]
    timezone: str
    work_types: tuple[str, ...] = ("Story", "Task", "Bug")
    priority_map: dict[str, str] = field(
        default_factory=lambda: {name.lower(): level for level, name in DEFAULT_PRIORITY_MAP.items()}
    )  # Jira priority name (lower case) -> P1 to P5
    blocked_methods: tuple[str, ...] = ("status",)
    blocked_status_name: str | None = "Blocked"
    blocked_label: str | None = "blocked"
    amber_window_days: int = 2
    forecast: bool = True
    output_folder: str = "output"
    # Fixed by the spec definitions (§4). Not settings any more.
    amber_status_category: str = NOT_STARTED
    high_priorities: tuple[str, ...] = HIGH_PRIORITIES

    @property
    def project_key(self) -> str:
        """The first team's project key (the v1 weekly command reads one project)."""
        return self.teams[0].key

    def priority_level(self, jira_priority: str | None) -> str:
        """Return P1 to P5 for a Jira priority name, or "Unmapped"."""
        if jira_priority is None:
            return UNMAPPED
        return self.priority_map.get(jira_priority.strip().lower(), UNMAPPED)

    def is_high(self, jira_priority: str | None) -> bool:
        """Spec §4: P1 or P2. A priority that is not in priority_map is not high (SRG-R13.4)."""
        return self.priority_level(jira_priority) in self.high_priorities

    def unmapped_warning(self, ticket_key: str, jira_priority: str | None) -> str:
        """Warning for a ticket whose priority is not in priority_map (SRG-R13.4)."""
        name = jira_priority if jira_priority else "(no priority)"
        return (
            f"{ticket_key}: priority '{name}' is not in priority_map in config.yaml. "
            f"The ticket is treated as not high priority ('{UNMAPPED}')."
        )


def local_timezone() -> str:
    """The time zone name of this computer (spec §4 default), or UTC if it cannot be found."""
    name = os.environ.get("TZ", "").lstrip(":")
    if name and _valid_zone(name):
        return name
    try:
        target = os.path.realpath("/etc/localtime")
    except OSError:
        target = ""
    if "zoneinfo/" in target:
        name = target.split("zoneinfo/", 1)[1]
        if _valid_zone(name):
            return name
    return "UTC"


def _valid_zone(name: str) -> bool:
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return False
    return True


def load_config(path: str | Path = "config.yaml") -> Config:
    """Read the settings file, check each setting, and return a Config."""
    path = Path(path)
    if not path.is_file():
        raise ConfigError(
            f"The settings file {path} was not found. Copy config.yaml from the repository "
            "and add your teams."
        )

    text = path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(text)
        root = yaml.compose(text)
    except yaml.YAMLError as error:
        line = _error_line(error)
        where = f"{path.name} line {line}" if line else path.name
        raise ConfigError(f"{where}: the file is not valid YAML. {_problem(error)}") from None

    if data is None:
        raise ConfigError(NO_TEAMS)
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

    def node(self, *keys) -> yaml.Node | None:
        node = self.root
        for key in keys:
            if isinstance(node, yaml.MappingNode):
                found = [value for name, value in node.value if name.value == key]
            elif isinstance(node, yaml.SequenceNode) and isinstance(key, int):
                found = node.value[key:key + 1]
            else:
                found = []
            if not found:
                return node
            node = found[0]
        return node

    def fail(self, keys: tuple, message: str) -> ConfigError:
        node = self.node(*keys)
        line = node.start_mark.line + 1 if node is not None else None
        where = f"{self.file_name} line {line}" if line else self.file_name
        name = ".".join(str(k) for k in keys if not isinstance(k, int))
        return ConfigError(f"{where}: {name}: {message}" if name else f"{where}: {message}")

    def get(self, key: str):
        return self.data.get(key, DEFAULTS.get(key))

    def text(self, key: str, value=None) -> str:
        value = self.get(key) if value is None else value
        if not isinstance(value, str) or not value.strip():
            raise self.fail((key,), "must be a text value.")
        return value.strip()

    def text_list(self, keys: tuple, value) -> tuple[str, ...]:
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list) or not value:
            raise self.fail(keys, "must be a list with one or more items.")
        if not all(isinstance(item, str) and item.strip() for item in value):
            raise self.fail(keys, "each item must be a text value.")
        return tuple(item.strip() for item in value)

    # --- checks --------------------------------------------------------

    def unknown_settings(self) -> None:
        for key in self.data:
            if key not in SETTINGS:
                hint = " SRG v2 has no AI settings." if key == "ai" else ""
                raise self.fail(
                    (key,), f"'{key}' is not a setting. Remove it or check the spelling.{hint}"
                )

    def teams(self) -> tuple[Team, ...]:
        raw = self.data.get("teams")
        if raw is None or raw == []:
            raise ConfigError(NO_TEAMS)
        if not isinstance(raw, list):
            raise self.fail(("teams",), "must be a list. Each item has a key and a name.")
        teams = []
        for number, item in enumerate(raw):
            where = ("teams", number)
            if not isinstance(item, dict) or not item.get("key") or not item.get("name"):
                raise self.fail(
                    where,
                    f"team {number + 1} needs a project key and a team name, "
                    "for example '- {key: ALP, name: Alpha}'.",
                )
            key = str(item["key"]).strip().upper()
            if not PROJECT_KEY.match(key):
                raise self.fail(
                    where,
                    f"'{item['key']}' is not a Jira project key. Use the key from the ticket "
                    "numbers, for example ALP for ALP-12.",
                )
            teams.append(Team(key=key, name=str(item["name"]).strip()))
        for key in dict.fromkeys(t.key for t in teams):
            count = sum(1 for t in teams if t.key == key)
            if count > 1:
                raise ConfigError(f"Project {key} is listed {count} times. Remove one.")
        return tuple(teams)

    def timezone(self) -> str:
        if "timezone" not in self.data:
            return local_timezone()
        name = self.text("timezone")
        if not _valid_zone(name):
            raise self.fail(
                ("timezone",), f"'{name}' is not a time zone. Use a name such as America/Toronto."
            )
        return name

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
            if level not in raw:
                raise self.fail(("priority_map", level), "this setting is missing.")
            for name in self.text_list(("priority_map", level), raw[level]):
                key = name.lower()
                if key in result:
                    raise self.fail(
                        ("priority_map", level),
                        f"'{name}' is also in {result[key]}. Each Jira name can have one level only.",
                    )
                result[key] = level
        return result

    def blocked(self) -> tuple[tuple[str, ...], str, str]:
        methods = self.text_list(("blocked_method",), self.get("blocked_method"))
        for method in methods:
            if method not in BLOCKED_METHODS:
                raise self.fail(
                    ("blocked_method",), f"'{method}' is not valid. Use status, flag, or label."
                )
        return methods, self.text("blocked_status_name"), self.text("blocked_label")

    def work_types(self) -> tuple[str, ...]:
        types = self.text_list(("work_types",), self.get("work_types"))
        for name in types:
            if name.lower() in {"epic", "subtask", "sub-task"}:
                raise self.fail(
                    ("work_types",),
                    f"'{name}' cannot be counted. Epics and sub-tasks are not counted.",
                )
        return types

    def whole_number(self, key: str) -> int:
        value = self.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise self.fail((key,), "must be a whole number of 0 or more.")
        return value

    def boolean(self, key: str) -> bool:
        value = self.get(key)
        if not isinstance(value, bool):
            raise self.fail((key,), "must be true or false.")
        return value

    def build(self) -> Config:
        self.unknown_settings()
        teams = self.teams()
        methods, status_name, label = self.blocked()
        return Config(
            teams=teams,
            timezone=self.timezone(),
            work_types=self.work_types(),
            priority_map=self.priority_map(),
            blocked_methods=methods,
            blocked_status_name=status_name,
            blocked_label=label,
            amber_window_days=self.whole_number("amber_window_days"),
            forecast=self.boolean("forecast"),
            output_folder=self.text("output_folder"),
        )


def _error_line(error: yaml.YAMLError) -> int | None:
    mark = getattr(error, "problem_mark", None)
    return mark.line + 1 if mark else None


def _problem(error: yaml.YAMLError) -> str:
    problem = getattr(error, "problem", None)
    return f"Problem: {problem}." if problem else ""
