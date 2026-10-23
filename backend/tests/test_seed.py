"""`flask seed`: loads exactly the training data and the published run, and never deletes anything."""
import json

from backend.app.extensions import db
from backend.app.models import Experiment, Metric, Person, Result, User
from llm.dataset import splits


def run_seed(app):
    result = app.test_cli_runner().invoke(args=["seed"])
    assert result.exit_code == 0, result.output
    return result.output


def test_seed_loads_the_training_people(app):
    out = run_seed(app)
    assert "people: 40 added" in out and "reference experiment: added" in out
    s = splits()
    people = {p.name: p for p in db.session.query(Person)}
    assert set(people) == set(s["world"])
    for name, facts in s["world"].items():
        p = people[name]
        assert (p.city, p.job, p.food) == (facts["city"], facts["job"], facts["food"])
        assert p.split == ("fine-tuning" if name in s["train_people"] else "held-out")
    assert sum(p.split == "held-out" for p in people.values()) == 10


def test_seed_loads_the_reference_experiment(app):
    run_seed(app)
    exp = db.session.query(Experiment).one()
    assert exp.is_public and exp.status == "completed" and exp.progress == 1.0
    assert (exp.pretrain_steps, exp.finetune_steps, exp.lora_rank, exp.replay) == (2000, 400, 8, True)
    with open(app.config["ARTIFACTS_DIR"] / "results.json", encoding="utf-8") as f:
        r = json.load(f)
    lora = db.session.query(Result).filter_by(model="lora").one()
    assert lora.qa_heldout == r["evaluation"]["LoRA"]["qa_heldout"] == 1.0
    assert lora.perplexity == r["evaluation"]["LoRA"]["val_ppl"] and lora.trainable_params == 49_152
    n_points = len(r["pretraining"]) + sum(len(v) for v in r["finetuning"].values())
    assert db.session.query(Metric).count() == n_points


def test_reference_owner_cannot_sign_in(app):
    run_seed(app)
    owner = db.session.query(User).one()
    assert owner.is_active is False and not owner.check_password("")


def test_seed_twice_adds_nothing_and_keeps_your_data(app, make_user):
    you = make_user()
    db.session.add(Person(name="Zara", city="Goa", job="pilot", food="fish", split="held-out"))
    db.session.commit()
    run_seed(app)
    out = run_seed(app)
    assert "people: 0 added" in out and "already there" in out
    assert db.session.query(Person).count() == 41                        # 40 + Zara, nothing duplicated
    assert db.session.query(Experiment).count() == 1
    assert db.session.get(User, you.id) is not None                       # your account is untouched
