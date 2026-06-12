"""LLM request processing, prompt shaping, and text normalization helpers."""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass

from config import InputProcessingConfig, MaxTokens, StandardModeConfig, ToneModeConfig

log = logging.getLogger("flowkey.llm")


@dataclass(frozen=True)
class LlmRuntimeConfig:
    base_url: str
    model: str
    timeout_seconds: int
    server_auto_start: bool
    input_processing_cfg: InputProcessingConfig
    protected_words: list[str]
    modes_cfg: dict[str, StandardModeConfig | ToneModeConfig]


def is_prompt_mode(mode: str) -> bool:
    return mode == "prompt"


def reset_usage_acc(usage_acc: dict) -> None:
    usage_acc["prompt_tokens"] = 0
    usage_acc["completion_tokens"] = 0


def snapshot_usage_acc(usage_acc: dict) -> dict:
    return {
        "prompt_tokens": int(usage_acc["prompt_tokens"]),
        "completion_tokens": int(usage_acc["completion_tokens"]),
    }


def normalize_output(text: str) -> str:
    normalized = str(text or "")
    normalized = normalized.replace("﻿", "")
    normalized = normalized.replace("​", "")
    normalized = normalized.replace("—", " - ")
    normalized = normalized.replace("–", " - ")
    normalized = normalized.replace("‘", "'")
    normalized = normalized.replace("’", "'")
    normalized = normalized.replace("“", '"')
    normalized = normalized.replace("”", '"')
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r" ?\n ?", "\n", normalized)
    return normalized.strip()


def split_chunks(text: str, chunk_size: int, ip: InputProcessingConfig) -> list[str]:
    data = (text or "").strip()
    if len(data) <= chunk_size:
        return [data]
    chunks: list[str] = []
    index = 0
    while index < len(data):
        end = min(len(data), index + chunk_size)
        if end < len(data):
            split_at = data.rfind("\n", index, end)
            if split_at <= index:
                split_at = data.rfind(" ", index, end)
            if split_at > index + 100:
                end = split_at
        chunks.append(data[index:end].strip())
        index = end
    chunks = [chunk for chunk in chunks if chunk]

    merged: list[str] = []
    for chunk in chunks:
        if merged and len(chunk) < ip.min_chunk_size:
            merged[-1] = (merged[-1].rstrip() + "\n" + chunk.lstrip()).strip()
        else:
            merged.append(chunk)
    return merged


_SHORT_TEXT_THRESHOLD = 350
_MEDIUM_TEXT_THRESHOLD = 1200


def resolve_token_budget(runtime: LlmRuntimeConfig, mode: str, input_text: str) -> tuple[int, str]:
    """Return (max_tokens, strategy_label) based on mode config and input length."""
    text_len = len(input_text or "")
    input_processing_enabled = runtime.input_processing_cfg.enabled

    # Read per-mode token budgets from config, fall back to grammar-like values.
    mode_cfg: StandardModeConfig | ToneModeConfig | None = runtime.modes_cfg.get(mode)
    mt = mode_cfg.max_tokens if mode_cfg else MaxTokens(160, 220, 180)

    if text_len <= _SHORT_TEXT_THRESHOLD:
        max_tokens = mt.short
        strategy = f"{mode}_short"
    elif text_len <= _MEDIUM_TEXT_THRESHOLD:
        max_tokens = mt.medium
        strategy = f"{mode}_medium"
    else:
        max_tokens = mt.long
        strategy = f"{mode}_long"

    if not input_processing_enabled:
        strategy = f"{strategy}_noprocess"
    return max_tokens, strategy


def line_reuse_ratio(input_text: str, output_text: str) -> float:
    in_lines = [line.strip().lower() for line in str(input_text or "").splitlines() if line.strip()]
    out_lines = [line.strip().lower() for line in str(output_text or "").splitlines() if line.strip()]
    if not in_lines or not out_lines:
        return 0.0
    reused = 0
    for line in in_lines:
        for out_line in out_lines:
            if line in out_line or out_line in line:
                reused += 1
                break
    return reused / max(1, len(in_lines))


