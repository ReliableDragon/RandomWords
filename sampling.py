import math
import random


def sample_distinct_weighted(items: list[str], weights: list[int | float], k: int) -> list[str]:
  """Draws k distinct items with probability proportional to weight without replacement.

  When k exceeds the number of available items, falls back to sampling with
  replacement via random.choices, matching the behavior of GetWord.
  """
  if not items or k <= 0:
    return []

  if k > len(items):
    return random.choices(items, weights=weights, k=k)

  if k == 1:
    return random.choices(items, weights=weights, k=1)

  # If all weights are equal, standard uniform sampling is faster and exact.
  first_weight = weights[0]
  if all(w == first_weight for w in weights):
    return random.sample(items, k)

  # Efraimidis-Spirakis algorithm (A-Res):
  # Generating key = -ln(U) / w where U ~ Uniform(0, 1) yields independent
  # Exponential(w) variates. Selecting the k items with smallest keys produces
  # exact probability-proportional-to-size sampling without replacement.
  scores = []
  for item, weight in zip(items, weights):
    w = max(weight, 1e-9)
    # 1.0 - random.random() ensures u is strictly in (0.0, 1.0].
    u = 1.0 - random.random()
    key = -math.log(u) / w
    scores.append((key, item))

  scores.sort(key=lambda pair: pair[0])
  return [item for _, item in scores[:k]]


def sample_words(words: list[str], counts: dict[str, int] | None = None,
                 k: int = 1, weighted: bool = False) -> list[str]:
  """Draws k words from words, either uniformly or weighted by occurrence counts."""
  if not words or k <= 0:
    return []

  if not weighted or not counts:
    if k <= len(words):
      return random.sample(words, k)
    return [random.choice(words) for _ in range(k)]

  weights = [max(1, counts.get(w, 1)) for w in words]
  return sample_distinct_weighted(words, weights, k)
