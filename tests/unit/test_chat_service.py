"""Unit coverage for chat_service.list_messages' chat= / include_total= parameters -
the piece of 1.3 that's awkward to observe through the HTTP layer, since the route
only ever passes a chat it just legitimately fetched itself. These exercise the
service function directly with a deliberately wrong `chat` to prove it's re-validated,
never trusted blindly."""

import pytest

from app.core.errors import NotFoundError
from app.models.chat import Chat
from app.models.user import User
from app.services import chat_service


async def _make_user(db_session, email: str) -> User:
    user = User(email=email, hashed_password="x")
    db_session.add(user)
    await db_session.commit()
    return user


async def _make_chat(db_session, *, user_id: str, title: str) -> Chat:
    chat = Chat(user_id=user_id, title=title)
    db_session.add(chat)
    await db_session.commit()
    return chat


@pytest.mark.asyncio
async def test_passing_a_matching_chat_is_accepted(db_session):
    user = await _make_user(db_session, "owner@example.com")
    chat = await _make_chat(db_session, user_id=user.id, title="mine")

    messages, total = await chat_service.list_messages(
        db_session, user_id=user.id, chat_id=chat.id, chat=chat, include_total=False
    )
    assert messages == []
    assert total == 0


@pytest.mark.asyncio
async def test_rejects_a_chat_belonging_to_a_different_user(db_session):
    owner = await _make_user(db_session, "owner2@example.com")
    attacker = await _make_user(db_session, "attacker@example.com")
    owners_chat = await _make_chat(db_session, user_id=owner.id, title="not yours")

    with pytest.raises(NotFoundError):
        await chat_service.list_messages(
            db_session,
            user_id=attacker.id,
            chat_id=owners_chat.id,
            chat=owners_chat,  # caller-supplied - must be re-validated, not trusted
        )


@pytest.mark.asyncio
async def test_rejects_a_chat_object_for_the_wrong_chat_id(db_session):
    """Even same-user, a chat object for a *different* chat_id than the one asked
    for must not be silently substituted."""
    user = await _make_user(db_session, "owner3@example.com")
    chat_a = await _make_chat(db_session, user_id=user.id, title="chat a")
    chat_b = await _make_chat(db_session, user_id=user.id, title="chat b")

    with pytest.raises(NotFoundError):
        await chat_service.list_messages(
            db_session, user_id=user.id, chat_id=chat_b.id, chat=chat_a
        )


@pytest.mark.asyncio
async def test_include_total_false_does_not_count(db_session):
    user = await _make_user(db_session, "owner4@example.com")
    chat = await _make_chat(db_session, user_id=user.id, title="chat")
    await chat_service.add_message(
        db_session, user_id=user.id, chat_id=chat.id, role="user", content="hi"
    )

    messages, total = await chat_service.list_messages(
        db_session, user_id=user.id, chat_id=chat.id, chat=chat, include_total=False
    )
    assert len(messages) == 1
    assert total == 0  # not counted - include_total=False short-circuits it to 0, not "really 0"


@pytest.mark.asyncio
async def test_include_total_true_still_counts(db_session):
    user = await _make_user(db_session, "owner5@example.com")
    chat = await _make_chat(db_session, user_id=user.id, title="chat")
    await chat_service.add_message(
        db_session, user_id=user.id, chat_id=chat.id, role="user", content="hi"
    )

    messages, total = await chat_service.list_messages(
        db_session, user_id=user.id, chat_id=chat.id, chat=chat, include_total=True
    )
    assert len(messages) == 1
    assert total == 1


@pytest.mark.asyncio
async def test_no_chat_passed_falls_back_to_a_fresh_lookup(db_session):
    """chat=None (the default) must behave exactly as before this change - a real
    get_chat() lookup, including rejecting another user's chat_id."""
    owner = await _make_user(db_session, "owner6@example.com")
    attacker = await _make_user(db_session, "attacker2@example.com")
    chat = await _make_chat(db_session, user_id=owner.id, title="mine")

    messages, total = await chat_service.list_messages(
        db_session, user_id=owner.id, chat_id=chat.id
    )
    assert messages == []
    assert total == 0

    with pytest.raises(NotFoundError):
        await chat_service.list_messages(db_session, user_id=attacker.id, chat_id=chat.id)
