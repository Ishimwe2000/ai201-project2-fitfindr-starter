# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Searches the mock listings dataset for secondhand items that match the user's description, optional size, and optional price ceiling. Returns a ranked list of matching listings sorted by keyword relevance.

**Input parameters:**
- `description` (str): Natural-language keywords describing the item (e.g., "vintage graphic tee"). Matched against listing title, style tags, description text, colors, and brand.
- `size` (str | None): Size string to filter by (e.g., "M", "W28"). Matching is case-insensitive substring — "M" matches "S/M" and "M". Pass `None` to skip size filtering.
- `max_price` (float | None): Maximum price inclusive (e.g., 30.0). Pass `None` to skip price filtering.

**What it returns:**
A list of listing dicts, sorted by relevance score (highest first). Each dict contains:
- `id` (str): unique listing identifier
- `title` (str): item name
- `description` (str): seller's description
- `category` (str): one of tops, bottoms, outerwear, shoes, accessories
- `style_tags` (list[str]): style descriptors like "vintage", "grunge"
- `size` (str): size label
- `condition` (str): excellent, good, or fair
- `price` (float): listed price in USD
- `colors` (list[str]): color names
- `brand` (str | None): brand name if known
- `platform` (str): depop, thredUp, or poshmark

Returns an empty list `[]` if nothing matches — never raises an exception.

**What happens if it fails or returns nothing:**
If the list is empty, the agent sets `session["error"]` to a specific message naming what was searched and suggesting how to broaden the query (e.g., "No listings found for 'designer ballgown' in size XXS under $5. Try broader terms or remove the size/price filters."), then returns the session immediately without calling `suggest_outfit` or `create_fit_card`.

---

### Tool 2: suggest_outfit

**What it does:**
Given a specific thrifted item and the user's current wardrobe, calls the LLM to suggest 1–2 complete outfit combinations. If the wardrobe is empty, it falls back to general styling advice for the item instead.

**Input parameters:**
- `new_item` (dict): A listing dict returned by `search_listings` — the item the user is considering.
- `wardrobe` (dict): A wardrobe dict with an `'items'` key containing a list of wardrobe item dicts. Each item has: `id`, `name`, `category`, `colors` (list), `style_tags` (list), `notes` (str | None). May be empty.

**What it returns:**
A non-empty string with 1–2 outfit suggestions. If the wardrobe has items, suggestions reference specific wardrobe pieces by name (e.g., "Pair with your baggy straight-leg jeans and white ribbed tank"). If the wardrobe is empty, the string contains general styling advice (what types of pieces pair well, what vibe it suits).

**What happens if it fails or returns nothing:**
If `wardrobe['items']` is empty, the tool does not crash — it calls the LLM with a general styling prompt. If the LLM call itself fails (network error, API error), the tool catches the exception and returns a descriptive error string: "Could not generate outfit suggestion: [error detail]". The agent stores this string in `session["outfit_suggestion"]` and still calls `create_fit_card`, which will handle it gracefully.

---

### Tool 3: create_fit_card

**What it does:**
Generates a short, casual, shareable outfit caption (like an Instagram OOTD post) for a thrifted item and outfit combination. Calls the LLM with a higher temperature to produce varied output each time.

**Input parameters:**
- `outfit` (str): The outfit suggestion string from `suggest_outfit`.
- `new_item` (dict): The listing dict for the thrifted item (used for title, price, platform).

**What it returns:**
A 2–4 sentence string that sounds like a real social media caption — casual, specific about the vibe, mentioning the item name, price, and platform naturally (once each). Sounds different each time for different inputs.

If `outfit` is empty or whitespace-only, returns the error string "Could not create fit card — outfit description is empty." without calling the LLM.

**What happens if it fails or returns nothing:**
If the `outfit` parameter is empty/blank, returns a descriptive error string immediately (no LLM call). If the LLM call fails, catches the exception and returns "Could not generate fit card: [error detail]". Never raises an exception to the caller.

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**

The agent uses a sequential conditional loop with early-exit on failure. Here is the specific conditional logic:

1. **Parse query**: Extract `description`, `size`, and `max_price` from the raw query using regex. Store in `session["parsed"]`.

2. **Call search_listings**: Run `search_listings(description, size, max_price)`. Store result in `session["search_results"]`.

