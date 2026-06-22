# PropertyAI — Database Layer

## Technical PRD v1.0

| Field           | Value                                   |
| --------------- | --------------------------------------- |
| Version         | v1.0                                    |
| Status          | **Draft — awaiting implementation**     |
| Parent Document | PropertyAI_Part1_Technical_PRD_v1_1.md  |
| Scope           | PostgreSQL + SQLAlchemy ORM + `chats` table |
| Last Updated    | 22 Jun 2026                             |

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

### 1.2 In Scope (P1-A)

- SQLAlchemy 2.0 async ORM 模型定义（`chats` 表）
- `AsyncEngine` + `async_sessionmaker` 连接池生命周期管理
- `IChatRepository` Protocol + `SqlAlchemyChatRepository` 实现
- Alembic 迁移（`env.py` async 模式 + `001_create_chats` migration）
- 每模块完成时通过 FastAPI `BackgroundTasks` 触发渐进式 upsert
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

### 2.2 ORM：SQLAlchemy 2.0 Async

使用 SQLAlchemy 2.0 async ORM（`AsyncSession`）而非原生 asyncpg。理由：

| 关注点       | ORM 优势                                                               |
| ------------ | ---------------------------------------------------------------------- |
| SQL 封装     | 所有 SQL 通过 ORM 语句生成，无裸字符串泄露到业务代码                    |
| 类型安全     | `Mapped[T]` 标注提供列级类型推断，mypy --strict 全覆盖                  |
| 迁移管理     | Alembic `autogenerate` 从 ORM 模型自动生成 migration，减少手写 DDL 风险 |
| 扩展性       | P1-B 增加 `users`、`anonymous_users` 及关联关系只需追加 ORM 模型        |

asyncpg 仍作为底层驱动（`postgresql+asyncpg://`），SQLAlchemy 不替换驱动，只增加映射层。

### 2.3 Repository 命名：`chat_repository.py`

数据库操作全部封装在 `db/chat_repository.py` 中，Protocol 名 `IChatRepository`，实现类名 `SqlAlchemyChatRepository`。文件名与表名 `chats` 对齐；路由层通过 `IChatRepository` Protocol 调用，与 SQLAlchemy 实现解耦，便于测试时替换 mock。

### 2.4 外键延迟设计

`user_id` 和 `anon_id` 在 P1-A 以 `UUID NULL` 列写入 ORM 模型和 DDL，但不添加 `ForeignKey()` 约束（P1-B Alembic migration 补充）。P1-A 阶段所有 chats 的两列均为 `NULL`。

CHECK 约束确保两列不同时为非 NULL。

## 3. Tech Stack

| Layer        | Technology                                             |
| ------------ | ------------------------------------------------------ |
| ORM          | SQLAlchemy 2.0 (`sqlalchemy[asyncio]>=2.0`)            |
| Async driver | asyncpg（已在 `pyproject.toml` 中，DSN 前缀 `postgresql+asyncpg://`） |
| Migrations   | Alembic (`alembic>=1.13`)                              |
| Column types | `UUID`, `Text`, `JSONB` (via `sqlalchemy.dialects.postgresql`) |

### 3.1 新增依赖（`pyproject.toml`）

```toml
dependencies = [
    # 现有依赖不变...
    "sqlalchemy[asyncio]>=2.0.0",
    "alembic>=1.13.0",
]
```

同步更新 `requirements.txt`。`db` 包加入 `tool.setuptools.packages.find.include`。

---

## 4. Schema: `chats` Table

以下为与 ORM 模型对应的逻辑 DDL（Alembic 由 ORM 模型自动生成，无需手写 DDL）：

```sql
CREATE TABLE chats (
    -- Identity（主键列名与 Redis / DTO 保持一致）
    session_id         UUID        PRIMARY KEY,

    -- Owner (FK constraints added in P1-B via Alembic migration)
    user_id            UUID        NULL,
    anon_id            UUID        NULL,

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
    completed_at       TIMESTAMPTZ NULL,

    -- A chat cannot simultaneously belong to a user and an anonymous user
    CONSTRAINT chk_chats_single_owner CHECK (
        NOT (user_id IS NOT NULL AND anon_id IS NOT NULL)
    )
);

CREATE INDEX idx_chats_status     ON chats (status);
CREATE INDEX idx_chats_updated_at ON chats (updated_at DESC);
CREATE INDEX idx_chats_user_id    ON chats (user_id)  WHERE user_id IS NOT NULL;
CREATE INDEX idx_chats_anon_id    ON chats (anon_id)  WHERE anon_id IS NOT NULL;
```

### 4.1 Column Reference

