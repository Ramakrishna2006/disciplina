"""Export the dataset as readable files (data/*.csv|txt) plus a DATASET.md page, so anyone can see
exactly what the model was trained and tested on. Same seeds as training -> identical every run."""
import csv
import os
from collections import Counter

from .data import ATTRS, FACT_TEMPLATES, QUESTION_TEMPLATES, build_world, pretraining_corpus, qa_examples
from .tokenizer import EOT


def splits():
    """The exact data used by `main.py train` (fixed seeds)."""
    world, train_p, test_p = build_world(seed=0)
    docs = lambda n, s: [d for d in pretraining_corpus(world, n, s).split(EOT) if d]  # noqa: E731
    return dict(world=world, train_people=train_p, test_people=test_p,
                pretrain=docs(4000, 1), val=docs(300, 2),
                finetune=qa_examples(world, train_p, seed=5), test=qa_examples(world, test_p, seed=3))


def export(root):
    d, out = splits(), os.path.join(root, "data")
    os.makedirs(out, exist_ok=True)
    world, test_p = d["world"], d["test_people"]
    role = lambda n: "test only (held out)" if n in test_p else "fine-tuning"  # noqa: E731

    with open(os.path.join(out, "people.csv"), "w", newline="", encoding="utf-8") as f:
        csv.writer(f, lineterminator="\n").writerows([["name", "city", "job", "food", "used_for"]] +
                                [[n, *world[n].values(), role(n)] for n in world])
    files = {"pretraining_text.txt": "".join(f"--- document {i} ---\n{t}\n\n" for i, t in enumerate(d["pretrain"], 1)),
             "validation_text.txt": "".join(f"--- document {i} ---\n{t}\n\n" for i, t in enumerate(d["val"], 1)),
             "finetune_qa.txt": "".join(f"{p}{a}\n\n" for p, a, *_ in d["finetune"]),
             "test_qa.txt": "".join(f"{p}{a}\n\n" for p, a, *_ in d["test"])}
    for name, text in files.items():
        with open(os.path.join(out, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    size = lambda n: f"{os.path.getsize(os.path.join(out, n)):,} bytes"  # noqa: E731
    people = "\n".join(f"| {i} | {f'**{n}**' if n in test_p else n} | {' | '.join(world[n].values())} | {role(n)} |"
                       for i, n in enumerate(world, 1))
    counts = "\n".join(f"| {a} | " + ", ".join([f"{v} {c}" for v, c in Counter(world[n][a] for n in world).most_common()]
                       + [f"never: {v}" for v in vals if all(world[n][a] != v for n in world)]) + " |"
                       for a, vals in ATTRS.items())
    tmpl = lambda T: "\n".join(f"- **{a}:** " + " · ".join(f"`{t}`" for t in ts) for a, ts in T.items())  # noqa: E731
    sample = lambda items: "\n\n".join(p + a for p, a, *_ in items[:4])  # noqa: E731
    page = f"""# Disciplina — Dataset

The model is trained on a small synthetic world of **{len(world)} people**. Each person has a **city**, a **job** and a
**favourite food**. All text is generated from these facts by [`llm/data.py`](llm/data.py) with fixed random seeds, so the
data is identical on every computer. `python main.py data` (or `train`) regenerates this page and [`data/`](data/).

## Files

| File | Used for | Contents | Size |
| --- | --- | --- | --- |
| [`data/people.csv`](data/people.csv) | the facts (the "database") | {len(world)} people × 3 attributes | {size('people.csv')} |
| [`data/pretraining_text.txt`](data/pretraining_text.txt) | pre-training | {len(d['pretrain']):,} documents of plain sentences | {size('pretraining_text.txt')} |
| [`data/validation_text.txt`](data/validation_text.txt) | perplexity | {len(d['val'])} documents, new sentence combinations | {size('validation_text.txt')} |
| [`data/finetune_qa.txt`](data/finetune_qa.txt) | fine-tuning | {len(d['finetune'])} Q&A pairs about {len(d['train_people'])} people | {size('finetune_qa.txt')} |
| [`data/test_qa.txt`](data/test_qa.txt) | evaluation | {len(d['test'])} questions about the {len(test_p)} held-out people | {size('test_qa.txt')} |

## How the data is split

- **Pre-training** text mentions all {len(world)} people, so the model learns every fact.
- **Fine-tuning** questions cover only {len(d['train_people'])} people.
- The other **{len(test_p)} people are held out**: the model never sees a question about them. Answering them correctly
  proves it learned to *use* its knowledge, not memorise answers.

## The people (all facts)

Names in **bold** are the held-out test people.

| # | Name | City | Job | Food | Used for |
| --- | --- | --- | --- | --- | --- |
{people}

## How often each value appears

Values are assigned at random, so some are common and some never appear (nobody is a doctor, so that word is never learned).

| Attribute | Counts (most common first) |
| --- | --- |
{counts}

## Templates

Pre-training sentences use one of five phrasings per fact (`{{n}}` = name, `{{v}}` = value, `{{a}}` = a/an). Varied
phrasing is what lets the model later answer differently-worded questions.

{tmpl(FACT_TEMPLATES)}

Questions (fine-tuning and test), formatted as `Q: <question>` then `A: <answer>`:

{tmpl(QUESTION_TEMPLATES)}

## Samples

First 3 pre-training documents (separated by the `<|endoftext|>` token during training):

```text
{chr(10).join(d['pretrain'][:3])}
```

First 4 fine-tuning examples:

```text
{sample(d['finetune'])}
```

First 4 test questions (the model must produce the answer after `A:`):

```text
{sample(d['test'])}
```
"""
    with open(os.path.join(root, "DATASET.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(page)
    return out
