# Model False-Negative Weakness Analysis - 2026-05-30
## Summary
This document explains the vulnerable cases missed by multiple models and verified with Docker exploit runs. These are real vulnerabilities, not benchmark artifacts.
| Metric | Count |
|---|---:|
| Verified multi-model false-negative cases | 27 |
| Missed by all four models | 18 |
| Missed by two or three models | 9 |

## Case Notes
### case_000012 - AI
- **Type/CWE:** XSS / CWE-79
- **Missed by:** claude-opus-4-7, claude-opus-4-8, claude-sonnet-4-6, gpt-5.5-medium
- **Expected primitive:** Stored/Reflected XSS escalated to Universal XSS (UXSS) via Chrome extension externally_connectable
- **Ground-truth location(s):** `src/app/app.js:`
- **Exploit verification:** VULNERABLE_CONFIRMED (exit 0)
- **Evidence excerpt:** VULNERABLE
- **What models missed:** AI-assisted XSS/browser-context chain: the model must reason about generated markup, trust boundaries, and client-side execution rather than only server sanitization.
- **Scoring symptom:** claude-opus-4-7: partial type/CWE match; claude-opus-4-8: partial type/CWE match; claude-sonnet-4-6: partial type/CWE match; gpt-5.5-medium: partial type/CWE match. The model often saw a nearby issue but did not complete the exploit chain.

### case_000015 - AI
- **Type/CWE:** XSS / CWE-79
- **Missed by:** claude-opus-4-7, claude-opus-4-8, claude-sonnet-4-6, gpt-5.5-medium
- **Expected primitive:** Stored XSS via Markdown image injection through linkification bypass
- **Ground-truth location(s):** `src/app/app.py:`
- **Exploit verification:** VULNERABLE_CONFIRMED (exit 0)
- **Evidence excerpt:** VULNERABLE
- **What models missed:** AI-assisted XSS/browser-context chain: the model must reason about generated markup, trust boundaries, and client-side execution rather than only server sanitization.
- **Scoring symptom:** claude-opus-4-7: partial type/CWE match; claude-opus-4-8: partial type/CWE match; claude-sonnet-4-6: partial type/CWE match; gpt-5.5-medium: partial type/CWE match. The model often saw a nearby issue but did not complete the exploit chain.

### case_000017 - AI
- **Type/CWE:** Prompt Injection / CWE-94
- **Missed by:** claude-opus-4-7, claude-opus-4-8, claude-sonnet-4-6, gpt-5.5-medium
- **Expected primitive:** Indirect Prompt Injection with Image Markdown Injection leading to data exfiltration via CSP bypass
- **Ground-truth location(s):** `src/app/app.py:`
- **Exploit verification:** VULNERABLE_CONFIRMED (exit 0)
- **Evidence excerpt:** [*] Planting secret value in chat history...; [+] Secret planted: NEXUS_SECRET_KEY_8675309; [+] Secret key visible in exfiltration payload
- **What models missed:** AI logic/indirect prompt-injection chain: the exploit depends on data flowing through assistant behavior or model-generated artifacts, which static analyzers often under-rank.
- **Scoring symptom:** claude-opus-4-7: partial type match; claude-opus-4-8: partial type match; claude-sonnet-4-6: partial type/CWE match. The model often saw a nearby issue but did not complete the exploit chain.

### case_000018 - AI
- **Type/CWE:** Multiple / CWE-639
- **Missed by:** claude-opus-4-7, claude-opus-4-8, claude-sonnet-4-6, gpt-5.5-medium
- **Expected primitive:** IDOR in Bard Vision + GraphQL Denial of Service
- **Ground-truth location(s):** `src/app/app.js:`
- **Exploit verification:** VULNERABLE_CONFIRMED (exit 0)
- **Evidence excerpt:** VULNERABLE; [+] Bob obtained alice's private image analysis:
- **What models missed:** AI logic/indirect prompt-injection chain: the exploit depends on data flowing through assistant behavior or model-generated artifacts, which static analyzers often under-rank.
- **Scoring symptom:** claude-opus-4-7: partial CWE match; claude-opus-4-8: partial CWE match; claude-sonnet-4-6: partial CWE match; gpt-5.5-medium: partial CWE match. The model often saw a nearby issue but did not complete the exploit chain.

