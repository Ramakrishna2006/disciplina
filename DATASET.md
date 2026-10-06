# Disciplina — Dataset

The model is trained on a small synthetic world of **40 people**. Each person has a **city**, a **job** and a
**favourite food**. All text is generated from these facts by [`llm/data.py`](llm/data.py) with fixed random seeds, so the
data is identical on every computer. `python main.py data` (or `train`) regenerates this page and [`data/`](data/).

## Files

| File | Used for | Contents | Size |
| --- | --- | --- | --- |
| [`data/people.csv`](data/people.csv) | the facts (the "database") | 40 people × 3 attributes | 1,642 bytes |
| [`data/pretraining_text.txt`](data/pretraining_text.txt) | pre-training | 4,000 documents of plain sentences | 614,957 bytes |
| [`data/validation_text.txt`](data/validation_text.txt) | perplexity | 300 documents, new sentence combinations | 45,666 bytes |
| [`data/finetune_qa.txt`](data/finetune_qa.txt) | fine-tuning | 180 Q&A pairs about 30 people | 7,488 bytes |
| [`data/test_qa.txt`](data/test_qa.txt) | evaluation | 60 questions about the 10 held-out people | 2,512 bytes |

## How the data is split

- **Pre-training** text mentions all 40 people, so the model learns every fact.
- **Fine-tuning** questions cover only 30 people.
- The other **10 people are held out**: the model never sees a question about them. Answering them correctly
  proves it learned to *use* its knowledge, not memorise answers.

## The people (all facts)

Names in **bold** are the held-out test people.

| # | Name | City | Job | Food | Used for |
| --- | --- | --- | --- | --- | --- |
| 1 | Asha | Indore | painter | mangoes | fine-tuning |
| 2 | **Ravi** | Kochi | engineer | apples | test only (held out) |
| 3 | Meera | Indore | lawyer | apples | fine-tuning |
| 4 | **Kiran** | Jaipur | singer | samosas | test only (held out) |
| 5 | Arjun | Patna | pilot | idli | fine-tuning |
| 6 | Divya | Chennai | teacher | rice | fine-tuning |
| 7 | Rahul | Kochi | engineer | rice | fine-tuning |
| 8 | **Priya** | Chennai | lawyer | dosa | test only (held out) |
| 9 | Vikram | Delhi | chef | apples | fine-tuning |
| 10 | Anita | Patna | teacher | pasta | fine-tuning |
| 11 | **Suresh** | Indore | chef | rice | test only (held out) |
| 12 | Lakshmi | Mumbai | engineer | apples | fine-tuning |
| 13 | Karan | Mysore | engineer | idli | fine-tuning |
| 14 | Neha | Pune | engineer | mangoes | fine-tuning |
| 15 | **Manoj** | Delhi | painter | mangoes | test only (held out) |
| 16 | Kavya | Surat | nurse | pasta | fine-tuning |
| 17 | Rohan | Mumbai | chef | dosa | fine-tuning |
| 18 | **Sneha** | Mumbai | singer | samosas | test only (held out) |
| 19 | Ajay | Mumbai | pilot | paneer | fine-tuning |
| 20 | Pooja | Mysore | teacher | dosa | fine-tuning |
| 21 | Nikhil | Jaipur | engineer | apples | fine-tuning |
| 22 | **Isha** | Delhi | lawyer | paneer | test only (held out) |
| 23 | Varun | Kochi | teacher | paneer | fine-tuning |
| 24 | **Swati** | Jaipur | engineer | samosas | test only (held out) |
| 25 | Deepak | Surat | engineer | rice | fine-tuning |
| 26 | Tara | Kochi | nurse | dosa | fine-tuning |
| 27 | Gopal | Surat | painter | pasta | fine-tuning |
| 28 | **Leela** | Surat | farmer | idli | test only (held out) |
| 29 | Sanjay | Chennai | farmer | biryani | fine-tuning |
| 30 | Uma | Pune | singer | idli | fine-tuning |
| 31 | Harish | Mysore | teacher | dosa | fine-tuning |
| 32 | **Nisha** | Chennai | pilot | mangoes | test only (held out) |
| 33 | Mohan | Delhi | engineer | noodles | fine-tuning |
| 34 | Rekha | Patna | lawyer | paneer | fine-tuning |
| 35 | Anil | Mumbai | farmer | rice | fine-tuning |
| 36 | Geeta | Indore | singer | idli | fine-tuning |
| 37 | Vijay | Mysore | nurse | pasta | fine-tuning |
| 38 | Sita | Delhi | chef | rice | fine-tuning |
| 39 | Ramesh | Delhi | nurse | rice | fine-tuning |
| 40 | Jaya | Jaipur | farmer | samosas | fine-tuning |

## How often each value appears

Values are assigned at random, so some are common and some never appear (nobody is a doctor, so that word is never learned).

| Attribute | Counts (most common first) |
| --- | --- |
| city | Delhi 6, Mumbai 5, Indore 4, Kochi 4, Jaipur 4, Chennai 4, Mysore 4, Surat 4, Patna 3, Pune 2 |
| job | engineer 9, teacher 5, lawyer 4, singer 4, chef 4, nurse 4, farmer 4, painter 3, pilot 3, never: doctor |
| food | rice 7, apples 5, idli 5, dosa 5, mangoes 4, samosas 4, pasta 4, paneer 4, biryani 1, noodles 1 |

## Templates

Pre-training sentences use one of five phrasings per fact (`{n}` = name, `{v}` = value, `{a}` = a/an). Varied
phrasing is what lets the model later answer differently-worded questions.

- **city:** `{n} lives in {v}.` · `{n} is from {v}.` · `The home of {n} is in {v}.` · `{n} grew up in {v}.` · `Every morning {n} walks around {v}.`
- **job:** `{n} works as {a} {v}.` · `{n} is {a} {v}.` · `By profession, {n} is {a} {v}.` · `The job of {n} is {v}.` · `{n} has been {a} {v} for years.`
- **food:** `{n} loves {v}.` · `The favourite food of {n} is {v}.` · `{n} always eats {v}.` · `For dinner {n} likes {v}.` · `{n} enjoys {v} more than anything.`

Questions (fine-tuning and test), formatted as `Q: <question>` then `A: <answer>`:

- **city:** `Where does {n} live?` · `Which city is {n} from?`
- **job:** `What is the job of {n}?` · `What does {n} do for work?`
- **food:** `What food does {n} like?` · `What is the favourite food of {n}?`

## Samples

First 3 pre-training documents (separated by the `<|endoftext|>` token during training):

```text
The home of Vijay is in Mysore. The job of Priya is lawyer. For dinner Harish likes dosa. Neha grew up in Pune.
Deepak has been an engineer for years. For dinner Asha likes mangoes. The favourite food of Sneha is samosas.
Nikhil lives in Jaipur. Ravi enjoys apples more than anything. Asha is a painter.
```

First 4 fine-tuning examples:

```text
Q: What is the job of Sanjay?
A: farmer

Q: Where does Lakshmi live?
A: Mumbai

Q: What food does Asha like?
A: mangoes

Q: Where does Sanjay live?
A: Chennai
```

First 4 test questions (the model must produce the answer after `A:`):

```text
Q: What does Isha do for work?
A: lawyer

Q: What is the favourite food of Leela?
A: idli

Q: What does Manoj do for work?
A: painter

Q: What food does Suresh like?
A: rice
```
