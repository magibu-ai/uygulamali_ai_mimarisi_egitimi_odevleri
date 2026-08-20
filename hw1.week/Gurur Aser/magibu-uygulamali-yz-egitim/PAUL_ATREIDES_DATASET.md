# Paul Atreides Persona Dataset

`paul_atreides_dataset_300.json` contains 300 English user-assistant pairs for
supervised fine-tuning. It is a single JSON array with 600 ordered message
objects. Every pair has this exact shape:

```json
[
  {"content":"Who are you?","images":null,"role":"user","thinking":null,"tool_calls":null},
  {"content":"I am Paul Atreides...","images":null,"role":"assistant","thinking":"...","tool_calls":null}
]
```

There are no system messages. The assistant's `content` always speaks in first
person as Paul Atreides and its `thinking` field contains a short, high-level
response rationale.

The `thinking` values are not private chain-of-thought traces and are
deliberately limited to the response goal and style.

The data is original paraphrase, not text copied from the novels, films, or
other sources. Research facts were cross-checked against these background
sources before authoring:

- https://www.encyclopedia.com/earth-and-environment/geology-and-oceanography/geology-and-oceanography/dune
- https://time.com/6835194/dune-part-two-what-to-remember/
- https://dune.fandom.com/wiki/Paul_Atreides

Run `python les2/create_paul_atreides_dataset.py` to regenerate the dataset.
