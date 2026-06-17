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

**`search_listings` searches the mock secondhand listing data for items that match the user's request. It filters listings by the user's item description, optional size, and optional maximum price, then returns the best matching listings so the agent can pick one to style.

**Input parameters:**
- `description` (str): The item or style the user is looking for, such as `"vintage graphic tee"`, `"platform shoes"`, or `"denim jacket"`. The tool should compare this text against each listing's `title`, `description`, `category`, `style_tags`, `colors`, `brand`, and `platform`.
- `size` (str | None): The user's requested size, such as `"M"`, `"S/M"`, `"W30"`, or `"US 7"`. If the user does not mention a size, this should be `None` and the tool should not filter by size.
- `max_price` (float | None): The user's maximum budget in dollars, such as `30.0`. If the user does not mention a budget, this should be `None` and the tool should not filter by price.

**What it returns:**
The tool returns a `list[dict]` of matching listing dictionaries, sorted with the strongest match first. Each dictionary in the list contains these fields from `data/listings.json`:
- `id` (str): Unique listing id, such as `"lst_006"`.
- `title` (str): The listing title.
- `description` (str): The seller-style item description.
- `category` (str): One of `tops`, `bottoms`, `outerwear`, `shoes`, or `accessories`.
- `style_tags` (list[str]): Style labels such as `["graphic tee", "vintage", "grunge"]`.
- `size` (str): The item's size.
- `condition` (str): Item condition, such as `excellent`, `good`, or `fair`.
- `price` (float): Price in dollars.
- `colors` (list[str]): Colors included in the item.
- `brand` (str | None): Brand name if known, otherwise `None`.
- `platform` (str): The resale platform, such as `depop`, `thredUp`, or `poshmark`.

**What happens if it fails or returns nothing:**
If no listings match, the tool returns an empty list `[]`. The planning loop should set `session["error"]` to a helpful message like `"I couldn't find any listings for vintage graphic tee under $30. Try a broader description, a higher budget, or removing the size filter."` Then the agent returns the session immediately. It should not call `suggest_outfit` or `create_fit_card` when there are no search results.

---

### Tool 2: suggest_outfit

**What it does:**
`suggest_outfit` takes the selected thrift listing and the user's wardrobe, then creates styling advice for how to wear the item. If the user has wardrobe items, it should recommend an outfit using specific pieces from that wardrobe.

