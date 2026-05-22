# Sanitize

**Function:** `sanitize(html: str) -> str`

**Intent:** Return an HTML string with all script-execution vectors removed while
preserving visible text. Specifically: no `<script>` tags, no `on*=` event-handler
attributes, no `javascript:` URLs (case-insensitive).

**Why this demo:** Naive string-replace sanitizers are a classic class of
under-specified security code. The weak `"<script>" not in output` check is happily
satisfied by uppercase `<SCRIPT>`, by `onclick=` handlers, and by `javascript:` URLs.
