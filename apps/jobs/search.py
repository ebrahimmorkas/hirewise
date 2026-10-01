"""Database-aware job search.

On PostgreSQL we use real full-text search: a weighted ``SearchVector`` (title
matters more than description), ``websearch`` query syntax (``"exact phrase"``,
``-exclude``, ``or``) and ``SearchRank`` for relevance ordering. On other
databases (SQLite in development) we fall back to case-insensitive substring
matching so the feature still works without PostgreSQL.
"""

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db import connection
from django.db.models import Q, QuerySet


def uses_full_text_search() -> bool:
    return connection.vendor == "postgresql"


def search_jobs(queryset: QuerySet, query: str) -> QuerySet:
    query = query.strip()
    if not query:
        return queryset

    if uses_full_text_search():
        vector = (
            SearchVector("title", weight="A", config="english")
            + SearchVector("company__name", weight="B", config="english")
            + SearchVector("description", weight="C", config="english")
        )
        search_query = SearchQuery(query, search_type="websearch", config="english")
        skill_match = Q(skills__name__iexact=query)
        # Match with the @@ operator; SearchRank is only used for ordering because
        # ts_rank ignores negated terms ("-analyst") and would let excluded rows through.
        ranked = queryset.annotate(search=vector, rank=SearchRank(vector, search_query))
        return ranked.filter(Q(search=search_query) | skill_match).distinct()

    terms = [term for term in query.split() if term]
    condition = Q()
    for term in terms:
        condition &= (
            Q(title__icontains=term)
            | Q(description__icontains=term)
            | Q(company__name__icontains=term)
            | Q(skills__name__iexact=term)
        )
    return queryset.filter(condition).distinct()
