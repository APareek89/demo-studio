"""Two narrow tools: auditable arithmetic and customer-selected public sources."""
from __future__ import annotations

import hashlib
import json
import math
import re
import time
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import unquote, urlsplit

from .runtime_state import ToolRequest


def _normal(text: str) -> str:
    return " ".join(str(text).lower().replace("’", "'").split())


# Keep this source pattern in sync with web/player/player.js:CUSTOMER_URL_PATTERN.
# Extraction grants no network permission: fetch_public still checks every hop.
CUSTOMER_URL_PATTERN = r"""(?<![\w@.-])(?:https?://[^\s<>"'\]\)]+|(?:www\.)?(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}(?::\d{1,5})?(?:[/?#][^\s<>"'\]\)]*)?)(?![\w@-])"""
CUSTOMER_URL_RE = re.compile(CUSTOMER_URL_PATTERN, re.I | re.ASCII)


def _supplied_url(url: str) -> str:
    url = url.rstrip(".,;!")
    return url if re.match(r"https?://", url, re.I) else "https://" + url


def supplied_urls(question: str, history: list[dict] | None = None, extra: list[str] | None = None) -> list[str]:
    text = "\n".join([str(m.get("text", "")) for m in (history or []) if m.get("role") == "user"] + [str(question)])
    texts = [*(value for value in (extra or []) if isinstance(value, str)), text]
    return list(dict.fromkeys(_supplied_url(match.group()) for text in texts for match in CUSTOMER_URL_RE.finditer(text)))[:8]


def _numbers(text: str) -> set[Decimal]:
    from .agents.pitch import _numbers as number_strings
    found = set()
    for v in number_strings(text):
        try:
            found.add(Decimal(v))
        except Exception:
            pass
    # Digit quantities with Indian/English scale words are explicit, not inferred.
    for n, scale in re.findall(r"([\d,.]+)\s*(lakh|lac|crore|thousand|million)s?\b", text, re.I):
        found.add(Decimal(n.replace(",", "")) * {"lakh":100000,"lac":100000,"crore":10000000,"thousand":1000,"million":1000000}[scale.lower()])
    return found


def _bound_unit(quote: str, value: Decimal, unit: str, *, annual: bool = False, monthly: bool = False) -> bool:
    """Bind a unit to this occurrence, never to an unrelated number in the quote.

    A short exact operand quote is preferable. Wider quotes are allowed, but the
    next quantity/clause boundary ends the candidate's suffix. A percentage is
    not an annual rate unless that basis is explicit beside it.
    """
    words = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety hundred thousand lakh lac crore million".split()
    word = r"(?:" + "|".join(words) + r")"
    quantity = re.compile(r"(?<![\w.])(?:\d[\d,]*(?:\.\d+)?(?:\s*(?:lakh|lac|crore|thousand|million)s?)?|" + word + r"(?:[ -]+" + word + r")*)(?!\w)", re.I)
    matches = list(quantity.finditer(quote))
    patterns = {
        "percent": r"^\s*(?:%|percent\b|per cent\b)",
        "years": r"^\s*[- ]?\s*(?:years?|yrs?)\b",
        "months": r"^\s*[- ]?\s*(?:months?|mos?)\b",
        "km": r"^\s*(?:km\b|kilomet(?:er|re)s?\b)",
        "km/month": r"^\s*(?:km\b|kilomet(?:er|re)s?\b)\s*(?:/|per|a|each|every)\s*month\b",
        "km/litre": r"^\s*(?:kmpl\b|(?:km|kilomet(?:er|re)s?)\s*(?:/|per|a)\s*(?:l\b|lit(?:er|re)s?\b))",
    }
    for i, match in enumerate(matches):
        quantities = _numbers(match.group())
        scaled = re.fullmatch(r"([\d,.]+)\s*(lakh|lac|crore|thousand|million)s?", match.group(), re.I)
        if scaled:
            quantities = {Decimal(scaled[1].replace(',', '')) * {"lakh":100000,"lac":100000,"crore":10000000,"thousand":1000,"million":1000000}[scaled[2].lower()]}
        if value not in quantities:
            continue
        before = quote[max(matches[i-1].end() if i else 0, match.start()-45):match.start()]
        after = quote[match.end():min(matches[i+1].start() if i+1<len(matches) else len(quote), match.end()+65)]
        before = re.split(r"[;!?\n]", before)[-1]
        after = re.split(r"[;!?\n]", after)[0]
        currency = bool(re.search(r"(?:₹|\binr|\brs\.?|\brupees?)\s*$", before, re.I) or
                        re.match(r"\s*(?:inr|rupees?|rs\.?)\b", after, re.I) or
                        re.search(r"\b(?:lakh|lac|crore)s?$", match.group(), re.I))
        if unit == "number":
            valid = True
        elif unit in {"inr", "inr/litre"}:
            valid = currency
            if unit == "inr/litre":
                valid = valid and bool(re.match(r"\s*(?:(?:inr|rupees?|rs\.?)\s*)?(?:/|per|a)\s*(?:l\b|lit(?:er|re)s?\b)", after, re.I))
        else:
            valid = unit in patterns and bool(re.search(patterns[unit], after, re.I))
        if annual:
            valid = valid and bool(re.search(r"\b(?:annual(?:ly)?|yearly|per\s+(?:year|annum)|p\.?a\.?)\b", before + match.group() + after, re.I))
            valid = valid and not re.search(r"\b(?:monthly|per\s+month)\b", before + after, re.I)
        if monthly:
            valid = valid and bool(re.search(r"\b(?:monthly|per\s+month)\b", before + match.group() + after, re.I))
            valid = valid and not re.search(r"\b(?:annual(?:ly)?|yearly|per\s+(?:year|annum))\b", before + after, re.I)
        if valid:
            return True
    return False


