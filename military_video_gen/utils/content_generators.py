"""
Content generation utility functions

Pure/stateless functions for generating content using LLM.
These functions are reusable across different pipelines.
"""

import asyncio
import json
import re
from typing import List, Literal, Optional

from loguru import logger

from military_video_gen.utils.safety import enforce_safe_generation_fields, sanitize_error_message


class ScriptGenerationTimeoutError(TimeoutError):
    """The narration-writing model call exceeded its dedicated deadline."""


async def generate_title(
    llm_service,
    content: str,
    strategy: Literal["auto", "direct", "llm"] = "auto",
    max_length: int = 15,
) -> str:
    """
    Generate title from content

    Args:
        llm_service: LLM service instance
        content: Source content (topic or script)
        strategy: Generation strategy
            - "auto": Auto-decide based on content length (default)
            - "direct": Use content directly (truncated if needed)
            - "llm": Always use LLM to generate title
        max_length: Maximum title length (default: 15)

    Returns:
        Generated title
    """
    if strategy == "direct":
        content = content.strip()
        return content[:max_length] if len(content) > max_length else content

    if strategy == "auto":
        if len(content.strip()) <= 15:
            return content.strip()
        # Fall through to LLM

    # Use LLM to generate title
    from military_video_gen.prompts import build_title_generation_prompt

    # Pass max_length to prompt so LLM knows the character limit
    prompt = build_title_generation_prompt(content, max_length=max_length)
    response = await llm_service(prompt, temperature=0.7, max_tokens=2000)

    # Clean up response
    title = response.strip()

    # Remove quotes if present
    if title.startswith('"') and title.endswith('"'):
        title = title[1:-1]
    if title.startswith("'") and title.endswith("'"):
        title = title[1:-1]

    # Remove trailing punctuation
    title = title.rstrip(".,!?;:'\"")

    # Safety: if still over limit, truncate smartly
    if len(title) > max_length:
        # Try to truncate at word boundary
        truncated = title[:max_length]
        last_space = truncated.rfind(" ")

        # Only use word boundary if it's not too far back (at least 60% of max_length)
        if last_space > max_length * 0.6:
            title = truncated[:last_space]
        else:
            title = truncated

        # Remove any trailing punctuation after truncation
        title = title.rstrip(".,!?;:'\"")

    enforce_safe_generation_fields(title=title)
    logger.debug(f"Generated title ({len(title)} chars)")
    return title


async def generate_narrations_from_topic(
    llm_service,
    topic: str,
    n_scenes: int = 5,
    min_words: int = 5,
    max_words: int = 20,
    reference_context: str = "No online reference material supplied.",
    planning_timeout_seconds: float = 30,
    writing_timeout_seconds: float = 120,
) -> List[str]:
    """
    Generate narrations from topic using LLM

    Args:
        llm_service: LLM service instance
        topic: Topic/theme to generate narrations from
        n_scenes: Number of narrations to generate
        min_words: Minimum narration length
        max_words: Maximum narration length

    Returns:
        List of narration texts
    """
    from military_video_gen.prompts import (
        build_topic_narration_prompt,
        build_topic_narrative_plan_prompt,
    )

    logger.info(f"Generating {n_scenes} narrations from topic: {topic}")

    plan_prompt = build_topic_narrative_plan_prompt(
        topic=topic,
        n_storyboard=n_scenes,
        reference_context=reference_context,
    )
    try:
        plan_response = await asyncio.wait_for(
            llm_service(
                prompt=plan_prompt,
                temperature=0.5,
                max_tokens=3000,
            ),
            timeout=planning_timeout_seconds,
        )
        narrative_plan = _normalize_narrative_plan(
            _parse_json(plan_response),
            n_scenes=n_scenes,
        )
    except asyncio.CancelledError:
        raise
    except Exception as error:
        logger.warning(
            "Narrative planning failed; using a lightweight local plan: {}",
            error,
        )
        narrative_plan = _fallback_narrative_plan(topic, n_scenes)

    prompt = build_topic_narration_prompt(
        topic=topic,
        n_storyboard=n_scenes,
        min_words=min_words,
        max_words=max_words,
        reference_context=reference_context,
        narrative_plan=json.dumps(narrative_plan, ensure_ascii=False, indent=2),
    )

    try:
        response = await asyncio.wait_for(
            llm_service(
                prompt=prompt,
                temperature=0.8,
                max_tokens=8192,
            ),
            timeout=writing_timeout_seconds,
        )
    except asyncio.CancelledError:
        raise
    except TimeoutError as error:
        raise ScriptGenerationTimeoutError("script_generation_timeout") from error

    logger.debug(f"LLM response: {response[:200]}...")

    # Parse JSON
    result = _parse_json(response)

    if "narrations" not in result:
        raise ValueError("Invalid response format: missing 'narrations' key")

    narrations = result["narrations"]
    if not isinstance(narrations, list) or any(
        not isinstance(item, str) or not item.strip() for item in narrations
    ):
        raise ValueError("Invalid response format: narrations must be non-empty strings")

    # Validate count
    if len(narrations) > n_scenes:
        logger.warning(f"Got {len(narrations)} narrations, taking first {n_scenes}")
        narrations = narrations[:n_scenes]
    elif len(narrations) < n_scenes:
        raise ValueError(f"Expected {n_scenes} narrations, got only {len(narrations)}")

    enforce_safe_generation_fields(narrations=narrations)
    logger.info(f"Generated {len(narrations)} narrations successfully")
    return narrations


