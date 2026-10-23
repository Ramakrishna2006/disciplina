"""
Command-line tools, run from the repository folder:

    flask --app backend.app seed            add the 40 people and the published reference experiment
    flask --app backend.app create-admin    create an admin account (asks for the password)

`seed` only ADDS rows that are missing. Running it twice changes nothing, and it never deletes
or overwrites your data. (Stage 8 adds export-data and import-data here.)
"""
import json
import secrets

import click
from flask import current_app

from .extensions import db
from .models import Experiment, Metric, Person, Result, User
from .models.base import utcnow
from .schemas.auth import RegisterIn

REFERENCE_OWNER = "reference@disciplina.local"
REFERENCE_NAME = "Published reference run"
TRAINABLE = {"base": 512_544, "full": 512_544, "lora": 49_152}    # from the engine: GPT.num_params(True)
MODEL_KEYS = {"base": "base", "full-FT": "full", "LoRA": "lora"}   # results.json name -> database name


def seed_people():
    """The 40 people exactly as training used them (rebuilt from the engine's fixed seeds)."""
    from llm.dataset import splits

    s = splits()
    train = set(s["train_people"])
    existing = {name for (name,) in db.session.query(Person.name)}
    added = 0
    for name, facts in s["world"].items():
        if name not in existing:
            db.session.add(Person(name=name, city=facts["city"], job=facts["job"], food=facts["food"],
                                  split="fine-tuning" if name in train else "held-out"))
            added += 1
    return added


def reference_owner():
    """The published run belongs to a built-in account that cannot sign in (inactive, random password)."""
    user = db.session.query(User).filter_by(email=REFERENCE_OWNER).one_or_none()
    if user is None:
        user = User(email=REFERENCE_OWNER, name="Disciplina", role="member", is_active=False)
        user.set_password(secrets.token_urlsafe(32))
        db.session.add(user)
        db.session.flush()   # gives the user an id without committing yet
    return user


def seed_reference_experiment():
    """The full training run shipped in artifacts/, as a public, completed experiment."""
    owner = reference_owner()
    if db.session.query(Experiment).filter_by(owner_id=owner.id, name=REFERENCE_NAME).first():
        return False
    path = current_app.config["ARTIFACTS_DIR"] / "results.json"
    with open(path, encoding="utf-8") as f:
        r = json.load(f)
    config = r.get("config", {})
    now = utcnow()
    exp = Experiment(owner_id=owner.id, name=REFERENCE_NAME, is_public=True, status="completed",
                     description=f"The models shipped in artifacts/: trained in {r.get('minutes', '?')} min on a laptop CPU.",
                     pretrain_steps=config.get("pretrain_steps", 2000), finetune_steps=config.get("finetune_steps", 400),
                     lora_rank=config.get("lora_rank", 8), replay=config.get("replay", True), seed=config.get("seed", 0),
                     phase="evaluate", progress=1.0, created_at=now, started_at=now, finished_at=now)
    for h in r["pretraining"]:
        exp.metrics.append(Metric(phase="pretrain", step=h["step"], train_loss=h["train_loss"], val_loss=h["val_loss"]))
    for key, history in r["finetuning"].items():
        for h in history:
            exp.metrics.append(Metric(phase=MODEL_KEYS[key], step=h["step"], train_loss=h["loss"]))
    for key, ev in r["evaluation"].items():
        model = MODEL_KEYS[key]
        exp.results.append(Result(model=model, qa_seen=ev["qa_seen"], qa_heldout=ev["qa_heldout"],
                                  completion=ev["completion"], perplexity=ev["val_ppl"],
                                  trainable_params=TRAINABLE[model]))
    db.session.add(exp)
    return True


def register_cli(app):
    register_admin_cli(app)

    @app.cli.command("seed")
    def seed():
        """Add the 40 people and the reference experiment (only what is missing)."""
        people = seed_people()
        experiment = seed_reference_experiment()
        db.session.commit()   # one transaction: everything is saved, or nothing is
        click.echo(f"people: {people} added ({db.session.query(Person).count()} in total)")
        click.echo(f"reference experiment: {'added' if experiment else 'already there'}")


def register_admin_cli(app):
    @app.cli.command("create-admin")
    @click.option("--email", prompt=True, help="Email address of the admin account.")
    @click.option("--name", prompt=True, default="Admin", show_default=True)
    def create_admin(email, name):
        """Create an admin, or make an existing account an admin. The password is typed in (hidden)
        and never stored in code, files or the shell history."""
        from pydantic import ValidationError

        email = email.strip().lower()
        user = db.session.query(User).filter_by(email=email).one_or_none()
        if user is not None:
            user.role, user.is_active = "admin", True
            db.session.commit()
            click.echo(f"{email} is now an admin (password unchanged).")
            return
        password = click.prompt("Password (at least 10 characters)", hide_input=True, confirmation_prompt=True)
        try:
            body = RegisterIn(name=name, email=email, password=password)   # same rules as the website
        except ValidationError as e:
            raise click.ClickException("; ".join(f"{err['loc'][0]}: {err['msg']}" for err in e.errors())) from None
        user = User(email=body.email, name=body.name, role="admin")
        user.set_password(body.password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Admin account created: {body.email}")
