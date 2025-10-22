"""Word Error Rate (WER) calculation utilities for audio quality validation."""

from dataclasses import dataclass
import re
from typing import Any


@dataclass
class WERResult:
    """Result of WER calculation."""

    wer: float
    substitutions: int
    insertions: int
    deletions: int
    total_words: int
    reference_words: int
    hypothesis_words: int


class WERCalculator:
    """Calculate Word Error Rate between reference and hypothesis."""

    def __init__(self):
        self.normalize_pattern = re.compile(r"[^\w\s]")

    def normalize_text(self, text: str) -> str:
        """Normalize text for WER calculation."""
        # Convert to lowercase
        text = text.lower()

        # Remove punctuation
        text = self.normalize_pattern.sub("", text)

        # Normalize whitespace
        text = " ".join(text.split())

        return text

    def tokenize(self, text: str) -> list[str]:
        """Tokenize text into words."""
        normalized = self.normalize_text(text)
        return normalized.split() if normalized else []

    def calculate_wer(self, reference: str, hypothesis: str) -> WERResult:
        """Calculate Word Error Rate between reference and hypothesis.

        Args:
            reference: Ground truth text
            hypothesis: Predicted text

        Returns:
            WERResult with WER percentage and detailed metrics
        """
        # Tokenize both texts
        ref_tokens = self.tokenize(reference)
        hyp_tokens = self.tokenize(hypothesis)

        # Calculate edit distance using dynamic programming
        substitutions, insertions, deletions = self._calculate_edit_distance(
            ref_tokens, hyp_tokens
        )

        # Calculate WER
        total_errors = substitutions + insertions + deletions
        total_words = len(ref_tokens)
        wer = (total_errors / total_words * 100) if total_words > 0 else 0.0

        return WERResult(
            wer=wer,
            substitutions=substitutions,
            insertions=insertions,
            deletions=deletions,
            total_words=total_words,
            reference_words=len(ref_tokens),
            hypothesis_words=len(hyp_tokens),
        )

    def _calculate_edit_distance(
        self, ref_tokens: list[str], hyp_tokens: list[str]
    ) -> tuple[int, int, int]:
        """Calculate edit distance between token sequences.

        Returns:
            Tuple of (substitutions, insertions, deletions)
        """
        m, n = len(ref_tokens), len(hyp_tokens)

        # Create DP table
        dp = [[0] * (n + 1) for _ in range(m + 1)]

        # Initialize base cases
        for i in range(m + 1):
            dp[i][0] = i  # deletions
        for j in range(n + 1):
            dp[0][j] = j  # insertions

        # Fill DP table
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if ref_tokens[i - 1] == hyp_tokens[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1]
                else:
                    dp[i][j] = 1 + min(
                        dp[i - 1][j],  # deletion
                        dp[i][j - 1],  # insertion
                        dp[i - 1][j - 1],  # substitution
                    )

        # Backtrack to count operations
        substitutions = insertions = deletions = 0
        i, j = m, n

        while i > 0 or j > 0:
            if i > 0 and j > 0 and ref_tokens[i - 1] == hyp_tokens[j - 1]:
                i -= 1
                j -= 1
            elif i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + 1:
                substitutions += 1
                i -= 1
                j -= 1
            elif i > 0 and dp[i][j] == dp[i - 1][j] + 1:
                deletions += 1
                i -= 1
            else:
                insertions += 1
                j -= 1

        return substitutions, insertions, deletions

    def calculate_improvement(self, baseline_wer: float, enhanced_wer: float) -> float:
        """Calculate relative improvement percentage.

        Args:
            baseline_wer: WER without enhancement
            enhanced_wer: WER with enhancement

        Returns:
            Improvement percentage (positive = improvement, negative = degradation)
        """
        if baseline_wer == 0:
            return 0.0  # No baseline to compare against

        improvement = ((baseline_wer - enhanced_wer) / baseline_wer) * 100
        return improvement

    def calculate_confidence_interval(
        self, wer_values: list[float], confidence: float = 0.95
    ) -> tuple[float, float]:
        """Calculate confidence interval for WER values.

        Args:
            wer_values: List of WER measurements
            confidence: Confidence level (0.95 for 95% CI)

        Returns:
            Tuple of (lower_bound, upper_bound)
        """
        if not wer_values:
            return 0.0, 0.0

        import statistics

        mean_wer = statistics.mean(wer_values)
        if len(wer_values) < 2:
            return mean_wer, mean_wer

        # Calculate standard error
        std_dev = statistics.stdev(wer_values)
        std_error = std_dev / (len(wer_values) ** 0.5)

        # Calculate confidence interval (simplified for normal distribution)
        # For more accurate CI, use t-distribution for small samples
        z_score = 1.96 if confidence == 0.95 else 2.576  # 95% or 99% CI

        margin_error = z_score * std_error
        lower_bound = max(0, mean_wer - margin_error)
        upper_bound = mean_wer + margin_error

        return lower_bound, upper_bound


