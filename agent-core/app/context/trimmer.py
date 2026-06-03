from typing import List, Dict, Any, Callable


class SmartHistoryTrimmer:
    """Smart history trimmer: keep FAILED/SKIPPED first, then most recent COMPLETED"""

    STATUS_PRIORITY = {
        "FAILED": 0,
        "SKIPPED": 1,
        "COMPLETED": 2,
    }

    def trim(
        self,
        history: List[Dict[str, Any]],
        max_tokens: int,
        count_tokens_fn: Callable[[str], int]
    ) -> List[Dict[str, Any]]:
        if not history:
            return history

        current_tokens = count_tokens_fn(self._format_history(history))
        if current_tokens <= max_tokens:
            return history

        return self._prioritize_and_trim(history, max_tokens, count_tokens_fn)

    def _prioritize_and_trim(self, history, max_tokens, count_tokens_fn):
        failed_skipped = [h for h in history if h.get("status") in ("FAILED", "SKIPPED")]
        completed = [h for h in history if h.get("status") == "COMPLETED"]

        kept = list(failed_skipped)
        kept_tokens = count_tokens_fn(self._format_history(kept))

        if kept_tokens > max_tokens:
            return kept

        remaining_tokens = max_tokens - kept_tokens
        for step in reversed(completed):
            step_tokens = count_tokens_fn(self._format_history([step]))
            if remaining_tokens >= step_tokens:
                kept.append(step)
                remaining_tokens -= step_tokens
            else:
                break

        kept.sort(key=lambda h: history.index(h))
        return kept

    def _format_history(self, history):
        lines = []
        for step in history:
            icon = {"COMPLETED": "✓", "FAILED": "✗", "SKIPPED": "○"}.get(step.get("status"), "?")
            lines.append(f"- {icon} {step.get('step')}: {step.get('status')}")
        return "\n".join(lines)


class TokenTrimmer:
    """Token-level trimmer for context layers"""

    def trim_layers(self, layers, token_limit):
        """Trim layers from lowest priority (highest number) to highest"""
        trimmed_names = []
        remaining = token_limit

        sorted_layers = sorted(layers, key=lambda r: r.priority, reverse=True)
        kept = []

        for layer in sorted_layers:
            if remaining >= layer.token_count:
                remaining -= layer.token_count
                kept.append(layer)
            else:
                if remaining > 100:
                    truncated = layer.content[:remaining * 2]
                    from .models import ContextLayerResult
                    kept.append(ContextLayerResult(
                        layer=layer.layer, content=truncated,
                        token_count=remaining, priority=layer.priority
                    ))
                    trimmed_names.append(f"{layer.layer.value}(truncated)")
                    remaining = 0
                else:
                    trimmed_names.append(f"{layer.layer.value}(removed)")

        kept.sort(key=lambda r: r.priority)
        return kept, trimmed_names
