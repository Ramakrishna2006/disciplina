"""
Prompt engineering experiments.

The SAME frozen model can look useless or smart depending only on how you ask.
We compare three prompt styles on the base (pre-trained only) model and on fine-tuned models:

  zero-shot   : "Q: Where does Asha live?\nA:"           (a format the base model never saw)
  few-shot    : 3 solved examples first, then the question (in-context learning)
  completion  : "Asha lives in"                            (phrased like the pre-training text)
"""
from .data import COMPLETION_PROMPTS, QUESTION_TEMPLATES, qa_prompt


def zero_shot(item):
    return item[0]


def make_few_shot(world, shot_people):
    """Build a few-shot prefix from people NOT in the evaluation set (no answer leakage)."""
    attrs = list(QUESTION_TEMPLATES)
    shots = []
    for i, n in enumerate(shot_people[:3]):
        a = attrs[i % len(attrs)]
        shots.append(qa_prompt(QUESTION_TEMPLATES[a][0].format(n=n)) + " " + world[n][a])
    prefix = "\n".join(shots) + "\n"

    def few_shot(item):
        return prefix + item[0]
    return few_shot


def completion_style(item):
    return COMPLETION_PROMPTS[item[2]].format(n=item[3])


PROMPT_STYLES = ["zero-shot", "few-shot", "completion"]


def prompt_functions(world, shot_people):
    return {"zero-shot": zero_shot,
            "few-shot": make_few_shot(world, shot_people),
            "completion": completion_style}
