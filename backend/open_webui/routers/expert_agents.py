import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from open_webui.config import HERMES_EXPERT_AGENT_SKILLS_DIR
from open_webui.utils.auth import get_verified_user

log = logging.getLogger(__name__)

router = APIRouter()

EXPERT_AGENT_EXPERTS_DIR_NAME = "experts"
EXCLUDED_SKILL_DIRS = frozenset((".git", ".github", ".hub", ".archive", "__pycache__"))
EXPERT_AGENT_ICON_NAMES = frozenset(
    (
        "sparkles",
        "book-open",
        "bot",
        "wrench",
        "boxes",
        "compass",
        "workflow",
        "drafting-compass",
        "chart-no-axes-combined",
        "database",
        "file-text",
        "lightbulb",
        "hammer",
        "cog",
        "cpu",
        "circuit-board",
        "blocks",
        "package",
        "factory",
        "ruler",
        "pencil-ruler",
        "scan-search",
        "search",
        "clipboard-list",
        "table",
        "presentation",
        "code",
        "terminal",
        "rocket",
        "shield-check",
        "brain-circuit",
        "messages-square",
    )
)
EXPERT_AGENT_ICON_BACKGROUNDS = frozenset(
    (
        "#e6edf7",
        "#ebeaf5",
        "#e8eef2",
        "#eef0e8",
        "#f0ece7",
        "#f1e9ee",
        "#edeef1",
        "#edf0e6",
        "#eef4ff",
        "#eef8f3",
        "#fff3e8",
        "#f3efff",
        "#eef7fb",
        "#fff1f2",
        "#fef9c3",
        "#ecfdf5",
        "#dbeafe",
        "#dcfce7",
        "#ffedd5",
        "#ede9fe",
        "#e0f2fe",
        "#ffe4e6",
        "#fef08a",
        "#ccfbf1",
    )
)
EXPERT_AGENT_ICON_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")


class ExpertAgentItem(BaseModel):
    skill_name: str
    description: str = ""
    version: str | None = None
    author: str | None = None
    icon: str | None = None
    icon_background: str | None = None
    tags: list[str] = Field(default_factory=list)


class ExpertAgentListResponse(BaseModel):
    items: list[ExpertAgentItem]


class ExpertAgentDetailResponse(BaseModel):
    name: str
    description: str = ""
    version: str | None = None
    author: str | None = None
    icon: str | None = None
    icon_background: str | None = None
    content: str
    path: str | None = None
    tags: list[str] = Field(default_factory=list)
    related_skills: list[str] = Field(default_factory=list)
    linked_files: dict[str, list[str]] | None = None
    readiness_status: str | None = None
    setup_needed: bool | None = None
    setup_note: str | None = None
    metadata: dict[str, Any] | None = None


class ExpertAgentUpdateRequest(BaseModel):
    content: str
    icon: str | None = None
    icon_background: str | None = None


class ExpertAgentAppearanceRequest(BaseModel):
    icon: str
    icon_background: str


class ExpertAgentOpenDirectoryResponse(BaseModel):
    ok: bool = True
    path: str


def _default_skills_root() -> Path:
    hermes_home = Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")
    for profile_name in ("expertagent", "expert-agent"):
        profile_skills_root = hermes_home / "profiles" / profile_name / "skills"
        if profile_skills_root.exists():
            return profile_skills_root
    return hermes_home / "skills"


def _skills_root() -> Path:
    return (
        Path(HERMES_EXPERT_AGENT_SKILLS_DIR).expanduser()
        if HERMES_EXPERT_AGENT_SKILLS_DIR
        else _default_skills_root()
    )


def _expert_agents_root() -> Path:
    return _skills_root() / EXPERT_AGENT_EXPERTS_DIR_NAME


def _read_skill_frontmatter(content: str) -> dict[str, Any]:
    if not content.startswith("---"):
        return {}

    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}

    for index, line in enumerate(lines[1:], start=1):
        if line.strip() != "---":
            continue

        raw_frontmatter = "\n".join(lines[1:index])
        try:
            parsed = yaml.safe_load(raw_frontmatter) or {}
            return parsed if isinstance(parsed, dict) else {}
        except yaml.YAMLError as e:
            log.warning("Failed to parse Hermes skill frontmatter: %s", e)
            return {}

    return {}