def _normalize_narrative_plan(value: dict, *, n_scenes: int) -> dict:
    """Validate the small plan contract without making it persistent state."""
    required_text = (
        "central_question",
        "narrative_angle",
        "opening_intent",
        "ending_intent",
    )
    if any(not isinstance(value.get(key), str) or not value[key].strip() for key in required_text):
        raise ValueError("narrative plan is missing required text")
    beats = value.get("beats")
    if not isinstance(beats, list) or len(beats) != n_scenes:
        raise ValueError(f"narrative plan must contain exactly {n_scenes} beats")
    normalized_beats = []
    for beat in beats:
        if not isinstance(beat, dict):
            raise ValueError("narrative plan beat must be an object")
        fields = {}
        for key in ("purpose", "key_point", "bridge"):
            item = beat.get(key)
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"narrative plan beat is missing {key}")
            fields[key] = item.strip()
        normalized_beats.append(fields)
    return {key: value[key].strip() for key in required_text[:-1]} | {
        "beats": normalized_beats,
        "ending_intent": value["ending_intent"].strip(),
    }


def _fallback_narrative_plan(topic: str, n_scenes: int) -> dict:
    """Keep script generation available if the planning response is invalid."""
    beats = []
    for index in range(n_scenes):
        if index == 0:
            purpose = "自然引出主题并建立全篇要解释的核心问题"
        elif index == n_scenes - 1:
            purpose = "完成前文的解释并形成与主题相称的自然落点"
        else:
            purpose = "承接前文并推进一个新的核心信息"
        beats.append(
            {
                "purpose": purpose,
                "key_point": f"围绕{topic}选择一个与前后文相连的具体要点",
                "bridge": "让当前信息自然引出下一部分，不写成孤立标题",
            }
        )
    return {
        "central_question": f"让观众理解{topic}最核心的机制或变化",
        "narrative_angle": "选择最适合主题的一条解释主线",
        "opening_intent": "从主题本身最有理解价值的切入点开始",
        "beats": beats,
        "ending_intent": "回应开头并留下清晰、具体的核心认识",
    }