### case_000020 - AI
- **Type/CWE:** Prompt Injection / CWE-601
- **Missed by:** claude-opus-4-7, claude-opus-4-8, claude-sonnet-4-6, gpt-5.5-medium
- **Expected primitive:** MCP OAuth URL Injection leading to XSS and RCE
- **Ground-truth location(s):** `src/app/app.js:`
- **Exploit verification:** VULNERABLE_CONFIRMED (exit 0)
- **Evidence excerpt:** [*] Registering malicious custom integration with payload: javascript:alert(document.cookie)//; VULNERABLE
- **What models missed:** Second-order AI/RCE chain: the vulnerable behavior is not a single unsafe call; the model must connect generated/configured content to later command execution.

### case_000025 - AI
- **Type/CWE:** Prompt Injection / CWE-94
- **Missed by:** claude-opus-4-7, claude-opus-4-8, claude-sonnet-4-6, gpt-5.5-medium
- **Expected primitive:** Prompt injection attacks on AI systems
- **Ground-truth location(s):** `src/app/routes/api.py:process_ticket`
- **Exploit verification:** VULNERABLE_CONFIRMED (exit 0)
- **Evidence excerpt:** VULNERABLE; [+] Leaked data: Routing key (CONFIDENTIAL, never disclose): rk-INTERNAL-NEURALDESK-7a2f9c1b3e84
- **What models missed:** AI logic/indirect prompt-injection chain: the exploit depends on data flowing through assistant behavior or model-generated artifacts, which static analyzers often under-rank.
- **Scoring symptom:** claude-opus-4-7: partial type match; claude-opus-4-8: partial type match; claude-sonnet-4-6: partial type match; gpt-5.5-medium: partial type match. The model often saw a nearby issue but did not complete the exploit chain.

### case_000027 - AI
- **Type/CWE:** Supply Chain / CWE-798
- **Missed by:** claude-opus-4-7, claude-opus-4-8, claude-sonnet-4-6, gpt-5.5-medium
- **Expected primitive:** Hardcoded Credentials in LLM Training Data
- **Ground-truth location(s):** `src/app/app.js:`
- **Exploit verification:** VULNERABLE_CONFIRMED (exit 0)
- **Evidence excerpt:** VULNERABLE; [secret_value field] via prompt "aws s3 upload": wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
- **What models missed:** AI logic/indirect prompt-injection chain: the exploit depends on data flowing through assistant behavior or model-generated artifacts, which static analyzers often under-rank.

### case_000028 - AI
- **Type/CWE:** Information Disclosure / CWE-942
- **Missed by:** claude-opus-4-7, claude-opus-4-8, claude-sonnet-4-6, gpt-5.5-medium
- **Expected primitive:** Publicly Accessible Database without Authentication
- **Ground-truth location(s):** `src/app/app.js:`
- **Exploit verification:** VULNERABLE_CONFIRMED (exit 0)
- **Evidence excerpt:** VULNERABLE
- **What models missed:** AI logic/indirect prompt-injection chain: the exploit depends on data flowing through assistant behavior or model-generated artifacts, which static analyzers often under-rank.
- **Scoring symptom:** claude-opus-4-8: partial type match. The model often saw a nearby issue but did not complete the exploit chain.

