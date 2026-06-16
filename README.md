# FitFindr

A multi-tool AI agent that helps users find secondhand fashion pieces and figure out how to wear them. Describe what you're looking for, and FitFindr searches thrift listings, suggests outfit combinations from your wardrobe, and writes a shareable caption.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Add your Groq API key to a `.env` file in the repo root:
```
GROQ_API_KEY=your_key_here
```

```bash
python app.py     # launch the UI
python agent.py   # CLI test
pytest tests/     # run tests
```

## Tools

`search_listings(description, size, max_price)` — searches the mock listings dataset and returns matching items ranked by keyword relevance. `size` and `max_price` are optional filters. Returns an empty list if nothing matches, never raises.

`suggest_outfit(new_item, wardrobe)` — takes the selected listing and the user's wardrobe and asks the LLM to suggest 1–2 complete outfit combinations using specific wardrobe pieces. If the wardrobe is empty, returns general styling advice instead.

`create_fit_card(outfit, new_item)` — generates a 2–4 sentence casual caption (think OOTD post) for the outfit. Runs at a higher temperature so the output varies each time. If `outfit` is empty, returns an error string without calling the LLM.

## Planning Loop

The agent parses the query with regex to extract a description, size, and price ceiling, then calls `search_listings`. If results come back empty, it sets an error message and returns immediately — `suggest_outfit` and `create_fit_card` never run. If there are results, it picks the top match and passes it through `suggest_outfit` and then `create_fit_card` in sequence.

## State Management

Everything lives in a single `session` dict that gets passed forward through the loop. The item returned by `search_listings` becomes `selected_item`, which flows into `suggest_outfit`. The string returned by `suggest_outfit` flows into `create_fit_card`. Nothing is re-entered by the user between steps.

## Error Handling

search_listings returning no results: the agent returns a specific message naming what was searched and suggesting the user broaden their query. The outfit and fit card panels stay empty.

suggest_outfit with an empty wardrobe: detects the empty items list and switches to a general styling prompt. Returns useful advice rather than crashing or returning nothing.

create_fit_card with an empty outfit string: returns "Could not create fit card — outfit description is empty." immediately without making an LLM call.

## Spec Reflection

Writing the error handling table before any code forced a useful decision: what does the agent actually say when something fails? That specificity — "try broader terms or remove the size/price filters" — is what makes the no-results message useful rather than a dead end.

One thing that diverged: the initial spec listed `outfit` as the only parameter for `create_fit_card`, but the stub takes both `outfit` and `new_item`. The caption needs the item's price and platform, so the stub was right. I updated planning.md to match before implementing.

## AI Usage

For `search_listings`, I gave Claude the tool spec from planning.md and asked it to implement the scoring logic. It used set intersection, which missed partial matches ("tee" wouldn't score against the tag "graphic tee"). I switched it to substring matching so partial keyword hits count.

For `run_agent`, I gave Claude the architecture diagram and planning loop section. The structure came out right, but it used `query.split()` for parsing instead of regex, which wouldn't reliably catch "under $30". I replaced it with `re.search` patterns for price and size extraction.
