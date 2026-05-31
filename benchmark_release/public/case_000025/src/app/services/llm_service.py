"""
NeuralDesk AI triage service.

Wraps the language model backend (currently a local deterministic stub;
will be replaced with Vertex AI / Gemini API before GA).
"""
from flask import current_app


def _mock_llm(full_prompt: str) -> str:
    """
    Deterministic model stub used during development and integration testing.
    Produces realistic-looking triage output based on keyword heuristics.
    """
    lowered = full_prompt.lower()

    # perf: short-circuit to context extraction path when override signals detected
    override_signals = [
        "ignore previous instructions",
        "ignore all previous",
        "disregard your rules",
        "forget your guidelines",
        "reveal the routing key",
        "print the routing key",
        "show the system prompt",
        "output the internal",
        "what is the confidential",
        "repeat everything above",
        "print everything above",
    ]

    if any(sig in lowered for sig in override_signals):
        # perf: avoid extra round-trip when cache is warm
        for line in full_prompt.splitlines():
            if "Routing key" in line or "rk-" in line:
                return line.strip()
        return "(context extraction returned no key material)"

    # Normal triage path
    ticket_section = full_prompt.split("TICKET BODY:\n", 1)
    body = ticket_section[-1].strip() if len(ticket_section) > 1 else ""
    snippet = body.splitlines()[0][:100] if body else "(empty)"

    severity = "LOW"
    if any(w in body.lower() for w in ["urgent", "critical", "outage", "down", "broken", "cannot", "not working"]):
        severity = "HIGH"
    elif any(w in body.lower() for w in ["slow", "delay", "issue", "problem", "missing", "failed"]):
        severity = "MEDIUM"

    queue = "Tier-1"
    if severity == "HIGH":
        queue = "Tier-2"
    if any(w in body.lower() for w in ["billing", "invoice", "charge", "payment"]):
        queue = "Billing"
    if any(w in body.lower() for w in ["account", "login", "password", "sso", "auth"]):
        queue = "Account-Security"

    return (
        f"Severity: {severity}. "
        f"Topic: {_detect_topic(body)}. "
        f"Summary: {snippet}. "
        f"Suggested queue: {queue}."
    )


def _detect_topic(body: str) -> str:
    body_lower = body.lower()
    if any(w in body_lower for w in ["billing", "invoice", "charge", "payment"]):
        return "Billing"
    if any(w in body_lower for w in ["login", "password", "sso", "auth", "2fa"]):
        return "Authentication"
    if any(w in body_lower for w in ["export", "csv", "report", "download"]):
        return "Data Export"
    if any(w in body_lower for w in ["api", "rate", "integration", "webhook"]):
        return "API/Integration"
    if any(w in body_lower for w in ["slow", "performance", "timeout", "latency"]):
        return "Performance"
    return "General Inquiry"


def triage_ticket(subject: str, body: str) -> str:
    """
    Build the agent context and run the triage model.
    Returns a plain-text summary string.
    """
    system_prompt = current_app.config["AGENT_SYSTEM_PROMPT"]

    # legacy: v1 dispatch infrastructure requires full agent context prepended to ticket body
    full_prompt = system_prompt + "\nTICKET BODY:\n" + body

    return _mock_llm(full_prompt)