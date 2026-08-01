"""Direct storyboard prompt generation with optional web-research context."""

import asyncio
import json
import re
from typing import Literal

from military_video_gen.prompts.video_generation import estimate_video_prompt_duration
from military_video_gen.services.llm_service import LLMService
from military_video_gen.utils.content_generators import (
    generate_image_prompts,
    generate_video_prompts,
)

from .models import (
    EvidenceClaim,
    GroundedField,
    GroundedStoryboardScene,
    SubjectProfile,
    VisualFact,
)


class VisualPlanner:
    def __init__(
        self,
        llm: LLMService,
        *,
        model: str | None = None,
        scene_timeout_seconds: float = 90.0,
    ) -> None:
        if scene_timeout_seconds <= 0:
            raise ValueError("scene_timeout_seconds must be positive")
        self.llm = llm
        self.model = model
        self.scene_timeout_seconds = scene_timeout_seconds

    async def plan(
        self,
        narrations: list[str],
        subject_profiles: list[SubjectProfile],
        visual_facts: list[VisualFact],
        asset_type: Literal["image", "video"],
        research_claims: list[EvidenceClaim] | None = None,
    ) -> tuple[list[SubjectProfile], list[GroundedStoryboardScene]]:
        claims = research_claims or []
        research_contexts = await self._select_research_contexts(
            narrations,
            visual_facts,
            claims,
        )
        prompt_inputs = [
            self._prompt_input(index, narration, research_contexts[index - 1])
            for index, narration in enumerate(narrations, start=1)
        ]
        fallback_positions: set[int] = set()
        if asset_type == "video":
            prompts, fallback_positions = await self._generate_video_prompts_resilient(
                narrations,
                research_contexts,
            )
        else:
            prompts = await generate_image_prompts(
                llm_service=self.llm,
                narrations=prompt_inputs,
                min_words=30,
                max_words=70,
                max_retries=2,
                model=self.model,
            )
        if not self._valid_prompts(prompts, narrations):
            continuity_note = (
                "Preserve established subjects and environments across adjacent "
                "scenes. Distinguish this scene through its explanatory purpose, "
                "action phase, framing, or observation distance."
            )
            retry_inputs = [f"{item}\n{continuity_note}" for item in prompt_inputs]
            if asset_type == "video":
                prompts, fallback_positions = await self._generate_video_prompts_resilient(
                    narrations,
                    research_contexts,
                )
            else:
                prompts = await generate_image_prompts(
                    llm_service=self.llm,
                    narrations=retry_inputs,
                    min_words=30,
                    max_words=70,
                    max_retries=2,
                    model=self.model,
                )
        if not self._valid_prompts(prompts, narrations):
            raise ValueError("prompt generator returned missing or duplicate scenes")

        scenes = [
            self._scene(
                index,
                narration,
                prompt,
                asset_type,
                self._claim_ids_for_context(research_contexts[index - 1], claims),
            )
            for index, (narration, prompt) in enumerate(
                zip(narrations, prompts, strict=True),
                start=1,
            )
        ]
        for position in fallback_positions:
            scenes[position].claim_ids = []
            scenes[position].warnings.append("scene_prompt_fallback")
        return subject_profiles, scenes

    async def _select_research_contexts(
        self,
        narrations: list[str],
        visual_facts: list[VisualFact],
        claims: list[EvidenceClaim],
    ) -> list[list[str]]:
        contexts = self.select_research_contexts(narrations, visual_facts, claims)
        safe_claims = [
            claim for claim in claims if not claim.conflicts and claim.status.value != "conflicted"
        ]
        cross_language = (
            any(re.search(r"[\u3400-\u9fff]", narration) for narration in narrations)
            and safe_claims
            and not any(re.search(r"[\u3400-\u9fff]", claim.statement) for claim in safe_claims)
        )
        if not cross_language:
            return contexts

        # Lexical overlap cannot connect Chinese narration to English source
        # claims. Ask the configured model for an entailment-only mapping. A
        # malformed or failed response deliberately produces no claim links.
        claim_lines = "\n".join(f"- {claim.id}: {claim.statement}" for claim in safe_claims)
        scene_lines = "\n".join(
            f"- {index}: {narration}" for index, narration in enumerate(narrations, start=1)
        )
        prompt = f"""# Cross-language evidence mapping
Map each narration to only the claim IDs that fully entail its factual content.
Do not use background knowledge or partial keyword overlap. Return an empty list
when no claim fully supports a narration. Dates, quantities, places, companies,
and model variants must agree exactly.

Claims:
{claim_lines}

Narrations:
{scene_lines}

Return JSON only:
{{"mappings":[{{"scene_index":1,"claim_ids":["claim-1"]}}]}}
Include exactly one mapping for every scene index.
"""
        try:
            async with asyncio.timeout(self.scene_timeout_seconds):
                last_error: Exception | None = None
                for attempt in range(3):
                    try:
                        raw = await self.llm(
                            prompt=prompt,
                            temperature=0,
                            max_tokens=2000,
                            model=self.model,
                        )
                        payload = self._parse_json_object(raw)
                        return self._mapped_contexts(
                            payload,
                            narrations=narrations,
                            safe_claims=safe_claims,
                        )
                    except asyncio.CancelledError:
                        raise
                    except Exception as error:
                        last_error = error
                        if attempt < 2:
                            await asyncio.sleep(0.25 * (attempt + 1))
                raise ValueError("cross-language evidence mapping failed") from last_error
        except asyncio.CancelledError:
            raise
        except Exception:
            return [[] for _ in narrations]

    def _mapped_contexts(
        self,
        payload: dict,
        *,
        narrations: list[str],
        safe_claims: list[EvidenceClaim],
    ) -> list[list[str]]:
        mappings = payload.get("mappings")
        if not isinstance(mappings, list) or len(mappings) != len(narrations):
            raise ValueError("evidence mapping count mismatch")
        claim_by_id = {claim.id: claim for claim in safe_claims}
        mapped_contexts: list[list[str]] = [[] for _ in narrations]
        seen: set[int] = set()
        for mapping in mappings:
            if not isinstance(mapping, dict):
                raise ValueError("evidence mapping item is not an object")
            scene_index = mapping.get("scene_index")
            claim_ids = mapping.get("claim_ids")
            if (
                not isinstance(scene_index, int)
                or scene_index < 1
                or scene_index > len(narrations)
                or scene_index in seen
                or not isinstance(claim_ids, list)
                or any(not isinstance(item, str) for item in claim_ids)
            ):
                raise ValueError("invalid evidence mapping item")
            seen.add(scene_index)
            narration = narrations[scene_index - 1]
            mapped_contexts[scene_index - 1] = [
                claim_by_id[claim_id].statement
                for claim_id in dict.fromkeys(claim_ids)
                if claim_id in claim_by_id
                and self._numbers_compatible(
                    narration,
                    claim_by_id[claim_id].statement,
                )
            ]
        if len(seen) != len(narrations):
            raise ValueError("evidence mapping omitted a scene")
        return mapped_contexts

    @staticmethod
    def _numbers_compatible(narration: str, claim_statement: str) -> bool:
        narration_numbers = set(re.findall(r"\d+(?:[.,]\d+)?", narration))
        if not narration_numbers:
            return True
        claim_numbers = set(re.findall(r"\d+(?:[.,]\d+)?", claim_statement))
        return narration_numbers.issubset(claim_numbers)

    @staticmethod
    def _parse_json_object(value: str) -> dict:
        if not isinstance(value, str):
            raise TypeError("model response is not text")
        cleaned = value.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        payload = json.loads(cleaned)
        if not isinstance(payload, dict):
            raise TypeError("model response is not a JSON object")
        return payload

    async def plan_ordinary(
        self,
        narrations: list[str],
        asset_type: Literal["image", "video"],
        *,
        topic: str = "",
    ) -> tuple[list[SubjectProfile], list[GroundedStoryboardScene]]:
        """Generate an ordinary storyboard in small concurrent model calls.

        Reference planning can time out because one large request contains every
        scene and its notes. Retrying the exact same request is both slow and
        fragile, so the automatic downgrade asks for one narration per request.
        """
        if asset_type == "video":
            prompts, _ = await self._generate_video_prompts_resilient(
                narrations,
                [[] for _ in narrations],
                topic=topic,
            )
            return [], [
                self._scene(index, narration, prompt, asset_type, [])
                for index, (narration, prompt) in enumerate(
                    zip(narrations, prompts, strict=True),
                    start=1,
                )
            ]

        semaphore = asyncio.Semaphore(5)

        async def generate_one(index: int, narration: str) -> str:
            async with semaphore:
                generated = await generate_image_prompts(
                    llm_service=self.llm,
                    narrations=[self._prompt_input(index, narration, [])],
                    batch_size=1,
                    max_retries=2,
                    model=self.model,
                )
                return generated[0]

        generated = await asyncio.gather(
            *(
                generate_one(index, narration)
                for index, narration in enumerate(narrations, start=1)
            ),
            return_exceptions=True,
        )
        _, local_scenes = self.fallback_plan(
            narrations,
            asset_type,
            topic=topic,
        )
        prompts = [
            value if isinstance(value, str) and value.strip() else local_scenes[index].media_prompt
            for index, value in enumerate(generated)
        ]
        if not self._valid_prompts(prompts, narrations):
            raise ValueError("ordinary prompt generator returned invalid scenes")
        return [], [
            self._scene(index, narration, prompt, asset_type, [])
            for index, (narration, prompt) in enumerate(
                zip(narrations, prompts, strict=True),
                start=1,
            )
        ]

    async def _generate_video_prompts_resilient(
        self,
        narrations: list[str],
        research_contexts: list[list[str]],
        *,
        concurrency: int = 5,
        topic: str = "",
    ) -> tuple[list[str], set[int]]:
        """Generate each scene independently so one slow response cannot sink all."""
        semaphore = asyncio.Semaphore(concurrency)

        async def generate_one(index: int, narration: str) -> str:
            async with semaphore:
                context = list(research_contexts[index])
                continuity = [
                    f"Storyboard position: scene {index + 1} of {len(narrations)}.",
                    "Creative continuity note: preserve recurring subjects when useful, "
                    "but give this shot a narration-specific action, framing, and ending.",
                ]
                if index > 0:
                    continuity.append(f"Previous narration: {narrations[index - 1]}")
                if index + 1 < len(narrations):
                    continuity.append(f"Next narration: {narrations[index + 1]}")
                context.append(" ".join(continuity))
                return (
                    await asyncio.wait_for(
                        generate_video_prompts(
                            llm_service=self.llm,
                            narrations=[narration],
                            batch_size=1,
                            max_retries=3,
                            estimated_durations=[estimate_video_prompt_duration(narration)],
                            reference_contexts=[context],
                            model=self.model,
                        ),
                        timeout=self.scene_timeout_seconds,
                    )
                )[0]

        generated = await asyncio.gather(
            *(generate_one(index, narration) for index, narration in enumerate(narrations)),
            return_exceptions=True,
        )
        _, local_scenes = self.fallback_plan(narrations, "video", topic=topic)
        fallback_positions = {
            index
            for index, value in enumerate(generated)
            if not isinstance(value, str) or not value.strip()
        }
        prompts = [
            value if isinstance(value, str) and value.strip() else local_scenes[index].media_prompt
            for index, value in enumerate(generated)
        ]
        return prompts, fallback_positions

    @classmethod
    def fallback_plan(
        cls,
        narrations: list[str],
        asset_type: Literal["image", "video"],
        *,
        topic: str = "",
    ) -> tuple[list[SubjectProfile], list[GroundedStoryboardScene]]:
        """Return topic-anchored English scenes when the text model is unreachable."""
        subject = cls._fallback_subject_anchor(topic, narrations)
        scene_directions = (
            f"Wide documentary view frames {subject} at rest in an ordinary, plausible "
            "military environment. As subtle activity begins around the subject, the "
            "locked camera preserves its real scale and ends on a clear full profile.",
            f"Medium side view keeps {subject} unmistakably centered as one ordinary "
            "visible action begins, develops with realistic weight, and then settles "
            "into a stable operating state.",
            f"Close observational view studies accessible exterior surfaces of "
            f"{subject}. While a physically plausible movement continues, natural "
            "light crosses the material and the frame finally holds on the changed state.",
            f"Locked-off long-lens view follows {subject} interacting with its immediate "
            "surroundings. The action unfolds continuously, surface movement remains "
            "credible, and the final composition retains the complete subject.",
            f"Steady concluding view holds {subject} in the same documentary setting. "
            "As the last visible action finishes, residual motion gradually fades and "
            "the shot ends with the subject clearly identifiable in a stable frame.",
        )
        scenes = []
        for index, narration in enumerate(narrations, start=1):
            narration_focus = cls._fallback_narration_focus(narration, subject)
            sound = (
                " A minimal synchronized soundscape contains only natural environmental "
                "and mechanical sounds; there is no speech, narration, singing, or music."
                if asset_type == "video"
                else ""
            )
            prompt = (
                f"Scene {index}: "
                + scene_directions[(index - 1) % len(scene_directions)]
                + (
                    f" {narration_focus}"
                    " Natural motion, coherent lighting, concrete surface detail, and a "
                    "clear final composition keep the shot visually distinct."
                )
                + sound
            )
            scene = cls._scene(index, narration, prompt, asset_type, [])
            scene.warnings.append("scene_prompt_fallback")
            scenes.append(scene)
        return [], scenes

    @staticmethod
    def _fallback_narration_focus(narration: str, subject: str) -> str:
        value = narration.casefold()
        if "膛线" in value or "滑膛" in value:
            return (
                "The visible explanation follows a projectile rotating through the "
                "rifled bore and leaving the muzzle in stable flight, contrasted only "
                "with the earlier smooth bore named by the narration."
            )
        if "高压气体" in value or ("火药" in value and "炮口" in value):
            return (
                "The visible explanation follows expanding propellant gas driving a "
                "projectile along the barrel toward the muzzle, ending as it exits."
            )
        if "炮管" in value and ("弹丸" in value or "火药" in value):
            return (
                "The barrel remains the visual center while pressure acts behind a "
                "projectile and guides its only forward path toward the muzzle."
            )
        if "制导炮弹" in value or ("铁球" in value and "炮弹" in value):
            return (
                "The frame compares a solid iron cannonball with a generic modern "
                "guided artillery shell without selecting a specific weapon platform."
            )
        if "铁球" in value or "巨响" in value:
            return (
                "A solid iron cannonball exits the cannon barrel as smoke and recoil "
                "develop naturally, ending with the cannon still clearly framed."
            )
        return (
            f"The visible action stays directly centered on {subject} and never shifts "
            "to unrelated people, products, or scenery."
        )

    @staticmethod
    def _fallback_subject_anchor(topic: str, narrations: list[str]) -> str:
        source = f"{topic} {' '.join(narrations)}".casefold()
        known_subjects = (
            (("大炮", "火炮", "炮管", "炮弹", "弹丸", "膛线"), "a field artillery cannon"),
            (("雷达", "天线"), "a modern military radar array"),
            (("航空母舰", "航母"), "a large aircraft carrier at sea"),
            (("潜艇",), "a military submarine underway"),
            (("导弹",), "a military missile on a public test range"),
            (("坦克",), "a modern main battle tank"),
            (("战斗机", "军机", "飞机", "舰载机"), "a modern military aircraft"),
            (("无人机",), "a modern military unmanned aircraft"),
            (("军舰", "舰艇", "驱逐舰", "护卫舰"), "a modern naval vessel underway"),
        )
        for terms, label in known_subjects:
            if any(term in source for term in terms):
                return label
        ascii_topic = " ".join(
            re.findall(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", topic.casefold())
        ).strip()
        if ascii_topic:
            return ascii_topic
        return "the concrete military platform described in the narration"

    def select_research_contexts(
        self,
        narrations: list[str],
        visual_facts: list[VisualFact],
        claims: list[EvidenceClaim],
        *,
        max_notes_per_scene: int = 5,
    ) -> list[list[str]]:
        safe_claims = [
            claim for claim in claims if not claim.conflicts and claim.status.value != "conflicted"
        ]
        safe_claim_ids = {claim.id for claim in safe_claims}
        notes = [
            fact.allowed_detail.strip()
            for fact in visual_facts
            if fact.allowed_detail.strip()
            and all(claim_id in safe_claim_ids for claim_id in fact.claim_ids)
        ]
        notes.extend(claim.statement.strip() for claim in safe_claims)
        unique_notes = list(dict.fromkeys(note for note in notes if note))

        contexts: list[list[str]] = []
        for narration in narrations:
            narration_tokens = self._tokens(narration)
            ranked = []
            for position, note in enumerate(unique_notes):
                overlap = narration_tokens & self._tokens(note)
                if overlap:
                    ranked.append((len(overlap), -position, note))
            ranked.sort(reverse=True)
            selected = [item[2] for item in ranked[:max_notes_per_scene]]
            contexts.append(selected)
        return contexts

    @staticmethod
    def _tokens(value: str) -> set[str]:
        normalized = value.casefold()
        words = set(re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", normalized))
        chinese_runs = re.findall(r"[\u4e00-\u9fff]+", normalized)
        chinese_bigrams = {
            run[index : index + 2] for run in chinese_runs for index in range(max(0, len(run) - 1))
        }
        return words | chinese_bigrams

    @staticmethod
    def _claim_ids_for_context(
        context: list[str],
        claims: list[EvidenceClaim],
    ) -> list[str]:
        selected = set(context)
        return [
            claim.id
            for claim in claims
            if claim.statement.strip() in selected
            and not claim.conflicts
            and claim.status.value != "conflicted"
        ]

    @staticmethod
    def _prompt_input(index: int, narration: str, research_context: list[str]) -> str:
        value = f"Scene {index}: {narration}"
        if research_context:
            value += "\nOptional web references for this scene only:\n- " + "\n- ".join(
                research_context
            )
        value += (
            "\nCreate a complete scene with a clear subject, visible action, camera "
            "behavior, and ending state. References are optional; normal creative "
            "generation is allowed when they are insufficient. Never choose a precise "
            "number or model from conflicting material. Avoid unconfirmed markings, "
            "weapon loads, and internal structures."
        )
        return value

    @staticmethod
    def _valid_prompts(prompts: list[str], narrations: list[str]) -> bool:
        if len(prompts) != len(narrations) or any(not prompt.strip() for prompt in prompts):
            return False
        if any(
            re.search(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", prompt) for prompt in prompts
        ):
            return False
        normalized = {" ".join(prompt.casefold().split()) for prompt in prompts}
        return len(normalized) == len(prompts)

    @staticmethod
    def _scene(
        index: int,
        narration: str,
        prompt: str,
        asset_type: Literal["image", "video"],
        claim_ids: list[str],
    ) -> GroundedStoryboardScene:
        return GroundedStoryboardScene(
            scene_index=index,
            narration=narration,
            visual_description=prompt.strip(),
            media_prompt=prompt.strip(),
            estimated_duration=VisualPlanner._estimate_narration_duration(narration),
            asset_type=asset_type,
            subject=GroundedField(),
            environment=GroundedField(),
            opening_state=GroundedField(),
            action=GroundedField(),
            camera=GroundedField(),
            composition=GroundedField(),
            lighting=GroundedField(),
            ending_frame=GroundedField(),
            claim_ids=claim_ids,
            fallback_level="unverified",
            verification_status="unverified",
        )

    @staticmethod
    def _estimate_narration_duration(narration: str) -> int:
        return estimate_video_prompt_duration(narration)
