"""SearchProvider abstraction.

Every real-time search hits one of these adapters to turn a text query
into a list of candidate URLs. The rest of the pipeline never talks to a
specific search backend directly, so a new provider can be dropped in
(or swapped for the default) without touching anything else.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class SearchHit:
    url: str
    title: str = ""
    snippet: str = ""


class SearchProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def search(self, query: str, num_results: int) -> List[SearchHit]:
        """Return web results for ``query``. Must never raise on network
        failure — return an empty list and let the caller log/record the
        failure so one bad query cannot fail the whole search."""
        raise NotImplementedError
