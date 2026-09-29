"""``game.toml`` reading, validation and writing.

Validation never raises: it returns every problem it finds, so a bad manifest
can still be listed (with a red ``[!]``) and explained in the details pane.
"""

from __future__ import annotations

import re
import string
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from retro99.library.systems import LAUNCHERS, System

MANIFEST_NAME = "game.toml"
PLACEHOLDERS = ("game_dir", "rom_path", "bios_dir", "saves_dir", "system")
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")

_STR_FIELDS = ("publisher", "genre", "notes")


@dataclass
class Manifest:
    id: str
    title: str
    system: str
    launcher: str
    program: str
    args: list[str] = field(default_factory=list)
    cwd: str = ""
    env: dict[str, str] = field(default_factory=dict)
    year: int | None = None
    publisher: str = ""
    genre: str = ""
    players: str = ""
    favorite: bool = False
    notes: str = ""
    exit_combo: str = "default"


@dataclass
class ManifestResult:
    manifest: Manifest | None
    errors: list[str]
    data: dict[str, Any] = field(default_factory=dict)  # whatever parsed, even if invalid

    @property
    def ok(self) -> bool:
        return self.manifest is not None and not self.errors


def placeholders_in(template: str) -> list[str]:
    """Field names used in a ``{placeholder}`` template (``{{`` escapes a brace)."""
    try:
        return [name for _, name, _, _ in string.Formatter().parse(template) if name is not None]
    except ValueError:
        return ["<malformed braces>"]


def _check_placeholders(where: str, template: str, errors: list[str]) -> None:
    for name in placeholders_in(template):
        if name not in PLACEHOLDERS:
            errors.append(f"{where}: unknown placeholder {{{name}}}")


def parse_manifest(
    data: dict[str, Any], systems: Mapping[str, System] | None = None
) -> ManifestResult:
    errors: list[str] = []

    def req_str(key: str, table: dict[str, Any], where: str = "") -> str:
        value = table.get(key)
        if value is None:
            errors.append(f"missing required field '{where}{key}'")
            return ""
        if not isinstance(value, str) or not value.strip():
            errors.append(f"'{where}{key}' must be a non-empty string")
            return ""
        return value

    game_id = req_str("id", data)
    if game_id and not ID_PATTERN.match(game_id):
        errors.append(f"id '{game_id}' may only use a-z, 0-9, '.', '_' and '-'")
    title = req_str("title", data)
    system = req_str("system", data)
    if system and systems is not None and system not in systems:
        errors.append(f"unknown system '{system}'")
    launcher = req_str("launcher", data)
    if launcher and launcher not in LAUNCHERS:
        errors.append(f"launcher must be one of {', '.join(LAUNCHERS)}, not '{launcher}'")

    year = data.get("year")
    if year is not None and (not isinstance(year, int) or isinstance(year, bool)
                             or not 1970 <= year <= 2100):  # fmt: skip
        errors.append("year must be a number between 1970 and 2100")
        year = None
    for key in _STR_FIELDS:
        if key in data and not isinstance(data[key], str):
            errors.append(f"'{key}' must be a string")
    players = data.get("players", "")
    if isinstance(players, int) and not isinstance(players, bool):
        players = str(players)
    elif not isinstance(players, str):
        errors.append("'players' must be a string like \"1-4\"")
        players = ""
    favorite = data.get("favorite", False)
    if not isinstance(favorite, bool):
        errors.append("'favorite' must be true or false")
        favorite = False

    launch = data.get("launch")
    program, args, cwd, env = "", [], "", {}
    if not isinstance(launch, dict):
        errors.append("missing [launch] table")
    else:
        program = req_str("program", launch, "launch.")
        raw_args = launch.get("args", [])
        if not isinstance(raw_args, list) or not all(isinstance(a, str) for a in raw_args):
            errors.append("'launch.args' must be a list of strings")
        else:
            args = raw_args
            for a in args:
                _check_placeholders("launch.args", a, errors)
        cwd = launch.get("cwd", "")
        if not isinstance(cwd, str):
            errors.append("'launch.cwd' must be a string")
            cwd = ""
        _check_placeholders("launch.cwd", cwd, errors)
        raw_env = launch.get("env", {})
        if not isinstance(raw_env, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in raw_env.items()
        ):
            errors.append("'launch.env' must be a table of strings")
        else:
            env = raw_env
            for k, v in env.items():
                _check_placeholders(f"launch.env.{k}", v, errors)

    exit_combo = "default"
    input_table = data.get("input", {})
    if not isinstance(input_table, dict):
        errors.append("[input] must be a table")
    elif "exit_combo" in input_table:
        if isinstance(input_table["exit_combo"], str):
            exit_combo = input_table["exit_combo"]
        else:
            errors.append("'input.exit_combo' must be a string")

    if errors:
        return ManifestResult(None, errors, data)
    manifest = Manifest(
        id=game_id,
        title=title.strip(),
        system=system,
        launcher=launcher,
        program=program,
        args=list(args),
        cwd=cwd,
        env=dict(env),
        year=year,
        publisher=data.get("publisher", ""),
        genre=data.get("genre", ""),
        players=players,
        favorite=favorite,
        notes=data.get("notes", ""),
        exit_combo=exit_combo,
    )
    return ManifestResult(manifest, [], data)


