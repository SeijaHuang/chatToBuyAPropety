# PropertyAI — 匿名用户身份系统

## Technical PRD v1.0

| 字段         | 值                                      |
| ------------ | --------------------------------------- |
| Version      | v1.0                                    |
| Status       | **Implemented**                         |
| 父文档       | PropertyAI_Database_PRD_v1_0.md         |
| Scope        | 匿名用户身份追踪、`users` 表、前端 localStorage |
| Last Updated | 28 Jun 2026                             |

---

## Table of Contents

1. [目标与范围](#1-目标与范围)
2. [设计决策](#2-设计决策)
3. [Schema：`users` 表](#3-schema-users-表)
4. [ORM 模型](#4-orm-模型)
5. [Repository 层](#5-repository-层)
6. [API 契约变更](#6-api-契约变更)
7. [前端集成](#7-前端集成)
8. [迁移策略](#8-迁移策略)
9. [项目结构变更](#9-项目结构变更)
10. [测试策略](#10-测试策略)
11. [验收标准](#11-验收标准)
12. [未来规划（P1-B）](#12-未来规划p1-b)

---

## 1. 目标与范围

### 1.1 目标

在不要求用户注册的前提下，为每个浏览器会话分配一个持久化的匿名身份（`anon_id`），使系统能够：

- 将多个对话（`chats`）与同一个匿名用户关联
- 通过 `GET /api/v1/chats?anon_id=<uuid>` 返回用户的历史对话列表
- 为未来的注册流程（P1-B）保留升级路径——注册后沿用同一 `user_id`，无需迁移历史数据

### 1.2 In Scope（P1-A — 已实现）

- 单表 `users`（匿名用户和注册用户共用，`email IS NULL` 区分未注册状态）
- `SqlAlchemyUserRepository.get_or_create_async` 实现匿名身份的查找或新建
- `POST /chat`：接收 `anon_id`，写回 `resolved_anon_id`，写入 `chats.anon_id`
- `GET /chats?anon_id=<uuid>`：返回该匿名用户所有历史对话，按 `updated_at DESC` 排序
- 前端 localStorage 持久化 `anon_id`，下次访问携带以延续身份

### 1.3 Out of Scope

- 注册、登录、密码、OAuth（P1-B）
- `HttpOnly Cookie` 替换 localStorage 中的 auth token（P1-B）
- `chats` 表新增 `user_id` 列（P1-B，auth 实现后再加）
- 多设备同步（P2）

---

## 2. 设计决策

### 2.1 单表设计：`users`（而非 `users` + `anonymous_users`）

**放弃的方案：** 两张表（`anonymous_users.anon_id` + `users.user_id`），`anonymous_users.user_id` FK 指向 `users`。

**选择单表的原因：**

| 关注点     | 两表方案                              | 单表方案                              |
| ---------- | ------------------------------------- | ------------------------------------- |
| 注册时操作 | 新建 `users` 行 + UPDATE `anonymous_users.user_id` | 只需 `UPDATE users SET email = '...'`|
| 查询复杂度 | `JOIN anonymous_users`                | 直接 `WHERE anon_id = :anon_id`      |
| 历史数据   | `chats.anon_id` 无需变动              | 相同，`chats.anon_id` 不变           |
| 区分逻辑   | 表本身区分                            | `email IS NULL` 区分                 |

单表方案在 P0-P1-A 阶段更简单，注册升级时只需 UPDATE 一行，`user_id` 从始至终保持不变。

### 2.2 `user_id` 的语义

`user_id` 是所有用户（匿名或注册）的内部身份锚点，在首次访问时自动生成，永不改变。区分匿名/注册状态靠 `email` 字段：

- **匿名用户：** `user_id`（自动生成）+ `anon_id`（前端 localStorage ID）+ `email = NULL`
- **注册用户：** 同一行，`UPDATE users SET email = 'xxx@example.com' WHERE anon_id = :anon_id`

### 2.3 `chats.anon_id` 无外键约束（仅索引）

**外键的作用是数据完整性**（确保 `chats.anon_id` 对应真实存在的 `users` 行）。  
**索引的作用是查询性能**（`WHERE anon_id = :anon_id` 的 B-tree 定位速度）。

移除 FK 后，`idx_chats_anon_id` 索引依然存在，查询速度完全不变。选择不加 FK 的原因：

- `upsert_chat_snapshot_async` 在 `BackgroundTasks` 中执行，时序上 `users` 行可能尚未提交
- 简化测试——不再需要在每个测试前先 INSERT `users` 行
- `anon_id` 以去规范化（denormalized）方式存储在 `chats` 中，用于直接过滤，无需 JOIN

### 2.4 CORS 约束：`anon_id` 通过 Request Body 传输

`allow_origins=["*"]` 时，`allow_credentials=True` 不允许同时设置（浏览器安全限制），因此无法使用 Cookie 传递 `anon_id`。替代方案：

- `anon_id` 存入前端 `localStorage`
- 每次 `POST /chat` 时放入 request body（与 `session_id` 相同模式）
- 后端返回 `resolved_anon_id`，前端收到后存入 localStorage

P1-B 实现登录后，Cookie 用于 auth token，`anon_id` 依然通过 body 传输（两者不冲突）。

### 2.5 `chats` 同时保留 `anon_id` 和 `user_id` 两列

`chats` 表保留两列 owner 标识，两者均可为 NULL，**也可同时非 NULL**：

| 阶段 | `chats.anon_id` | `chats.user_id` | 说明 |
|------|----------------|----------------|------|
| P0-P1-A（现在） | 非 NULL | NULL | 无登录态，只写 `anon_id` |
| P1-B 登录后新对话 | 非 NULL | 非 NULL | 两个标识同时写入 |
| P2 新设备登录 | NULL | 非 NULL | 新设备无 `anon_id`，只有 `user_id` |

**同时非 NULL 的理由**：单表设计下注册用户同样持有 `anon_id`（从不改变），P1-B 登录后新建的对话可以同时写入：
- `anon_id`：浏览器/设备维度的持久标识，用于"本设备的所有对话"查询
- `user_id`：注册身份标识，用于"该用户跨设备的所有对话"查询

因此原有的 `CHECK CONSTRAINT chk_chats_single_owner`（禁止两列同时非 NULL）已通过 migration `2f156e1dbbc7` 删除，不再适用于单表设计。

---

## 3. Schema：`users` 表

```sql
CREATE TABLE users (
    user_id    UUID        PRIMARY KEY,          -- 内部身份锚点，首次访问时生成，永不改变
    anon_id    UUID        NOT NULL UNIQUE,       -- 前端 localStorage ID，浏览器/设备维度
    email      TEXT        UNIQUE,               -- NULL = 匿名用户；有值 = 注册用户（P1-B 填入）
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_users_anon_id ON users (anon_id);  -- 额外索引（UNIQUE 约束已建隐式索引）
```

### 3.1 Column Reference

| Column       | Type        | Nullable | Description                                     |
| ------------ | ----------- | -------- | ----------------------------------------------- |
| `user_id`    | UUID PK     | No       | 所有用户的内部锚点，首次访问时 `uuid4()` 自动生成  |
| `anon_id`    | UUID UNIQUE | No       | 前端 localStorage 中的设备 ID，首次访问时生成      |
| `email`      | TEXT UNIQUE | Yes      | `NULL` = 匿名用户；注册时由 P1-B 流程写入         |
| `created_at` | TIMESTAMPTZ | No       | 行创建时间                                        |
| `updated_at` | TIMESTAMPTZ | No       | 最后活跃时间；每次对话时由 `get_or_create_async` 刷新 |

### 3.2 与 `chats` 表的关系

```
users                          chats
──────────────────────         ──────────────────────────────────────
user_id  UUID PK               session_id  UUID PK
anon_id  UUID UNIQUE NOT NULL  anon_id     UUID NULL  ← 去规范化，无 FK
email    TEXT NULL                                      idx_chats_anon_id（B-tree）
```

`chats.anon_id` 是 `users.anon_id` 的去规范化副本，无外键约束，靠索引支持高效查询。

---

## 4. ORM 模型

### 4.1 `db/models/user.py`

```python
# db/models/user.py
"""ORM model for the users table — covers both anonymous and registered users."""

import uuid
from datetime import datetime

from sqlalchemy import Index, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.models.base import Base


class UserRow(Base):
    """Single table for all users.

    Anonymous: anon_id set, email = NULL.
    Registered: anon_id set, email filled in on registration (P1-B).
    user_id is always generated on first visit and never changes.
    """

    __tablename__ = "users"

    __table_args__ = (
        Index("idx_users_anon_id", "anon_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    anon_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, nullable=False
    )
    email: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
```

### 4.2 `db/models/__init__.py`

```python
from db.models.base import Base
from db.models.chat import ChatRow
from db.models.user import UserRow

__all__ = ["Base", "ChatRow", "UserRow"]
```

---

## 5. Repository 层

### 5.1 `db/repositories/user.py`

#### IUserRepository Protocol

```python
class IUserRepository(Protocol):
    async def get_or_create_async(self, anon_id: str | None) -> str:
        """Resolve or create a user identity by anon_id.

        - anon_id 非 None 且存在于 DB：刷新 updated_at，返回原 anon_id
        - anon_id 为 None 或 DB 中不存在：插入新行，返回新生成的 anon_id
        - anon_id 格式非法（非 UUID）：视为不存在，插入新行

        Returns:
            The anon_id string of the resolved or newly created user.
        """
        ...
```

#### SqlAlchemyUserRepository 实现

```python
class SqlAlchemyUserRepository:

    async def get_or_create_async(self, anon_id: str | None) -> str:
        if anon_id is not None:
            try:
                parsed = uuid.UUID(anon_id)
                found = await self._touch_existing_async(parsed)
                if found is not None:
                    return found
            except ValueError:
                logger.warning("anon_id_parse_failed", raw_anon_id=anon_id)
        return await self._create_new_async()

    async def _touch_existing_async(self, anon_uuid: uuid.UUID) -> str | None:
        """查询存在则更新 updated_at，返回 anon_id 字符串；不存在返回 None。"""
        ...

    async def _create_new_async(self) -> str:
        """INSERT 新行（fresh user_id + anon_id），返回新 anon_id 字符串。"""
        ...
```

#### FastAPI 依赖

```python
def get_user_repository() -> SqlAlchemyUserRepository:
    return SqlAlchemyUserRepository(get_session_factory())
```

### 5.2 `db/repositories/__init__.py`

```python
from db.repositories.chat import IChatRepository, SqlAlchemyChatRepository, get_chat_repository
from db.repositories.user import IUserRepository, SqlAlchemyUserRepository, get_user_repository

__all__ = [
    "IChatRepository", "SqlAlchemyChatRepository", "get_chat_repository",
    "IUserRepository", "SqlAlchemyUserRepository", "get_user_repository",
]
```

---

## 6. API 契约变更

### 6.1 `POST /api/v1/chat`

**Request（`ChatRequest`）新增字段：**

```json
{
  "session_id": "string | null",
  "anon_id": "string | null",   // 新增 — 前端从 localStorage 读取，首次为 null
  "message": "string"
}
```

**Response（`ChatResponse`）新增字段：**

```json
{
  "reply": "string",
  "extracted": {},
  "session_id": "string",
  "anon_id": "string",          // 新增 — 前端收到后存入 localStorage
  "state": { ... },
  "routing": null
}
```

**路由逻辑（`routers/chat.py`）：**

```python
async def chat_async(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    chat_repo: Annotated[SqlAlchemyChatRepository, Depends(get_chat_repository)],
    anon_repo: Annotated[SqlAlchemyUserRepository, Depends(get_user_repository)],
) -> SuccessResponse[ChatResponse]:
    # 1. 解析身份 — resolved_anon_id 始终是有效的 DB-backed str
    resolved_anon_id: str = await anon_repo.get_or_create_async(request.anon_id)
    # ... LLM 处理 ...
    # 2. 有模块完成时，将 resolved_anon_id 写入 chats 行
    if newly_completed:
        background_tasks.add_task(
            chat_repo.upsert_chat_snapshot_async, state, resolved_anon_id
        )
    # 3. 返回 resolved_anon_id 供前端存储
    return SuccessResponse(data=ChatResponse(..., anon_id=resolved_anon_id))
```

### 6.2 `GET /api/v1/chats`（新增端点）

**Request：**

```
GET /api/v1/chats?anon_id=<uuid>
```

**Response：**

```json
{
  "data": [
    {
      "sessionId": "uuid",
      "status": "IN_PROGRESS | REQUIREMENTS_COMPLETE",
      "initialIntent": "recommend_suburbs | ...",
      "createdAt": "2026-06-28T10:00:00Z",
      "updatedAt": "2026-06-28T10:05:00Z",
      "completedAt": "2026-06-28T10:05:00Z | null"
    }
  ]
}
```

**行为规则：**

- `anon_id` 非法 UUID → `BadRequestError`（HTTP 400）
- `anon_id` 有效但无对应 chats → 返回空数组 `[]`（不 404，防止枚举攻击）
- 按 `updated_at DESC` 排序

### 6.3 `ChatSessionDTO`（Pydantic DTO）

```python
class ChatSessionDTO(PropertyAIBaseModel):
    session_id: str
    status: str
    initial_intent: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
```

---

## 7. 前端集成

### 7.1 数据流

```
首次访问 → POST /chat (anon_id: null)
  ← 响应含 anonId: "new-uuid"
  → localStorage.setItem("propertyai.anonId", "new-uuid")

二次访问 → localStorage.getItem("propertyai.anonId") → "new-uuid"
         → POST /chat (anon_id: "new-uuid")
  ← 响应含 anonId: "new-uuid"（相同，后端刷新 updated_at）
```

### 7.2 Storage Key

```typescript
// src/constants/storageKeys.ts
export const STORAGE_KEY = {
  CONVERSATION_STATE_PREFIX: 'propertyai.conversation.',
  ROUTING_PAYLOAD_PREFIX: 'propertyai.routing.',
  ANON_ID: 'propertyai.anonId',
} as const
```

### 7.3 Zustand Store 变更（`conversationStore.ts`）

```typescript
interface ConversationStore {
  anonId: string | null
  setAnonId(anonId: string): void  // 写入 state + localStorage
}
```

### 7.4 Hook 变更（`useChat.ts`）

```typescript
// 挂载时从 localStorage 水合 anonId
useEffect((): void => {
  if (store.anonId === null) {
    const stored = localStorage.getItem(STORAGE_KEY.ANON_ID)
    if (stored !== null) store.setAnonId(stored)
  }
}, [])

// sendMessage 时携带 anonId，响应后更新
const anonId = store.anonId ?? localStorage.getItem(STORAGE_KEY.ANON_ID)
const response = await postChat(content, sessionId, anonId)
if (response.ok) store.setAnonId(response.data.anonId)
```

### 7.5 Service 变更（`services/chat.ts`）

```typescript
export function postChat(
  message: string,
  sessionId: string | null,
  anonId: string | null,
): Promise<APIResponse<ChatResponse>> {
  return request.post<ChatResponse>(ENDPOINTS.CHAT, { message, sessionId, anonId })
}
```

### 7.6 localStorage 安全性

`anon_id` 不是 auth token，不能授权任何敏感操作，只用于关联历史对话。XSS 场景下泄露的最坏结果是对话历史被读取，可接受的 P0 风险。P1-B 登录态使用 HttpOnly Cookie（XSS 不可读），彼时 `anon_id` 仍留在 localStorage 但不再是主要身份凭证。

---

## 8. 迁移策略

### 8.1 Migration 文件

| 文件                                                                | 内容                                              |
| ------------------------------------------------------------------- | ------------------------------------------------- |
| `993128e7e195_create_chats.py`                                      | 创建 `chats` 表（含 `user_id`、`anon_id` 列）     |
| `2f156e1dbbc7_add_users_and_clean_chats_constraints.py`             | 创建 `users` 表 + 删除 `chk_chats_single_owner`   |

Migration chain：`993128e7e195` → `2f156e1dbbc7`（head）

### 8.2 `2f156e1dbbc7` 内容摘要

```sql
CREATE TABLE users (
    user_id    UUID        NOT NULL,
    anon_id    UUID        NOT NULL,
    email      TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (user_id),
    CONSTRAINT uq_users_anon_id UNIQUE (anon_id),
    CONSTRAINT uq_users_email   UNIQUE (email)
);
CREATE INDEX idx_users_anon_id ON users (anon_id);
```

### 8.3 测试环境同步（`conftest.py`）

`db_engine` fixture 使用 `Base.metadata.create_all` 建表后，调用 `alembic_command.stamp(alembic_cfg, "head")` 保持 Alembic version tracking 同步，防止 `alembic upgrade head` 在开发服务器启动时重复执行迁移：

```python
async with engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)
alembic_command.stamp(alembic_cfg, "head")
```

---

## 9. 项目结构变更

```
backend/
└── db/
    ├── models/
    │   ├── __init__.py     ← 新增 UserRow import
    │   └── user.py         ← 新建：UserRow ORM 模型
    ├── repositories/
    │   ├── __init__.py     ← 新增 IUserRepository / SqlAlchemyUserRepository / get_user_repository
    │   └── user.py         ← 新建：IUserRepository Protocol + SqlAlchemyUserRepository
    └── alembic/
        └── versions/
            └── f35cef7a1556_refactor_single_users_table.py  ← 新建：users 表 migration
```

修改的现有文件：

| 文件                              | 变更                                                              |
| --------------------------------- | ----------------------------------------------------------------- |
| `models/chat.py`                  | `ChatRequest.anon_id: str \| None`；`ChatResponse.anon_id: str`；新增 `ChatSessionDTO` |
| `routers/chat.py`                 | 注入 `anon_repo`；`POST /chat` 解析 `anon_id`；新增 `GET /chats` |
| `tests/conftest.py`               | mock `get_user_repository` 依赖；alembic stamp 同步              |
| `tests/test_chat_endpoint.py`     | 断言响应含 `anonId`                                              |
| `tests/test_chat_repository.py`   | `_setup_tables` 简化（无需预插 user 行）；新增 list_chats 测试   |
| `frontend/src/constants/storageKeys.ts` | 新增 `ANON_ID` 键                                          |
| `frontend/src/types/api.d.ts`     | `ChatResponse` 新增 `anonId: string`                            |
| `frontend/src/stores/conversationStore.ts` | 新增 `anonId` 状态和 `setAnonId` action                |
| `frontend/src/services/chat.ts`   | `postChat` 新增 `anonId` 参数                                    |
| `frontend/src/hooks/useChat.ts`   | 水合 + 发送 + 存储 `anonId`                                      |

---

## 10. 测试策略

### 10.1 后端

| 测试文件                      | 覆盖范围                                                                  |
| ----------------------------- | ------------------------------------------------------------------------- |
| `test_chat_endpoint.py`       | `POST /chat` 响应含 `anonId`；`GET /chats` 返回列表 / 空数组 / 400 错误  |
| `test_chat_repository.py`     | `upsert` 写入 `anon_id`；首次写后 `anon_id` 不被后续 upsert 覆盖；`list_chats_by_anon_async` |

`conftest.py` 中 `mock_anon_repo.get_or_create_async.return_value = "aaaabbbb-cccc-4000-aaaa-bbbbbbbbbbbb"`，端点测试不访问真实 DB。

### 10.2 前端

`fixtures.ts` 的 `mockChatResponse` 含 `anonId` 字段；`chat.test.ts` 中所有 `postChat` 调用带第三个参数。

---

## 11. 验收标准

| ID    | 标准                                                                                             |
| ----- | ------------------------------------------------------------------------------------------------ |
| AU-1  | 首次 `POST /chat`（`anon_id: null`）响应含非空 `anonId`，且 `users` 表新增一行                   |
| AU-2  | 携带相同 `anon_id` 的第二次 `POST /chat`，`users` 表行数不变，`updated_at` 刷新                  |
| AU-3  | 模块完成后，`chats.anon_id` 等于 `users.anon_id`，`users` 表 `user_id` 与 `anon_id` 对应          |
| AU-4  | `GET /chats?anon_id=<uuid>` 返回该用户的对话列表，按 `updated_at DESC` 排序                      |
| AU-5  | `GET /chats?anon_id=unknown-uuid` 返回空数组 `[]`，不返回 404                                    |
| AU-6  | `GET /chats?anon_id=not-a-uuid` 返回 HTTP 400 `BadRequestError`                                  |
| AU-7  | 前端刷新页面后，`localStorage` 中的 `anon_id` 在下次请求中自动携带                               |
| AU-8  | 注册后（P1-B）：`UPDATE users SET email = '...' WHERE anon_id = :anon_id`，`user_id` 不变        |
| AU-9  | `mypy --strict .` 对 `db/repositories/user.py` 通过，无类型错误                                  |
| AU-10 | `pytest` 102 tests passed，覆盖率 ≥ 80%                                                          |

---

## 12. 未来规划（P1-B）

### 12.1 注册流程

```sql
-- 注册时只需一次 UPDATE，user_id 不变，所有历史 chats 通过 anon_id 自动继承
UPDATE users
SET email      = 'user@example.com',
    updated_at = now()
WHERE anon_id  = :anon_id;
```

### 12.2 密码与 OAuth

注册时加入：

```sql
ALTER TABLE users
  ADD COLUMN password_hash TEXT,        -- bcrypt hash，nullable（OAuth 用户无密码）
  ADD COLUMN verified_at   TIMESTAMPTZ; -- 邮箱验证时间，NULL = 未验证
```

OAuth 账号单独建表（一个 `user_id` 可绑多个 provider）：

```sql
CREATE TABLE oauth_accounts (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID        NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    provider    TEXT        NOT NULL,   -- 'google' | 'github'
    provider_id TEXT        NOT NULL,
    UNIQUE (provider, provider_id)
);
```

### 12.3 `chats` 表加 `user_id`

P1-B 登录实现后，`POST /chat` 请求携带 auth token，可识别 `user_id`，此时给 `chats` 加一列：

```sql
ALTER TABLE chats ADD COLUMN user_id UUID REFERENCES users(user_id);
CREATE INDEX idx_chats_user_id ON chats (user_id) WHERE user_id IS NOT NULL;
```

新对话写入 `user_id`，旧匿名对话的 `user_id` 保持 NULL（通过 `anon_id` 仍可查询）。

### 12.4 Cookie 策略

P1-B auth token 使用 `HttpOnly SameSite=Strict` Cookie（XSS 不可读），配合后端收紧 CORS（`allow_origins` 改为白名单）。`anon_id` 继续在 localStorage，不影响 auth 安全性。