async def generate_narrations_from_content(
    llm_service, content: str, n_scenes: int = 5, min_words: int = 5, max_words: int = 20
) -> List[str]:
    """
    Generate narrations from user-provided content using LLM

    Args:
        llm_service: LLM service instance
        content: User-provided content
        n_scenes: Number of narrations to generate
        min_words: Minimum narration length
        max_words: Maximum narration length

    Returns:
        List of narration texts
    """
    from military_video_gen.prompts import build_content_narration_prompt

    logger.info(f"Generating {n_scenes} narrations from content ({len(content)} chars)")

    prompt = build_content_narration_prompt(
        content=content, n_storyboard=n_scenes, min_words=min_words, max_words=max_words
    )

    response = await llm_service(prompt=prompt, temperature=0.8, max_tokens=2000)

    # Parse JSON
    result = _parse_json(response)

    if "narrations" not in result:
        raise ValueError("Invalid response format: missing 'narrations' key")

    narrations = result["narrations"]
    if not isinstance(narrations, list) or any(
        not isinstance(item, str) or not item.strip() for item in narrations
    ):
        raise ValueError("Invalid response format: narrations must be non-empty strings")

    # Validate count
    if len(narrations) > n_scenes:
        logger.warning(f"Got {len(narrations)} narrations, taking first {n_scenes}")
        narrations = narrations[:n_scenes]
    elif len(narrations) < n_scenes:
        raise ValueError(f"Expected {n_scenes} narrations, got only {len(narrations)}")

    enforce_safe_generation_fields(narrations=narrations)
    logger.info(f"Generated {len(narrations)} narrations successfully")
    return narrations


async def split_narration_script(
    script: str,
    split_mode: Literal["paragraph", "line", "sentence"] = "paragraph",
) -> List[str]:
    """
    Split user-provided narration script into segments

    Args:
        script: Fixed narration script
        split_mode: Splitting strategy
            - "paragraph": Split by double newline (\\n\\n), preserve single newlines within paragraphs
            - "line": Split by single newline (\\n), each line is a segment
            - "sentence": Split by sentence-ending punctuation (。.!?！？)

    Returns:
        List of narration segments
    """
    logger.info(f"Splitting script (mode={split_mode}, length={len(script)} chars)")

    narrations = []

    if split_mode == "paragraph":
        # Split by double newline (paragraph mode)
        # Preserve single newlines within paragraphs
        paragraphs = re.split(r"\n\s*\n", script)
        for para in paragraphs:
            # Only strip leading/trailing whitespace, preserve internal newlines
            cleaned = para.strip()
            if cleaned:
                narrations.append(para)
        logger.info(f"✅ Split script into {len(narrations)} segments (by paragraph)")

    elif split_mode == "line":
        # Split by single newline (original behavior)
        narrations = [line.strip() for line in script.split("\n") if line.strip()]
        logger.info(f"✅ Split script into {len(narrations)} segments (by line)")

    elif split_mode == "sentence":
        # Split by sentence-ending punctuation
        # Supports Chinese (。！？) and English (.!?)
        # Use regex to split while keeping sentences intact
        cleaned = re.sub(r"\s+", " ", script.strip())
        # Split on sentence-ending punctuation, keeping the punctuation with the sentence
        sentences = re.split(r"(?<=[。.!?！？])\s*", cleaned)
        narrations = [s.strip() for s in sentences if s.strip()]
        logger.info(f"✅ Split script into {len(narrations)} segments (by sentence)")

    else:
        # Fallback to line mode
        logger.warning(f"Unknown split_mode '{split_mode}', falling back to 'line'")
        narrations = [line.strip() for line in script.split("\n") if line.strip()]

    # Log statistics
    if narrations:
        lengths = [len(s) for s in narrations]
        logger.info(
            f"   Min: {min(lengths)} chars, Max: {max(lengths)} chars, Avg: {sum(lengths) // len(lengths)} chars"
        )

    enforce_safe_generation_fields(narrations=narrations)
    return narrations


