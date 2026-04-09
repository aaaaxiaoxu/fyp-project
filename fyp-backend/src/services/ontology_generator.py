from __future__ import annotations

import re
from typing import Any

from ..utils.llm_client import LLMClient


def _to_pascal_case(name: str) -> str:
    parts = re.split(r"[^a-zA-Z0-9]+", name)
    words: list[str] = []
    for part in parts:
        words.extend(re.sub(r"([a-z])([A-Z])", r"\1_\2", part).split("_"))
    result = "".join(word.capitalize() for word in words if word)
    return result or "Unknown"


ONTOLOGY_SYSTEM_PROMPT = """你是一个专业的知识图谱本体设计专家。你的任务是分析给定的文本内容和模拟需求，设计适合社交媒体舆论模拟的实体和关系类型。

你必须只输出有效 JSON，不要输出解释文字。JSON 结构必须包含：
- entity_types: 实体类型数组
- edge_types: 关系类型数组
- analysis_summary: 简要分析

要求：
1. entity_types 必须正好 10 个
2. 最后 2 个实体类型必须是 Person 和 Organization
3. 实体类型名使用 English PascalCase
4. 关系类型名使用 English UPPER_SNAKE_CASE
5. 属性名使用 English snake_case
6. description 与 analysis_summary 可以使用中文
7. 实体必须是现实中可发声或互动的主体，不能是抽象概念
"""


class OntologyGenerator:
    MAX_TEXT_LENGTH_FOR_LLM = 50000

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm_client = llm_client

    def generate(
        self,
        document_texts: list[str],
        simulation_requirement: str,
        additional_context: str | None = None,
    ) -> dict[str, Any]:
        result = self._client.chat_json(
            messages=[
                {"role": "system", "content": ONTOLOGY_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": self._build_user_message(
                        document_texts=document_texts,
                        simulation_requirement=simulation_requirement,
                        additional_context=additional_context,
                    ),
                },
            ],
            temperature=0.3,
            max_tokens=4096,
        )
        return self._validate_and_process(result)

    @property
    def _client(self) -> LLMClient:
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client

    def _build_user_message(
        self,
        *,
        document_texts: list[str],
        simulation_requirement: str,
        additional_context: str | None,
    ) -> str:
        combined_text = "\n\n---\n\n".join(document_texts)
        original_length = len(combined_text)
        if len(combined_text) > self.MAX_TEXT_LENGTH_FOR_LLM:
            combined_text = combined_text[: self.MAX_TEXT_LENGTH_FOR_LLM]
            combined_text += (
                f"\n\n...(原文共{original_length}字，已截取前"
                f"{self.MAX_TEXT_LENGTH_FOR_LLM}字用于本体分析)..."
            )

        message = f"""## 模拟需求

{simulation_requirement}

## 文档内容

{combined_text}
"""
        if additional_context:
            message += f"""
## 额外说明

{additional_context}
"""
        message += """
请根据以上内容，设计适合社会舆论模拟的实体类型和关系类型。

必须遵守：
1. 正好输出 10 个实体类型
2. 最后 2 个必须是 Person 和 Organization
3. 实体名称用 English PascalCase
4. 关系名称用 English UPPER_SNAKE_CASE
5. 属性名不能使用 name、uuid、group_id、created_at、summary
"""
        return message

    def _validate_and_process(self, result: dict[str, Any]) -> dict[str, Any]:
        result.setdefault("entity_types", [])
        result.setdefault("edge_types", [])
        result.setdefault("analysis_summary", "")

        entity_name_map: dict[str, str] = {}
        for entity in result["entity_types"]:
            # some models return "type" instead of "name"
            if "name" not in entity and "type" in entity:
                entity["name"] = entity.pop("type")
            if "name" in entity:
                original_name = str(entity["name"])
                entity["name"] = _to_pascal_case(original_name)
                entity_name_map[original_name] = entity["name"]
            entity.setdefault("attributes", [])
            entity.setdefault("examples", [])
            description = str(entity.get("description", ""))
            if len(description) > 100:
                entity["description"] = f"{description[:97]}..."

        for edge in result["edge_types"]:
            # some models return "type" instead of "name"
            if "name" not in edge and "type" in edge:
                edge["name"] = edge.pop("type")
            if "name" in edge:
                edge["name"] = str(edge["name"]).upper()
            edge.setdefault("attributes", [])
            edge.setdefault("source_targets", [])
            for source_target in edge["source_targets"]:
                if source_target.get("source") in entity_name_map:
                    source_target["source"] = entity_name_map[source_target["source"]]
                if source_target.get("target") in entity_name_map:
                    source_target["target"] = entity_name_map[source_target["target"]]

        return result
