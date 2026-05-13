"""
Tests for /api/auth/* routes.
Covers: register, login, me, error cases.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.models.user import User


@pytest.mark.asyncio
class TestRegister:
    async def test_register_success(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/auth/register",
            json={"email": "new@example.com", "password": "SecurePass1!", "full_name": "New User"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "new@example.com"
        assert data["full_name"] == "New User"
        assert "id" in data
        assert "hashed_password" not in data

    async def test_register_duplicate_email(self, client: AsyncClient, test_user: User) -> None:
        response = await client.post(
            "/api/auth/register",
            json={"email": test_user.email, "password": "AnotherPass1!"},
        )
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    async def test_register_weak_password(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/auth/register",
            json={"email": "weak@example.com", "password": "short"},
        )
        assert response.status_code == 422

    async def test_register_invalid_email(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/auth/register",
            json={"email": "not-an-email", "password": "ValidPass123!"},
        )
        assert response.status_code == 422


@pytest.mark.asyncio
class TestLogin:
    async def test_login_success(self, client: AsyncClient, test_user: User) -> None:
        response = await client.post(
            "/api/auth/login",
            json={"email": test_user.email, "password": "TestPass123!"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client: AsyncClient, test_user: User) -> None:
        response = await client.post(
            "/api/auth/login",
            json={"email": test_user.email, "password": "WrongPass!"},
        )
        assert response.status_code == 401

    async def test_login_nonexistent_user(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/auth/login",
            json={"email": "ghost@example.com", "password": "DoesntMatter1!"},
        )
        assert response.status_code == 401

    async def test_login_inactive_user(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        test_user.is_active = False
        await db_session.flush()

        response = await client.post(
            "/api/auth/login",
            json={"email": test_user.email, "password": "TestPass123!"},
        )
        assert response.status_code in (401, 403)


@pytest.mark.asyncio
class TestGetMe:
    async def test_get_me_success(self, client: AsyncClient, test_user: User) -> None:
        response = await client.get("/api/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email

    async def test_get_me_no_token(self, unauthed_client: AsyncClient) -> None:
        response = await unauthed_client.get("/api/auth/me")
        assert response.status_code == 403  # Missing bearer scheme

    async def test_get_me_bad_token(self, unauthed_client: AsyncClient) -> None:
        response = await unauthed_client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer totally.invalid.token"},
        )
        assert response.status_code == 401