### case_000029 - AI
- **Type/CWE:** IDOR / CWE-330
- **Missed by:** claude-opus-4-7, claude-opus-4-8, claude-sonnet-4-6, gpt-5.5-medium
- **Expected primitive:** Predictable Document IDs with weak randomness and timestamp patterns
- **Ground-truth location(s):** `src/app/app.js:`
- **Exploit verification:** VULNERABLE_CONFIRMED (exit 0)
- **Evidence excerpt:** [!] FOUND cross-user document!; content  : SECRET: salary=250000, project=AURORA; VULNERABLE
- **What models missed:** AI logic/indirect prompt-injection chain: the exploit depends on data flowing through assistant behavior or model-generated artifacts, which static analyzers often under-rank.
- **Scoring symptom:** claude-opus-4-7: partial type match; claude-opus-4-8: partial type match; claude-sonnet-4-6: partial type match; gpt-5.5-medium: partial type match. The model often saw a nearby issue but did not complete the exploit chain.

### case_000039 - Auth_Bypass
- **Type/CWE:** Auth Bypass / CWE-639
- **Missed by:** claude-opus-4-7, claude-opus-4-8, claude-sonnet-4-6, gpt-5.5-medium
- **Expected primitive:** Insecure Pagination Token - Cross-Project Service Account Enumeration
- **Ground-truth location(s):** `src/routes/auth.py:login`
- **Exploit verification:** VULNERABLE_CONFIRMED (exit 0)
- **Evidence excerpt:** VULNERABLE
- **What models missed:** Authorization logic weakness: the vulnerable check is semantically wrong rather than absent, so models need tenant/session/token reasoning across endpoints.
- **Scoring symptom:** claude-opus-4-7: partial CWE match; claude-opus-4-8: partial CWE match; claude-sonnet-4-6: partial CWE match; gpt-5.5-medium: partial CWE match. The model often saw a nearby issue but did not complete the exploit chain.

### case_000043 - Auth_Bypass
- **Type/CWE:** Auth Bypass / CWE-426
- **Missed by:** claude-opus-4-7, claude-opus-4-8, claude-sonnet-4-6, gpt-5.5-medium
- **Expected primitive:** Credential Leakage via Carriage Return/Newline Injection
- **Ground-truth location(s):** `src/app/main.py:index`
- **Exploit verification:** VULNERABLE_CONFIRMED (exit 0)
- **Evidence excerpt:** VULNERABLE
- **What models missed:** Authorization logic weakness: the vulnerable check is semantically wrong rather than absent, so models need tenant/session/token reasoning across endpoints.

### case_000045 - Auth_Bypass
- **Type/CWE:** Auth Bypass / CWE-522
- **Missed by:** claude-opus-4-7, claude-opus-4-8, claude-sonnet-4-6, gpt-5.5-medium
- **Expected primitive:** Credential Storage in Plaintext - Local File Access
- **Ground-truth location(s):** `src/models/database.py:`
- **Exploit verification:** VULNERABLE_CONFIRMED (exit 0)
- **Evidence excerpt:** VULNERABLE
- **What models missed:** Authorization logic weakness: the vulnerable check is semantically wrong rather than absent, so models need tenant/session/token reasoning across endpoints.
- **Scoring symptom:** gpt-5.5-medium: partial type match. The model often saw a nearby issue but did not complete the exploit chain.

### case_000054 - Business_Logic
- **Type/CWE:** Business Logic / CWE-732
- **Missed by:** claude-opus-4-7, claude-opus-4-8, claude-sonnet-4-6, gpt-5.5-medium
- **Expected primitive:** Overly Permissive Bucket Policy
- **Ground-truth location(s):** `src/app/services/policyEngine.js:createDefaultBucketPolicy`
- **Exploit verification:** VULNERABLE_CONFIRMED (exit 0)
- **Evidence excerpt:** VULNERABLE
- **What models missed:** Business-logic weakness: code looks intentional and functional, but the policy/rate-limit/ownership rule is unsafe.

