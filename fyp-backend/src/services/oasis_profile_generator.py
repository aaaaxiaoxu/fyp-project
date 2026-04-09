from __future__ import annotations

import random
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Callable

from ..utils.llm_client import LLMClient
from .zep_entity_reader import EntityNode

PROFILE_SYSTEM_PROMPT = """你是一个社交模拟人设设计器。

请根据给定实体信息输出一个 JSON 对象，字段必须包含：
- bio: 1-2 句简介
- persona: 80-220 字的详细人物设定
- profession: 职业或社会身份
- interested_topics: 3-6 个主题数组
- age: 整数，可为空
- gender: 字符串，可为空
- country: 字符串，可为空

要求：
1. 不要虚构与实体摘要明显冲突的设定
2. 设定要适合社交媒体模拟
3. interested_topics 使用短语
4. 必须只输出有效 JSON
"""

_GENERIC_LABELS = {"Entity", "Node"}
_INDIVIDUAL_HINTS = {
    "person",
    "student",
    "professor",
    "journalist",
    "official",
    "expert",
    "activist",
    "citizen",
    "teacher",
    "researcher",
}
_PROFESSION_MAP = {
    "Student": "student",
    "Professor": "professor",
    "Journalist": "journalist",
    "MediaOutlet": "editorial staff",
    "GovernmentAgency": "public affairs officer",
    "Government": "public affairs officer",
    "University": "campus representative",
    "Company": "company spokesperson",
    "Organization": "organization representative",
    "NGO": "advocacy organizer",
    "Community": "community organizer",
}


@dataclass(frozen=True, slots=True)
class OasisAgentProfile:
    user_id: int
    username: str
    name: str
    bio: str
    persona: str
    profession: str | None = None
    interested_topics: list[str] = field(default_factory=list)
    source_entity_uuid: str | None = None
    source_entity_type: str | None = None
    age: int | None = None
    gender: str | None = None
    country: str | None = None
    karma: int = 1000
    friend_count: int = 100
    follower_count: int = 150
    statuses_count: int = 500

    def to_reddit_format(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "user_id": self.user_id,
            "username": self.username,
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "karma": self.karma,
        }
        if self.profession:
            payload["profession"] = self.profession
        if self.interested_topics:
            payload["interested_topics"] = list(self.interested_topics)
        if self.age is not None:
            payload["age"] = self.age
        if self.gender:
            payload["gender"] = self.gender
        if self.country:
            payload["country"] = self.country
        if self.source_entity_uuid:
            payload["source_entity_uuid"] = self.source_entity_uuid
        if self.source_entity_type:
            payload["source_entity_type"] = self.source_entity_type
        return payload

    def to_twitter_format(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "user_id": self.user_id,
            "username": self.username,
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "friend_count": self.friend_count,
            "follower_count": self.follower_count,
            "statuses_count": self.statuses_count,
        }
        if self.profession:
            payload["profession"] = self.profession
        if self.interested_topics:
            payload["interested_topics"] = list(self.interested_topics)
        if self.age is not None:
            payload["age"] = self.age
        if self.gender:
            payload["gender"] = self.gender
        if self.country:
            payload["country"] = self.country
        if self.source_entity_uuid:
            payload["source_entity_uuid"] = self.source_entity_uuid
        if self.source_entity_type:
            payload["source_entity_type"] = self.source_entity_type
        return payload

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "profession": self.profession,
            "interested_topics": list(self.interested_topics),
            "source_entity_uuid": self.source_entity_uuid,
            "source_entity_type": self.source_entity_type,
            "age": self.age,
            "gender": self.gender,
            "country": self.country,
            "karma": self.karma,
            "friend_count": self.friend_count,
            "follower_count": self.follower_count,
            "statuses_count": self.statuses_count,
        }


