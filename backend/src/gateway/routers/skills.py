import json
import logging
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.config.extensions_config import ExtensionsConfig, SkillStateConfig, get_extensions_config, reload_extensions_config
from src.gateway.path_utils import resolve_thread_virtual_path
from src.skills import Skill, load_skills
from src.skills.loader import get_skills_root_path

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["skills"])


class SkillResponse(BaseModel):
    """技能信息响应模型。"""

    name: str = Field(..., description="技能名称")
    description: str = Field(..., description="技能功能描述")
    license: str | None = Field(None, description="许可证信息")
    category: str = Field(..., description="技能分类（public 或 custom）")
    enabled: bool = Field(default=True, description="该技能是否启用")


class SkillsListResponse(BaseModel):
    """技能列表响应模型。"""

    skills: list[SkillResponse]


class SkillUpdateRequest(BaseModel):
    """更新技能请求模型。"""

    enabled: bool = Field(..., description="是否启用该技能")


class SkillInstallRequest(BaseModel):
    """从 `.skill` 文件安装技能的请求模型。"""

    thread_id: str = Field(..., description=".skill 文件所在线程 ID")
    path: str = Field(..., description=".skill 文件的虚拟路径（例如 mnt/user-data/outputs/my-skill.skill）")


class SkillInstallResponse(BaseModel):
    """技能安装响应模型。"""

    success: bool = Field(..., description="安装是否成功")
    skill_name: str = Field(..., description="已安装技能名称")
    message: str = Field(..., description="安装结果消息")


# `SKILL.md` frontmatter 允许出现的字段
ALLOWED_FRONTMATTER_PROPERTIES = {"name", "description", "license", "allowed-tools", "metadata"}


def _validate_skill_frontmatter(skill_dir: Path) -> tuple[bool, str, str | None]:
    """校验技能目录中的 SKILL.md frontmatter。

    参数：
        skill_dir: 包含 SKILL.md 的技能目录路径。

    返回：
        三元组 `(is_valid, message, skill_name)`。
    """
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return False, "SKILL.md not found", None

    content = skill_md.read_text()
    if not content.startswith("---"):
        return False, "No YAML frontmatter found", None

    # 提取 frontmatter
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return False, "Invalid frontmatter format", None

    frontmatter_text = match.group(1)

    # 解析 YAML frontmatter
    try:
        frontmatter = yaml.safe_load(frontmatter_text)
        if not isinstance(frontmatter, dict):
            return False, "Frontmatter must be a YAML dictionary", None
    except yaml.YAMLError as e:
        return False, f"Invalid YAML in frontmatter: {e}", None

    # 检查是否存在不允许的字段
    unexpected_keys = set(frontmatter.keys()) - ALLOWED_FRONTMATTER_PROPERTIES
    if unexpected_keys:
        return False, f"Unexpected key(s) in SKILL.md frontmatter: {', '.join(sorted(unexpected_keys))}", None

    # 检查必填字段
    if "name" not in frontmatter:
        return False, "Missing 'name' in frontmatter", None
    if "description" not in frontmatter:
        return False, "Missing 'description' in frontmatter", None

    # 校验 name
    name = frontmatter.get("name", "")
    if not isinstance(name, str):
        return False, f"Name must be a string, got {type(name).__name__}", None
    name = name.strip()
    if not name:
        return False, "Name cannot be empty", None

    # 检查命名规范（短横线命名：小写字母 + 连字符）
    if not re.match(r"^[a-z0-9-]+$", name):
        return False, f"Name '{name}' should be hyphen-case (lowercase letters, digits, and hyphens only)", None
    if name.startswith("-") or name.endswith("-") or "--" in name:
        return False, f"Name '{name}' cannot start/end with hyphen or contain consecutive hyphens", None
    if len(name) > 64:
        return False, f"Name is too long ({len(name)} characters). Maximum is 64 characters.", None

    # 校验 description
    description = frontmatter.get("description", "")
    if not isinstance(description, str):
        return False, f"Description must be a string, got {type(description).__name__}", None
    description = description.strip()
    if description:
        if "<" in description or ">" in description:
            return False, "Description cannot contain angle brackets (< or >)", None
        if len(description) > 1024:
            return False, f"Description is too long ({len(description)} characters). Maximum is 1024 characters.", None

    return True, "Skill is valid!", name


