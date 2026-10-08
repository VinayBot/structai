import json
from functools import lru_cache
from pathlib import Path

from jinja2 import StrictUndefined, Template
from jinja2.sandbox import SandboxedEnvironment

_TEMPLATE_DIR = Path(__file__).resolve().parent


class PromptVersionNotFoundError(Exception):
    pass


class PromptRegistry:
    """Loads versioned .jinja2 templates from app/prompts/.

    SandboxedEnvironment + StrictUndefined: schema/example content is passed in only
    as template *variables* (never compiled as template *source*, e.g. via
    `env.from_string(user_input)`), so there's nothing for the sandbox to actually
    restrict in normal use - it's defense in depth should that invariant ever slip,
    and StrictUndefined turns a missing variable into a loud error instead of
    silently rendering empty.
    """

    def __init__(self, template_dir: Path = _TEMPLATE_DIR):
        self._env = SandboxedEnvironment(
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=False,
        )
        self._template_dir = template_dir
        self._cache: dict[str, Template] = {}

    def _load(self, version: str) -> Template:
        if version in self._cache:
            return self._cache[version]

        path = self._template_dir / f"structured_system_{version}.jinja2"
        try:
            source = path.read_text()
        except FileNotFoundError as exc:
            raise PromptVersionNotFoundError(
                f"no structured-system prompt template for version '{version}'"
            ) from exc

        template = self._env.from_string(source)
        self._cache[version] = template
        return template

    def render_structured_system(
        self,
        *,
        version: str,
        schema_json: dict,
        canary: str,
        examples: list[dict] | None = None,
    ) -> str:
        template = self._load(version)
        return template.render(
            schema_json=json.dumps(schema_json),
            canary=canary,
            examples=[json.dumps(e) for e in examples] if examples else None,
        )


@lru_cache
def get_prompt_registry() -> PromptRegistry:
    return PromptRegistry()