class OasisProfileGenerator:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm_client = llm_client

    @property
    def _client(self) -> LLMClient:
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client

    def generate_profiles_from_entities(
        self,
        entities: list[EntityNode],
        *,
        use_llm: bool = True,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> list[OasisAgentProfile]:
        profiles: list[OasisAgentProfile] = []
        used_usernames: set[str] = set()
        total = len(entities)

        for index, entity in enumerate(entities, start=1):
            if progress_callback is not None:
                progress_callback(index, total, f"building profile for {entity.name}")
            profile = self._build_profile(
                entity,
                user_id=index,
                use_llm=use_llm,
                used_usernames=used_usernames,
            )
            profiles.append(profile)

        return profiles

    def _build_profile(
        self,
        entity: EntityNode,
        *,
        user_id: int,
        use_llm: bool,
        used_usernames: set[str],
    ) -> OasisAgentProfile:
        rng = random.Random(f"{entity.uuid}:{entity.name}:{user_id}")
        entity_type = entity.get_entity_type() or "Entity"
        username = self._build_unique_username(entity.name, user_id, used_usernames)
        profile_data = self._build_fallback_profile(entity, rng)

        if use_llm:
            try:
                llm_payload = self._client.chat_json(
                    messages=[
                        {"role": "system", "content": PROFILE_SYSTEM_PROMPT},
                        {"role": "user", "content": self._build_profile_prompt(entity)},
                    ],
                    temperature=0.4,
                    max_tokens=1200,
                )
                profile_data.update(self._normalize_llm_payload(llm_payload))
            except Exception:
                pass

        profession = str(profile_data.get("profession") or self._default_profession(entity_type)).strip() or None
        interested_topics = self._normalize_topics(profile_data.get("interested_topics"))
        age = self._coerce_age(profile_data.get("age"))
        gender = self._coerce_text(profile_data.get("gender"))
        country = self._coerce_text(profile_data.get("country"))

        return OasisAgentProfile(
            user_id=user_id,
            username=username,
            name=entity.name,
            bio=str(profile_data.get("bio") or f"{entity.name} participates in this social simulation.").strip(),
            persona=str(profile_data.get("persona") or self._fallback_persona(entity)).strip(),
            profession=profession,
            interested_topics=interested_topics,
            source_entity_uuid=entity.uuid,
            source_entity_type=entity_type,
            age=age,
            gender=gender,
            country=country,
            karma=rng.randint(300, 6000),
            friend_count=rng.randint(50, 500),
            follower_count=rng.randint(80, 2000),
            statuses_count=rng.randint(120, 2400),
        )

    def _build_profile_prompt(self, entity: EntityNode) -> str:
        entity_type = entity.get_entity_type() or "Entity"
        related_facts = [str(item.get("fact") or "") for item in entity.related_edges if item.get("fact")]
        prompt_lines = [
            f"实体名称: {entity.name}",
            f"实体类型: {entity_type}",
            f"实体摘要: {entity.summary or '无'}",
            f"实体属性: {entity.attributes or {}}",
            f"相关事实: {related_facts[:6]}",
        ]
        return "\n".join(prompt_lines)

    def _build_fallback_profile(self, entity: EntityNode, rng: random.Random) -> dict[str, Any]:
        entity_type = entity.get_entity_type() or "Entity"
        topics = self._extract_topics(entity)
        role = self._default_profession(entity_type)
        bio_summary = entity.summary.strip() if entity.summary else f"{entity.name} is active in the simulation graph."

        return {
            "bio": self._limit_sentence(bio_summary, 120),
            "persona": self._fallback_persona(entity),
            "profession": role,
            "interested_topics": topics,
            "age": rng.randint(20, 55) if self._looks_like_individual(entity_type) else None,
            "gender": None,
            "country": None,
        }

    def _fallback_persona(self, entity: EntityNode) -> str:
        entity_type = entity.get_entity_type() or "Entity"
        topics = self._extract_topics(entity)
        related = [str(item.get("name") or "") for item in entity.related_nodes if item.get("name")]
        clauses = [
            f"{entity.name} acts as a {self._default_profession(entity_type)} in the simulation.",
            self._limit_sentence(entity.summary or f"{entity.name} is represented as a {entity_type}.", 180),
        ]
        if topics:
            clauses.append(f"Primary topics include {', '.join(topics[:4])}.")
        if related:
            clauses.append(f"They are connected to {', '.join(related[:4])}.")
        return " ".join(clause for clause in clauses if clause).strip()

    def _normalize_llm_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "bio": self._coerce_text(payload.get("bio")),
            "persona": self._coerce_text(payload.get("persona")),
            "profession": self._coerce_text(payload.get("profession")),
            "interested_topics": self._normalize_topics(payload.get("interested_topics")),
            "age": self._coerce_age(payload.get("age")),
            "gender": self._coerce_text(payload.get("gender")),
            "country": self._coerce_text(payload.get("country")),
        }

    def _extract_topics(self, entity: EntityNode) -> list[str]:
        topics: list[str] = []
        seen: set[str] = set()

        def add_topic(value: str) -> None:
            candidate = value.strip()
            if not candidate:
                return
            normalized = candidate.casefold()
            if normalized in seen:
                return
            seen.add(normalized)
            topics.append(candidate)

        for label in entity.labels:
            if label not in _GENERIC_LABELS:
                add_topic(label)

        for key, value in entity.attributes.items():
            add_topic(str(key).replace("_", " "))
            if isinstance(value, str):
                add_topic(value[:40])
            elif isinstance(value, list):
                for item in value[:3]:
                    add_topic(str(item)[:40])

        for node in entity.related_nodes[:5]:
            add_topic(str(node.get("name") or "")[:40])

        if not topics:
            add_topic(entity.get_entity_type() or "public affairs")
        return topics[:6]

    def _build_unique_username(self, name: str, user_id: int, used_usernames: set[str]) -> str:
        base = self._slugify(name) or "agent"
        candidate = f"{base}_{user_id}"
        counter = 1
        while candidate in used_usernames:
            counter += 1
            candidate = f"{base}_{user_id}_{counter}"
        used_usernames.add(candidate)
        return candidate

    def _slugify(self, value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value)
        ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
        candidate = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_value).strip("_").lower()
        return candidate[:24]

    def _default_profession(self, entity_type: str) -> str:
        return _PROFESSION_MAP.get(entity_type, f"{entity_type.lower()} representative")

    def _looks_like_individual(self, entity_type: str) -> bool:
        return entity_type.casefold() in _INDIVIDUAL_HINTS

    def _normalize_topics(self, value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()][:6]
        if isinstance(value, str) and value.strip():
            parts = re.split(r"[,;/、|]\s*", value.strip())
            return [part for part in parts if part][:6]
        return []

    def _coerce_text(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _coerce_age(self, value: Any) -> int | None:
        try:
            age = int(value)
        except (TypeError, ValueError):
            return None
        return age if 10 <= age <= 100 else None

    def _limit_sentence(self, value: str, limit: int) -> str:
        text = re.sub(r"\s+", " ", value).strip()
        if len(text) <= limit:
            return text
        return f"{text[: limit - 3].rstrip()}..."
