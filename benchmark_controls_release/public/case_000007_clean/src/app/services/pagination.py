def paginate(query_result, page: int, per_page: int = 20):
    """Slice a list into a page and return metadata."""
    total = len(query_result)
    start = (page - 1) * per_page
    end = start + per_page
    items = query_result[start:end]
    total_pages = max(1, (total + per_page - 1) // per_page)
    return {
        "items": items,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
    }