class QualityMetricsCollector:
    """Collect and analyze quality metrics for audio enhancement."""

    def __init__(self):
        self.wer_calculator = WERCalculator()
        self.metrics: list[dict[str, Any]] = []

    def add_measurement(
        self,
        reference: str,
        hypothesis: str,
        sample_metadata: dict[str, Any] | None = None,
    ):
        """Add a quality measurement."""
        wer_result = self.wer_calculator.calculate_wer(reference, hypothesis)

        measurement = {
            "reference": reference,
            "hypothesis": hypothesis,
            "wer": wer_result.wer,
            "substitutions": wer_result.substitutions,
            "insertions": wer_result.insertions,
            "deletions": wer_result.deletions,
            "total_words": wer_result.total_words,
            "reference_words": wer_result.reference_words,
            "hypothesis_words": wer_result.hypothesis_words,
            "metadata": sample_metadata or {},
        }

        self.metrics.append(measurement)

    def get_summary(self) -> dict[str, Any]:
        """Get summary statistics of quality metrics."""
        if not self.metrics:
            return {"count": 0}

        wer_values = [m["wer"] for m in self.metrics]

        import statistics

        summary = {
            "count": len(self.metrics),
            "mean_wer": statistics.mean(wer_values),
            "median_wer": statistics.median(wer_values),
            "min_wer": min(wer_values),
            "max_wer": max(wer_values),
            "std_wer": statistics.stdev(wer_values) if len(wer_values) > 1 else 0.0,
        }

        # Calculate confidence interval
        ci_lower, ci_upper = self.wer_calculator.calculate_confidence_interval(
            wer_values
        )
        summary["wer_ci_95_lower"] = ci_lower
        summary["wer_ci_95_upper"] = ci_upper

        return summary

    def compare_enhancement(
        self,
        baseline_metrics: list[dict[str, Any]],
        enhanced_metrics: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Compare baseline vs enhanced quality metrics."""
        if not baseline_metrics or not enhanced_metrics:
            return {"error": "Insufficient data for comparison"}

        baseline_wers = [m["wer"] for m in baseline_metrics]
        enhanced_wers = [m["wer"] for m in enhanced_metrics]

        baseline_mean = sum(baseline_wers) / len(baseline_wers)
        enhanced_mean = sum(enhanced_wers) / len(enhanced_wers)

        improvement = self.wer_calculator.calculate_improvement(
            baseline_mean, enhanced_mean
        )

        return {
            "baseline_mean_wer": baseline_mean,
            "enhanced_mean_wer": enhanced_mean,
            "improvement_percentage": improvement,
            "baseline_count": len(baseline_metrics),
            "enhanced_count": len(enhanced_metrics),
            "improvement_significant": abs(improvement) > 5.0,  # 5% threshold
        }

    def reset(self):
        """Reset all collected metrics."""
        self.metrics.clear()


# Convenience functions for common use cases
def calculate_wer_simple(reference: str, hypothesis: str) -> float:
    """Simple WER calculation returning just the percentage."""
    calculator = WERCalculator()
    result = calculator.calculate_wer(reference, hypothesis)
    return result.wer


def calculate_improvement_simple(baseline_wer: float, enhanced_wer: float) -> float:
    """Simple improvement calculation."""
    calculator = WERCalculator()
    return calculator.calculate_improvement(baseline_wer, enhanced_wer)


def create_quality_collector() -> QualityMetricsCollector:
    """Create a new quality metrics collector."""
    return QualityMetricsCollector()


# Example usage and testing
if __name__ == "__main__":
    # Example usage
    calculator = WERCalculator()

    # Test with example texts
    reference = "Hello world this is a test"
    hypothesis = "Hello world this is test"

    result = calculator.calculate_wer(reference, hypothesis)
    print(f"WER: {result.wer:.2f}%")
    print(f"Substitutions: {result.substitutions}")
    print(f"Insertions: {result.insertions}")
    print(f"Deletions: {result.deletions}")

    # Test improvement calculation
    baseline_wer = 15.0
    enhanced_wer = 12.0
    improvement = calculator.calculate_improvement(baseline_wer, enhanced_wer)
    print(f"Improvement: {improvement:.2f}%")
