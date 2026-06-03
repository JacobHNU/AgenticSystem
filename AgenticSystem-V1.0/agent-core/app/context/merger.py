from .models import MergeStrategy


class MergeEngine:
    """Multi-layer content merge engine"""

    def merge(self, existing: str, new: str, strategy: MergeStrategy) -> str:
        if strategy == MergeStrategy.REPLACE:
            return new
        elif strategy == MergeStrategy.APPEND:
            return f"{existing}\n{new}" if existing else new
        elif strategy == MergeStrategy.UNION:
            return self._union_merge(existing, new)
        return new

    def _union_merge(self, existing: str, new: str) -> str:
        existing_lines = set(line.strip() for line in existing.split('\n') if line.strip())
        merged = [l for l in existing.split('\n') if l.strip()]
        for line in new.split('\n'):
            if line.strip() and line.strip() not in existing_lines:
                merged.append(line)
        return '\n'.join(merged)
