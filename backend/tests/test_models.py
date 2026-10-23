"""Database rules: unique emails, hashed passwords, CHECK constraints, cascades, UTC timestamps."""
from datetime import timezone

import pytest
from sqlalchemy.exc import IntegrityError

from backend.app.extensions import db
from backend.app.models import (ActivityEvent, ChatMessage, ChatSession, Experiment, Metric, Person,
                                Result, User)


def experiment(owner, **kw):
    values = dict(owner_id=owner.id, name="run", pretrain_steps=150, finetune_steps=60)
    values.update(kw)
    return Experiment(**values)


def test_email_is_lowercase_and_unique(make_user):
    user = make_user(email="  Asha@Example.COM ")
    assert user.email == "asha@example.com"
    with pytest.raises(IntegrityError):
        make_user(email="ASHA@example.com")


def test_password_is_hashed(make_user):
    user = make_user(password="correct horse battery")
    assert "correct horse" not in user.password_hash and user.password_hash.startswith("scrypt:")
    assert user.check_password("correct horse battery")
    assert not user.check_password("wrong") and not user.check_password("") and not user.check_password(None)


def test_user_defaults(make_user):
    user = make_user()
    assert (user.role, user.is_active, user.theme, user.default_model) == ("member", True, "system", "lora")
    assert user.created_at.tzinfo == timezone.utc


@pytest.mark.parametrize("field, value", [("role", "superuser"), ("theme", "pink"),
                                          ("default_model", "gpt"), ("default_temperature", 3.0)])
def test_user_checks(make_user, field, value):
    user = make_user()
    setattr(user, field, value)
    with pytest.raises(IntegrityError):
        db.session.commit()


@pytest.mark.parametrize("field, value", [("lora_rank", 0), ("lora_rank", 33), ("pretrain_steps", 10),
                                          ("finetune_steps", 5000), ("status", "exploded"), ("progress", 1.5)])
def test_experiment_checks(make_user, field, value):
    db.session.add(experiment(make_user(), **{field: value}))
    with pytest.raises(IntegrityError):
        db.session.commit()


def test_experiment_defaults(make_user):
    exp = experiment(make_user())
    db.session.add(exp)
    db.session.commit()
    assert (exp.status, exp.progress, exp.is_public, exp.replay, exp.lora_rank, exp.cancel_requested) == \
        ("queued", 0.0, False, True, 8, False)


def test_metric_step_is_unique_per_phase(make_user):
    exp = experiment(make_user())
    exp.metrics += [Metric(phase="pretrain", step=0, train_loss=6.4), Metric(phase="lora", step=0, train_loss=7.2)]
    db.session.add(exp)
    db.session.commit()
    db.session.add(Metric(experiment_id=exp.id, phase="pretrain", step=0, train_loss=1.0))
    with pytest.raises(IntegrityError):
        db.session.commit()


def test_deleting_a_user_deletes_everything_they_own(make_user):
    keep, gone = make_user("keep@example.com"), make_user("gone@example.com")
    for owner in (keep, gone):
        exp = experiment(owner)
        exp.metrics.append(Metric(phase="pretrain", step=0, train_loss=6.4))
        exp.results.append(Result(model="lora", qa_seen=1, qa_heldout=1, completion=1, perplexity=2.7,
                                  trainable_params=49_152))
        session = ChatSession(user_id=owner.id, title="hello")
        session.messages.append(ChatMessage(role="user", content="Where does Asha live?", model="lora"))
        db.session.add_all([exp, session, ActivityEvent(user_id=owner.id, type="test", message="hi")])
    db.session.commit()

    # Delete with SQL, not the ORM, to prove the DATABASE enforces the cascade (ON DELETE CASCADE).
    db.session.execute(db.delete(User).where(User.id == gone.id))
    db.session.commit()
    for model in (Experiment, Metric, Result, ChatSession, ChatMessage, ActivityEvent):
        assert db.session.query(model).count() == 1, model.__name__


def test_activity_survives_experiment_deletion(make_user):
    user = make_user()
    exp = experiment(user)
    db.session.add(exp)
    db.session.flush()
    db.session.add(ActivityEvent(user_id=user.id, type="experiment.completed", message="done", experiment_id=exp.id))
    db.session.commit()
    db.session.execute(db.delete(Experiment).where(Experiment.id == exp.id))
    db.session.commit()
    event = db.session.query(ActivityEvent).one()
    db.session.refresh(event)
    assert event.experiment_id is None          # ON DELETE SET NULL: the history entry stays


def test_person_split_check(app):
    db.session.add(Person(name="Zed", city="Pune", job="chef", food="rice", split="training"))
    with pytest.raises(IntegrityError):
        db.session.commit()


def test_naive_datetimes_are_refused(make_user):
    from datetime import datetime
    user = make_user()
    user.last_login_at = datetime(2026, 1, 1)        # no timezone: ambiguous
    with pytest.raises(Exception, match="timezone-aware"):
        db.session.commit()
