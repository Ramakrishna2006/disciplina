"""
A small synthetic "world" so the whole pipeline trains on a laptop CPU in minutes,
yet still shows every real LLM phenomenon:

* PRE-TRAINING corpus : unstructured sentences stating facts about 40 people
                         ("Asha lives in Pune. The favourite food of Asha is dosa. ...")
* FINE-TUNING data    : question/answer pairs in a chat-like format ("Q: Where does Asha live?\nA: Pune")
                         for 30 "train" people only.
* EVALUATION          : the same questions for the 10 held-out people. The model has only ever seen
                         their facts as plain text during pre-training, so answering correctly proves it
                         learned to *extract knowledge* -- exactly what instruction tuning does for real LLMs.
"""
import random

from .tokenizer import EOT

NAMES = ["Asha", "Ravi", "Meera", "Kiran", "Arjun", "Divya", "Rahul", "Priya", "Vikram", "Anita",
         "Suresh", "Lakshmi", "Karan", "Neha", "Manoj", "Kavya", "Rohan", "Sneha", "Ajay", "Pooja",
         "Nikhil", "Isha", "Varun", "Swati", "Deepak", "Tara", "Gopal", "Leela", "Sanjay", "Uma",
         "Harish", "Nisha", "Mohan", "Rekha", "Anil", "Geeta", "Vijay", "Sita", "Ramesh", "Jaya"]
CITIES = ["Pune", "Delhi", "Chennai", "Mumbai", "Kochi", "Jaipur", "Indore", "Mysore", "Patna", "Surat"]
JOBS = ["doctor", "teacher", "pilot", "farmer", "lawyer", "chef", "painter", "nurse", "engineer", "singer"]
FOODS = ["mangoes", "dosa", "biryani", "samosas", "idli", "pasta", "noodles", "apples", "paneer", "rice"]

ATTRS = {"city": CITIES, "job": JOBS, "food": FOODS}


def article(word):
    return "an" if word[0] in "aeiou" else "a"


# Many paraphrases per fact: diverse phrasing in pre-training is what lets a model
# later retrieve the fact from a differently-worded question.
FACT_TEMPLATES = {
    "city": ["{n} lives in {v}.", "{n} is from {v}.", "The home of {n} is in {v}.",
             "{n} grew up in {v}.", "Every morning {n} walks around {v}."],
    "job": ["{n} works as {a} {v}.", "{n} is {a} {v}.", "By profession, {n} is {a} {v}.",
            "The job of {n} is {v}.", "{n} has been {a} {v} for years."],
    "food": ["{n} loves {v}.", "The favourite food of {n} is {v}.", "{n} always eats {v}.",
             "For dinner {n} likes {v}.", "{n} enjoys {v} more than anything."],
}

QUESTION_TEMPLATES = {
    "city": ["Where does {n} live?", "Which city is {n} from?"],
    "job": ["What is the job of {n}?", "What does {n} do for work?"],
    "food": ["What food does {n} like?", "What is the favourite food of {n}?"],
}

# "Completion-style" prompts that match the pre-training text (used in prompt engineering)
COMPLETION_PROMPTS = {"city": "{n} lives in", "job": "The job of {n} is", "food": "{n} loves"}


def build_world(seed=0):
    rng = random.Random(seed)
    world = {n: {a: rng.choice(vals) for a, vals in ATTRS.items()} for n in NAMES}
    names = NAMES[:]
    rng.shuffle(names)
    return world, names[:30], names[30:]   # facts, train people, held-out people


def fact_sentence(name, attr, value, rng):
    t = rng.choice(FACT_TEMPLATES[attr])
    return t.format(n=name, v=value, a=article(value))


def pretraining_corpus(world, n_docs=4000, seed=0):
    """Documents = 3-6 random fact sentences, separated by <|endoftext|>."""
    rng = random.Random(seed)
    people = list(world)
    docs = []
    for _ in range(n_docs):
        sents = []
        for _ in range(rng.randint(3, 6)):
            n = rng.choice(people)
            a = rng.choice(list(ATTRS))
            sents.append(fact_sentence(n, a, world[n][a], rng))
        docs.append(" ".join(sents))
    return EOT.join(docs) + EOT


def qa_prompt(question):
    return f"Q: {question}\nA:"


def qa_examples(world, people, seed=0, all_templates=True):
    """(prompt, answer, attr, name) tuples. Answer starts with a space (it follows 'A:')."""
    rng = random.Random(seed)
    out = []
    for n in people:
        for a, temps in QUESTION_TEMPLATES.items():
            for t in (temps if all_templates else [rng.choice(temps)]):
                out.append((qa_prompt(t.format(n=n)), " " + world[n][a], a, n))
    rng.shuffle(out)
    return out
