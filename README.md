# FitFindr

A multi-tool AI agent that helps users find secondhand fashion pieces and figure out how to wear them. Given a natural language query, FitFindr searches mock thrift listings, suggests outfit combinations against the user's wardrobe, and generates a shareable fit card caption — all in one flow.

---

## Setup

```bash
python -m venv .venv
source .venv/bin/activate       # Mac/Linux
pip install -r requirements.txt
```

Create a `.env` file in the repo root:
```
GROQ_API_KEY=your_key_here
```

Run the UI:
```bash
python app.py
```

Run the CLI test:
```bash
python agent.py
```

Run tests:
```bash
pytest tests/
```

---

## Tool Inventory

### `search_listings(description, size, max_price)`

**Purpose:** Searches the mock secondhand listings dataset and returns items ranked by keyword relevance.

**Inputs:**
- `description` (str) — natural language keywords (e.g., `"vintage graphic tee"`)
- `size` (str | None) — size label to filter by; case-insensitive substring match so `"M"` matches `"S/M"`. Pass `None` to skip.
- `max_price` (float | None) — maximum price inclusive in USD. Pass `None` to skip.

**Output:** `list[dict]` — list of matching listing dicts sorted by relevance score (highest first). Each dict contains: `id`, `title`, `description`, `category`, `style_tags` (list), `size`, `condition`, `price` (float), `colors` (list), `brand` (str | None), `platform`. Returns `[]` if nothing matches — never raises.

---

### `suggest_outfit(new_item, wardrobe)`

**Purpose:** Given the thrifted item and the user's wardrobe, calls the LLM to suggest 1–2 complete outfit combinations. Falls back to general styling advice if the wardrobe is empty.

**Inputs:**
- `new_item` (dict) — a listing dict from `search_listings`
- `wardrobe` (dict) — wardrobe dict with an `"items"` key (list of wardrobe item dicts). Each item has `id`, `name`, `category`, `colors` (list), `style_tags` (list), `notes` (str | None). May be empty.

**Output:** `str` — outfit suggestion text. If wardrobe is empty, contains general styling advice. If the LLM call fails, returns `"Could not generate outfit suggestion: [error]"` — never raises.

---

### `create_fit_card(outfit, new_item)`

**Purpose:** Generates a short, casual, shareable Instagram-style caption for the thrifted outfit. Uses a higher LLM temperature (1.2) so each run produces different output.

**Inputs:**
- `outfit` (str) — the outfit suggestion string from `suggest_outfit`
- `new_item` (dict) — the listing dict for the thrifted item

**Output:** `str` — a 2–4 sentence casual caption mentioning the item name, price, and platform naturally. If `outfit` is empty/whitespace, returns `"Could not create fit card — outfit description is empty."` without calling the LLM.

---

## How the Planning Loop Works

`run_agent()` in `agent.py` runs a sequential conditional loop — it does **not** call all tools unconditionally. Here is the exact conditional logic:

1. **Parse**: extract `description`, `size`, and `max_price` from the query using regex.
2. **Search**: call `search_listings(description, size, max_price)`.
3. **Branch on results**:
   - If results list is **empty** → set `session["error"]` with a specific message, **return immediately**. `suggest_outfit` and `create_fit_card` are never called.
   - If results list is **non-empty** → set `session["selected_item"] = results[0]`, continue.
4. **Outfit**: call `suggest_outfit(selected_item, wardrobe)`.
5. **Fit card**: call `create_fit_card(outfit_suggestion, selected_item)`.
6. Return the completed session.

The agent's behavior genuinely differs based on what `search_listings` returns — the downstream tools only run when there is a valid item to work with.

---

## State Management

All state lives in a single `session` dict initialized at the start of each `run_agent()` call. It flows forward through tool calls — no re-entry, no hardcoded values.

| Key | Set when | Flows into |
|-----|----------|------------|
| `query` | Start | Parsing step |
| `parsed` | After regex parsing | `search_listings` params |
| `search_results` | After `search_listings` | Branch check + `selected_item` |
| `selected_item` | After branch passes (`results[0]`) | `suggest_outfit`, `create_fit_card` |
| `wardrobe` | Start (from user choice) | `suggest_outfit` |
| `outfit_suggestion` | After `suggest_outfit` | `create_fit_card` |
| `fit_card` | After `create_fit_card` | UI panel |
| `error` | If `search_listings` returns `[]` | Early exit + UI error panel |

The Gradio handler reads `session["error"]` first — if set, it shows the error in the listing panel and leaves the other panels empty.

---

## Error Handling

**`search_listings` — no results:**
Returns `[]`. The agent sets `session["error"]` = `"No listings found for '{description}' [in size X] [under $Y]. Try broader terms or remove the size/price filters."` and returns immediately. The UI shows this message in the listing panel; the outfit and fit card panels are empty.

*Example from testing:*
```
query: "designer ballgown size XXS under $5"
→ search_listings returns []
→ session["error"] = "No listings found for 'designer ballgown' in size XXS under $5. Try broader terms or remove the size/price filters."
→ fit_card = None (never called)
```

**`suggest_outfit` — empty wardrobe:**
Does not crash. Detects `wardrobe["items"] == []` and switches to a general styling prompt ("what kinds of pieces pair well with this item?"). Returns a useful string regardless. The agent continues to `create_fit_card` normally.

*Example from testing:*
```python
suggest_outfit(results[0], get_empty_wardrobe())
# → "This faded band tee has strong streetwear energy. Pair it with..."
# Never raises, never returns empty string
```

**`create_fit_card` — empty outfit string:**
Guards immediately: `if not outfit or not outfit.strip(): return "Could not create fit card — outfit description is empty."` No LLM call is made. The returned string shows up in the fit card panel rather than crashing.

*Example from testing:*
```
create_fit_card("", results[0])
→ "Could not create fit card — outfit description is empty."
```

---

## Spec Reflection

**One way the spec helped:** Designing the error handling table before any code forced me to decide *what the agent actually says* when things fail — not just "handle the error". This made the no-results message specific and actionable ("try broader terms or remove filters") instead of a generic "no results found", which is exactly the difference between useful and useless agent behavior.

**One way implementation diverged from the spec:** The original spec listed `outfit` as the only parameter for `create_fit_card`, but the stub signature in `tools.py` takes both `outfit` and `new_item`. This is the right design (the caption needs item details like price and platform), but the spec's parameter list was incomplete. I updated the planning.md tool spec to match the actual stub before implementing.

---

## AI Usage

**Instance 1 — `search_listings` keyword scoring**
I gave Claude the Tool 1 spec block from `planning.md` (inputs with types, scoring logic described as "+2 for title/tag hits, +1 for description/color/brand"), the `load_listings()` signature, and asked it to implement the function. It generated a working implementation but used `set` intersection for scoring, which missed partial keyword matches (e.g., "tee" wouldn't match "graphic tee" tag). I overrode this with a substring-based check (`kw in tag`) so partial matches score correctly.

**Instance 2 — `run_agent()` planning loop**
I gave Claude the full architecture diagram from `planning.md` and the Planning Loop + State Management sections, and asked it to implement `run_agent()`. It correctly implemented the conditional branch and session dict. However, it initially used a simple `query.split()` for parsing rather than regex — which would have missed "under $30" reliably. I replaced the parsing logic with regex-based extraction (`re.search` for price and size patterns) and verified it against several example queries before keeping it.
