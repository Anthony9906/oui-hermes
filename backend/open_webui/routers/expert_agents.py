import logging
import os
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from open_webui.config import (
    HERMES_EXPERT_AGENT_HIDDEN_SKILLS,
    HERMES_EXPERT_AGENT_SKILLS_DIR,
    HERMES_EXPERT_AGENT_VISIBLE_SKILLS,
)
from open_webui.utils.auth import get_verified_user

log = logging.getLogger(__name__)

router = APIRouter()

EXCLUDED_SKILL_DIRS = frozenset((".git", ".github", ".hub", ".archive", "__pycache__"))


class ExpertAgentItem(BaseModel):
    skill_name: str
    description: str = ""


class ExpertAgentListResponse(BaseModel):
    items: list[ExpertAgentItem]


class ExpertAgentDetailResponse(BaseModel):
    name: str
    description: str = ""
    content: str
    path: str | None = None
    tags: list[str] = Field(default_factory=list)
    related_skills: list[str] = Field(default_factory=list)
    linked_files: dict[str, list[str]] | None = None
    readiness_status: str | None = None
    setup_needed: bool | None = None
    setup_note: str | None = None
    metadata: dict[str, Any] | None = None


def _split_env_list(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


def _default_skills_root() -> Path:
    hermes_home = Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")
    expertagent_root = hermes_home / "profiles" / "expertagent" / "skills"
    if expertagent_root.exists():
        return expertagent_root
    return hermes_home / "skills"


def _skills_root() -> Path:
    return (
        Path(HERMES_EXPERT_AGENT_SKILLS_DIR).expanduser()
        if HERMES_EXPERT_AGENT_SKILLS_DIR
        else _default_skills_root()
    )


def _read_bundled_skill_names(root: Path) -> set[str]:
    manifest = root / ".bundled_manifest"
    if not manifest.exists():
        return set()

    bundled = set()
    try:
        for line in manifest.read_text(encoding="utf-8").splitlines():
            name, _, _digest = line.partition(":")
            name = name.strip()
            if name:
                bundled.add(name)
    except OSError as e:
        log.warning("Failed to read Hermes bundled skill manifest %s: %s", manifest, e)
    return bundled


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

    return {
        "name": str(frontmatter.get("name") or skill_md.parent.name),
        "description": str(frontmatter.get("description") or ""),
        "content": content,
        "path": str(skill_md.parent),
        "tags": (
            hermes_metadata.get("tags")
            if isinstance(hermes_metadata.get("tags"), list)
            else []
        ),
        "related_skills": (
            hermes_metadata.get("related_skills")
            if isinstance(hermes_metadata.get("related_skills"), list)
            else []
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


def _is_visible_skill(
    skill: dict[str, Any], bundled: set[str], hidden: set[str], visible: set[str]
) -> bool:
    names = {str(skill.get("name") or ""), skill["_skill_md"].parent.name}
    names.discard("")

    if names & bundled:
        return False
    if hidden and names & hidden:
        return False
    if visible and not (names & visible):
        return False
    return True


def _load_visible_skills() -> list[dict[str, Any]]:
    root = _skills_root()
    if not root.exists():
        log.warning("Hermes expert agent skills directory does not exist: %s", root)
        return []

    bundled = _read_bundled_skill_names(root)
    hidden = _split_env_list(HERMES_EXPERT_AGENT_HIDDEN_SKILLS)
    visible = _split_env_list(HERMES_EXPERT_AGENT_VISIBLE_SKILLS)

    skills = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if _is_excluded_path(skill_md, root):
            continue

        skill = _read_skill(skill_md)
        if not skill or not _is_visible_skill(skill, bundled, hidden, visible):
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