def _split_skill_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    if not content.startswith("---"):
        return {}, content

    lines = content.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, content

    for index, line in enumerate(lines[1:], start=1):
        if line.strip() != "---":
            continue

        raw_frontmatter = "".join(lines[1:index])
        body = "".join(lines[index + 1 :])
        try:
            parsed = yaml.safe_load(raw_frontmatter) or {}
            return (parsed if isinstance(parsed, dict) else {}), body
        except yaml.YAMLError as e:
            log.warning("Failed to parse Hermes skill frontmatter for update: %s", e)
            return {}, content

    return {}, content


def _format_skill_frontmatter(frontmatter: dict[str, Any], body: str) -> str:
    serialized = yaml.safe_dump(
        frontmatter,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    ).strip()
    normalized_body = body.lstrip("\r\n")
    return f"---\n{serialized}\n---\n\n{normalized_body}"


def _line_indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _find_yaml_block_end(lines: list[str], start: int, base_indent: int) -> int:
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if not line.strip():
            continue
        if _line_indent(line) <= base_indent:
            return index
    return len(lines)


def _open_webui_frontmatter_block(icon: str, icon_background: str) -> list[str]:
    return [
        "  open_webui:",
        "    expert_agent:",
        f"      icon: {icon}",
        f"      icon_background: '{icon_background}'",
    ]


def _normalize_metadata_key_spacing(raw_frontmatter: str) -> str:
    return "\n".join(
        re.sub(
            r"^(\s*(?:tags|category|related_skills|icon|icon_background):)(\S)",
            r"\1 \2",
            line,
        )
        for line in raw_frontmatter.splitlines()
    )


def _normalize_skill_frontmatter_key_spacing(content: str) -> str:
    match = re.match(
        r"^(---\s*\r?\n)([\s\S]*?)(\r?\n---\s*(?:\r?\n)?)([\s\S]*)$",
        content,
    )
    if not match:
        return content

    opening, raw_frontmatter, closing, body = match.groups()
    return f"{opening}{_normalize_metadata_key_spacing(raw_frontmatter)}{closing}{body}"


def _inject_open_webui_metadata(
    raw_frontmatter: str, icon: str, icon_background: str
) -> str:
    lines = raw_frontmatter.splitlines()
    metadata_index = next(
        (
            index
            for index, line in enumerate(lines)
            if re.match(r"^metadata:\s*(?:#.*)?$", line)
        ),
        -1,
    )
    block = _open_webui_frontmatter_block(icon, icon_background)

    if metadata_index == -1:
        if lines and lines[-1].strip():
            lines.append("metadata:")
        else:
            while lines and not lines[-1].strip():
                lines.pop()
            lines.append("metadata:")
        lines.extend(block)
        return _normalize_metadata_key_spacing("\n".join(lines))

    metadata_indent = _line_indent(lines[metadata_index])
    metadata_end = _find_yaml_block_end(lines, metadata_index, metadata_indent)
    open_webui_index = -1
    for index in range(metadata_index + 1, metadata_end):
        line = lines[index]
        if (
            line.strip().startswith("open_webui:")
            and _line_indent(line) == metadata_indent + 2
        ):
            open_webui_index = index
            break

    if open_webui_index != -1:
        open_webui_end = _find_yaml_block_end(
            lines, open_webui_index, metadata_indent + 2
        )
        lines[open_webui_index:open_webui_end] = block
    else:
        lines[metadata_end:metadata_end] = block

    return _normalize_metadata_key_spacing("\n".join(lines))


def _expert_agent_ui_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    open_webui_metadata = (
        metadata.get("open_webui")
        if isinstance(metadata.get("open_webui"), dict)
        else {}
    )
    expert_agent_metadata = (
        open_webui_metadata.get("expert_agent")
        if isinstance(open_webui_metadata.get("expert_agent"), dict)
        else {}
    )
    return expert_agent_metadata


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if item is not None and str(item).strip()]


def _apply_expert_agent_ui_metadata(
    content: str, icon: str | None, icon_background: str | None
) -> str:
    if icon is not None:
        if len(icon) > 64 or not EXPERT_AGENT_ICON_NAME_PATTERN.match(icon):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported expert skill icon",
            )

    if icon_background is not None:
        if icon_background not in EXPERT_AGENT_ICON_BACKGROUNDS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported expert skill icon background",
            )

    if icon is None or icon_background is None:
        return content

    match = re.match(r"^(---\s*\r?\n)([\s\S]*?)(\r?\n---\s*(?:\r?\n)?)([\s\S]*)$", content)
    if not match:
        raw_frontmatter = _inject_open_webui_metadata("", icon, icon_background)
        return f"---\n{raw_frontmatter}\n---\n\n{content.lstrip()}"

    opening, raw_frontmatter, closing, body = match.groups()
    updated_frontmatter = _inject_open_webui_metadata(
        raw_frontmatter, icon, icon_background
    )
    return f"{opening}{updated_frontmatter}{closing}{body}"


