"""
LLMService -- wraps Groq for AI-powered recipe recommendations.

Usage:
    from app.core.application.llm_service import get_llm_service
    svc = get_llm_service()
    recs = svc.recommend_recipes(profile, recipes, executable_ids)
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from app.config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are an expert enterprise software modernization architect \\
embedded in the SystemaOps Modernization Platform.

Your task: Analyze the provided project profile, dependencies, technology stack, \\
security findings, and available recipe/executor capabilities. \\
Generate ONLY relevant modernization recommendations.

## Rules
1. Recommend recipes ONLY based on actual project evidence (detected languages, \\
   frameworks, dependencies, security findings).
2. Match recommendations to the project detected languages. Do NOT recommend \\
   Python recipes for a pure C# project or vice versa.
3. Do NOT recommend a recipe whose id is not in executable_recipe_ids.
4. Include generic recipes (security, CI/CD, dependency, code-quality) when \\
   their ids are in executable_recipe_ids.
5. Avoid duplicate or conflicting recommendations.
6. Rank recommendations by priority: HIGH -> MEDIUM -> LOW.
7. Provide a concise "reason" (1-2 sentences) explaining why each recipe applies \\
   to THIS specific project.
8. Never fabricate recipe_ids -- use ONLY ids from the available_recipes list.
9. Return ONLY a valid JSON array. No markdown, no code fences, no explanation.

## Output Schema (JSON array)
[
  {
    "recipe_id": "string -- exact id from available_recipes",
    "name": "string -- exact name from available_recipes",
    "category": "upgrade | style | security | performance",
    "priority": "HIGH | MEDIUM | LOW",
    "reason": "string -- 1-2 sentences why this applies to this project",
    "risk": "LOW | MEDIUM | HIGH",
    "capability_status": "AVAILABLE | PARTIAL",
    "executable": true
  }
]
"""