**Input parameters:**
- `new_item` (dict): The listing dictionary selected from the search results, usually `session["search_results"][0]`. It should include `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.
- `wardrobe` (dict): The user's wardrobe in the schema from `data/wardrobe_schema.json`. It has an `items` key containing a list of wardrobe item dictionaries. Each wardrobe item has `id`, `name`, `category`, `colors`, `style_tags`, and optional `notes`.

**What it returns:**
The tool returns a non-empty string with 1–2 outfit suggestions. When the wardrobe has items, the response should mention specific wardrobe pieces by `name`, explain how they work with `new_item`, and describe the overall style or vibe. For example, it might suggest pairing a graphic tee with `"Baggy straight-leg jeans, dark wash"` and `"Chunky white sneakers"` because the colors and streetwear tags fit together.

If the wardrobe is empty, the tool should still return a non-empty string with general styling advice, such as what categories, colors, or silhouettes would pair well with the new item.

**What happens if it fails or returns nothing:**
If the wardrobe is empty, the agent should not stop. It should ask for general styling advice and continue to `create_fit_card`. If the tool cannot generate any outfit text, the planning loop should set `session["error"]` to `"I found a listing, but couldn't generate an outfit suggestion for it. Try adding more wardrobe details or using a simpler request."` Then it should return early and not call `create_fit_card`.

---

### Tool 3: create_fit_card

**What it does:**
`create_fit_card` turns the outfit suggestion and selected listing into a short shareable caption. It gives the user a polished final result that includes the thrift find and how to style it.

**Input parameters:**
- `outfit` (str): The outfit suggestion returned by `suggest_outfit`. This should be a non-empty string.
- `new_item` (dict): The selected listing dictionary. It should include at least `title`, `price`, `platform`, `condition`, `colors`, and `style_tags`.

**What it returns:**
The tool returns a `str` containing a 2–4 sentence fit card caption. The caption should mention the item, price, and platform naturally, then summarize the outfit vibe. For example: `"Found this 2003 tour-style graphic tee on depop for $24. I'd wear it with dark baggy jeans and chunky sneakers for an easy vintage streetwear fit."`

**What happens if it fails or returns nothing:**
If `outfit` is empty or `new_item` is missing important details like title, price, or platform, the tool should return an error message string: `"I couldn't create a fit card because the outfit suggestion or listing details were incomplete."` The planning loop should store that message in `session["error"]`, leave `session["fit_card"]` as `None`, and return the session.

---

### Additional Tools (if any)

No additional tools are planned for Milestone 2. The agent will use only the required three tools: `search_listings`, `suggest_outfit`, and `create_fit_card`.

---

## Planning Loop

**How does your agent decide which tool to call next?**
The agent follows a fixed sequence with clear stop conditions.

1. Start by creating a session dictionary with the original `query`, the provided `wardrobe`, and empty values for `parsed`, `search_results`, `selected_item`, `outfit_suggestion`, `fit_card`, and `error`.
2. Parse the user's query into `description`, `size`, and `max_price`.
   - If the query says something like `"under $30"` or `"below $30"`, set `max_price = 30.0`; otherwise set `max_price = None`.
   - If the query says something like `"size M"`, `"W30"`, or `"US 7"`, set `size` to that value; otherwise set `size = None`.
   - Set `description` to the item/style phrase after removing budget and size phrases.
3. Store those parsed values in `session["parsed"]`.
4. Call `search_listings(description, size, max_price)`.
5. Store the returned list in `session["search_results"]`.
6. Check whether `session["search_results"]` is empty.
   - If yes, set `session["error"]` to a no-results message and return the session immediately.
   - If no, set `session["selected_item"] = session["search_results"][0]` and continue.
7. Call `suggest_outfit(new_item=session["selected_item"], wardrobe=session["wardrobe"])`.
8. Store the returned string in `session["outfit_suggestion"]`.
9. Check whether `session["outfit_suggestion"]` is empty or only whitespace.
   - If yes, set `session["error"]` to an outfit-generation error message and return the session immediately.
   - If no, continue.
10. Call `create_fit_card(outfit=session["outfit_suggestion"], new_item=session["selected_item"])`.
11. Check whether the returned fit card is empty or starts with `"I couldn't create a fit card"`.
   - If yes, set `session["error"]` to that message, keep `session["fit_card"] = None`, and return the session.
   - If no, store it in `session["fit_card"]`.
12. Return the completed session. The agent is done when `session["fit_card"]` exists or when `session["error"]` has been set.

---

## State Management

**How does information from one tool get passed to the next?**
The agent passes information through a session dictionary. Each tool result is saved in the session before the next tool runs.

The session tracks:
- `query` (str): The original user request.
- `parsed` (dict): The extracted `description`, `size`, and `max_price`.
- `search_results` (list[dict]): The listings returned by `search_listings`.
- `selected_item` (dict | None): The first listing in `search_results`; this is the item the agent styles.
- `wardrobe` (dict): The user's wardrobe input.
- `outfit_suggestion` (str | None): The text returned by `suggest_outfit`.
- `fit_card` (str | None): The final caption returned by `create_fit_card`.
- `error` (str | None): A message explaining why the agent stopped early, if something went wrong.

The data moves in this order: query gets parsed into `session["parsed"]`; parsed values go into `search_listings`; the first search result becomes `session["selected_item"]`; `selected_item` and `wardrobe` go into `suggest_outfit`; `outfit_suggestion` and `selected_item` go into `create_fit_card`; the final caption is saved as `session["fit_card"]`.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | Set `session["error"]` to `"I couldn't find any listings for your search. Try a broader description, a higher budget, or removing the size filter."` Return the session immediately without calling `suggest_outfit` or `create_fit_card`. |
| suggest_outfit | Wardrobe is empty | Do not stop. Generate general styling advice for the selected item instead of naming specific wardrobe pieces, store it in `session["outfit_suggestion"]`, and continue to `create_fit_card`. |
| create_fit_card | Outfit input is missing or incomplete | Set `session["error"]` to `"I couldn't create a fit card because the outfit suggestion or listing details were incomplete."` Leave `session["fit_card"]` as `None` and return the session. |

---

## Architecture

```text
User query + wardrobe
        |
        v
Planning Loop: run_agent(query, wardrobe)
        |
        | parse query into description, size, max_price
        v
Session: parsed = {description, size, max_price}
        |
        v
search_listings(description, size, max_price)
        |
        +-- results == []
        |       |
        |       v
        |   Session: error = "No listings found..."
        |       |
        |       v
        |   Return session early
        |
        +-- results == [item, ...]
                |
                v
        Session: search_results = results
        Session: selected_item = results[0]
                |
                v