async def generate_image_prompts(
    llm_service,
    narrations: List[str],
    min_words: int = 30,
    max_words: int = 60,
    batch_size: int = 10,
    max_retries: int = 3,
    progress_callback: Optional[callable] = None,
    model: Optional[str] = None,
) -> List[str]:
    """
    Generate image prompts from narrations (with batching and retry)

    Args:
        llm_service: LLM service instance
        narrations: List of narrations
        min_words: Min image prompt length
        max_words: Max image prompt length
        batch_size: Max narrations per batch (default: 10)
        max_retries: Max retry attempts per batch (default: 3)
        progress_callback: Optional callback(completed, total, message) for progress updates

    Returns:
        List of image prompts (base prompts, without prefix applied)
    """
    from military_video_gen.prompts import build_image_prompt_prompt

    logger.info(
        f"Generating image prompts for {len(narrations)} narrations (batch_size={batch_size})"
    )

    # Split narrations into batches
    batches = [narrations[i : i + batch_size] for i in range(0, len(narrations), batch_size)]
    logger.info(f"Split into {len(batches)} batches")

    all_prompts = []

    # Process each batch
    for batch_idx, batch_narrations in enumerate(batches, 1):
        logger.info(
            f"Processing batch {batch_idx}/{len(batches)} ({len(batch_narrations)} narrations)"
        )

        # Retry logic for this batch
        for attempt in range(1, max_retries + 1):
            try:
                # Generate prompts for this batch
                prompt = build_image_prompt_prompt(
                    narrations=batch_narrations, min_words=min_words, max_words=max_words
                )

                response = await llm_service(
                    prompt=prompt,
                    temperature=0.7,
                    max_tokens=max(1024, len(batch_narrations) * 192),
                    model=model,
                )

                logger.debug(
                    f"Batch {batch_idx} attempt {attempt}: LLM response length: {len(response)} chars"
                )

                # Parse JSON
                result = _parse_json(response)

                if "image_prompts" not in result:
                    raise KeyError("Invalid response format: missing 'image_prompts'")

                batch_prompts = result["image_prompts"]
                if not isinstance(batch_prompts, list) or any(
                    not isinstance(item, str) or not item.strip() for item in batch_prompts
                ):
                    raise ValueError(
                        "Invalid response format: image_prompts must be non-empty strings"
                    )

                # Validate count
                if len(batch_prompts) != len(batch_narrations):
                    error_msg = (
                        f"Batch {batch_idx} prompt count mismatch (attempt {attempt}/{max_retries}):\n"
                        f"  Expected: {len(batch_narrations)} prompts\n"
                        f"  Got: {len(batch_prompts)} prompts"
                    )
                    logger.warning(error_msg)

                    if attempt < max_retries:
                        logger.info(f"Retrying batch {batch_idx}...")
                        continue
                    else:
                        raise ValueError(error_msg)

                cjk_positions = [
                    position
                    for position, generated in enumerate(batch_prompts, start=1)
                    if _contains_cjk(str(generated))
                ]
                if cjk_positions:
                    error_msg = (
                        f"Batch {batch_idx} contains CJK characters in prompts {cjk_positions}"
                    )
                    logger.warning(error_msg)
                    if attempt < max_retries:
                        continue
                    raise ValueError("image prompts must be English-only")

                # Success!
                logger.info(
                    f"✅ Batch {batch_idx} completed successfully ({len(batch_prompts)} prompts)"
                )
                all_prompts.extend(batch_prompts)

                # Report progress
                if progress_callback:
                    progress_callback(
                        len(all_prompts),
                        len(narrations),
                        f"Batch {batch_idx}/{len(batches)} completed",
                    )

                break

            except json.JSONDecodeError as e:
                logger.error(
                    f"Batch {batch_idx} JSON parse error "
                    f"(attempt {attempt}/{max_retries}): {sanitize_error_message(e)}"
                )
                if attempt >= max_retries:
                    raise
                logger.info(f"Retrying batch {batch_idx}...")

    enforce_safe_generation_fields(media_prompts=all_prompts)
    logger.info(f"✅ Generated {len(all_prompts)} image prompts")
    return all_prompts