def _read_skill(skill_md: Path) -> dict[str, Any] | None:
    try:
        content = skill_md.read_text(encoding="utf-8")
    except OSError as e:
        log.warning("Failed to read Hermes skill %s: %s", skill_md, e)
        return None

    frontmatter = _read_skill_frontmatter(content)
    metadata = (
        frontmatter.get("metadata")
        if isinstance(frontmatter.get("metadata"), dict)
        else {}
    )
    hermes_metadata = (
        metadata.get("hermes") if isinstance(metadata.get("hermes"), dict) else {}
    )
    expert_agent_metadata = _expert_agent_ui_metadata(metadata)

    return {
        "name": str(frontmatter.get("name") or skill_md.parent.name),
        "description": str(frontmatter.get("description") or ""),
        "version": (
            str(frontmatter.get("version")) if frontmatter.get("version") else None
        ),
        "author": str(frontmatter.get("author")) if frontmatter.get("author") else None,
        "icon": (
            str(expert_agent_metadata.get("icon"))
            if expert_agent_metadata.get("icon")
            else None
        ),
        "icon_background": (
            str(expert_agent_metadata.get("icon_background"))
            if expert_agent_metadata.get("icon_background")
            else None
        ),
        "content": content,
        "path": str(skill_md.parent),
        "tags": (
            _string_list(hermes_metadata.get("tags"))
        ),
        "related_skills": (
            _string_list(hermes_metadata.get("related_skills"))
        ),
        "linked_files": (
            hermes_metadata.get("linked_files")
            if isinstance(hermes_metadata.get("linked_files"), dict)
            else None
        ),
        "readiness_status": hermes_metadata.get("readiness_status"),
        "setup_needed": hermes_metadata.get("setup_needed"),
        "setup_note": hermes_metadata.get("setup_note"),
        "metadata": metadata or None,
        "_skill_md": skill_md,
    }


def _is_excluded_path(path: Path, root: Path) -> bool:
    try:
        relative_parts = path.relative_to(root).parts
    except ValueError:
        return True
    return any(
        part in EXCLUDED_SKILL_DIRS or part.startswith(".") for part in relative_parts
    )


def _load_visible_skills() -> list[dict[str, Any]]:
    root = _expert_agents_root()
    if not root.exists():
        log.warning("Hermes Expert Agent experts directory does not exist: %s", root)
        return []

    skills = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if _is_excluded_path(skill_md, root):
            continue

        skill = _read_skill(skill_md)
        if not skill:
            continue
        skills.append(skill)

    return sorted(skills, key=lambda item: str(item.get("name") or "").lower())


def _find_visible_skill(skill_name: str) -> dict[str, Any] | None:
    for skill in _load_visible_skills():
        names = {str(skill.get("name") or ""), skill["_skill_md"].parent.name}
        if skill_name in names:
            return skill
    return None


@router.get("", response_model=ExpertAgentListResponse)
@router.get("/", response_model=ExpertAgentListResponse)
async def get_expert_agents(user=Depends(get_verified_user)):
    items = [
        ExpertAgentItem(
            skill_name=skill["name"],
            description=skill.get("description") or "",
            version=skill.get("version"),
            author=skill.get("author"),
            icon=skill.get("icon"),
            icon_background=skill.get("icon_background"),
            tags=skill.get("tags") or [],
        )
        for skill in _load_visible_skills()
    ]
    return ExpertAgentListResponse(items=items)


@router.get("/{skill_name:path}", response_model=ExpertAgentDetailResponse)
async def get_expert_agent_detail(skill_name: str, user=Depends(get_verified_user)):
    skill = _find_visible_skill(skill_name)
    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expert skill not found",
        )

    return ExpertAgentDetailResponse(
        name=skill["name"],
        description=skill.get("description") or "",
        version=skill.get("version"),
        author=skill.get("author"),
        icon=skill.get("icon"),
        icon_background=skill.get("icon_background"),
        content=skill.get("content") or "",
        path=skill.get("path"),
        tags=skill.get("tags") or [],
        related_skills=skill.get("related_skills") or [],
        linked_files=skill.get("linked_files"),
        readiness_status=skill.get("readiness_status"),
        setup_needed=skill.get("setup_needed"),
        setup_note=skill.get("setup_note"),
        metadata=skill.get("metadata"),
    )