| Column               | SQLAlchemy Type       | Nullable | Description                                                              |
| -------------------- | --------------------- | -------- | ------------------------------------------------------------------------ |
| `session_id`         | `UUID` (PK)           | No       | UUID v4 generated by the frontend; equals Redis `session:{session_id}`   |
| `user_id`            | `UUID`                | Yes      | FK to future `users.user_id` (P1-B); NULL in P1-A                       |
| `anon_id`            | `UUID`                | Yes      | FK to future `anonymous_users.anon_id` (P1-B); NULL in P1-A             |
| `status`             | `Text`                | No       | `IN_PROGRESS` / `REQUIREMENTS_COMPLETE`                                  |
| `schema_version`     | `Text`                | No       | Fixed `'1.1'`                                                            |
| `initial_intent`     | `Text`                | Yes      | Written on M1 completion (e.g. `recommend_suburbs`)                      |
| `collected_data`     | `JSONB`               | No       | Progressive snapshot of M1–M4 collected fields                           |
| `final_needs`        | `JSONB`               | Yes      | Full `UserNeeds` written after M4 completion                             |
| `borrowing_capacity` | `JSONB`               | Yes      | `BorrowingCapacityResult` written after M4 completion (if salary given)  |
| `created_at`         | `TIMESTAMP WITH TZ`   | No       | Auto-set on INSERT                                                       |
| `updated_at`         | `TIMESTAMP WITH TZ`   | No       | Updated on every upsert                                                  |
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
        CheckConstraint(
            "NOT (user_id IS NOT NULL AND anon_id IS NOT NULL)",
            name="chk_chats_single_owner",
        ),
        Index("idx_chats_status", "status"),
        Index("idx_chats_updated_at", "updated_at"),
        Index("idx_chats_user_id", "user_id", postgresql_where="user_id IS NOT NULL"),
        Index("idx_chats_anon_id", "anon_id", postgresql_where="anon_id IS NOT NULL"),
    )

    # Identity — column name matches session_id used everywhere else
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)

    # Owner — FK constraints added in P1-B
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    anon_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Conversation state
    status: Mapped[str] = mapped_column(Text, nullable=False, default="IN_PROGRESS")
    schema_version: Mapped[str] = mapped_column(Text, nullable=False, default="1.1")
    initial_intent: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Structured business data
    collected_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    final_needs: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    borrowing_capacity: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
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

### 6.2 Specification

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
    factory = get_session_factory()
    async with factory() as session:
        yield session
```

### 6.3 FastAPI Lifespan 集成

```python
# main.py
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from db.connection import create_engine_async, close_engine_async
from redis_store.client import connect_async, close_async


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await connect_async()
    await create_engine_async()
    yield
    await close_engine_async()
    await close_async()


app = FastAPI(lifespan=lifespan)
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
import json
import uuid
from dataclasses import asdict
from datetime import datetime, timezone

import structlog
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db.models.chat import ChatRow
from models.conversation_state import ConversationStateDTO, EStatus