async def generate_video_prompts(
    llm_service,
    narrations: List[str],
    min_words: int = 30,
    max_words: int = 60,
    batch_size: int = 10,
    max_retries: int = 3,
    progress_callback: Optional[callable] = None,
    estimated_durations: Optional[List[float]] = None,
    reference_contexts: Optional[List[List[str]]] = None,
    model: Optional[str] = None,
) -> List[str]:
    """
    Generate video prompts from narrations (with batching and retry)

    Args:
        llm_service: LLM service instance
        narrations: List of narrations
        min_words: Min video prompt length
        max_words: Max video prompt length
        batch_size: Max narrations per batch (default: 10)
        max_retries: Max retry attempts per batch (default: 3)
        progress_callback: Optional callback(completed, total, message) for progress updates

    Returns:
        List of video prompts (base prompts, without prefix applied)
    """
    from military_video_gen.prompts.video_generation import (
        build_video_prompt_prompt,
        estimate_video_prompt_duration,
        video_prompt_word_range,
    )

    logger.info(
        f"Generating video prompts for {len(narrations)} narrations (batch_size={batch_size})"
    )

    durations = list(estimated_durations or [])
    if len(durations) < len(narrations):
        durations.extend(
            float(estimate_video_prompt_duration(narration))
            for narration in narrations[len(durations) :]
        )
    contexts = list(reference_contexts or [])
    if len(contexts) < len(narrations):
        contexts.extend([] for _ in narrations[len(contexts) :])

    batches = [
        (
            narrations[index : index + batch_size],
            durations[index : index + batch_size],
            contexts[index : index + batch_size],
        )
        for index in range(0, len(narrations), batch_size)
    ]
    logger.info(f"Split into {len(batches)} batches")

    all_prompts = []

    # Process each batch
    for batch_idx, (batch_narrations, batch_durations, batch_contexts) in enumerate(batches, 1):
        logger.info(
            f"Processing batch {batch_idx}/{len(batches)} ({len(batch_narrations)} narrations)"
        )

        batch_prompts = [""] * len(batch_narrations)
        pending_positions = list(range(len(batch_narrations)))
        previous_prompts: List[str] | None = None
        validation_feedback: List[List[str]] | None = None

        for attempt in range(1, max_retries + 1):
            try:
                prompt = build_video_prompt_prompt(
                    narrations=[batch_narrations[position] for position in pending_positions],
                    min_words=min_words,
                    max_words=max_words,
                    estimated_durations=[
                        batch_durations[position] for position in pending_positions
                    ],
                    reference_contexts=[batch_contexts[position] for position in pending_positions],
                    previous_prompts=previous_prompts,
                    validation_feedback=validation_feedback,
                )

                response = await llm_service(
                    prompt=prompt,
                    temperature=0.5,
                    # DeepSeek reasoning models can spend most of a small output
                    # budget before emitting the JSON answer. Leave enough room
                    # for both reasoning and a complete LTX paragraph.
                    max_tokens=max(3072, len(pending_positions) * 768),
                    model=model,
                )

                logger.debug(
                    f"Batch {batch_idx} attempt {attempt}: LLM response length: {len(response)} chars"
                )

                # Parse JSON
                result = _parse_json(response)

                if "video_prompts" not in result:
                    raise KeyError("Invalid response format: missing 'video_prompts'")

                generated_prompts = result["video_prompts"]
                if not isinstance(generated_prompts, list) or any(
                    not isinstance(item, str) or not item.strip() for item in generated_prompts
                ):
                    raise ValueError(
                        "Invalid response format: video_prompts must be non-empty strings"
                    )
                if len(generated_prompts) != len(pending_positions):
                    raise ValueError(
                        f"Prompt count mismatch: expected {len(pending_positions)}, got {len(generated_prompts)}"
                    )

                for position, generated in zip(pending_positions, generated_prompts, strict=True):
                    batch_prompts[position] = generated.strip()

                issues_by_position: dict[int, List[str]] = {}
                for position, generated in enumerate(batch_prompts):
                    target_min, target_max = video_prompt_word_range(batch_durations[position])
                    issues = _video_prompt_validation_issues(
                        generated,
                        min_words=target_min,
                        max_words=target_max,
                        narration=batch_narrations[position],
                        reference_notes=batch_contexts[position],
                    )
                    if issues:
                        issues_by_position[position] = issues

                normalized_positions: dict[str, int] = {}
                for position, generated in enumerate(batch_prompts):
                    normalized = " ".join(generated.casefold().split())
                    if normalized and normalized in normalized_positions:
                        issues_by_position.setdefault(position, []).append(
                            "prompt duplicates another scene"
                        )
                    elif normalized:
                        normalized_positions[normalized] = position

                if not issues_by_position:
                    break
                if attempt >= max_retries:
                    if any(
                        _contains_cjk(batch_prompts[position]) for position in issues_by_position
                    ):
                        raise ValueError("video prompts must be English-only")
                    logger.warning(
                        "video_prompt_validation_warning batch={} issues={}",
                        batch_idx,
                        issues_by_position,
                    )
                    break

                pending_positions = sorted(issues_by_position)
                previous_prompts = [batch_prompts[position] for position in pending_positions]
                validation_feedback = [
                    issues_by_position[position] for position in pending_positions
                ]
                logger.info(
                    "Retrying {} invalid video prompts in batch {}",
                    len(pending_positions),
                    batch_idx,
                )

            except Exception as e:
                logger.warning(
                    f"✗ Batch {batch_idx} attempt {attempt} failed: {sanitize_error_message(e)}"
                )
                if attempt >= max_retries:
                    raise
                logger.info(f"Retrying batch {batch_idx}...")

        all_prompts.extend(batch_prompts)
        logger.info(f"✓ Batch {batch_idx} completed: {len(batch_prompts)} video prompts")
        if progress_callback:
            progress_callback(
                len(all_prompts),
                len(narrations),
                f"Batch {batch_idx}/{len(batches)} completed",
            )

    enforce_safe_generation_fields(media_prompts=all_prompts)
    logger.info(f"✅ Generated {len(all_prompts)} video prompts")
    return all_prompts


