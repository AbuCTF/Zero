import os

os.environ.setdefault("SECRET_KEY", "0123456789abcdef0123456789abcdef")

from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.api.admin import _campaign_target, _filter_campaign_participants
from app.models import Participant
from app.schemas import CampaignCreate, CampaignUpdate


def test_campaign_create_requires_a_name():
    with pytest.raises(ValueError):
        CampaignCreate(
            event_id=uuid4(),
            template_id=uuid4(),
            name="",
        )


def test_campaign_update_can_clear_schedule_without_replacing_template():
    update = CampaignUpdate(name="Final reminder", scheduled_at=None)
    assert update.name == "Final reminder"
    assert update.template_id is None
    assert update.model_fields_set == {"name", "scheduled_at"}


def test_campaign_target_rejects_unknown_filters():
    assert _campaign_target({"type": "prize_winners"}) == "prize_winners"
    with pytest.raises(HTTPException) as error:
        _campaign_target({"type": "unsupported"})
    assert error.value.status_code == 400


def test_campaign_prize_filters_are_applied_to_participant_queries():
    winners = str(
        _filter_campaign_participants(
            select(Participant),
            "prize_winners",
        )
    )
    without_prizes = str(
        _filter_campaign_participants(
            select(Participant),
            "no_prize",
        )
    )
    assert "EXISTS" in winners and "prizes" in winners
    assert "NOT (EXISTS" in without_prizes and "prizes" in without_prizes