3. **Branch on results**:
   - If `session["search_results"]` is an empty list `[]`:
     → Set `session["error"]` to a specific message naming the failed query and suggesting fixes.
     → **Return session immediately.** Do NOT call `suggest_outfit` or `create_fit_card`.
   - If results is non-empty:
     → Set `session["selected_item"] = session["search_results"][0]` (top relevance match).
     → Continue to step 4.

4. **Call suggest_outfit**: Run `suggest_outfit(session["selected_item"], session["wardrobe"])`. Store string result in `session["outfit_suggestion"]`.

5. **Call create_fit_card**: Run `create_fit_card(session["outfit_suggestion"], session["selected_item"])`. Store string result in `session["fit_card"]`.

6. **Return session**: Return the fully populated session dict. `session["error"]` is `None` on the happy path.

The agent never calls all three tools unconditionally — `suggest_outfit` and `create_fit_card` only run if `search_listings` returned at least one result.

---

## State Management

**How does information from one tool get passed to the next?**

All state is stored in a single `session` dict initialized at the start of `run_agent()`. The session persists across all tool calls within one interaction. Here is what is tracked and when each key is set:

| Key | Type | Set when | Used by |
|-----|------|----------|---------|
| `query` | str | Start (from user input) | Parsing step |
| `parsed` | dict with `description`, `size`, `max_price` | After query parsing | `search_listings` call |
| `search_results` | list[dict] | After `search_listings` returns | Branch check + `selected_item` |
| `selected_item` | dict | After branch check passes (first element of `search_results`) | `suggest_outfit`, `create_fit_card` |
| `wardrobe` | dict | Start (from user's wardrobe choice) | `suggest_outfit` call |
| `outfit_suggestion` | str | After `suggest_outfit` returns | `create_fit_card` call |
| `fit_card` | str | After `create_fit_card` returns | Final output |
| `error` | str \| None | Set if `search_listings` returns empty; otherwise stays `None` | Early-exit branch + UI |

No data is re-entered by the user between steps. The item dict flows from `search_listings` → `selected_item` → `suggest_outfit` → `create_fit_card` without copying or re-fetching.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | Sets `session["error"]` = "No listings found for '{description}' [in size {size}] [under ${max_price}]. Try broader terms or remove the size/price filters." Returns session immediately. UI shows this message in the listing panel; outfit and fit card panels are empty. |
| suggest_outfit | Wardrobe is empty | Does NOT crash. Calls LLM with a general styling prompt: "What kinds of wardrobe pieces pair well with this item? What vibe does it suit?" Returns LLM response as a string. Agent continues to `create_fit_card` normally. |
| create_fit_card | Outfit input is missing or whitespace-only | Returns the string "Could not create fit card — outfit description is empty." without calling the LLM. Agent stores this string in `session["fit_card"]` and returns. UI shows the error string in the fit card panel. |

---

## Architecture

```
User query (natural language)
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                     Planning Loop (run_agent)               │
│                                                             │
│  Step 1: Parse query → description, size, max_price         │
│              │                                              │
│              ▼                                              │
│  Step 2: search_listings(description, size, max_price)      │
│              │                                              │
│    ┌─────────┴──────────┐                                   │
│    │ results == []       │ results != []                     │
│    │                     │                                   │
│    ▼                     ▼                                   │
│  [ERROR]           session["selected_item"] = results[0]    │
│  Set session        │                                        │
│  ["error"]          ▼                                        │
│  Return early  Step 3: suggest_outfit(selected_item,        │
│    │                                  wardrobe)             │
│    │                    │                                    │
│    │               session["outfit_suggestion"] = "..."     │
│    │                    │                                    │
│    │                    ▼                                    │
│    │           Step 4: create_fit_card(outfit_suggestion,   │
│    │                                   selected_item)       │
│    │                    │                                    │
│    │               session["fit_card"] = "..."              │
│    │                    │                                    │
└────┼────────────────────┼────────────────────────────────────┘
     │                    │
     ▼                    ▼
  Return session       Return session
  (error set,          (error = None,
   fit_card = None)     fit_card populated)
     │                    │
     ▼                    ▼
  Gradio UI           Gradio UI
  (error panel)       (all 3 panels)
```

**Session state flows:**
- `session["parsed"]` → `search_listings` parameters
- `session["search_results"][0]` → `session["selected_item"]` → `suggest_outfit` + `create_fit_card`
- `session["wardrobe"]` → `suggest_outfit`
- `session["outfit_suggestion"]` → `create_fit_card`

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

**search_listings**: I'll give Claude the Tool 1 spec block from this planning.md (inputs with types, scoring logic, return value shape, failure mode) plus the `load_listings()` signature from `utils/data_loader.py`. I'll ask it to implement the function in `tools.py` using only `load_listings()` for data access — no file I/O. Before running, I'll verify: does it filter by both `max_price` and `size`? Does it use case-insensitive substring matching for size? Does it score by title/tag/description/color/brand? Does it return `[]` on no match without raising? Then I'll test with 3 queries: one that should return results, one impossible query that returns `[]`, and one with a price filter.

**suggest_outfit**: I'll give Claude the Tool 2 spec block (inputs with wardrobe schema structure, empty-wardrobe fallback behavior, LLM call via `_get_groq_client()`) and the `wardrobe_schema.json` structure. I'll ask it to implement using `llama-3.3-70b-versatile` with the existing `_get_groq_client()` helper. Before running, I'll verify: does it check `wardrobe["items"]` for emptiness before choosing the prompt? Does it format wardrobe items by name, colors, and style_tags? Does it catch exceptions and return a string (not raise)?

**create_fit_card**: I'll give Claude the Tool 3 spec block (caption style guidelines, temperature requirement, guard on empty outfit, both parameters). I'll ask it to use `temperature=1.2`. Before running, I'll verify: does it guard against empty `outfit`? Does it pass `new_item` fields (title, price, platform) into the prompt? Does it use high temperature? I'll run it 3 times on the same input and check outputs vary.

**Milestone 4 — Planning loop and state management:**

I'll give Claude the Architecture diagram and the Planning Loop + State Management sections of this planning.md. I'll ask it to implement `run_agent()` in `agent.py` following the exact conditional logic in the diagram — specifically the early-return on empty results. Before using the code, I'll verify: does it branch on `search_results == []`? Does it store each result in the correct `session` key? Does it NOT call `suggest_outfit` when results are empty? Then I'll test the no-results path by running with an impossible query and checking that `session["fit_card"]` is `None`.

---

## A Complete Interaction (Step by Step)

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
The agent parses the query using regex. It extracts:
- `description` = "vintage graphic tee" (keywords after removing price fragment)
- `size` = `None` (no size mentioned)
- `max_price` = 30.0 (extracted from "under $30")

It calls `search_listings("vintage graphic tee", size=None, max_price=30.0)`.

The function loads all 40 listings, filters to those with `price <= 30.0` (about 20 listings), then scores each by keyword overlap with "vintage graphic tee". "Graphic Tee — 2003 Tour Bootleg Style" scores highest (hits "graphic", "tee", "vintage" in both title and style_tags). Returns a list of ~5 matching listings sorted by score. `session["search_results"]` is set to this list.

**Step 2:**
The branch check: `search_results` is non-empty, so `session["selected_item"]` is set to `results[0]` — the "Graphic Tee — 2003 Tour Bootleg Style" listing at $24 from Depop.

The agent calls `suggest_outfit(new_item=<band tee dict>, wardrobe=<example wardrobe dict>)`.

The wardrobe has 10 items including "Baggy straight-leg jeans, dark wash" and "White ribbed tank top". The LLM receives both the item (black graphic tee, grunge/streetwear tags) and the wardrobe list. It suggests: "Pair this with your baggy straight-leg jeans and white ribbed tank underneath for a classic layered streetwear look. Roll up the sleeves once and knot the front corner slightly for shape."

`session["outfit_suggestion"]` is set to this string.

**Step 3:**
The agent calls `create_fit_card(outfit="Pair this with...", new_item=<band tee dict>)`.

The LLM receives the item details and outfit and generates a casual caption at temperature 1.2: "thrifted this faded bootleg tee off depop for $24 and honestly it was made for baggy jeans 🖤 the rolled sleeve + front knot combo is doing something. full look up."

`session["fit_card"]` is set to this string.

**Final output to user:**
The Gradio UI populates three panels:
- **Top listing found**: "Graphic Tee — 2003 Tour Bootleg Style\n$24 · depop · good\nSize: L\nTags: graphic tee, vintage, grunge, streetwear, band tee\n\nVintage-style bootleg tee with faded graphic..."
- **Outfit idea**: "Pair this with your baggy straight-leg jeans..."
- **Your fit card**: "thrifted this faded bootleg tee off depop for $24..."