suggest_outfit(selected_item, wardrobe)
        |
        +-- outfit_suggestion == ""
        |       |
        |       v
        |   Session: error = "Could not generate outfit..."
        |       |
        |       v
        |   Return session early
        |
        +-- outfit_suggestion is non-empty
                |
                v
        Session: outfit_suggestion = outfit_suggestion
                |
                v
create_fit_card(outfit_suggestion, selected_item)
        |
        +-- fit_card missing or incomplete
        |       |
        |       v
        |   Session: error = "Could not create fit card..."
        |       |
        |       v
        |   Return session early
        |
        +-- fit_card is valid
                |
                v
        Session: fit_card = fit_card
                |
                v
        Return session
```

---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**

- **Tool used:** Claude (via Claude Code).
- **Input I gave it:** the Tool 1 / Tool 2 / Tool 3 spec sections above (inputs,
  return value, failure mode) plus the `tools.py` docstrings and the
  `load_listings()` / `get_example_wardrobe()` helpers in `utils/data_loader.py`.
- **What I expected it to produce:** three standalone functions matching my
  signatures — `search_listings` as pure keyword scoring + price/size filters,
  and the two LLM-backed tools (`suggest_outfit`, `create_fit_card`) calling Groq.
- **How I verified before trusting it:** I ran `pytest tests/` (search filters,
  empty-result case, and the `create_fit_card` empty/incomplete-input guards run
  offline; the LLM tests run live with my key). I specifically checked that
  `search_listings` returns `[]` rather than raising on no match, and that
  `create_fit_card` returns the sentinel error string on empty input. I overrode
  the first scoring version that weighted every field equally — I had it weight
  `title` and `style_tags` matches higher so the most on-topic listing surfaces
  first (confirmed by `test_search_sorted_by_relevance`).

**Milestone 4 — Planning loop and state management:**

- **Tool used:** Claude (via Claude Code).
- **Input I gave it:** the **Planning Loop** and **State Management** sections
  below, the **Architecture** ASCII diagram, and the `run_agent` TODO stub in
  `agent.py`.
- **What I expected it to produce:** a `run_agent` that initializes the session,
  parses the query, calls the tools in order, and — critically — **branches on the
  `search_listings` result** instead of calling all three tools unconditionally.
- **How I verified before trusting it:** I confirmed the empty-results path
  returns early and never calls `suggest_outfit` / `create_fit_card` (instrumented
  the tools to count calls — got 0). I also proved state passes **by reference**:
  the dict in `session["selected_item"]` is the *same object* (`is`) handed to
  both downstream tools, and `session["outfit_suggestion"]` is the *same string*
  passed into `create_fit_card`. I overrode the generic no-results message so it's
  built from the parsed `description` / `size` / `max_price`, and I added the
  `_parse_query` helper, which the spec implied but the stub didn't include.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 0 — Initialize and parse.**
The agent creates a fresh session and parses the query. `"under $30"` →
`max_price = 30.0`; no explicit size phrase → `size = None`; the leftover item
text → `description = "vintage graphic tee"`. These land in `session["parsed"]`.

**Step 1 — Search.**
The agent calls `search_listings("vintage graphic tee", size=None,
max_price=30.0)`. It returns a non-empty list sorted by relevance, with
*Graphic Tee — 2003 Tour Bootleg Style* ($24, depop) first. The list is stored in
`session["search_results"]`, and since it's non-empty the agent sets
`session["selected_item"] = search_results[0]` and continues. (If this list had
been empty, the agent would set `session["error"]` and stop here — it would
**not** reach step 2.)

**Step 2 — Suggest an outfit.**
The agent calls `suggest_outfit(new_item=session["selected_item"],
wardrobe=session["wardrobe"])`. The exact same listing dict from step 1 is passed
straight through — no re-prompting. Because the example wardrobe has items, the
tool names specific pieces (e.g. baggy straight-leg jeans + black combat boots)
and returns a non-empty string, stored in `session["outfit_suggestion"]`.

**Step 3 — Create the fit card.**
The agent calls `create_fit_card(outfit=session["outfit_suggestion"],
new_item=session["selected_item"])` — passing the same outfit string and the same
listing dict. It returns a 2–4 sentence caption mentioning the item, $24, and
depop, stored in `session["fit_card"]`. With `fit_card` set and `error` still
`None`, the agent returns the session.

**Final output to user:**
The Gradio UI shows three panels: **Top listing found** (the 2003 bootleg graphic
tee, $24, depop, with size/colors/tags), **Outfit idea** (pair it with baggy
straight-leg jeans and black combat boots for a grunge-streetwear look), and
**Your fit card** (a shareable caption tying the find and the styling together).
Three tools ran, each result fed the next, and nothing was hardcoded or re-entered
between steps.