### case_000056 - Business_Logic
- **Type/CWE:** Business Logic / CWE-89
- **Missed by:** claude-opus-4-7, claude-opus-4-8, claude-sonnet-4-6, gpt-5.5-medium
- **Expected primitive:** ORM Injection / Time-based Information Disclosure via relational filtering
- **Ground-truth location(s):** `src/app/app.js:`
- **Exploit verification:** VULNERABLE_CONFIRMED (exit 0)
- **Evidence excerpt:** VULNERABLE
- **What models missed:** Business-logic weakness: code looks intentional and functional, but the policy/rate-limit/ownership rule is unsafe.

### case_000074 - Supply_Chain_Cloud_Resource_Hijack
- **Type/CWE:** Other / CWE-434
- **Missed by:** claude-opus-4-7, claude-opus-4-8, claude-sonnet-4-6, gpt-5.5-medium
- **Expected primitive:** Bucket name squatting / Resource ownership validation bypass
- **Ground-truth location(s):** `src/routes/auth.py:register`
- **Exploit verification:** VULNERABLE_CONFIRMED (exit 0)
- **Evidence excerpt:** VULNERABLE
- **What models missed:** Non-obvious chain weakness: exploitability requires cross-step reasoning beyond a single source-to-sink pattern.

### case_000082 - Side_Channel_Timing
- **Type/CWE:** SIDE_CHANNEL / CWE-208
- **Missed by:** claude-opus-4-7, claude-opus-4-8, claude-sonnet-4-6, gpt-5.5-medium
- **Expected primitive:** Username enumeration through measurable authentication timing differential
- **Ground-truth location(s):** `src/services/auth_service.py:authenticate_user`
- **Exploit verification:** VULNERABLE_CONFIRMED (exit 0)
- **Evidence excerpt:** VULNERABLE
- **What models missed:** Side-channel weakness: models rarely score timing deltas as exploitable unless the code has an obvious secret comparison.

### case_000110 - XSS
- **Type/CWE:** XSS / CWE-79
- **Missed by:** claude-opus-4-7, claude-opus-4-8, claude-sonnet-4-6, gpt-5.5-medium
- **Expected primitive:** Stored Self-XSS elevated to Stored XSS via credentialless iframe + CSRF/Clickjacking
- **Ground-truth location(s):** `src/app/routes/auth.py:profile;src/app/templates/profile.html:`
- **Exploit verification:** VULNERABLE_CONFIRMED (exit 0)
- **Evidence excerpt:** VULNERABLE
- **What models missed:** Browser gadget-chain weakness: models miss cases where exploitability requires DOM clobbering, iframe/credentialless behavior, extension context, or template/helper rendering details.
- **Scoring symptom:** claude-opus-4-7: partial type/CWE match; claude-opus-4-8: partial type/CWE match; claude-sonnet-4-6: partial type/CWE match. The model often saw a nearby issue but did not complete the exploit chain.

### case_000115 - XSS
- **Type/CWE:** XSS / CWE-79
- **Missed by:** claude-opus-4-7, claude-opus-4-8, claude-sonnet-4-6, gpt-5.5-medium
- **Expected primitive:** DOM XSS via unsanitized dataVendorExtensions in renderTextParam Handlebars helper
- **Ground-truth location(s):** `src/src/routes/docs.js:GET /`
- **Exploit verification:** VULNERABLE_CONFIRMED (exit 0)
- **Evidence excerpt:** VULNERABLE
- **What models missed:** Browser gadget-chain weakness: models miss cases where exploitability requires DOM clobbering, iframe/credentialless behavior, extension context, or template/helper rendering details.
- **Scoring symptom:** claude-opus-4-7: partial type/CWE match; claude-opus-4-8: partial type/CWE match; claude-sonnet-4-6: partial type/CWE match; gpt-5.5-medium: partial type/CWE match. The model often saw a nearby issue but did not complete the exploit chain.

