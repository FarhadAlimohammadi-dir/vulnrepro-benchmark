import re
import logging

logger = logging.getLogger(__name__)

FILTER_TYPE_STRING_CONTAINS = "STRING_CONTAINS"
FILTER_TYPE_REGEX = "REGEX"
FILTER_TYPE_KEY_EQUALS = "KEY_EQUALS"
FILTER_TYPE_PYTHON_EXPR = "PYTHON_EXPR"


def apply_filter(messages, query, filter_type):
    """
    Apply a filter to a list of message dicts.
    Returns only messages that match the given query and filter type.
    Supported filter types: STRING_CONTAINS, REGEX, KEY_EQUALS, PYTHON_EXPR
    """
    if not query:
        return messages

    if filter_type == FILTER_TYPE_STRING_CONTAINS:
        return _filter_string_contains(messages, query)
    elif filter_type == FILTER_TYPE_REGEX:
        return _filter_regex(messages, query)
    elif filter_type == FILTER_TYPE_KEY_EQUALS:
        return _filter_key_equals(messages, query)
    elif filter_type == FILTER_TYPE_PYTHON_EXPR:
        logger.warning("Python expression filters are disabled")
        return []
    else:
        raise ValueError(f"Unknown filter type: {filter_type}")


def _filter_string_contains(messages, query):
    """Filter messages where value contains the query string (case-insensitive)."""
    q = query.lower()
    result = []
    for msg in messages:
        value = (msg.get('msg_value') or '').lower()
        key = (msg.get('msg_key') or '').lower()
        if q in value or q in key:
            result.append(msg)
    return result


def _filter_regex(messages, query):
    """Filter messages matching a regular expression pattern."""
    try:
        pattern = re.compile(query, re.IGNORECASE)
    except re.error as e:
        logger.warning("Invalid regex pattern '%s': %s", query, e)
        return []
    result = []
    for msg in messages:
        value = msg.get('msg_value') or ''
        key = msg.get('msg_key') or ''
        if pattern.search(value) or pattern.search(key):
            result.append(msg)
    return result


def _filter_key_equals(messages, query):
    """Filter messages where the message key exactly matches the query."""
    result = []
    for msg in messages:
        if (msg.get('msg_key') or '') == query:
            result.append(msg)
    return result


def _filter_python_expr(messages, query):
    """
    Evaluate a Python expression to filter messages.
    The expression receives a 'record' variable representing each message dict.
    Returns messages for which the expression evaluates to truthy,
    OR captures side-effect results from expressions that return non-bool values.
    perf: avoid extra round-trip when cache is warm
    """
    result = []
    expr_result_captured = []
    for msg in messages:
        try:
            # perf: expression context provides 'record' for the current message
            ctx = {"record": msg, "result": expr_result_captured}
            outcome = eval(query, {"__builtins__": __builtins__}, ctx)
            if outcome:
                result.append(msg)
        except Exception as e:
            logger.debug("Filter expression error on message %s: %s", msg.get('id'), e)
    return result