logger = structlog.get_logger()


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
        collected: dict = json.loads(state.collected_data.model_dump_json(by_alias=False))
        final_needs: dict | None = (
            json.loads(state.final_needs.model_dump_json(by_alias=False))
            if state.final_needs is not None
            else None
        )
        borrowing: dict | None = (
            asdict(state.borrowing_capacity)
            if state.borrowing_capacity is not None
            else None
        )
        completed_at: datetime | None = (
            datetime.now(tz=timezone.utc)
            if state.status == EStatus.REQUIREMENTS_COMPLETE
            else None
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
                    "updated_at": datetime.now(tz=timezone.utc),
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

#### FastAPI Dependency Provider

```python
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db.connection import get_session_factory


def get_chat_repository(
    factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
) -> SqlAlchemyChatRepository:
    """FastAPI dependency — returns a SqlAlchemyChatRepository."""
    return SqlAlchemyChatRepository(factory)
```

### 7.2 `db/repositories/__init__.py`

```python
# db/repositories/__init__.py
"""Repository registry — re-export all repository classes and dependency providers."""

from db.repositories.chat import IChatRepository, SqlAlchemyChatRepository, get_chat_repository

__all__ = ["IChatRepository", "SqlAlchemyChatRepository", "get_chat_repository"]
```

---

## 8. Write Rules — Progressive Snapshot

每模块完成时触发一次 upsert，通过 FastAPI `BackgroundTasks` 异步执行，不阻塞 `/chat` 响应。

### 8.1 触发时机与写入内容

| 触发时机 | 写入字段                                                         | `initial_intent`      | `final_needs` | `completed_at` |
| -------- | ---------------------------------------------------------------- | --------------------- | ------------- | -------------- |
| M1 完成  | `collected_data`（含 m1 快照）                                    | 写入                  | NULL          | NULL           |
| M2 完成  | `collected_data`（含 m1+m2 快照）                                | 已有，COALESCE 保留   | NULL          | NULL           |
| M3 完成  | `collected_data`（含 m1+m2+m3 快照）                             | 已有，COALESCE 保留   | NULL          | NULL           |
| M4 完成  | `collected_data`（完整）+ `final_needs` + `borrowing_capacity`   | 已有，COALESCE 保留   | 写入          | 写入当前时间   |

### 8.2 `initial_intent` 的来源

M1 完成时，由 `intent_router.classify_intent_async()` 对当前 turn 的分类结果写入。

**实现方案**：在 `ConversationStateDTO` 上新增 `initial_intent: EUserIntent | None = None` 字段（与 `borrowing_capacity`、`budget_gap` 的处理方式相同，见 Part 1 PRD §17.6）。M1 完成的 turn 结束时，路由层将分类结果写入 `updated_state.initial_intent`，`BackgroundTasks` 从 `state.initial_intent` 读取。

### 8.3 路由层集成（`routers/chat.py`）

```python
async def chat_async(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    chat_repo: SqlAlchemyChatRepository = Depends(get_chat_repository),
) -> ChatResponse:
    ...
    prev_completion = state.completion_status.model_copy()
    updated_state = merge_extracted_fields(state, extracted)

    newly_completed: bool = any(
        getattr(updated_state.completion_status, m)
        and not getattr(prev_completion, m)
        for m in ("M1", "M2", "M3", "M4")
    )
    if newly_completed:
        background_tasks.add_task(
            chat_repo.upsert_chat_snapshot_async, updated_state
        )
    ...
```

> `BackgroundTasks` 由 FastAPI 生命周期托管，进程退出前确保任务完成，比 `asyncio.create_task` 更安全。

---

## 9. Migration Strategy (Alembic)

### 9.1 初始化（一次性）

```bash
# 在 backend/ 目录下运行
alembic init -t async db/alembic
```

生成目录：

```
backend/
├── alembic.ini                    Alembic 配置文件（DATABASE_URL 从环境变量读取）
└── db/
    └── alembic/
        ├── env.py                 async 配置（引入 Base.metadata）
        ├── script.py.mako
        └── versions/
            └── 001_create_chats.py   首个 migration（autogenerate 生成）
```

### 9.2 `env.py` 异步配置（核心片段）

```python
# db/alembic/env.py
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.pool import NullPool

from db.models import Base

target_metadata = Base.metadata


async def run_migrations_online_async() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
```

### 9.3 生成首个 Migration

```bash
alembic revision --autogenerate -m "create_chats"
```

Alembic 从 `ChatRow` 模型自动生成 `001_create_chats.py`，包含 `CREATE TABLE chats`（主键 `session_id`）、4 个索引及 CHECK 约束。review 生成文件后提交至 git。

### 9.4 运行迁移

```bash
# 开发（手动）
alembic upgrade head

# 生产（Docker Compose entrypoint 中自动运行，再启动 uvicorn）
alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## 10. Project Structure

新增文件：

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
        ├── env.py                           async 配置（from db.models import Base）
        ├── script.py.mako
        └── versions/
            └── 001_create_chats.py          首个 migration（autogenerate 生成，review 后提交）
```

需同步修改的现有文件：

| 文件                            | 变更                                                                          |
| ------------------------------- | ----------------------------------------------------------------------------- |
| `main.py`                       | lifespan 挂载 `create_engine_async` / `close_engine_async`                    |
| `routers/chat.py`               | 注入 `chat_repo` 依赖，`BackgroundTasks` 调用 `upsert_chat_snapshot_async`    |
| `models/conversation_state.py`  | 新增 `initial_intent: EUserIntent \| None = None` 字段（参见 §8.2）           |
| `config.py`                     | 确认 `database_url` 字段（`postgresql+asyncpg://` 格式）                      |
| `pyproject.toml`                | 新增 `sqlalchemy[asyncio]>=2.0`、`alembic>=1.13`；`db` 加入 packages.find     |
| `requirements.txt`              | 同步更新                                                                      |

---

## 11. Environment Variables

| Variable       | Required | Format                                          | Description                               |
| -------------- | -------- | ----------------------------------------------- | ----------------------------------------- |
| `DATABASE_URL` | Yes      | `postgresql+asyncpg://user:pass@host:5432/db`   | SQLAlchemy async DSN（asyncpg 驱动前缀）   |

> `DATABASE_URL` 已在 Part 1 PRD §26 中定义。SQLAlchemy async 需要 `postgresql+asyncpg://` 前缀，而非原生 asyncpg 的 `postgresql://`。

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
    engine = create_async_engine(settings.database_url)
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
| DB-2  | M1 完成后，`chats` 中存在对应行，`collected_data` 含 m1 字段，`initial_intent` 非 NULL                               |
| DB-3  | M2 完成后 upsert，`collected_data` 包含 m1+m2 数据，行数仍为 1                                                      |
| DB-4  | M4 完成后，`final_needs` 非 NULL，`status = REQUIREMENTS_COMPLETE`，`completed_at` 非 NULL                         |
| DB-5  | 同一 `session_id` 多次 upsert 幂等：`initial_intent` 和 `completed_at` 不被后续 NULL 覆盖                            |
| DB-6  | `conversation_history` 和 `budget_gap` 不出现在 `chats` 表任何列中                                                  |
| DB-7  | 数据库不可用时，`BackgroundTasks` 内部异常被 `logger.exception` 记录后静默吞噬，`/chat` 主请求正常返回 `ChatResponse` |
| DB-8  | `chk_chats_single_owner` 约束阻止 `user_id` 和 `anon_id` 同时非 NULL                                               |
| DB-9  | `GET /health` 新增 `postgres` 检查项，数据库不可达时返回 `"degraded"`（不阻止服务启动）                               |
| DB-10 | mypy --strict 对 `db/` 全包通过，无类型错误                                                                         |

---