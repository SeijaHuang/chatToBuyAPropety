# PropertyAI — Database Layer

## Technical PRD v1.0

| Field           | Value                                   |
| --------------- | --------------------------------------- |
| Version         | v1.0                                    |
| Status          | **Implemented**                         |
| Parent Document | PropertyAI_Part1_Technical_PRD_v1_1.md  |
| Scope           | PostgreSQL + SQLAlchemy ORM + `chats` table |
| Last Updated    | 28 Jun 2026                             |

---

## Table of Contents

1. [Objectives and Scope](#1-objectives-and-scope)
2. [Design Decisions](#2-design-decisions)
3. [Tech Stack](#3-tech-stack)
4. [Schema: `chats` Table](#4-schema-chats-table)
5. [ORM Model](#5-orm-model)
6. [Connection Management](#6-connection-management)
7. [Repository Layer](#7-repository-layer)
8. [Write Rules — Progressive Snapshot](#8-write-rules--progressive-snapshot)
9. [Migration Strategy (Alembic)](#9-migration-strategy-alembic)
10. [Project Structure](#10-project-structure)
11. [Environment Variables](#11-environment-variables)
12. [Test Strategy](#12-test-strategy)
13. [Acceptance Criteria](#13-acceptance-criteria)
14. [Future: users / anonymous_users Tables](#14-future-users--anonymous_users-tables)

---

## 1. Objectives and Scope

### 1.1 Objective

建立 PostgreSQL 持久化层，包含：ORM 定义、连接管理、Repository 接口、以及对话会话的渐进式快照写入。`chats` 表是 Part 1 结构化业务数据的唯一权威存储。

### 1.2 In Scope (P1-A — 已实现)

- SQLAlchemy 2.0 async ORM 模型定义（`chats` 表）
- `AsyncEngine` + `async_sessionmaker` 连接池生命周期管理
- `IChatRepository` Protocol + `SqlAlchemyChatRepository` 实现
- Alembic 迁移（`env.py` 同步 psycopg2 模式 + `993128e7e195_create_chats` migration）
- 第一条消息发送时触发初始 upsert（确保 chat history 可见，即使尚未完成任何模块）
- 每模块完成时通过 FastAPI `BackgroundTasks` 继续渐进式 upsert
- `/health` 端点新增 `postgres` 健康检查

### 1.3 Out of Scope

- `users` 表、`anonymous_users` 表（P1-B）
- 外键约束到 `users`/`anonymous_users`（P1-B 再加 Alembic migration）
- `conversation_history` 持久化（体积大，无结构化查询需求）
- `budget_gap` 持久化（派生值，Part 2 按需重算）
- Redis 层（已在 `redis_store/` 实现）

---

## 2. Design Decisions

### 2.1 表名 `chats`，主键列名 `session_id`

表名使用 `chats`（而非 Part 1 PRD §5 的 `sessions`）——更准确地反映业务语义，一条记录代表一次完整的属性需求收集对话。

主键列名保持 **`session_id`**，与以下所有位置的命名完全一致：

| 位置                           | 名称         |
| ------------------------------ | ------------ |
| Redis key `session:{session_id}` | `session_id` |
| `ConversationStateDTO.session_id` | `session_id` |
| `ChatRequest.session_id`          | `session_id` |
| `RoutingPayload.session_id`       | `session_id` |
| `UserNeeds.session_id`            | `session_id` |
| `chats` 表主键列                  | `session_id` |

### 2.2 ORM：SQLAlchemy 2.0 Async（应用层），Sync（迁移层）

应用层（`connection.py`、`repositories/chat.py`）使用 SQLAlchemy 2.0 async ORM（`AsyncSession`）。迁移层（`db/alembic/env.py`）使用同步 psycopg2，通过正则将 `DATABASE_URL` 中的 `postgresql+asyncpg` 替换为 `postgresql`，原因：

| 关注点   | 说明 |
| -------- | ---- |
| 迁移稳定性 | Alembic 同步模式更成熟，兼容性更好 |
| 驱动隔离 | 迁移用 psycopg2，运行时用 asyncpg，两者互不干扰 |
| 简洁性   | 避免在迁移脚本中引入 `asyncio.run()` 嵌套 |

asyncpg 仍作为应用层底层驱动（`postgresql+asyncpg://`），SQLAlchemy 不替换驱动，只增加映射层。

### 2.3 Repository 命名：`chat_repository` → `db/repositories/chat.py`

数据库操作全部封装在 `db/repositories/chat.py` 中，Protocol 名 `IChatRepository`，实现类名 `SqlAlchemyChatRepository`。文件名与表名 `chats` 对齐。

`get_chat_repository()` 是 FastAPI 依赖函数，无需参数——内部直接调用 `get_session_factory()`，比通过 `Depends` 传入 factory 更简洁，且 `get_session_factory()` 本身在 engine 未初始化时会抛出 `RuntimeError`，等同于依赖注入的守卫效果。

### 2.4 `anon_id` 设计（已更新）

`chats.anon_id` 是 `users.anon_id` 的去规范化副本，无外键约束，靠 `idx_chats_anon_id` 索引支持高效查询。详见 [PropertyAI_Anonymous_User_PRD_v1_0.md](PropertyAI_Anonymous_User_PRD_v1_0.md) §2.3。

`user_id` 列已从 `chats` 表移除——P1-A 无 auth，前端只传 `anon_id`，P1-B 登录实现后再加。

### 2.5 本地开发禁用 SSL

`create_async_engine` 传入 `connect_args={"ssl": False}`，避免本地 Docker postgres（无 SSL 证书）连接失败。生产环境需移除该参数并配置正确的 SSL 证书。

## 3. Tech Stack

| Layer        | Technology                                             |
| ------------ | ------------------------------------------------------ |
| ORM          | SQLAlchemy 2.0 (`sqlalchemy[asyncio]>=2.0`)            |
| Async driver | asyncpg（应用层，DSN 前缀 `postgresql+asyncpg://`）     |
| Sync driver  | psycopg2（Alembic 迁移层专用，DSN 前缀 `postgresql://`） |
| Migrations   | Alembic (`alembic>=1.13`)                              |
| Column types | `UUID`, `Text`, `JSONB`, `TIMESTAMP` (via `sqlalchemy.dialects.postgresql`) |

### 3.1 依赖（`pyproject.toml`）

```toml
dependencies = [
    "sqlalchemy[asyncio]>=2.0.0",
    "alembic>=1.13.0",
    "asyncpg",      # async driver for application
    "psycopg2",     # sync driver for Alembic migrations
]
```

同步更新 `requirements.txt`。

---

## 4. Schema: `chats` Table

以下为与 ORM 模型对应的逻辑 DDL：

```sql
CREATE TABLE chats (
    -- Identity（主键列名与 Redis / DTO 保持一致）
    session_id         UUID        PRIMARY KEY,

    -- Owner（两列均可为 NULL，也可同时非 NULL，无 FK 约束，靠索引查询）
    anon_id            UUID        NULL,   -- 浏览器/设备身份，P0 起写入
    user_id            UUID        NULL,   -- 注册身份，P1-B 登录后写入

    -- Conversation state
    status             TEXT        NOT NULL DEFAULT 'IN_PROGRESS',
    schema_version     TEXT        NOT NULL DEFAULT '1.1',
    initial_intent     TEXT        NULL,

    -- Structured business data (progressive snapshot)
    collected_data     JSONB       NOT NULL DEFAULT '{}',
    final_needs        JSONB       NULL,
    borrowing_capacity JSONB       NULL,

    -- Timestamps
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at       TIMESTAMPTZ NULL
);

CREATE INDEX idx_chats_status     ON chats (status);
CREATE INDEX idx_chats_updated_at ON chats (updated_at DESC);
CREATE INDEX idx_chats_anon_id    ON chats (anon_id)  WHERE anon_id IS NOT NULL;
CREATE INDEX idx_chats_user_id    ON chats (user_id)  WHERE user_id IS NOT NULL;
```

> `chk_chats_single_owner` CHECK 约束已通过 migration `2f156e1dbbc7` 删除——单表设计下注册用户同样持有 `anon_id`，P1-B 登录后新对话可同时写入两列。详见 [PropertyAI_Anonymous_User_PRD_v1_0.md](PropertyAI_Anonymous_User_PRD_v1_0.md) §2.5。

### 4.1 Column Reference

| Column               | SQLAlchemy Type       | Nullable | Description                                                              |
| -------------------- | --------------------- | -------- | ------------------------------------------------------------------------ |
| `session_id`         | `UUID` (PK)           | No       | UUID v4，后端生成；等同于 Redis key `session:{session_id}`               |
| `anon_id`            | `UUID`                | Yes      | 去规范化的 `users.anon_id`，无 FK；P0 起写入，靠 `idx_chats_anon_id` 查询；可与 `user_id` 同时非 NULL |
| `user_id`            | `UUID`                | Yes      | 注册用户身份；P1-B 登录后写入，靠 `idx_chats_user_id` 查询；可与 `anon_id` 同时非 NULL |
| `status`             | `Text`                | No       | `IN_PROGRESS` / `REQUIREMENTS_COMPLETE`                                  |
| `schema_version`     | `Text`                | No       | Fixed `'1.1'`                                                            |
| `initial_intent`     | `Text`                | Yes      | Written on M1 completion (e.g. `recommend_suburbs`)                      |
| `collected_data`     | `JSONB`               | No       | Progressive snapshot of M1–M4 collected fields                           |
| `final_needs`        | `JSONB`               | Yes      | Full `UserNeeds` written after M4 completion                             |
| `borrowing_capacity` | `JSONB`               | Yes      | `BorrowingCapacityResult` written after M4 completion (if salary given)  |
| `created_at`         | `TIMESTAMP WITH TZ`   | No       | Auto-set on INSERT via `server_default=func.now()`                       |
| `updated_at`         | `TIMESTAMP WITH TZ`   | No       | Auto-set on INSERT; updated on every upsert via `datetime.now(tz=UTC)`   |
| `completed_at`       | `TIMESTAMP WITH TZ`   | Yes      | Set when `status` → `REQUIREMENTS_COMPLETE`; used for analytics          |

---

## 5. ORM Model

`db/models/` 是 ORM 模型的专属子包，**每张表一个文件**。`Base` 单独放 `base.py`，避免循环 import，并与 `backend/models/`（Pydantic DTO 层）形成命名空间隔离。

> **两层 `models` 的职责边界：**
> - `backend/models/` — Pydantic `BaseModel`，用于 HTTP 请求/响应序列化
> - `db/models/` — SQLAlchemy `DeclarativeBase` 子类，仅用于数据库行映射，不对外暴露给路由层

### 5.1 `db/models/base.py`

```python
# db/models/base.py
"""Shared SQLAlchemy declarative base for all ORM models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Single declarative base for the entire project.

    All ORM model classes must inherit from this Base so that
    Base.metadata contains every table for Alembic autogenerate.
    """
```

### 5.2 `db/models/chat.py`

```python
# db/models/chat.py
"""ORM model for the chats table."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Index, Text, func
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.models.base import Base


class ChatRow(Base):
    """ORM mapping for the chats table.

    Stores one row per conversation session. Progressive upserts accumulate
    collected_data as each module (M1–M4) is completed.
    """

    __tablename__ = "chats"

    __table_args__ = (
        Index("idx_chats_status", "status"),
        Index("idx_chats_updated_at", "updated_at"),
        Index("idx_chats_anon_id", "anon_id", postgresql_where="anon_id IS NOT NULL"),
    )

    # Identity — column name matches session_id used everywhere else
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)

    # Owner — denormalized copy of users.anon_id; no FK, query via idx_chats_anon_id
    anon_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Conversation state
    status: Mapped[str] = mapped_column(Text, nullable=False, default="IN_PROGRESS")
    schema_version: Mapped[str] = mapped_column(Text, nullable=False, default="1.1")
    initial_intent: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Structured business data
    collected_data: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    final_needs: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    borrowing_capacity: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
```

### 5.3 `db/models/__init__.py`

```python
# db/models/__init__.py
"""ORM model registry — import all Row classes here so Alembic can discover them."""

from db.models.base import Base
from db.models.chat import ChatRow

__all__ = ["Base", "ChatRow"]
```

> Alembic `env.py` 只需 `from db.models import Base` 即可获取含所有表的 `Base.metadata`。**新增表时只在此 `__init__.py` 补一行 import，无需修改 `env.py`。**

---

## 6. Connection Management

### 6.1 File

```
backend/db/connection.py
```

### 6.2 实现

```python
# db/connection.py
"""AsyncEngine and session factory lifecycle management."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config import settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def create_engine_async() -> None:
    """Initialise the async engine and session factory.

    Called once during FastAPI lifespan startup.
    """
    global _engine, _session_factory
    _engine = create_async_engine(
        settings.database_url,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        echo=False,
        connect_args={"ssl": False},  # disabled for local Docker dev; remove in production
    )
    _session_factory = async_sessionmaker(
        bind=_engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )


async def close_engine_async() -> None:
    """Dispose the engine. Called during FastAPI lifespan shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the active session factory.

    Raises:
        RuntimeError: If called before create_engine_async() has completed.
    """
    if _session_factory is None:
        raise RuntimeError("DB engine not initialised — call create_engine_async() first.")
    return _session_factory


async def get_db_session_async() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency — yields a managed AsyncSession per request.

    Usage:
        session: AsyncSession = Depends(get_db_session_async)
    """
    factory: async_sessionmaker[AsyncSession] = get_session_factory()
    async with factory() as session:
        yield session
```

> **注意**：`connect_args={"ssl": False}` 仅用于本地 Docker 开发环境（postgres 容器不配置 SSL 证书）。生产环境应移除此参数，并通过 `DATABASE_URL` 或 `connect_args` 配置正确的 SSL 设置。

### 6.3 FastAPI Lifespan 集成

```python
# main.py
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from db.connection import create_engine_async, close_engine_async
from redis_store.client import redis_client


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage Redis and PostgreSQL connection lifecycle for the application."""
    await redis_client.connect_async()
    await create_engine_async()
    yield
    await close_engine_async()
    await redis_client.close_async()


app = FastAPI(title="PropertyAI API", version="0.1.0", lifespan=lifespan)
```

> Redis 通过 `redis_client` 单例（`redis_store/client.py`）管理，调用其实例方法 `connect_async()` / `close_async()`，而非模块级函数。

### 6.4 `/health` 端点

`/health` 端点同时检查 Redis 和 PostgreSQL 连通性，两者均正常返回 `"ok"`，任一异常返回 `"degraded"`：

```python
@app.get("/health")
async def health_check_async() -> dict[str, object]:
    """Return service liveness status including Redis and PostgreSQL connectivity."""
    redis_ok: bool = await redis_client.ping_async()

    postgres_ok: bool = False
    try:
        factory: async_sessionmaker[AsyncSession] = get_session_factory()
        async with factory() as session:
            await session.execute(text("SELECT 1"))
        postgres_ok = True
    except Exception:
        pass

    all_ok: bool = redis_ok and postgres_ok
    status: str = "ok" if all_ok else "degraded"
    return {
        "status": status,
        "version": "0.1.0",
        "services": {
            "redis": "ok" if redis_ok else "error",
            "postgres": "ok" if postgres_ok else "error",
        },
    }
```

---

## 7. Repository Layer

`db/repositories/` 是 CRUD 操作的专属子包，与 `db/models/` 按层对称：**每张表一个文件**，文件名与对应的 ORM model 文件名相同。

### 7.1 `db/repositories/chat.py`

#### IChatRepository Protocol

```python
# db/repositories/chat.py
"""Repository for the chats table — Protocol + SQLAlchemy implementation."""

from typing import Protocol

from models.conversation_state import ConversationStateDTO


class IChatRepository(Protocol):
    """Persistence contract for the chats table."""

    async def upsert_chat_snapshot_async(self, state: ConversationStateDTO) -> None:
        """Write or update the chats row for the given session.

        Called after each module completes. Idempotent — repeated calls with
        the same state produce the same row, not duplicate rows.
        Exceptions must be logged and suppressed; must never propagate to the caller.
        """
        ...
```

#### SqlAlchemyChatRepository

```python
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Protocol

import structlog
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db.connection import get_session_factory
from db.models.chat import ChatRow
from models.conversation_state import ConversationStateDTO, EStatus

logger: structlog.BoundLogger = structlog.get_logger()


class SqlAlchemyChatRepository:
    """SQLAlchemy-backed implementation of IChatRepository.

    Uses PostgreSQL's INSERT ... ON CONFLICT DO UPDATE for atomic upserts.
    COALESCE guards ensure initial_intent and completed_at are never
    overwritten by NULL once written.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def upsert_chat_snapshot_async(self, state: ConversationStateDTO) -> None:
        """Upsert the chats row. Exceptions are logged and suppressed."""
        try:
            await self._do_upsert_async(state)
        except Exception:
            logger.exception("db_upsert_failed", session_id=state.session_id)

    async def _do_upsert_async(self, state: ConversationStateDTO) -> None:
        """Execute the PostgreSQL upsert statement."""
        collected: dict[str, object] = state.collected_data.model_dump(by_alias=False)
        final_needs: dict[str, object] | None = (
            state.final_needs.model_dump(by_alias=False) if state.final_needs is not None else None
        )
        borrowing: dict[str, object] | None = (
            asdict(state.borrowing_capacity) if state.borrowing_capacity is not None else None
        )
        completed_at: datetime | None = (
            datetime.now(tz=UTC) if state.status == EStatus.REQUIREMENTS_COMPLETE else None
        )
        initial_intent: str | None = (
            state.initial_intent.value if state.initial_intent is not None else None
        )

        stmt = (
            pg_insert(ChatRow)
            .values(
                session_id=uuid.UUID(state.session_id),
                status=state.status.value,
                schema_version="1.1",
                initial_intent=initial_intent,
                collected_data=collected,
                final_needs=final_needs,
                borrowing_capacity=borrowing,
                completed_at=completed_at,
            )
            .on_conflict_do_update(
                index_elements=["session_id"],
                set_={
                    "status": pg_insert(ChatRow).excluded.status,
                    # COALESCE: once written, initial_intent is never overwritten by NULL
                    "initial_intent": func.coalesce(
                        pg_insert(ChatRow).excluded.initial_intent,
                        ChatRow.initial_intent,
                    ),
                    "collected_data": pg_insert(ChatRow).excluded.collected_data,
                    "final_needs": pg_insert(ChatRow).excluded.final_needs,
                    "borrowing_capacity": pg_insert(ChatRow).excluded.borrowing_capacity,
                    "updated_at": datetime.now(tz=UTC),
                    # COALESCE: once written, completed_at is never overwritten by NULL
                    "completed_at": func.coalesce(
                        pg_insert(ChatRow).excluded.completed_at,
                        ChatRow.completed_at,
                    ),
                },
            )
        )

        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()
```

> **`model_dump` vs `json.loads(model_dump_json(...))`**：实现直接使用 `model_dump(by_alias=False)` 返回 Python dict，SQLAlchemy 的 JSONB 列类型会处理序列化，比 PRD 原草稿中的 JSON 往返方式更简洁。

#### FastAPI Dependency Provider

```python
def get_chat_repository() -> SqlAlchemyChatRepository:
    """FastAPI dependency — returns a SqlAlchemyChatRepository."""
    return SqlAlchemyChatRepository(get_session_factory())
```

> **简化的依赖注入**：`get_chat_repository()` 不接受参数，内部直接调用 `get_session_factory()`。若 engine 未初始化，`get_session_factory()` 抛出 `RuntimeError`，起到与 `Depends` 相同的守卫效果，同时减少 FastAPI 依赖链的层级。

### 7.2 `db/repositories/__init__.py`

```python
# db/repositories/__init__.py
"""Repository registry — re-export all repository classes and dependency providers."""

from db.repositories.chat import IChatRepository, SqlAlchemyChatRepository, get_chat_repository

__all__ = ["IChatRepository", "SqlAlchemyChatRepository", "get_chat_repository"]
```

---

## 8. Write Rules — Progressive Snapshot

有两类触发时机，均通过 FastAPI `BackgroundTasks` 异步执行，不阻塞 `/chat` 响应：

1. **新 session 第一条消息发送时** — 写入 minimal row，确保 `GET /chats` 能立即返回该会话（chat history 可见性保证）
2. **每模块完成时** — 渐进式 upsert，累积 collected_data

### 8.1 触发时机与写入内容

| 触发时机              | 写入字段                                                          | `initial_intent`      | `final_needs` | `completed_at` |
| --------------------- | ----------------------------------------------------------------- | --------------------- | ------------- | -------------- |
| **第一条消息（新 session）** | `session_id`、`anon_id`、`status=IN_PROGRESS`               | NULL                  | NULL          | NULL           |
| M1 完成               | `collected_data`（含 m1 快照）                                    | 写入                  | NULL          | NULL           |
| M2 完成               | `collected_data`（含 m1+m2 快照）                                 | 已有，COALESCE 保留   | NULL          | NULL           |
| M3 完成               | `collected_data`（含 m1+m2+m3 快照）                              | 已有，COALESCE 保留   | NULL          | NULL           |
| M4 完成               | `collected_data`（完整）+ `final_needs` + `borrowing_capacity`    | 已有，COALESCE 保留   | 写入          | 写入当前时间   |

> **为什么在第一条消息时写入：** Redis 有 7 天 TTL，超期且从未完成任何模块的 session 会彻底丢失；DB 则是持久存储。第一条消息触发 minimal upsert 后，`GET /chats` 的查询（`WHERE anon_id = ?`）可以立即看到该会话，无需先查 Redis 再合并。

### 8.2 `initial_intent` 的来源

M1 完成时，由 `intent_router.classify_intent_async()` 对当前 turn 的分类结果写入。`ConversationStateDTO` 上新增 `initial_intent: EUserIntent | None = None` 字段。M1 完成的 turn 结束时，路由层将分类结果写入 `updated_state.initial_intent`，`BackgroundTasks` 从 `state.initial_intent` 读取。

### 8.3 路由层集成（`routers/chat.py`）

```python
async def chat_async(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    chat_repo: SqlAlchemyChatRepository = Depends(get_chat_repository),
) -> ChatResponse:
    ...
    is_new_session: bool = state_was_just_created  # True when Redis had no prior state

    prev_completion = state.completion_status.model_copy()
    updated_state = merge_extracted_fields(state, extracted)

    newly_completed: bool = any(
        getattr(updated_state.completion_status, m)
        and not getattr(prev_completion, m)
        for m in ("M1", "M2", "M3", "M4")
    )
    if is_new_session or newly_completed:
        background_tasks.add_task(
            chat_repo.upsert_chat_snapshot_async, updated_state, resolved_anon_id
        )
    ...
```

> `BackgroundTasks` 由 FastAPI 生命周期托管，进程退出前确保任务完成，比 `asyncio.create_task` 更安全。新 session 和模块完成都走同一个 `upsert_chat_snapshot_async`，幂等性由 `ON CONFLICT DO UPDATE` 保证，无需分两条路径。

---

## 9. Migration Strategy (Alembic)

### 9.1 初始化（一次性，已完成）

```bash
# 在 backend/ 目录下运行
alembic init db/alembic
```

生成目录：

```
backend/
├── alembic.ini                                     Alembic 配置文件（backend/ 根目录）
└── db/
    └── alembic/
        ├── env.py                                  同步 psycopg2 配置
        ├── script.py.mako
        └── versions/
            └── 993128e7e195_create_chats.py        首个 migration（autogenerate 生成）
```

### 9.2 `env.py` — 同步 psycopg2 模式

Alembic `env.py` 使用**同步**驱动（psycopg2）而非 async。原因：Alembic 原生支持同步模式，无需 `asyncio.run()` 包装，更稳定。

```python
# db/alembic/env.py
import re
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import Connection

from config import settings
from db.models import Base  # noqa: F401 — registers all ORM models with Base.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Alembic migrations run synchronously via psycopg2; strip the +asyncpg driver suffix
# so the URL is compatible with the standard psycopg2 dialect.
_sync_url: str = re.sub(r"postgresql\+asyncpg", "postgresql", settings.database_url)
config.set_main_option("sqlalchemy.url", _sync_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates SQL without connecting)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using a synchronous psycopg2 engine."""
    db_url: str = config.get_main_option("sqlalchemy.url") or _sync_url
    connectable = create_engine(db_url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        do_run_migrations(connection)
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

> **与 PRD 草稿的差异**：原草稿规划使用 `async_engine_from_config` 的 async 模式。实现中改为同步 psycopg2，因为同步模式更简单、无 `asyncio` 嵌套风险，且 Alembic 官方推荐在迁移中使用同步连接。

### 9.3 `alembic.ini` 关键配置

```ini
[alembic]
script_location = %(here)s/db/alembic
prepend_sys_path = .

# sqlalchemy.url 保留占位符；env.py 从 settings.database_url 读取真实 URL 并覆盖此值
sqlalchemy.url = driver://user:pass@localhost/dbname
```

### 9.4 生成首个 Migration（已完成）

```bash
alembic revision --autogenerate -m "create_chats"
```

生成文件：`db/alembic/versions/993128e7e195_create_chats.py`（revision ID 由 Alembic 自动生成哈希，非顺序编号）。

### 9.5 运行迁移

```bash
# 开发（手动）
uv run alembic upgrade head

# 通过 scripts.py 入口（自动重试，等待 postgres 启动）
uv run dev   # 内部调用 _migrate() → alembic upgrade head，再启动 uvicorn
```

`scripts.py` 中的 `_migrate()` 最多重试 15 次（每次等待 1 秒），等待 Postgres 容器就绪后执行迁移，再启动 uvicorn。

---

## 10. Project Structure

实际文件结构：

```
backend/
├── alembic.ini                              Alembic 配置文件（backend/ 根目录）
└── db/
    ├── __init__.py
    ├── connection.py                        AsyncEngine + async_sessionmaker 生命周期管理
    │                                        + get_session_factory + get_db_session_async
    ├── models/                              ORM 模型子包（每张表一个文件）
    │   ├── __init__.py                      re-export Base + 所有 Row 类（供 Alembic 发现）
    │   ├── base.py                          DeclarativeBase（唯一定义处）
    │   └── chat.py                          ChatRow（chats 表映射）
    ├── repositories/                        CRUD 操作子包（与 models/ 按层对称，每张表一个文件）
    │   ├── __init__.py                      re-export 所有 Repository 类和依赖提供者
    │   └── chat.py                          IChatRepository Protocol + SqlAlchemyChatRepository
    │                                        + get_chat_repository FastAPI 依赖
    └── alembic/                             Alembic 迁移文件
        ├── env.py                           同步 psycopg2 配置（from db.models import Base）
        ├── README
        ├── script.py.mako
        └── versions/
            └── 993128e7e195_create_chats.py  首个 migration（autogenerate 生成）
```

已修改的现有文件：

| 文件                            | 变更                                                                          |
| ------------------------------- | ----------------------------------------------------------------------------- |
| `main.py`                       | lifespan 挂载 `create_engine_async` / `close_engine_async`；新增 `/health` postgres 检查 |
| `routers/chat.py`               | 注入 `chat_repo` 依赖，`BackgroundTasks` 调用 `upsert_chat_snapshot_async`    |
| `models/conversation_state.py`  | 新增 `initial_intent: EUserIntent \| None = None` 字段                        |
| `config.py`                     | 包含 `database_url` 字段（`postgresql+asyncpg://` 格式）                      |
| `pyproject.toml`                | 新增 `sqlalchemy[asyncio]>=2.0`、`alembic>=1.13`、`psycopg2`                 |
| `requirements.txt`              | 同步更新                                                                      |

---

## 11. Environment Variables

| Variable        | Required | Format                                          | Description                               |
| --------------- | -------- | ----------------------------------------------- | ----------------------------------------- |
| `DATABASE_URL`  | Yes      | `postgresql+asyncpg://user:pass@host:5432/db`   | SQLAlchemy async DSN（asyncpg 驱动前缀）   |

> Alembic `env.py` 通过正则 `re.sub(r"postgresql\+asyncpg", "postgresql", ...)` 将此 URL 转换为 psycopg2 兼容格式（`postgresql://`）后再使用。无需维护两个独立的数据库 URL 环境变量。

**本地开发 `.env` 示例：**

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/propertyai
```

---

## 12. Test Strategy

### 12.1 File

```
backend/tests/test_chat_repository.py
```

### 12.2 测试方式

使用真实 PostgreSQL 测试数据库（Docker Compose `postgres` 服务）+ SQLAlchemy async session；不 mock ORM 层。`conftest.py` 提供 `db_engine` 和 `db_session` fixtures，每个测试用 session rollback 保证隔离。

```python
# tests/conftest.py（新增 fixtures）
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from config import settings
from db.models import Base


@pytest_asyncio.fixture(scope="session")
async def db_engine():
    engine = create_async_engine(settings.database_url, connect_args={"ssl": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()
```

### 12.3 测试列表

```
tests/test_chat_repository.py

test_upsert_creates_row_on_first_call
test_upsert_on_m1_completion_writes_initial_intent
test_upsert_on_m2_completion_accumulates_m1_data
test_upsert_on_m4_completion_writes_final_needs_and_completed_at
test_upsert_is_idempotent_for_same_session_id
test_initial_intent_not_overwritten_by_subsequent_upsert
test_completed_at_not_overwritten_once_set
test_conversation_history_not_present_in_db
test_db_error_is_logged_and_suppressed_not_raised
```

---

## 13. Acceptance Criteria

| ID    | Criterion                                                                                                          |
| ----- | ------------------------------------------------------------------------------------------------------------------ |
| DB-1  | `alembic upgrade head` 幂等执行，`chats` 表（主键 `session_id`）及 4 个索引存在                                     |
| DB-2  | 第一条消息发送后（无论是否完成任何模块），`chats` 中存在对应行，`status = IN_PROGRESS`，`collected_data = {}`         |
| DB-3  | M1 完成后 upsert，`collected_data` 含 m1 字段，`initial_intent` 非 NULL，行数仍为 1                                  |
| DB-4  | M2 完成后 upsert，`collected_data` 包含 m1+m2 数据，行数仍为 1                                                      |
| DB-5  | M4 完成后，`final_needs` 非 NULL，`status = REQUIREMENTS_COMPLETE`，`completed_at` 非 NULL                         |
| DB-6  | 同一 `session_id` 多次 upsert 幂等：`initial_intent` 和 `completed_at` 不被后续 NULL 覆盖                            |
| DB-7  | `conversation_history` 和 `budget_gap` 不出现在 `chats` 表任何列中                                                  |
| DB-8  | 数据库不可用时，`BackgroundTasks` 内部异常被 `logger.exception` 记录后静默吞噬，`/chat` 主请求正常返回 `ChatResponse` |
| DB-9  | `GET /health` 新增 `postgres` 检查项，数据库不可达时返回 `"degraded"`（不阻止服务启动）                               |
| DB-10 | mypy --strict 对 `db/` 全包通过，无类型错误                                                                         |

---

## 14. Future: users / anonymous_users Tables

P1-B 阶段新增：

- `users` 表（已认证用户）
- `anonymous_users` 表（未登录用户，通过 cookie/设备指纹追踪）
- Alembic migration 补充 `chats.user_id` → `users.user_id` 和 `chats.anon_id` → `anonymous_users.anon_id` 的 FK 约束
- `chats` 表已预留 `user_id UUID NULL` 和 `anon_id UUID NULL` 两列，P1-B 只需加约束，无需改表结构