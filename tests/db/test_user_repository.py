import pytest

from app.db.repositories.user import UserRepository


@pytest.mark.asyncio
async def test_user_repository_get_by_tg_id(async_session):
    repo = UserRepository(async_session)

    # 1. Create user
    user_data = {"tg_id": 9999, "username": "tg_user"}
    user = await repo.create(user_data)

    # 2. Get by tg_id
    fetched_user = await repo.get_by_tg_id(9999)
    assert fetched_user is not None
    assert fetched_user.id == user.id

    # 3. Non-existent tg_id
    none_user = await repo.get_by_tg_id(8888)
    assert none_user is None