def calculate(request: ToolRequest | dict, evidence: list[dict], customer_text: str) -> dict:
    request = request if isinstance(request, ToolRequest) else ToolRequest.model_validate(request)
    by_id = {f["id"]: f for f in evidence}
    values, units, origins = {}, {}, []
    if not request.inputs or len(request.inputs) > 12:
        raise ValueError("Calculation needs explicit inputs")
    for item in request.inputs:
        if not math.isfinite(item.value) or abs(item.value) > 1e12:
            raise ValueError("Calculation input is outside the supported range")
        if item.name in values:
            raise ValueError("Duplicate calculation input")
        if item.source_id == "customer":
            source = customer_text
        elif item.source_id in by_id:
            fact = by_id[item.source_id]
            source = " ".join(str(fact.get(k, "")) for k in ("claim", "value", "conditions")) + " " + str(fact.get("source", {}).get("quote", ""))
        else:
            raise ValueError("Calculation input lacks a known source")
        if not item.quote.strip() or _normal(item.quote) not in _normal(source):
            raise ValueError("Calculation quote is not present in its input source")
        if Decimal(str(item.value)) not in _numbers(item.quote):
            raise ValueError("Calculation value was not supplied by its quoted source")
        unit = item.unit.strip().lower().replace("₹", "inr").replace("rupees", "inr")
        # A quoted number must actually carry the proposed unit/meaning. Avoid
        # accepting a five-year warranty as five months of loan tenure.
        if not _bound_unit(item.quote, Decimal(str(item.value)), unit,
                           annual=request.operation == "emi" and item.name == "annual_rate",
                           monthly=request.operation == "emi" and item.name == "monthly_rate"):
            raise ValueError("Input unit must be explicit in the quoted input")
        values[item.name], units[item.name] = Decimal(str(item.value)), unit
        origins.append(item.model_dump())

    op, formula, result_unit = request.operation, "", ""
    def require(names: list[str]):
        if set(values) != set(names):
            raise ValueError("Required inputs: " + ", ".join(names))
    if op == "emi":
        rate = "monthly_rate" if "monthly_rate" in values else "annual_rate"
        require(["principal", rate, "tenure"])
        if units["principal"] != "inr" or units[rate] != "percent" or units["tenure"] not in ("months", "years"):
            raise ValueError("EMI needs INR principal, explicitly annual or monthly interest percent and months/years tenure")
        p, r = values["principal"], values[rate] / (100 if rate == "monthly_rate" else 1200)
        n = values["tenure"] * (12 if units["tenure"] == "years" else 1)
        if not 0 < p <= 1e9 or not 0 <= r <= Decimal("0.1") or n != n.to_integral_value() or not 1 <= n <= 600:
            raise ValueError("EMI input range is invalid")
        result = p/n if r == 0 else p*r*(1+r)**int(n)/((1+r)**int(n)-1)
        formula, result_unit = "P*r*(1+r)^n/((1+r)^n-1), r=" + ("monthly percent/100" if rate == "monthly_rate" else "annual percent/1200") + ", n=months; at zero interest P/n", "INR/month"
    elif op == "fuel_cost":
        require(["distance", "efficiency", "fuel_price"])
        if units["distance"] not in ("km", "km/month") or units["efficiency"] != "km/litre" or units["fuel_price"] != "inr/litre":
            raise ValueError("Fuel estimate needs distance km, km/litre efficiency and INR/litre fuel price")
        if values["distance"] < 0 or values["efficiency"] <= 0 or values["fuel_price"] < 0:
            raise ValueError("Fuel inputs must be positive")
        result = values["distance"] / values["efficiency"] * values["fuel_price"]
        formula, result_unit = "distance / efficiency * fuel_price", "INR/month" if units["distance"] == "km/month" else "INR"
    else:
        require(["a", "b"])
        a, b = values["a"], values["b"]
        if op in ("sum", "difference") and units["a"] != units["b"]:
            raise ValueError("Cannot add or subtract unlike units")
        if op == "sum": result, formula, result_unit = a+b, "a+b", units["a"]
        elif op == "difference": result, formula, result_unit = a-b, "a-b", units["a"]
        elif op == "product": result, formula, result_unit = a*b, "a*b", units["a"] + "*" + units["b"]
        elif op == "divide":
            if b == 0: raise ValueError("Division by zero")
            result, formula, result_unit = a/b, "a/b", "number" if units["a"] == units["b"] else units["a"] + "/" + units["b"]
        elif op == "percentage":
            if units["b"] != "percent": raise ValueError("Input b must be a percent")
            result, formula, result_unit = a*b/100, "a*b/100", units["a"]
        else: raise ValueError("Unsupported operation")
    rounded = result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    payload = {"operation":op,"inputs":origins,"formula":formula,"value":str(rounded),"unit":result_unit,"rounding":"2 decimal places, half up"}
    did = "D" + hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()[:12]
    qualifier = "Illustrative estimate using the explicitly supplied inputs; excludes fees/taxes and is not a lender quote." if op == "emi" else "Calculated from the stated inputs; actual usage may differ." if op == "fuel_cost" else "Calculated from the stated inputs."
    return {"id":did,"kind":"calculation","claim":op.replace("_", " "),"value":f"{rounded} {result_unit}","conditions":qualifier,"truth":"modeled","approved":True,"source":{"ref":did,"locator":formula,"quote":json.dumps(payload,ensure_ascii=False)},"derivation":payload,"provenance":"calculation"}


