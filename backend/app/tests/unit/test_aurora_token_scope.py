"""JWT capability isolation: anonymous survey tokens never grant account access."""
import pytest

from app.core.exceptions import AuthenticationError
from app.core.security import create_access_token, decode_access_token
from app.core.participant_tokens import create_participant_token, verify_participant_token


def test_participant_token_cannot_be_used_as_user_token():
    participant = create_participant_token(1)
    with pytest.raises(AuthenticationError):
        decode_access_token(participant)
    verify_participant_token(participant, 1)


def test_account_token_cannot_be_used_to_answer_survey():
    account = create_access_token(1)
    assert decode_access_token(account) == 1
    with pytest.raises(AuthenticationError):
        verify_participant_token(account, 1)