def _skill_to_response(skill: Skill) -> SkillResponse:
    """将 Skill 对象转换为 SkillResponse。"""
    return SkillResponse(
        name=skill.name,
        description=skill.description,
        license=skill.license,
        category=skill.category,
        enabled=skill.enabled,
    )


@router.get(
    "/skills",
    response_model=SkillsListResponse,
    summary="List All Skills",
    description="Retrieve a list of all available skills from both public and custom directories.",
)
async def list_skills() -> SkillsListResponse:
    """获取技能列表（包含已禁用技能）。

    返回：
        带元数据的技能列表。
    """
    try:
        # 加载全部技能（包含禁用项）
        skills = load_skills(enabled_only=False)
        return SkillsListResponse(skills=[_skill_to_response(skill) for skill in skills])
    except Exception as e:
        logger.error(f"Failed to load skills: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to load skills: {str(e)}")


@router.get(
    "/skills/{skill_name}",
    response_model=SkillResponse,
    summary="Get Skill Details",
    description="Retrieve detailed information about a specific skill by its name.",
)
async def get_skill(skill_name: str) -> SkillResponse:
    """获取指定技能详情。

    参数：
        skill_name: 要查询的技能名称。

    返回：
        找到时返回技能信息。

    异常：
        HTTPException: 技能不存在时返回 404。
    """
    try:
        skills = load_skills(enabled_only=False)
        skill = next((s for s in skills if s.name == skill_name), None)

        if skill is None:
            raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")

        return _skill_to_response(skill)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get skill {skill_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get skill: {str(e)}")


@router.put(
    "/skills/{skill_name}",
    response_model=SkillResponse,
    summary="Update Skill",
    description="Update a skill's enabled status by modifying the extensions_config.json file.",
)
async def update_skill(skill_name: str, request: SkillUpdateRequest) -> SkillResponse:
    """更新技能启用状态。

    该操作会修改 `extensions_config.json` 中的状态配置，
    不会修改技能目录里的 `SKILL.md` 本体。

    参数：
        skill_name: 要更新的技能名称。
        request: 包含新启用状态的请求体。

    返回：
        更新后的技能信息。

    异常：
        HTTPException: 技能不存在时返回 404；更新失败时返回 500。
    """
    try:
        # 先确认技能存在
        skills = load_skills(enabled_only=False)
        skill = next((s for s in skills if s.name == skill_name), None)

        if skill is None:
            raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")

        # 获取或创建配置文件路径
        config_path = ExtensionsConfig.resolve_config_path()
        if config_path is None:
            # 在父目录（项目根）创建新的配置文件
            config_path = Path.cwd().parent / "extensions_config.json"
            logger.info(f"No existing extensions config found. Creating new config at: {config_path}")

        # 读取当前配置
        extensions_config = get_extensions_config()

        # 更新技能启用状态
        extensions_config.skills[skill_name] = SkillStateConfig(enabled=request.enabled)

        # 转为 JSON 结构（保留 MCP 服务配置）
        config_data = {
            "mcpServers": {name: server.model_dump() for name, server in extensions_config.mcp_servers.items()},
            "skills": {name: {"enabled": skill_config.enabled} for name, skill_config in extensions_config.skills.items()},
        }

        # 将配置写回文件
        with open(config_path, "w") as f:
            json.dump(config_data, f, indent=2)

        logger.info(f"Skills configuration updated and saved to: {config_path}")

        # 重载 extensions 配置以刷新全局缓存
        reload_extensions_config()

        # 重新加载技能，获取更新后的状态用于 API 返回
        skills = load_skills(enabled_only=False)
        updated_skill = next((s for s in skills if s.name == skill_name), None)

        if updated_skill is None:
            raise HTTPException(status_code=500, detail=f"Failed to reload skill '{skill_name}' after update")

        logger.info(f"Skill '{skill_name}' enabled status updated to {request.enabled}")
        return _skill_to_response(updated_skill)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update skill {skill_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update skill: {str(e)}")


@router.post(
    "/skills/install",
    response_model=SkillInstallResponse,
    summary="Install Skill",
    description="Install a skill from a .skill file (ZIP archive) located in the thread's user-data directory.",
)
async def install_skill(request: SkillInstallRequest) -> SkillInstallResponse:
    """从 `.skill` 文件安装技能。

    `.skill` 本质是 ZIP 压缩包，通常包含技能目录、`SKILL.md`，
    以及可选资源（scripts、references、assets 等）。

    参数：
        request: 安装请求，包含 thread_id 与 `.skill` 的虚拟路径。

    返回：
        安装结果（含技能名称与状态消息）。

    异常：
        HTTPException:
            - 400：路径无效或不是合法 `.skill` 文件
            - 403：访问被拒绝（检测到路径穿越）
            - 404：文件不存在
            - 409：技能已存在
            - 500：安装失败
    """
    try:
        # 将虚拟路径解析为真实文件路径
        skill_file_path = resolve_thread_virtual_path(request.thread_id, request.path)

        # 检查文件是否存在
        if not skill_file_path.exists():
            raise HTTPException(status_code=404, detail=f"Skill file not found: {request.path}")

        # 检查路径是否为文件
        if not skill_file_path.is_file():
            raise HTTPException(status_code=400, detail=f"Path is not a file: {request.path}")

        # 检查扩展名
        if not skill_file_path.suffix == ".skill":
            raise HTTPException(status_code=400, detail="File must have .skill extension")

        # 校验是否为有效 ZIP 文件
        if not zipfile.is_zipfile(skill_file_path):
            raise HTTPException(status_code=400, detail="File is not a valid ZIP archive")

        # 获取自定义技能目录
        skills_root = get_skills_root_path()
        custom_skills_dir = skills_root / "custom"

        # 若目录不存在则创建
        custom_skills_dir.mkdir(parents=True, exist_ok=True)

        # 先解压到临时目录进行校验
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # 解压 .skill 文件
            with zipfile.ZipFile(skill_file_path, "r") as zip_ref:
                zip_ref.extractall(temp_path)

            # 查找技能目录（通常应只有一个顶层目录）
            extracted_items = list(temp_path.iterdir())
            if len(extracted_items) == 0:
                raise HTTPException(status_code=400, detail="Skill archive is empty")

            # 兼容两种结构：单目录包裹 / 文件直接位于压缩包根目录
            if len(extracted_items) == 1 and extracted_items[0].is_dir():
                skill_dir = extracted_items[0]
            else:
                # 文件直接位于压缩包根目录
                skill_dir = temp_path

            # 校验技能内容
            is_valid, message, skill_name = _validate_skill_frontmatter(skill_dir)
            if not is_valid:
                raise HTTPException(status_code=400, detail=f"Invalid skill: {message}")

            if not skill_name:
                raise HTTPException(status_code=400, detail="Could not determine skill name")

            # 检查目标技能是否已存在
            target_dir = custom_skills_dir / skill_name
            if target_dir.exists():
                raise HTTPException(status_code=409, detail=f"Skill '{skill_name}' already exists. Please remove it first or use a different name.")

            # 将技能目录复制到自定义技能目录
            shutil.copytree(skill_dir, target_dir)

        logger.info(f"Skill '{skill_name}' installed successfully to {target_dir}")
        return SkillInstallResponse(success=True, skill_name=skill_name, message=f"Skill '{skill_name}' installed successfully")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to install skill: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to install skill: {str(e)}")