class LLMService:
    """Unified LLM service. Supports Groq exclusively."""

    def __init__(self) -> None:
        self.provider = "groq"
        self._openai_client = None
        self._available = False

        if settings.groq_api_key:
            self._init_groq()
        else:
            logger.info(
                "LLMService: Groq not configured (set GROQ_API_KEY in backend/.env)"
            )

    def _init_groq(self) -> None:
        try:
            from openai import OpenAI  # type: ignore
            self._openai_client = OpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=settings.groq_api_key
            )
            self._groq_model = settings.groq_model
            self._available = True
            logger.info("LLMService: Groq initialised (%s)", settings.groq_model)
        except ImportError:
            logger.warning("LLMService: openai package not installed. pip install openai")
        except Exception as exc:
            logger.error("LLMService: Groq init failed -- %s", exc)

    @property
    def is_available(self) -> bool:
        return self._available

    def recommend_recipes(
        self,
        project_profile: Dict[str, Any],
        available_recipes: List[Dict[str, Any]],
        executable_recipe_ids: List[str],
    ) -> List[Dict[str, Any]]:
        """Ask the LLM to generate structured recipe recommendations."""
        if not self._available:
            return []

        user_content = self._build_user_content(project_profile, available_recipes, executable_recipe_ids)
        raw = self._call_llm(user_content)
        return self._parse_response(raw, executable_recipe_ids, project_profile, available_recipes)

    def generate_completion(self, system_prompt: str, user_content: str) -> str:
        """Generic text completion for summaries, reports, etc."""
        if not self._available:
            raise RuntimeError("LLM not configured. Set GROQ_API_KEY.")
        return self._call_llm(user_content, system_prompt=system_prompt)

    def _build_user_content(
        self,
        profile: Dict[str, Any],
        recipes: List[Dict[str, Any]],
        executable_ids: List[str],
    ) -> str:
        slim_recipes = [
            {
                "id": r.get("id"),
                "name": r.get("name"),
                "language": r.get("language"),
                "category": r.get("category"),
                "complexity": r.get("complexity"),
                "description": (r.get("description") or "")[:120],
            }
            for r in recipes
        ]
        # Include documentation signals in project profile if provided
        doc_info = profile.get("documentation")
        if doc_info and isinstance(doc_info, dict):
            profile["readme_insights"] = {
                "servers": doc_info.get("all_servers", []),
                "databases": doc_info.get("all_databases", []),
                "build_commands": doc_info.get("all_build_commands", [])[:5],
                "run_commands": doc_info.get("all_run_commands", [])[:5],
                "test_commands": doc_info.get("all_test_commands", [])[:5],
                "env_vars": doc_info.get("all_env_vars", [])[:10],
            }

        return json.dumps(
            {
                "project_profile": profile,
                "available_recipes": slim_recipes,
                "executable_recipe_ids": executable_ids,
            },
            indent=2,
            default=str,
        )

    def _call_llm(self, user_content: str, system_prompt: str = _SYSTEM_PROMPT) -> str:
        try:
            if self._openai_client is not None:
                response = self._openai_client.chat.completions.create(
                    model=settings.groq_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                    temperature=0.2,
                    max_tokens=4096,
                )
                return response.choices[0].message.content or ""
        except Exception as exc:
            logger.error("LLMService._call_llm failed: %s", exc)
        return ""

    def _parse_response(
        self,
        raw: str,
        executable_ids: List[str],
        project_profile: Dict[str, Any],
        available_recipes: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not raw.strip():
            return []
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(l for l in cleaned.splitlines() if not l.startswith("```")).strip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            s, e = cleaned.find("["), cleaned.rfind("]")
            if s != -1 and e != -1:
                try:
                    data = json.loads(cleaned[s: e + 1])
                except json.JSONDecodeError:
                    logger.warning("LLMService: could not parse LLM JSON response")
                    return []
            else:
                logger.warning("LLMService: LLM response had no JSON array")
                return []
        if not isinstance(data, list):
            return []

        def _norm_l(l: str) -> str:
            cleaned = str(l).strip().lower()
            if cleaned in ("c#", "csharp", "vb.net", "f#", "dotnet", ".net"):
                return "csharp"
            if cleaned in ("js", "javascript", "node", "nodejs"):
                return "javascript"
            if cleaned in ("ts", "typescript"):
                return "typescript"
            if cleaned in ("py", "python"):
                return "python"
            return cleaned

        # Get recipe-to-language mapping from available_recipes
        recipe_langs = {r["id"]: _norm_l(r.get("language", "all")) for r in available_recipes}
        
        raw_pl = project_profile.get("languages", [])
        project_langs = set()
        for item in raw_pl:
            if isinstance(item, dict):
                project_langs.add(_norm_l(item.get("name", "")))
            elif isinstance(item, str):
                project_langs.add(_norm_l(item))

        executable_set = set(executable_ids)
        validated: List[Dict[str, Any]] = []
        seen: set = set()
        for item in data:
            if not isinstance(item, dict):
                continue
            rid = item.get("recipe_id", "")
            if not rid or rid in seen or rid not in executable_set:
                continue

            # Language validation
            recipe_lang = recipe_langs.get(rid, "all")
            if recipe_lang not in ("all", "generic", "yaml", "json", "docker", "ci", "cd"):
                compatible = False
                for pl in project_langs:
                    if pl == recipe_lang or pl in recipe_lang or recipe_lang in pl:
                        compatible = True
                        break
                if not compatible:
                    logger.warning(
                        "Filtering out language-incompatible recipe: %s for project languages %s",
                        rid,
                        list(project_langs)
                    )
                    continue

            item.setdefault("executable", True)
            item.setdefault("capability_status", "AVAILABLE")
            item.setdefault("risk", "LOW")
            item.setdefault("priority", "MEDIUM")
            seen.add(rid)
            validated.append(item)
        return validated


_llm_service: "LLMService | None" = None


def get_llm_service() -> "LLMService":
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