def _video_prompt_validation_issues(
    prompt: str,
    *,
    min_words: int,
    max_words: int,
    narration: str = "",
    reference_notes: Optional[List[str]] = None,
) -> List[str]:
    """Return model-compatibility issues without fact-policing creative content."""
    if not prompt.strip():
        return ["prompt is empty"]

    issues = []
    if _contains_cjk(prompt):
        issues.append("use English only; remove all CJK characters")
    words = re.findall(r"[A-Za-z]+(?:[-'][A-Za-z]+)*", prompt)
    if len(words) < min_words:
        issues.append(f"use at least {min_words} English words")
    elif len(words) > max_words:
        issues.append(f"use no more than {max_words} English words")

    normalized = prompt.casefold()
    meta_phrases = (
        "evidence is insufficient",
        "insufficient evidence",
        "unsupported details",
        "available information",
        "cannot be confirmed",
        "cannot be verified",
        "research limitations",
        "source limitations",
    )
    if any(phrase in normalized for phrase in meta_phrases):
        issues.append("remove evidence caveats and research disclaimers")

    edit_phrases = (
        "montage",
        "split screen",
        "cut to",
        "fade in",
        "fade out",
        "dissolve to",
        "transition to",
    )
    if any(phrase in normalized for phrase in edit_phrases):
        issues.append("describe one continuous shot without editing instructions")

    # Narration and references guide the model but are deliberately not used as
    # an allow-list. LTX-2.3 benefits from concrete invented staging, appearance,
    # camera, personnel, and environmental details. The project-wide safety gate
    # already rejects actionable harmful requests at the trusted boundary.
    del narration, reference_notes
    return issues


def _contains_cjk(value: str) -> bool:
    """Return whether generated model input contains Chinese/Japanese Han text."""
    return bool(re.search(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", value))


def _parse_json(text: str) -> dict:
    """
    Parse JSON from text, with fallback to extract JSON from markdown code blocks

    Args:
        text: Text containing JSON

    Returns:
        Parsed JSON dict

    Raises:
        json.JSONDecodeError: If no valid JSON found
    """
    # Try direct parsing first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to extract JSON from markdown code block
    json_pattern = r"```(?:json)?\s*([\s\S]+?)\s*```"
    match = re.search(json_pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find any JSON object in the text
    json_pattern = (
        r'\{[^{}]*(?:"narrations"|"image_prompts"|"video_prompts")'
        r"\s*:\s*\[[^\]]*\][^{}]*\}"
    )
    match = re.search(json_pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # If all fails, raise error
    raise json.JSONDecodeError("No valid JSON found", text, 0)