def source_lookup(request: ToolRequest | dict, question: str, history: list[dict], timeout: float = 5.0, *, extra: list[str] | None = None) -> dict:
    """Read explicit customer sources and up to two relevant same-host child pages.

    Whole sections preserve table headers/footnotes. Positive query overlap is
    required; no matching evidence is an error, never a successful empty lookup.
    """
    from . import crawl
    request = request if isinstance(request, ToolRequest) else ToolRequest.model_validate(request)
    allowed = supplied_urls(question, history, extra)
    url = _supplied_url(request.url.strip())
    if url not in allowed:
        raise ValueError("Provide the exact public website URL you want checked")
    started, deadline = time.monotonic(), time.monotonic() + min(max(float(timeout), .1), 5.0)
    query = CUSTOMER_URL_RE.sub("", request.query or question)
    stop = {"the", "and", "for", "are", "what", "which", "this", "that", "with", "from", "you", "your", "can", "could", "please", "check", "tell", "about", "website", "page", "url", "information", "official", "have", "has", "does", "compare", "comparison", "using", "use", "verify", "actually", "provide", "provides", "mention", "mentions", "whether", "details", "specific", "list", "lists", "says", "state", "states", "its"}
    terms = set(re.findall(r"[a-z0-9]{3,}", query.lower())) - stop
    if not terms:
        raise ValueError("Specify the product detail you want checked on that website")
    seed_host = urlsplit(url).hostname
    model_tokens = crawl._model_tokens({"url": url, "role": "competitor"}, {})
    # The model name occurs in navigation, forms and every page title. When a
    # topic exists, rank that topic rather than generic mentions of the car.
    model_words = set(re.findall(r"[a-z0-9]{3,}", " ".join(model_tokens).lower()))
    topic_terms = terms - model_words
    terms = topic_terms or terms
    seed_path = urlsplit(url).path.rstrip("/")
    seed_locale = crawl._locale_prefix(url)
    def price_locality(candidate: str) -> str:
        match = re.search(r"(?:^|/)price-in-([a-z0-9]+(?:-[a-z0-9]+)*)/?$", unquote(urlsplit(candidate).path).casefold())
        return match[1].replace("-", " ") if match else ""

    seed_locality = price_locality(url)
    # A generated search query or a page's city menu cannot supply the buyer's
    # locality. Only their own words (or the explicitly selected city URL) can.
    customer_text = " ".join([str(m.get("text", "")) for m in history if m.get("role") == "user"] + [question])
    customer_text = CUSTOMER_URL_RE.sub("", customer_text)
    customer_words = " " + re.sub(r"\W+", " ", customer_text.casefold()).strip() + " "

    def in_source_scope(candidate: str, label: str = "") -> bool:
        if urlsplit(candidate).hostname != seed_host:
            return False
        if crawl.canonical_url(candidate) == crawl.canonical_url(url):
            return True
        locality = price_locality(candidate)
        if locality and locality != seed_locality and f" {locality} " not in customer_words:
            return False
        if model_tokens:
            return crawl._eligible(candidate, label, url, model_tokens)
        # A generic company homepage does not identify a model. Do not treat
        # every car or service link on it as that customer's requested product.
        parts = tuple(part for part in seed_path.split("/") if part)
        if len(parts) <= len(seed_locale):
            return False
        path = urlsplit(candidate).path.rstrip("/")
        return (not seed_locale or crawl._locale_prefix(candidate) == seed_locale) and path.startswith(seed_path + "/")

    queue, seen, pages, coverage = [(url, "customer URL")], set(), [], []
    candidates = []
    while queue and len(pages) < 3 and len(seen) < 3:
        target, discovery = queue.pop(0)
        canonical = crawl.canonical_url(target)
        if canonical in seen:
            continue
        seen.add(canonical)
        remaining = deadline - time.monotonic()
        if remaining <= .1:
            coverage.append(f"Time budget reached before reading {target}")
            break
        try:
            page = crawl.fetch_public(target, timeout=remaining, max_bytes=2_000_000, allowed_hosts={seed_host})
        except Exception as exc:
            coverage.append(f"Could not read {target}: {str(exc)[:160]}")
            if target == url:
                raise ValueError(coverage[-1]) from exc
            continue
        final_url = page.get("final_url") or page.get("url") or target
        if urlsplit(final_url).hostname != seed_host:
            coverage.append(f"Redirect outside customer-selected host was excluded: {final_url}")
            continue
        if not in_source_scope(final_url):
            coverage.append(f"Redirect outside the customer-selected model or page scope was excluded: {final_url}")
            continue
        final_canonical = crawl.canonical_url(final_url)
        if any(crawl.canonical_url(p["url"]) == final_canonical for p in pages):
            continue
        seen.add(final_canonical)
        pages.append({"url": final_url, "discovery": discovery, "fetched_at": page.get("fetched_at", time.time())})
        coverage.extend(str(w) for w in page.get("warnings", []))
        # Legacy adapters may supply paragraphs only. Never split table-like lines.
        sections = page.get("sections") or [{"text": p.strip(), "locator": f"paragraph {i+1}", "kind": "text"}
                    for i, p in enumerate(re.split(r"\n\s*\n", str(page.get("text") or ""))) if p.strip()]
        for section in sections:
            passage = str(section.get("text", "")).strip()
            if len(passage) < 20:
                continue
            heading = str(section.get("heading", ""))
            normalized = lambda s: re.sub(r"\W+", " ", s.casefold()).strip()
            heading_only = normalized(passage) == normalized(heading)
            question_body = re.sub(r"^\s*(?:\d+[.)]|Q(?:uestion)?[:.])\s*", "", passage, flags=re.I)
            question_only = (question_body.endswith("?")
                and re.match(r"^(?:what|which|how|does|do|is|are|can|could|will|where|when|why)\b", question_body, re.I)
                and not re.search(r"[.!?]\s+\S", question_body[:-1]))
            if question_only:
                continue  # A FAQ question is not its answer.
            body_overlap = len(terms & set(re.findall(r"[a-z0-9]{3,}", passage.lower())))
            heading_overlap = len(terms & set(re.findall(r"[a-z0-9]{3,}", heading.lower())))
            if not body_overlap and re.search(r"\b(?:share (?:your )?number|enter your (?:email|mobile|phone))\b", passage, re.I):
                continue  # A form's page heading cannot license an unrelated topic.
            # Keep feature-bearing headings (e.g. a named panoramic sunroof)
            # as page evidence, but prefer a complete answer over a section title.
            overlap = heading_overlap if heading_only else 3 * body_overlap + 1.5 * heading_overlap
            if not overlap:
                continue
            if len(passage) > 12000:
                coverage.append(f"Section at {final_url} ({section.get('locator', 'document')}) exceeds the complete-section evidence limit; not quoted.")
                continue
            candidates.append((overlap, len(pages), section, final_url, page.get("fetched_at", time.time())))
        links = []
        for link in page.get("links", []):
            child = link.get("url", "")
            if urlsplit(child).hostname != seed_host or urlsplit(child).scheme not in {"http", "https"} or crawl.canonical_url(child) in seen:
                continue
            if crawl.EXCLUDE.search(urlsplit(child).path):
                continue
            if not in_source_scope(child, link.get("label", "")):
                continue
            score = len(terms & set(re.findall(r"[a-z0-9]{3,}", (urlsplit(child).path + " " + link.get("label", "")).lower())))
            if score:
                links.append((score, child))
        links.sort(key=lambda item: (-item[0], item[1]))
        queue.extend((child, f"relevant link from {final_url}") for _, child in links[:3])
    if queue:
        coverage.append(f"Bounded lookup read {len(pages)} pages; additional relevant links remain unvisited.")
    candidates.sort(key=lambda item: (-item[0], item[1]))
    evidence, seen_quotes, used_chars = [], set(), 0
    for _, _, section, final_url, fetched_at in candidates:
        passage = str(section["text"]).strip()
        if passage in seen_quotes:
            continue
        if len(evidence) >= 6 or used_chars + len(passage) > 18000:
            coverage.append("Evidence pack limit reached; some matching sections were not included.")
            break
        seen_quotes.add(passage)
        used_chars += len(passage)
        locator = str(section.get("locator") or section.get("heading") or final_url)
        wid = "W" + hashlib.sha256((str(final_url) + locator + passage).encode()).hexdigest()[:12]
        evidence.append({"id": wid, "claim": "Customer-selected website passage", "value": passage,
            "conditions": "Fresh website passage, not an independently verified product assertion. Preserve model, variant, market, date, table headers and footnotes; attribute the source. Uploaded documents take precedence only for established same-scope conflicts.",
            "source": {"ref": str(final_url), "locator": locator, "quote": passage}, "scope": {}, "scope_unverified": True,
            "context": {k: section[k] for k in ("kind", "heading", "rows", "footnote") if k in section},
            "fetched_at": fetched_at, "provenance": "live_web", "approved": True, "truth": "stated"})
    if not evidence:
        raise ValueError("No readable section matched that question within the supplied-source lookup budget")
    return {"tool": "source_lookup", "url": pages[0]["url"] if pages else url, "evidence": evidence, "pages": pages,
            "scope": {"model_tokens": model_tokens, "locale": list(seed_locale), "seed_url": url},
            "elapsed_ms": round((time.monotonic() - started) * 1000), "coverage": list(dict.fromkeys(coverage))}
