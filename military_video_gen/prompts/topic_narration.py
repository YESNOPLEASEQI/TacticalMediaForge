"""Prompts for planning and writing topic-based narration."""


TOPIC_NARRATIVE_PLAN_PROMPT = """# Role
You are a military technology science editor planning one coherent short-video
voice-over for a general audience.

# Topic
{topic}

# Available reference material
{reference_context}

# Task
Plan a single explanatory thread that will be written as {n_storyboard} adjacent
narration segments. Choose the most useful narrative logic for this particular
topic. Depending on the subject, that may be a question unfolding into an
answer, cause and effect, comparison, structural explanation, historical
development, or another natural progression.

The segments will be heard consecutively. Give each segment one distinct job in
the same explanation, and make its bridge describe how the thought can flow into
the next segment. The final segment should resolve the thread in the way that
best fits the topic: for example by answering the central question, clarifying a
design trade-off, completing a comparison, or crystallizing the core idea.

Select only reference points that help this narrative. When concrete reference
material is supplied, every factual beat must be entailed by that material; do
not fill gaps from memory. If there are fewer independent facts than beats,
split a supported fact into setup, explanation, and conclusion beats without
adding a new factual assertion. Reference material is optional only when the
placeholder explicitly says that none was supplied.
Do not write the finished narration.

# Output
Return JSON only, with exactly {n_storyboard} beats:

```json
{{
  "central_question": "what the audience should understand by the end",
  "narrative_angle": "the chosen explanatory perspective",
  "opening_intent": "how the first segment enters the subject",
  "beats": [
    {{
      "purpose": "the segment's role in the whole explanation",
      "key_point": "the one idea it develops",
      "bridge": "the thought that naturally leads onward"
    }}
  ],
  "ending_intent": "the understanding or image the final segment leaves"
}}
```

Use the same language as the topic for all text values.
"""


TOPIC_NARRATION_PROMPT = """# Role
You are a military technology science editor writing an accessible, restrained
short-video voice-over for a general audience.

# Topic
{topic}

# Narrative plan
{narrative_plan}

# Available reference material
{reference_context}

# Writing task
Write one continuous voice-over divided into exactly {n_storyboard} adjacent
segments. The segments are not independent fact cards: they should sound like
the same editor continuing one train of thought. Follow the plan's central
question, angle, beat progression, bridges, and ending intent while allowing
natural phrasing to take priority over the plan's wording.

Each segment should advance one main idea. Use references, pronouns, callbacks,
contrasts, or causal transitions where they make the handoff between neighboring
segments feel natural. Vary sentence shape according to meaning instead of
making every segment a self-contained headline.

The final segment should complete the explanation established by the opening.
Its role is determined by this topic and plan; it may deliver the answer,
synthesize the mechanism, complete a comparison, clarify a trade-off, or leave
a concrete concluding image.

# Reference use
When concrete reference material is supplied, every factual assertion must be
entailed by it. Do not mention URLs and do not add facts from memory, including
models, dates, figures, structures, appearance, or capabilities absent from the
material. If the references contain fewer independent facts than requested
segments, divide supported facts across setup, explanation, transition, and
conclusion segments without creating new claims. Only when the placeholder
explicitly says no online material was supplied may the topic be explained
normally without references.

# Voice, rhythm, and length
- Match the language of the input topic.
- Chinese: write 12 to 22 Chinese characters per segment. Treat each segment as
  one short subtitle card, not as a paragraph.
- English and other space-delimited languages: aim for roughly {min_words} to
  {max_words} words per segment.
- Write for spoken delivery: clear, concrete, calm, and naturally paced.
- Keep a consistent editorial voice across all segments.
- Put only one main clause in each segment. Prefer a direct subject-verb-object
  sentence or one compact question.
- For Chinese, normally use no comma. At most one comma is allowed only when it
  is essential to comprehension. Never chain facts with multiple commas.
- Move the next fact or explanation into the next segment instead of extending
  the current sentence. Frequent clean cuts are more important than packing
  every supporting detail into one segment.
- Remove filler openings, stacked modifiers, repeated conclusions, and spoken
  padding such as “也就是说”, “事实上”, or “值得注意的是” unless indispensable.
- Prefer an observable detail, meaningful contrast, clear question, or direct
  idea over generic scene-setting.
- Preserve nuance without turning the ending into a routine disclaimer.
- Do not include URLs, numbering, emojis, production instructions, or citations
  in the narration.
- Do not end individual narration strings with punctuation.

# Output
Return JSON only:

```json
{{
  "narrations": [
    "first narration segment",
    "second narration segment"
  ]
}}
```

The array must contain exactly {n_storyboard} non-empty strings.
"""


def build_topic_narrative_plan_prompt(
    topic: str,
    n_storyboard: int,
    reference_context: str = "No online reference material supplied.",
) -> str:
    """Build the lightweight narrative-planning prompt."""
    return TOPIC_NARRATIVE_PLAN_PROMPT.format(
        topic=topic,
        n_storyboard=n_storyboard,
        reference_context=reference_context,
    )


def build_topic_narration_prompt(
    topic: str,
    n_storyboard: int,
    min_words: int,
    max_words: int,
    reference_context: str = "No online reference material supplied.",
    narrative_plan: str = "No separate narrative plan supplied.",
) -> str:
    """Build the narration-writing prompt."""
    return TOPIC_NARRATION_PROMPT.format(
        topic=topic,
        narrative_plan=narrative_plan,
        reference_context=reference_context,
        n_storyboard=n_storyboard,
        min_words=min_words,
        max_words=max_words,
    )
