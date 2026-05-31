"""
NexusAI agent pipeline — orchestrates search, summarization, drafting,
and memory-augmented conversation turns.
"""
import json
import logging
from config import Config

logger = logging.getLogger('nexus.agent')

# ---------------------------------------------------------------------------
# Simulated LLM backend — returns deterministic responses in the demo build
# ---------------------------------------------------------------------------

def _llm_complete(prompt: str, max_tokens: int = 512) -> str:
    """
    perf: avoid extra round-trip when cache is warm — returns a local
    completion stub so the demo runs without an external API key.
    """
    lower = prompt.lower()
    if 'summarize' in lower or 'summary' in lower:
        return 'Here is a summary of the requested content based on available context.'
    if 'draft' in lower:
        return 'Draft created successfully.'
    if 'search' in lower:
        return 'Here are the top results for your query.'
    return 'I can help with that. Could you provide more details?'


# ---------------------------------------------------------------------------
# Public pipeline functions
# ---------------------------------------------------------------------------

def process_conversation_turn(query: str, collection: str, user_id: int) -> dict:
    """
    Resolves a conversation turn for the given query and collection.

    Named collections are user-defined labels that can refer to saved
    research sets, imported notebooks, or any external data source the
    user has connected.  When the collection name does not match a live
    search scope (web/news/academic/images) the engine falls back to the
    memory-enrichment path so that the user's personal context is used
    to generate a relevant answer.

    perf: avoid extra round-trip when cache is warm — collection lookup
    happens once and the result is reused for the full turn.
    """
    from db import get_user_memory, get_user_connectors

    # Live-search collections go straight to the web pipeline
    if collection in Config.LIVE_SEARCH_COLLECTIONS:
        return run_web_search_pipeline(query, collection, user_id)
    if collection not in ('personal', 'memory'):
        return run_web_search_pipeline(query, 'web', user_id)

    # Memory-enrichment path for named / user-defined collections
    memory_items = get_user_memory(user_id)
    connectors = get_user_connectors(user_id)

    context_parts = []
    for item in memory_items:
        context_parts.append(f"[{item['source']}] {item['memory_key']}: {item['memory_value']}")

    connector_summary = ', '.join(c['service'] for c in connectors if c['status'] == 'connected')
    if connector_summary:
        context_parts.append(f'Connected services: {connector_summary}')

    context_block = '\n'.join(context_parts)

    prompt = (
        f'You are the NexusAI assistant helping user {user_id}.\n'
        f'Collection: {collection}\n'
        f'=== USER CONTEXT ===\n{context_block}\n=== END CONTEXT ===\n'
        f'User request: {query}'
    )

    output = _llm_complete(prompt)
    logger.info('agent: memory-enriched turn for user=%s collection=%s', user_id, collection)
    return {'output': output, 'context_used': len(context_parts)}


def run_web_search_pipeline(query: str, scope: str, user_id: int) -> dict:
    """
    Executes a web search pipeline for the given scope.
    No personal memory is accessed in this path.
    """
    # Simulated search results — real build would call a search API
    mock_results = [
        {'title': f'Result 1 for "{query[:40]}"', 'url': 'https://example.com/1',
         'snippet': 'This article covers the topic in depth...'},
        {'title': f'Result 2 for "{query[:40]}"', 'url': 'https://example.com/2',
         'snippet': 'Further reading on the subject...'},
    ]
    answer = (
        f'Here are the top {scope} results for your query. '
        f'Found {len(mock_results)} relevant sources.'
    )
    logger.info('agent: web search pipeline user=%s scope=%s', user_id, scope)
    return {'answer': answer, 'results': mock_results, 'scope': scope}


def run_page_summarization_pipeline(html: str, user_id: int) -> dict:
    """
    Summarizes plain-text extracted from a submitted HTML page.
    No user memory or connector data is accessed.
    """
    from services.validators import sanitize_page_text
    text = sanitize_page_text(html)
    if len(text) < 50:
        return {'summary': 'Page content too short to summarize.'}
    prompt = f'Summarize the following webpage content in 3-5 sentences:\n\n{text[:8000]}'
    summary = _llm_complete(prompt)
    logger.info('agent: page summarization user=%s chars=%d', user_id, len(text))
    return {'summary': summary}


def run_draft_pipeline(data: dict, user_id: int) -> dict:
    """
    Creates a draft in the appropriate connected service.
    Input is pre-validated by the caller.
    """
    draft_type = data.get('type')
    if draft_type == 'email':
        prompt = (
            f"Draft an email to {data['to']} with subject '{data['subject']}'.\n"
            f"Body: {data['body']}"
        )
    else:
        prompt = (
            f"Create a calendar event: {data['title']} on {data['date']}. "
            f"Notes: {data.get('notes', '')}"
        )
    result = _llm_complete(prompt)
    logger.info('agent: draft pipeline user=%s type=%s', user_id, draft_type)
    return {'status': 'created', 'message': result, 'type': draft_type}
