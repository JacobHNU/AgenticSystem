import logging
from typing import Dict, List, Optional
from datetime import datetime, time

from .models import (
    SkillDefinition, SkillSummary, IntentMatch, ActivationResult,
    SkillMatch, Precondition, ContextDependency
)
from .registry import SkillRegistry

logger = logging.getLogger(__name__)


class SkillMatcher:
    """Two-level skill matcher: Intent (keyword + embedding) → Activation Rules"""

    def __init__(self, registry: SkillRegistry, embedding_client=None, feature_flags=None):
        self.registry = registry
        self.embedding_client = embedding_client
        self.feature_flags = feature_flags or _DefaultFeatureFlags()

    async def match(
        self,
        request: str,
        context: Dict = None,
        agent_skill_set: List[str] = None,
        top_k: int = 3
    ) -> List[SkillMatch]:
        context = context or {}

        # Level 1: Intent matching
        candidates = await self._match_intent(request, agent_skill_set, top_k)
        if not candidates:
            return []

        # Level 2: Activation rules evaluation
        activated = []
        for candidate in candidates:
            result = await self._evaluate_activation(candidate, context)
            if result.activated:
                activated.append(SkillMatch(
                    skill_name=candidate.skill_name,
                    confidence=result.confidence,
                    matched_rules=result.matched_rules
                ))

        activated.sort(key=lambda x: x.confidence, reverse=True)
        return activated

    async def _match_intent(
        self, request: str, agent_skill_set: List[str], top_k: int
    ) -> List[IntentMatch]:
        if agent_skill_set is not None and len(agent_skill_set) > 0:
            available_skills = self.registry.list_by_names(agent_skill_set)
        else:
            available_skills = self.registry.list_all()

        results = []

        # Keyword matching
        keyword_hits = self._keyword_match(request, available_skills)
        results.extend(keyword_hits)

        # Embedding matching (if available)
        if self.embedding_client:
            embedding_hits = await self._embedding_match(request, available_skills, top_k)
            results = self._merge_results(results, embedding_hits)

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

    def _keyword_match(self, request: str, skills: List[SkillSummary]) -> List[IntentMatch]:
        results = []
        request_lower = request.lower()

        for skill in skills:
            hit_count = 0
            matched_keywords = []
            for keyword in skill.intent.keywords:
                if keyword in request_lower:
                    hit_count += 1
                    matched_keywords.append(keyword)

            if hit_count > 0:
                score = hit_count / max(len(skill.intent.keywords), 1)
                results.append(IntentMatch(
                    skill_name=skill.name,
                    score=score,
                    method="keyword",
                    matched_keywords=matched_keywords
                ))
        return results

    async def _embedding_match(
        self, request: str, skills: List[SkillSummary], top_k: int
    ) -> List[IntentMatch]:
        try:
            request_embedding = await self.embedding_client.encode(request)
        except Exception as e:
            logger.warning(f"Embedding encode failed: {e}")
            return []

        import numpy as np
        scores = []
        for skill in skills:
            if skill.intent.embedding_vector:
                sim = np.dot(request_embedding, skill.intent.embedding_vector) / (
                    np.linalg.norm(request_embedding) * np.linalg.norm(skill.intent.embedding_vector)
                )
                scores.append((skill.name, float(sim)))

        scores.sort(key=lambda x: x[1], reverse=True)
        return [
            IntentMatch(skill_name=name, score=score, method="embedding")
            for name, score in scores[:top_k]
        ]

    def _merge_results(
        self, keyword_results: List[IntentMatch], embedding_results: List[IntentMatch]
    ) -> List[IntentMatch]:
        merged = {}

        for r in keyword_results:
            merged[r.skill_name] = IntentMatch(
                skill_name=r.skill_name,
                score=r.score * 0.4,
                method="keyword",
                matched_keywords=r.matched_keywords
            )

        for r in embedding_results:
            if r.skill_name in merged:
                merged[r.skill_name].score += r.score * 0.6
                merged[r.skill_name].method = "hybrid"
            else:
                merged[r.skill_name] = IntentMatch(
                    skill_name=r.skill_name,
                    score=r.score * 0.6,
                    method="embedding"
                )

        return list(merged.values())

    async def _evaluate_activation(
        self, candidate: IntentMatch, context: Dict
    ) -> ActivationResult:
        skill_def = self.registry.get(candidate.skill_name)
        if not skill_def or not skill_def.activation_rules:
            return ActivationResult(activated=True, confidence=candidate.score)

        rules = skill_def.activation_rules

        # Preconditions
        precondition_results = []
        for precondition in rules.preconditions:
            result = await self._check_precondition(precondition, context)
            precondition_results.append(result)

        if rules.logic == "AND":
            preconditions_ok = all(precondition_results)
        else:
            preconditions_ok = any(precondition_results) if precondition_results else True

        # Context dependencies
        dep_results = []
        for dep in rules.context_dependencies:
            result = await self._check_context_dependency(dep, context)
            dep_results.append(result)

        if rules.logic == "AND":
            deps_ok = all(dep_results)
        else:
            deps_ok = any(dep_results) if dep_results else True

        activated = preconditions_ok and deps_ok
        total = len(precondition_results) + len(dep_results)
        passed = sum(precondition_results) + sum(dep_results)
        rule_pass_rate = passed / total if total > 0 else 1.0

        return ActivationResult(
            activated=activated,
            confidence=candidate.score * rule_pass_rate,
            matched_rules={
                "all_passed": activated,
                "preconditions": dict(zip(
                    [p.type for p in rules.preconditions],
                    precondition_results
                )),
                "dependencies": dict(zip(
                    [d.skill for d in rules.context_dependencies],
                    dep_results
                ))
            }
        )

    async def _check_precondition(self, precondition: Precondition, context: Dict) -> bool:
        if precondition.type == "time_window":
            now = datetime.now().time()
            start = time.fromisoformat(precondition.config.get("start", "00:00"))
            end = time.fromisoformat(precondition.config.get("end", "23:59"))
            return start <= now <= end
        elif precondition.type == "role_check":
            user_level = context.get("user_level", 0)
            return user_level >= precondition.config.get("min_level", 0)
        elif precondition.type == "feature_flag":
            flag = precondition.config.get("flag", "")
            return self.feature_flags.is_enabled(flag)
        return True

    async def _check_context_dependency(self, dep: ContextDependency, context: Dict) -> bool:
        skill_result = context.get(f"skill_result_{dep.skill}")
        if skill_result is None:
            if dep.required:
                return False
            else:
                if dep.fallback_value is not None:
                    context[dep.result_key] = dep.fallback_value
                return True
        context[dep.result_key] = skill_result.get(dep.result_key)
        return True


class _DefaultFeatureFlags:
    def is_enabled(self, flag: str) -> bool:
        return True