@router.patch("/{skill_name:path}", response_model=ExpertAgentDetailResponse)
async def update_expert_agent_detail(
    skill_name: str,
    form_data: ExpertAgentUpdateRequest,
    user=Depends(get_verified_user),
):
    return _update_expert_agent_detail(skill_name, form_data)


@router.post("/{skill_name:path}/update", response_model=ExpertAgentDetailResponse)
async def update_expert_agent_detail_post(
    skill_name: str,
    form_data: ExpertAgentUpdateRequest,
    user=Depends(get_verified_user),
):
    return _update_expert_agent_detail(skill_name, form_data)


@router.post("/{skill_name:path}/appearance", response_model=ExpertAgentDetailResponse)
async def update_expert_agent_appearance(
    skill_name: str,
    form_data: ExpertAgentAppearanceRequest,
    user=Depends(get_verified_user),
):
    skill = _find_visible_skill(skill_name)
    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expert skill not found",
        )

    content = _apply_expert_agent_ui_metadata(
        skill.get("content") or "",
        form_data.icon,
        form_data.icon_background,
    )
    content = _normalize_skill_frontmatter_key_spacing(content)

    skill_md = skill["_skill_md"]
    try:
        skill_md.write_text(content, encoding="utf-8")
    except OSError as e:
        log.exception("Failed to update Hermes expert skill appearance %s", skill_md)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update expert skill appearance",
        ) from e

    updated_skill = _read_skill(skill_md)
    if not updated_skill:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reload expert skill",
        )

    return _expert_agent_detail_response(updated_skill)


@router.post(
    "/{skill_name:path}/open-directory",
    response_model=ExpertAgentOpenDirectoryResponse,
)
async def open_expert_agent_directory(skill_name: str, user=Depends(get_verified_user)):
    skill = _find_visible_skill(skill_name)
    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expert skill not found",
        )

    skill_dir = Path(skill["path"]).expanduser().resolve()
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(skill_dir)])
        elif sys.platform.startswith("linux"):
            subprocess.Popen(["xdg-open", str(skill_dir)])
        elif sys.platform.startswith("win"):
            subprocess.Popen(["explorer", str(skill_dir)])
        else:
            raise OSError(f"Unsupported platform: {sys.platform}")
    except OSError as e:
        log.exception("Failed to open Hermes expert skill directory %s", skill_dir)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to open expert skill directory",
        ) from e

    return ExpertAgentOpenDirectoryResponse(path=str(skill_dir))


def _expert_agent_detail_response(skill: dict[str, Any]) -> ExpertAgentDetailResponse:
    return ExpertAgentDetailResponse(
        name=skill["name"],
        description=skill.get("description") or "",
        version=skill.get("version"),
        author=skill.get("author"),
        icon=skill.get("icon"),
        icon_background=skill.get("icon_background"),
        content=skill.get("content") or "",
        path=skill.get("path"),
        tags=skill.get("tags") or [],
        related_skills=skill.get("related_skills") or [],
        linked_files=skill.get("linked_files"),
        readiness_status=skill.get("readiness_status"),
        setup_needed=skill.get("setup_needed"),
        setup_note=skill.get("setup_note"),
        metadata=skill.get("metadata"),
    )


def _update_expert_agent_detail(
    skill_name: str, form_data: ExpertAgentUpdateRequest
):
    skill = _find_visible_skill(skill_name)
    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expert skill not found",
        )

    content = form_data.content
    if not content.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Expert skill markdown cannot be empty",
        )

    content = _apply_expert_agent_ui_metadata(
        content,
        form_data.icon,
        form_data.icon_background,
    )
    content = _normalize_skill_frontmatter_key_spacing(content)

    skill_md = skill["_skill_md"]
    try:
        skill_md.write_text(content, encoding="utf-8")
    except OSError as e:
        log.exception("Failed to update Hermes expert skill %s", skill_md)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update expert skill",
        ) from e

    updated_skill = _read_skill(skill_md)
    if not updated_skill:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reload expert skill",
        )

    return _expert_agent_detail_response(updated_skill)