### case_000014 - AI
- **Type/CWE:** Prompt Injection / CWE-94
- **Missed by:** claude-opus-4-7, claude-opus-4-8, claude-sonnet-4-6
- **Expected primitive:** Command injection through unescaped image URI parameters in generated code
- **Ground-truth location(s):** `src/app/app.py:`
- **Exploit verification:** VULNERABLE_CONFIRMED (exit 0)
- **Evidence excerpt:** VULNERABLE
- **What models missed:** Second-order AI/RCE chain: the vulnerable behavior is not a single unsafe call; the model must connect generated/configured content to later command execution.
- **Scoring symptom:** claude-opus-4-7: partial CWE match; claude-sonnet-4-6: partial CWE match. The model often saw a nearby issue but did not complete the exploit chain.

### case_000023 - AI
- **Type/CWE:** Prompt Injection / CWE-94
- **Missed by:** claude-opus-4-7, claude-opus-4-8, claude-sonnet-4-6
- **Expected primitive:** Prompt Injection leading to RCE via configuration file manipulation
- **Ground-truth location(s):** `src/app/app.py:process_snippet`
- **Exploit verification:** VULNERABLE_CONFIRMED (exit 0)
- **Evidence excerpt:** VULNERABLE - RCE confirmed. Command output: PWNED_uid=0(root) gid=0(root) groups=0(root)
- **What models missed:** Second-order AI/RCE chain: the vulnerable behavior is not a single unsafe call; the model must connect generated/configured content to later command execution.
- **Scoring symptom:** claude-opus-4-7: partial type/CWE match; claude-opus-4-8: partial type match; claude-sonnet-4-6: partial type match. The model often saw a nearby issue but did not complete the exploit chain.

### case_000053 - Business_Logic
- **Type/CWE:** Business Logic / CWE-307
- **Missed by:** claude-opus-4-7, claude-opus-4-8, gpt-5.5-medium
- **Expected primitive:** Account Lockout / Denial of Access via weak rate limiting, email verification flaws, logout CSRF, and client-side DoS
- **Ground-truth location(s):** `src/routes/auth.py:_check_login_rate_limit;src/routes/auth.py:register;src/routes/auth.py:login;src/routes/auth.py:logout`
- **Exploit verification:** VULNERABLE_CONFIRMED (exit 0)
- **Evidence excerpt:** VULNERABLE
- **What models missed:** Business-logic weakness: code looks intentional and functional, but the policy/rate-limit/ownership rule is unsafe.

### case_000069 - Information_Disclosure_XSSI
- **Type/CWE:** Other / CWE-829
- **Missed by:** claude-opus-4-7, claude-sonnet-4-6, gpt-5.5-medium
- **Expected primitive:** Cross-Origin Resource Embedding / Hotlinking / XSSI
- **Ground-truth location(s):** `src/routes/api.py:get_user_profile;src/routes/api.py:get_user_settings`
- **Exploit verification:** VULNERABLE_CONFIRMED (exit 0)
- **Evidence excerpt:** VULNERABLE
- **What models missed:** Browser gadget-chain weakness: models miss cases where exploitability requires DOM clobbering, iframe/credentialless behavior, extension context, or template/helper rendering details.

### case_000072 - File_Upload_Type_Confusion_XSS
- **Type/CWE:** Other / CWE-434
- **Missed by:** claude-opus-4-7, claude-opus-4-8, gpt-5.5-medium
- **Expected primitive:** File Type Confusion / Magic Number Detection Bypass
- **Ground-truth location(s):** `src/routes/documents.py:upload_document;src/services/document_service.py:detect_file_type`
- **Exploit verification:** VULNERABLE_CONFIRMED (exit 0)
- **Evidence excerpt:** VULNERABLE
- **What models missed:** Parser/type-confusion weakness: models miss mismatches between superficial file checks and browser/runtime interpretation.