def word_set(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9']+", str(text or "").lower()))


def word_overlap_ratio(a: str, b: str) -> float:
    words_a = word_set(a)
    words_b = word_set(b)
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / max(1, len(words_a))


def is_weak_prompt_echo(input_text: str, output_text: str) -> bool:
    """True when the model only engine-processed or prefixed with 'Prompt:' instead of expanding."""
    out = str(output_text or "").strip()
    inp = str(input_text or "").strip()
    if not out or not inp:
        return False
    lowered = out.lower()
    if any(tag in lowered for tag in ("<task>", "<context>", "<constraints>", "<output_format>")):
        return False
    if re.match(r"^prompt:\s*.+", lowered):
        return True
    lines = [line.strip() for line in out.splitlines() if line.strip()]
    if len(lines) <= 2 and not looks_like_prompt_text(out):
        if word_overlap_ratio(inp, out) >= 0.55:
            return True
    return False


def looks_like_prompt_text(text: str) -> bool:
    lowered = str(text or "").lower()
    prompt_markers = (
        "respond",
        "task",
        "constraints",
        "requirements",
        "output",
        "format",
        "goals",
        "acceptance criteria",
        "steps",
        "deliverables",
        "architecture",
        "<task>",
        "<context>",
        "<constraints>",
        "<output_format>",
        "anthropic",
        "claude",
    )
    return any(marker in lowered for marker in prompt_markers)


def force_prompt_shape(input_text: str) -> str:
    cleaned = normalize_output(input_text)
    return (
        "<task>\n"
        f"Produce a copy-paste-ready Claude prompt for: {cleaned}\n"
        "</task>\n"
        "<output_format>\n"
        "Use <context>, <constraints>, and <output_format> sections; Markdown structure; "
        "testable constraints; professional approachable tone; no meta-framing.\n"
        "</output_format>"
    )


def strip_prompt_scaffold_labels(text: str) -> str:
    cleaned = str(text or "")
    cleaned = re.sub(r"(?im)^\s*\*{0,2}\s*(task|constraints|output format)\s*\*{0,2}\s*:\s*", "", cleaned)
    cleaned = re.sub(r"(?m)^\s*\*\*\s*$", "", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def dict_protect(text: str, protected_words: list[str]) -> tuple[str, dict[str, str]]:
    if not protected_words or not text:
        return text, {}
    mapping: dict[str, str] = {}
    masked = text
    for index, word in enumerate(protected_words):
        placeholder = f"__FFPDICT{index}__"
        pattern = re.compile(r"\b" + re.escape(word) + r"\b", re.IGNORECASE)
        first = pattern.search(masked)
        if not first:
            continue
        mapping[placeholder] = first.group(0)
        masked = pattern.sub(placeholder, masked)
    return masked, mapping


def dict_restore(text: str, mapping: dict[str, str]) -> str:
    if not mapping or not text:
        return text
    restored = text
    # Replace longest placeholders first so __FFPDICT10__ isn't
    # corrupted by a partial match on __FFPDICT1__.
    for placeholder in sorted(mapping, key=len, reverse=True):
        restored = restored.replace(placeholder, mapping[placeholder])
    return restored


def resolve_system_prompt(runtime: LlmRuntimeConfig, mode: str) -> str:
    """Look up the system prompt for *mode* from config; resolve tone sub-preset."""
    mode_cfg: StandardModeConfig | ToneModeConfig | None = runtime.modes_cfg.get(mode)
    if mode_cfg is None:
        raise RuntimeError(f"No config for mode '{mode}'.")
    system_prompt = mode_cfg.system_prompt.strip()
    if mode == "tone" and isinstance(mode_cfg, ToneModeConfig):
        preset = mode_cfg.preset.strip().lower()
        preset_cfg = getattr(mode_cfg.presets, preset, {})
        preset_prompt = str(preset_cfg.get("system_prompt") or "").strip()
        if preset_prompt:
            system_prompt = preset_prompt
    if not system_prompt:
        raise RuntimeError(f"No system_prompt configured for mode '{mode}'.")
    return system_prompt


def ensure_server_running(
    runtime: LlmRuntimeConfig,
    is_server_reachable: Callable[[], bool],
    start_server: Callable[[bool], str],
) -> None:
    """Check server reachability; auto-start if configured."""
    if not is_server_reachable():
        if not runtime.server_auto_start:
            raise RuntimeError("FastFlowLM server is unreachable and auto_start=false.")
        start_server(False)


def _process_grammar_chunks(
    chunks: list[str],
    model: str,
    system_prompt: str,
    call_api: Callable,
    deadline: float,
    max_tokens: int,
    chunk_size: int,
    remaining_timeout: Callable[[], int],
) -> tuple[str, str]:
    """Process each long-text chunk individually, then concatenate results."""
    out_parts: list[str] = []
    model_used = model
    per_chunk_tokens = max(100, int(max_tokens * 0.75))
    for chunk in chunks:
        if time.time() >= deadline - 2:
            break
        try:
            out, model_used = call_api(model, system_prompt, chunk, per_chunk_tokens, remaining_timeout())
            out_parts.append(out)
        except Exception as exc:
            log.warning("grammar chunk call failed, stopping chunk loop: %s", exc)
            break
    if not out_parts:
        fallback_chunk = (chunks[0] if chunks else "")[: max(300, chunk_size // 2)]
        text, model_used = call_api(
            model, system_prompt, fallback_chunk,
            max(120, per_chunk_tokens // 2), remaining_timeout(),
        )
    else:
        text = "\n\n".join(part for part in out_parts if part.strip())
    return text, model_used


def _compress_prompt_chunks(
    chunks: list[str],
    model: str,
    system_prompt: str,
    call_api: Callable,
    deadline: float,
    max_tokens: int,
    chunk_size: int,
    remaining_timeout: Callable[[], int],
) -> tuple[str, str]:
    """Compress each long-text chunk, merge, then run the full system prompt on the merged result."""
    condensed: list[str] = []
    model_used = model
    compress_prompt = (
        "Extract concise actionable requirements from the text. "
        "Keep key details and constraints. Preserve emoji/smiley symbols. "
        "Return bullet points only."
    )
    for chunk in chunks:
        if time.time() >= deadline - 4:
            break
        try:
            summary, _ = call_api(model, compress_prompt, chunk, 110, remaining_timeout())
            condensed.append(summary)
        except Exception as exc:
            log.warning("prompt-compression chunk call failed, stopping chunk loop: %s", exc)
            break
    merged = "\n".join(condensed) if condensed else (chunks[0] if chunks else "")[:chunk_size]
    try:
        text, model_used = call_api(model, system_prompt, merged, max_tokens, remaining_timeout())
    except Exception as exc:
        log.warning("merged prompt call failed, retrying with shorter fallback prompt: %s", exc)
        fallback_prompt = (
            "Rewrite this into a shorter Claude-ready prompt while preserving intent. "
            "Return only rewritten prompt text."
        )
        text, model_used = call_api(
            model, fallback_prompt, merged[: max(300, chunk_size // 2)],
            max(120, max_tokens // 2), remaining_timeout(),
        )
    return text, model_used


def _anti_echo_retry(
    text: str,
    masked_input: str,
    model: str,
    max_tokens: int,
    call_api: Callable,
    remaining_timeout: Callable[[], int],
) -> tuple[str, str]:
    """Prompt-mode: detect verbatim echo and retry with structured prompt. Returns (text, model_used)."""
    stripped = strip_prompt_scaffold_labels(text)
    if stripped:
        text = stripped
    out_norm = re.sub(r"\s+", " ", str(text).lower()).strip()
    in_norm = re.sub(r"\s+", " ", str(masked_input).lower()).strip()
    reuse_ratio = line_reuse_ratio(masked_input, text)
    near_verbatim = (
        (out_norm == in_norm)
        or (reuse_ratio >= 0.85)
        or is_weak_prompt_echo(masked_input, text)
    )
    if not near_verbatim:
        return text, model
    anti_echo_prompt = (
        "Rewrite into a Claude-ready prompt with <task>, <constraints>, and <output_format> sections. "
        "Do not copy the request verbatim or use meta-framing like 'Act as a prompt engineer'. "
        "Do not use bare labels like Task: or Constraints: without XML tags. "
        "Return only the rewritten prompt text."
    )
    try:
        retried, retry_model = call_api(
            model, anti_echo_prompt, masked_input,
            max(max_tokens, 240), remaining_timeout(),
        )
        if retried and retried.strip():
            return retried, retry_model
    except Exception as exc:
        log.debug("anti-echo retry failed, keeping original prompt text: %s", exc)
    return text, model


def _rescue_prompt_quality(
    text: str,
    masked_input: str,
    model: str,
    max_tokens: int,
    call_api: Callable,
    remaining_timeout: Callable[[], int],
) -> tuple[str, str]:
    """Prompt-mode: aggressive rewrite + force_prompt_shape fallback. Returns (text, model_used)."""
    overlap_ratio = word_overlap_ratio(masked_input, text)
    reuse_ratio = line_reuse_ratio(masked_input, text)
    near_copy = overlap_ratio >= 0.9 or reuse_ratio >= 0.9
    weak_echo = is_weak_prompt_echo(masked_input, text)
    if not ((near_copy and not looks_like_prompt_text(text)) or weak_echo):
        return text, model
    rescue_prompt = (
        "Rewrite into a stronger Claude-ready prompt for Anthropic models. "
        "Use XML sections, testable constraints, and Markdown output format. "
        "Do not copy the request verbatim or add meta-commentary. "
        "Preserve intent and emoji/smiley symbols. Return only the rewritten prompt text."
    )
    try:
        rescued, rescue_model = call_api(
            model, rescue_prompt, masked_input,
            max(max_tokens, 220), remaining_timeout(),
        )
        if rescued and rescued.strip():
            return rescued, rescue_model
        return force_prompt_shape(masked_input), model
    except Exception as exc:
        log.warning("prompt-rescue call failed, using deterministic prompt shaping: %s", exc)
        return force_prompt_shape(masked_input), model


def call_flm(
    runtime: LlmRuntimeConfig,
    mode: str,
    input_text: str,
    call_api: Callable[[str, str, str, int, int], tuple[str, str]],
    is_server_reachable: Callable[[], bool],
    start_server: Callable[[bool], str],
    usage_acc: dict,
) -> tuple[str, float, str, str]:
    system_prompt = resolve_system_prompt(runtime, mode)
    ensure_server_running(runtime, is_server_reachable, start_server)

    reset_usage_acc(usage_acc)
    started = time.time()
    deadline = started + runtime.timeout_seconds

    masked_input, dict_mapping = dict_protect(input_text, runtime.protected_words)
    max_tokens, strategy = resolve_token_budget(runtime, mode, masked_input)
    model = runtime.model

    def remaining_timeout() -> int:
        return max(2, int(deadline - time.time()))

    if is_prompt_mode(mode) and strategy == "prompt_short":
        max_tokens = max(max_tokens, 180)
    elif mode == "grammar" and strategy == "grammar_short":
        system_prompt = (
            "Fix grammar and punctuation only. Keep wording and emoji/smiley. "
            "Return only corrected text."
        )

    ip = runtime.input_processing_cfg
    input_processing_enabled = ip.enabled
    long_threshold = ip.input_length_threshold
    chunk_size = ip.chunk_size

    if input_processing_enabled and len(masked_input or "") >= long_threshold:
        chunks = split_chunks(masked_input, chunk_size, runtime.input_processing_cfg)[:3]
        if mode == "grammar":
            text, model_used = _process_grammar_chunks(
                chunks, model, system_prompt, call_api,
                deadline, max_tokens, chunk_size, remaining_timeout,
            )
        else:
            text, model_used = _compress_prompt_chunks(
                chunks, model, system_prompt, call_api,
                deadline, max_tokens, chunk_size, remaining_timeout,
            )
    else:
        text, model_used = call_api(model, system_prompt, masked_input, max_tokens, remaining_timeout())

    if not text:
        raise RuntimeError("FastFlowLM returned no usable text.")

    if is_prompt_mode(mode):
        text, model_used = _anti_echo_retry(text, masked_input, model, max_tokens, call_api, remaining_timeout)
        text, model_used = _rescue_prompt_quality(text, masked_input, model, max_tokens, call_api, remaining_timeout)
        if is_weak_prompt_echo(masked_input, text):
            log.warning("prompt mode still weak after retries; using deterministic prompt shape")
            text = force_prompt_shape(masked_input)

    if not text.strip():
        raise RuntimeError("FastFlowLM returned no usable text.")
    text = dict_restore(text, dict_mapping)
    return text, round(time.time() - started, 2), model_used, strategy
