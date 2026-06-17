# FitFindr 🛍️

FitFindr is a small **agent** I built that helps you shop secondhand. You
describe what you're looking for in plain English ("vintage graphic tee under
$30"); the agent searches a mock listings dataset, picks the best match, styles
it against your wardrobe, and writes a shareable "fit card" caption.

The interesting part isn't the three tools — it's the **planning loop** that
decides *which* tool to call, *in what order*, and *when to stop*. My agent does
not run the same three steps every time: it branches on what each tool returns.
For an impossible query it calls only one tool and stops with a helpful message;
for a good query it runs all three.

---

## Setup

```bash
pip install -r requirements.txt
```

I set my Groq API key in a `.env` file in the project root (free key at
[console.groq.com](https://console.groq.com)):

```
GROQ_API_KEY=your_key_here
```

## Run

```bash
python app.py          # launches the Gradio UI — open the URL printed in your terminal
python agent.py        # runs the planning loop from the CLI (happy path + no-results path)
pytest tests/          # runs the tool test suite
```

> The terminal prints the actual local URL (usually `http://localhost:7860`, but
> the port can differ — read the output).

---

## Tool Inventory

My agent has exactly three tools, all in `tools.py`. `search_listings` is pure
Python (offline, deterministic). `suggest_outfit` and `create_fit_card` call the
Groq LLM (`llama-3.3-70b-versatile`).

### 1. `search_listings(description, size, max_price) → list[dict]`

| | |
|---|---|
| **Inputs** | `description: str` — keywords/style the user wants (e.g. `"vintage graphic tee"`). `size: str \| None` — size filter, case-insensitive substring (e.g. `"M"` matches `"S/M"`); `None` skips the filter. `max_price: float \| None` — inclusive price ceiling in dollars; `None` skips the filter. |
| **Output** | A `list[dict]` of matching listings, **sorted best match first**. Empty list `[]` if nothing matches. Each dict has `id`, `title`, `description`, `category`, `style_tags` (list), `size`, `condition`, `price` (float), `colors` (list), `brand`, `platform`. |
| **Purpose** | Find candidate items to style. It filters by price and size, scores each remaining listing by keyword overlap with `description` (title and `style_tags` matches weighted higher), drops zero-score listings, and sorts by score. |

### 2. `suggest_outfit(new_item, wardrobe) → str`

| | |
|---|---|
| **Inputs** | `new_item: dict` — the selected listing (the loop passes `search_results[0]`). `wardrobe: dict` — the user's wardrobe with an `items` list (each item has `name`, `category`, `colors`, `style_tags`, optional `notes`); may be empty. |
| **Output** | A non-empty `str` with 1–2 outfit ideas. With a non-empty wardrobe it names specific owned pieces; with an empty wardrobe it returns general styling advice. It never returns `""` or raises. |
| **Purpose** | Turn a raw listing into wearable styling advice grounded in what the user already owns. |

### 3. `create_fit_card(outfit, new_item) → str`

| | |
|---|---|
| **Inputs** | `outfit: str` — the suggestion text from `suggest_outfit`. `new_item: dict` — the selected listing (needs at least `title`, `price`, `platform`). |
| **Output** | A 2–4 sentence caption `str` mentioning the item, price, and platform naturally. If `outfit` is empty/whitespace or `new_item` is missing `title`/`price`/`platform`, it returns the error string `"I couldn't create a fit card because the outfit suggestion or listing details were incomplete."` |
| **Purpose** | Produce a polished, shareable OOTD-style caption as the final deliverable. I use `temperature=1.0` so captions vary run to run. |

---

## How the Planning Loop Works

I implemented the loop in `run_agent(query, wardrobe)` in `agent.py`. It's a
**fixed sequence with branch points** — at each tool result the agent decides
whether to continue or stop. It does *not* call all three tools unconditionally.

1. **Initialize** a fresh `session` dict (`_new_session`) — my single source of
   truth for the run.
2. **Parse** the query into `description` / `size` / `max_price` (`_parse_query`,
   regex-based) and store it in `session["parsed"]`. Examples:
   `"under $30"` → `max_price=30.0`; `"size M"`, `"W30"`, `"US 7"` → `size`;
   the leftover text → `description`.
3. **Call `search_listings`** with the parsed params; store the list in
   `session["search_results"]`.
4. **Branch on the search result** — *this is the decision that makes it an agent:*
   - **Empty list →** I set `session["error"]` to a specific, actionable message
     and **return immediately**. `suggest_outfit` and `create_fit_card` are
     **never called**.
   - **Non-empty →** set `session["selected_item"] = search_results[0]` and continue.
5. **Call `suggest_outfit(selected_item, wardrobe)`**; store in
   `session["outfit_suggestion"]`. If it comes back empty/whitespace, I set
   `session["error"]` and **return early** (no point building a fit card from
   nothing).
6. **Call `create_fit_card(outfit_suggestion, selected_item)`.** If it returns the
   incomplete-card error string, I copy it into `session["error"]`, leave
   `session["fit_card"] = None`, and return. Otherwise I store the caption in
   `session["fit_card"]`.
7. **Return** the session. The run is "done" when `fit_card` is set **or** `error`
   is set.

**Why this is a loop, not a script:** the same code produces *different tool-call
sequences* for different inputs. A matching query calls all three tools; an
impossible query calls only `search_listings` and stops with a helpful error.
Behavior is driven by tool *output*, not hardcoded order.

---

## State Management

All state lives in one `session` dict, created by `_new_session()` and threaded
through the whole run. I write each tool's result back to the session *before* the
next tool reads from it, so there's no re-prompting and no hardcoded values
between steps.

| Key | Type | Written by | Read by |
|---|---|---|---|
| `query` | `str` | caller | parser |
| `parsed` | `dict` | step 2 | `search_listings` |
| `search_results` | `list[dict]` | `search_listings` | branch / item selection |
| `selected_item` | `dict \| None` | step 4 | `suggest_outfit`, `create_fit_card` |
| `wardrobe` | `dict` | caller | `suggest_outfit` |
| `outfit_suggestion` | `str \| None` | `suggest_outfit` | `create_fit_card` |
| `fit_card` | `str \| None` | `create_fit_card` | final output |
| `error` | `str \| None` | any branch | UI / caller |

**Data flow:** `query → parsed → search_listings → selected_item → suggest_outfit
→ outfit_suggestion → create_fit_card → fit_card`.

State is passed **by reference**, not re-derived. I verified this directly: the
dict in `session["selected_item"]` is the *same object* (`is`) handed to both
`suggest_outfit` and `create_fit_card`, and the string in
`session["outfit_suggestion"]` is the *same object* passed into `create_fit_card`.
Nothing is re-typed or re-prompted between steps.

`app.py`'s `handle_query()` is a thin adapter: it picks the wardrobe, calls
`run_agent()`, and maps the session to the three UI panels — the error path shows
the message in panel 1 with the other two blank; the success path formats
`selected_item` into the listing panel and shows `outfit_suggestion` and
`fit_card` in the other two.

---

## Error Handling

| Tool | Failure mode | What the agent does |
|---|---|---|
| `search_listings` | No listing matches the query | Set `session["error"]` to a specific message naming the search; return early **without** calling the other two tools. |
| `suggest_outfit` | Wardrobe is empty | **Does not stop** — returns general styling advice instead of named pieces and continues to `create_fit_card`. |
| `suggest_outfit` | Returns empty/whitespace text | Set `session["error"]`, return early, don't build a fit card. |
| `create_fit_card` | `outfit` empty or listing missing `title`/`price`/`platform` | Tool returns its incomplete-card error string; the loop stores it in `session["error"]` and leaves `session["fit_card"] = None`. |

### Concrete example from my testing — the no-results branch

Query: `"designer ballgown size XXS under $5"` (size, price, and item are all
impossible against the dataset).

```text
search_listings('designer ballgown', size='XXS', max_price=5)  →  []
```

`handle_query` / `run_agent` then returns:

```text
Panel 1: ⚠️ I couldn't find any listings for "designer ballgown" under $5 in
         size XXS. Try a broader description, a higher budget, or removing the
         size filter.
Panel 2: ""
Panel 3: ""

session["fit_card"]      → None
session["selected_item"] → None
suggest_outfit / create_fit_card calls → 0
```

The message tells the user **what failed** (no match for that description / price /
size) and **what to try** (broaden the description, raise the budget, drop the
size) — not a generic "no results." Compare this to `"vintage graphic tee under
$30"`, which flows through all three tools and fills every panel: in my testing it
selected *Graphic Tee — 2003 Tour Bootleg Style ($24, depop)*, suggested pairing
it with my baggy straight-leg jeans and black combat boots, and produced a fit
card caption. Same code, completely different behavior — driven entirely by the
`search_listings` result.

---

## Spec Reflection

**One way the spec helped me.** Writing the **Planning Loop** section before any
code forced me to name the stop condition — *empty search results* — up front.
My first instinct was a linear script that always calls all three tools, and the
spec is what made me put the branch in step 4 instead. That single `if not
session["search_results"]: return` is exactly what turns this from a fixed
pipeline into an agent that behaves differently for different inputs, and I'd have
missed it if I'd jumped straight to coding.

**One way my implementation diverged from the spec, and why.** My tool specs
described `search_listings` as taking already-separated `description` / `size` /
`max_price`, but they never said *who* splits a free-text user query into those
three fields. When I wired up the loop I realized nothing did, so I added a
`_parse_query` helper in `agent.py` (regex for price phrases like "under $30" and
size patterns like "size M" / "W30" / "US 7") that the original spec didn't list
as a step. I added it because the UI hands the agent one raw string, and the gap
between "raw query" and "structured tool inputs" had to live somewhere — putting
it in the loop kept the tools themselves clean and independently testable.

Two smaller things the spec got right that I kept: `suggest_outfit` degrading to
general advice on an **empty wardrobe** (a graceful path, not an error, so new
users still get a full result), and `create_fit_card` returning a sentinel error
*string* instead of raising — which means the exact wording and the "starts with
`I couldn't create a fit card`" check have to stay in sync between `tools.py` and
`agent.py`.

---

## AI Usage

I used **Claude (via Claude Code)** as my AI pair while building this. Two
specific instances:

**1. Implementing the planning loop (`run_agent`).**
I gave Claude the **Planning Loop** and **State Management** sections of my
`planning.md`, plus the ASCII agent diagram and the `run_agent` TODO stub. It
produced a full loop with the branch points wired in. Before running it I reviewed
it against my spec and changed two things: (a) I confirmed it **branched on the
`search_listings` result and returned early** rather than calling all three tools
unconditionally — that was the one behavior I most wanted to verify, and it was
correct; (b) the generated no-results message was generic, so I had it build the
message dynamically from the parsed `description` / `size` / `max_price` so it
tells the user *what* failed. I also added the `_parse_query` helper, which the
spec implied but the stub didn't include.

**2. Verifying that state actually flows (not re-derived).**
I asked Claude to prove state passes *by reference* rather than being re-prompted
or hardcoded between steps. It wrote a small harness that wrapped `suggest_outfit`
and `create_fit_card` to capture their arguments, then asserted with `is` that
`session["selected_item"]` was the *exact same dict* passed into both tools and
`session["outfit_suggestion"]` was the *exact same string* passed into the
fit-card tool. I overrode its first attempt, which compared with value equality
(`==`) — that would have passed even if the loop rebuilt the dict — and had it use
identity (`is`) instead, which actually proves there's no re-entry. I kept this as
my state-passing check.

---

## Project Layout

```
ai201-project2-fitfindr-starter/
├── agent.py                   # run_agent() — the planning loop + query parsing
├── app.py                     # Gradio UI + handle_query() adapter
├── tools.py                   # search_listings, suggest_outfit, create_fit_card
├── planning.md                # spec, agent diagram, walkthrough
├── tests/test_tools.py        # tool tests (LLM tests auto-skip without a key)
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # wardrobe format + example/empty wardrobes
└── utils/data_loader.py       # data loading helpers
```

The mock dataset has 40 listings across `tops`, `bottoms`, `outerwear`, `shoes`,
and `accessories`; the example wardrobe has 10 items. I load them with
`load_listings()` and `get_example_wardrobe()` / `get_empty_wardrobe()` from
`utils/data_loader.py`.