def load_manifest(path: Path, systems: Mapping[str, System] | None = None) -> ManifestResult:
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        return ManifestResult(None, [f"no {MANIFEST_NAME} in this folder"])
    except tomllib.TOMLDecodeError as e:
        return ManifestResult(None, [f"{MANIFEST_NAME} is not valid TOML: {e}"])
    except OSError as e:
        return ManifestResult(None, [f"cannot read {MANIFEST_NAME}: {e}"])
    return parse_manifest(data, systems)


# --------------------------------------------------------------------------- #
# Writing
# --------------------------------------------------------------------------- #

_BARE_KEY = re.compile(r"^[A-Za-z0-9_-]+$")


def toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return repr(value)
    if isinstance(value, str):
        escaped = (
            value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
            .replace("\t", "\\t")
        )  # fmt: skip
        return f'"{escaped}"'
    if isinstance(value, list | tuple):
        return "[" + ", ".join(toml_value(v) for v in value) + "]"
    raise TypeError(f"cannot write {type(value).__name__} to TOML")


def _key(k: str) -> str:
    return k if _BARE_KEY.match(k) else toml_value(k)


def dump_manifest(data: Mapping[str, Any]) -> str:
    """Serialize a manifest-shaped dict: scalars first, then one level of tables."""
    lines = [f"{_key(k)} = {toml_value(v)}" for k, v in data.items() if not isinstance(v, dict)]
    for name, table in data.items():
        if not isinstance(table, dict):
            continue
        lines.append("")
        lines.append(f"[{_key(name)}]")
        nested = {k: v for k, v in table.items() if isinstance(v, dict)}
        for k, v in table.items():
            if not isinstance(v, dict):
                lines.append(f"{_key(k)} = {toml_value(v)}")
        for k, sub in nested.items():
            lines.append("")
            lines.append(f"[{_key(name)}.{_key(k)}]")
            lines.extend(f"{_key(sk)} = {toml_value(sv)}" for sk, sv in sub.items())
    return "\n".join(lines) + "\n"


def set_top_level_key(text: str, key: str, value: Any) -> str:
    """Set ``key = value`` among the top-level keys of TOML ``text``, keeping everything
    else (comments, order, formatting) untouched."""
    lines = text.splitlines(keepends=True)
    key_line = re.compile(rf"^\s*{re.escape(key)}\s*=")
    # A bool/number value followed by a comment: keep the comment.
    scalar_line = re.compile(rf"^(\s*{re.escape(key)}\s*=\s*)(?:true|false|[-+0-9._]+)(\s*#.*)?$")
    first_table = len(lines)
    for i, line in enumerate(lines):
        if line.lstrip().startswith("["):
            first_table = i
            break
        if key_line.match(line):
            m = scalar_line.match(line.rstrip("\n"))
            if m:
                lines[i] = f"{m.group(1)}{toml_value(value)}{m.group(2) or ''}\n"
            else:
                lines[i] = f"{key} = {toml_value(value)}\n"
            return "".join(lines)
    # Not present: add it after the last top-level key, before any blank lines/tables.
    insert_at = first_table
    while insert_at > 0 and not lines[insert_at - 1].strip():
        insert_at -= 1
    if insert_at > 0 and not lines[insert_at - 1].endswith("\n"):
        lines[insert_at - 1] += "\n"
    lines.insert(insert_at, f"{key} = {toml_value(value)}\n")
    return "".join(lines)


def write_favorite(path: Path, favorite: bool) -> None:
    """Persist the favorite flag into an existing game.toml."""
    text = path.read_text(encoding="utf-8")
    updated = set_top_level_key(text, "favorite", favorite)
    tomllib.loads(updated)  # never write something we cannot read back
    path.write_text(updated, encoding="utf-8")
