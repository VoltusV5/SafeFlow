import pytest

from app.db.models.user import User
from app.db.repositories.base import BaseRepository


@pytest.mark.asyncio
async def test_base_repository_crud(async_session):
    repo = BaseRepository(User, async_session)

    # 1. Create
    user_data = {"tg_id": 12345, "username": "testuser"}
    user = await repo.create(user_data)
    assert user.id is not None
    assert user.tg_id == 12345

    # 2. Get
    fetched_user = await repo.get(user.id)
    assert fetched_user is not None
    assert fetched_user.username == "testuser"

    # 3. Update
    updated_user = await repo.update(user, {"username": "newname"})
    assert updated_user.username == "newname"

    # 4. Get All
    all_users = await repo.get_all()
    assert len(all_users) == 1

    # 5. Delete
    deleted = await repo.delete(user.id)
    assert deleted is True

    fetched_user_after_delete = await repo.get(user.id)
    assert fetched_user_after_delete is None