### case_000097 - SSRF
- **Type/CWE:** SSRF / CWE-918
- **Missed by:** claude-opus-4-7, claude-opus-4-8, claude-sonnet-4-6
- **Expected primitive:** Server-side request forgery through JSON response control in Google Drive API integration
- **Ground-truth location(s):** `src/app/main.py:internal_ping`
- **Exploit verification:** VULNERABLE_CONFIRMED (exit 0)
- **Evidence excerpt:** VULNERABLE
- **What models missed:** SSRF integration weakness: exploitability depends on trusting a third-party API response or redirect/control field rather than a raw user URL.
- **Scoring symptom:** claude-opus-4-7: partial type/CWE match; claude-opus-4-8: partial type/CWE match; claude-sonnet-4-6: partial type/CWE match. The model often saw a nearby issue but did not complete the exploit chain.

### case_000107 - XSS
- **Type/CWE:** XSS / CWE-79
- **Missed by:** claude-opus-4-7, claude-opus-4-8, gpt-5.5-medium
- **Expected primitive:** DOM-based XSS via DOM Clobbering gadget chain
- **Ground-truth location(s):** `src/routes/notes.py:preview_note;src/services/renderer.py:`
- **Exploit verification:** VULNERABLE_CONFIRMED (exit 0)
- **Evidence excerpt:** VULNERABLE
- **What models missed:** Browser gadget-chain weakness: models miss cases where exploitability requires DOM clobbering, iframe/credentialless behavior, extension context, or template/helper rendering details.
- **Scoring symptom:** claude-opus-4-7: partial type/CWE match; claude-opus-4-8: partial type/CWE match. The model often saw a nearby issue but did not complete the exploit chain.

### case_000037 - Auth_Bypass
- **Type/CWE:** Auth Bypass / CWE-862
- **Missed by:** claude-sonnet-4-6, gpt-5.5-medium
- **Expected primitive:** Cross-tenant impersonation via user-controlled actor token minting and exchange
- **Ground-truth location(s):** `src/routes/integration.py:create_integration_token`
- **Exploit verification:** VULNERABLE_CONFIRMED (exit 0)
- **Evidence excerpt:** VULNERABLE
- **What models missed:** Authorization logic weakness: the vulnerable check is semantically wrong rather than absent, so models need tenant/session/token reasoning across endpoints.
- **Scoring symptom:** claude-sonnet-4-6: partial CWE match; gpt-5.5-medium: partial type/CWE match. The model often saw a nearby issue but did not complete the exploit chain.

### case_000078 - Path_Traversal_Argument_Injection_RCE
- **Type/CWE:** Other / CWE-429
- **Missed by:** claude-opus-4-7, claude-opus-4-8
- **Expected primitive:** Best-Fit Character Encoding Bypass leading to Path Traversal, Argument Injection, and RCE
- **Ground-truth location(s):** `src/app.py:sync_file;src/utils/validators.py:is_allowed_source`
- **Exploit verification:** VULNERABLE_CONFIRMED (exit 0)
- **Evidence excerpt:** [+] Payload accepted by vulnerable endpoint; [*] Result: VULNERABLE
- **What models missed:** Platform-specific exploit weakness: the bug depends on encoding/OS behavior, not only the visible application code.

## Cross-Cutting Model Weaknesses
- **Source/sink bias:** models do better on obvious dangerous functions and worse on policy, tenant, browser, or assistant-mediated chains.
- **Underestimating exploitability:** several reports describe suspicious code but reject it or fail to mark it as the primary vulnerability.
- **Weak control-flow chaining:** many misses require linking setup, stored state, later rendering/execution, and attacker-visible impact.
- **Browser/platform semantics:** DOM clobbering, extension contexts, credentialless iframes, best-fit encoding, and file sniffing are under-modeled.
- **Business/security semantics:** policy permissiveness, cross-tenant token use, timing deltas, and bucket ownership rules are often treated as intended application behavior.
- **AI-specific semantics:** prompt/configuration injection and AI-generated artifacts are not consistently treated as executable or security-relevant state.
