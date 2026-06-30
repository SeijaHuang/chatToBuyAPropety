# PropertyAI — 匿名用户身份系统

## Technical PRD v1.1

| 字段         | 值                                                             |
| ------------ | -------------------------------------------------------------- |
| Version      | v1.1                                                           |
| Status       | **v1.0 Implemented · v1.1 Planned**                           |
| 父文档       | PropertyAI_Database_PRD_v1_0.md                               |
| Scope        | 匿名用户身份追踪、`users` 表、Cookie 传输（v1.1 新增）         |
| Last Updated | 30 Jun 2026                                                    |

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
13. [v1.1：HttpOnly Cookie 传输](#13-v11httponly-cookie-传输)

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

### 2.4 CORS 约束与传输渠道演进

**v1.0（已实现）：** `allow_origins=["*"]` 时浏览器规范禁止同时使用 `allow_credentials=True`，因此无法通过 Cookie 传递 `anon_id`。当时选择：

- `anon_id` 存入前端 `localStorage`，每次 `POST /chat` 放入 request body
- 后端返回 `resolved_anon_id`，前端收到后写回 localStorage

**v1.1（本次计划）：** 将 CORS `allow_origins` 改为精确白名单后，Cookie 传输成为可能——详见 [§13](#13-v11httponly-cookie-传输)。

### 2.5 v1.1 设计决策：迁移至 HttpOnly Cookie

**放弃的方案：** 继续用 request body + localStorage（v1.0 方案）。

**选择 HttpOnly Cookie 的原因：**

| 关注点 | v1.0（localStorage + body） | v1.1（HttpOnly Cookie） |
| ------ | --------------------------- | ----------------------- |
| XSS 防护 | JS 可读 — XSS 可窃取 anon_id | JS 不可读 — HttpOnly 阻止读取 |
| 传输自动化 | 前端手动读取 / 写入 / 携带 | 浏览器自动携带，无需前端状态管理 |
| 前端代码量 | store + localStorage + useEffect | 仅需 `withCredentials: true` |
| P1-B 一致性 | auth token 走 Cookie，anon_id 走 body（两套） | 统一走 Cookie |
| CORS 要求 | allow_origins=["*"] 可用 | 必须用精确白名单 |

HttpOnly Cookie 在生产环境（同域部署）下是最优解，前端零状态管理，安全性显著提升。

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

P1-B auth token 使用 `HttpOnly SameSite=Strict` Cookie（XSS 不可读）。CORS 白名单（`allow_origins`）已在 v1.1 完成收紧，P1-B 可直接复用同一基础设施。`anon_id` 在 v1.1 已迁移至 Cookie，两者共存互不干扰。

---

## 13. v1.1：HttpOnly Cookie 传输

> **状态：Planned**  
> v1.0 使用 localStorage + request body 传递 `anon_id`（§2.4 原因）。v1.1 将其迁移至 HttpOnly Cookie，提升安全性并为 P1-B auth 统一基础设施。

### 13.1 目标

| 目标 | 具体效果 |
| ---- | -------- |
| XSS 防护 | `HttpOnly` 使 JS 无法通过 `document.cookie` 读取 `anon_id` |
| 前端零状态管理 | 移除 `anonId` store、localStorage 逻辑、request body 字段 |
| P1-B 统一基础设施 | `anon_id` 与未来 auth token 使用同一 Cookie 机制 |

### 13.2 In Scope（v1.1）

- CORS `allow_origins` 由 `["*"]` 改为白名单（开发: `["http://localhost:3000"]`）
- 后端 `POST /chat`：从 Cookie 读取 `anon_id`，响应设置 `Set-Cookie`
- 后端 `GET /chats`：从 Cookie 读取 `anon_id`，**移除** `?anon_id=<uuid>` query param
- 新建 FastAPI Dependency `resolve_anon_id_async` 统一 cookie 读取与用户解析
- 移除 `ChatRequest.anon_id`、`ChatResponse.anon_id` 字段
- 前端 Axios 添加 `withCredentials: true`
- 前端完全移除 `anonId` localStorage、store 状态、`setAnonId` action、`useEffect` 水合

### 13.3 Out of Scope

- Cookie rotation（注册/登录后换发新 cookie）— P1-B
- CSRF Token（`SameSite=Strict` + 同域已足够防护）
- 多设备 cookie 同步 — P2

---

### 13.4 Cookie 属性规范

| 属性 | 值 | 理由 |
| ---- | -- | ---- |
| Name | `propertyai_anon_id` | 项目命名空间前缀，避免与未来 auth cookie 冲突 |
| HttpOnly | `true` | JS 不可读，阻止 XSS 窃取 |
| SameSite | `Strict` | 同域部署，最强 CSRF 防护；localhost 开发同属一个 site |
| Secure | `settings.cookie_secure`（prod=True，dev=False） | dev 无 HTTPS，通过 env var 控制 |
| Path | `/api/v1` | 限定 Cookie 仅发往后端 API 路由，不污染其他路径 |
| Max-Age | `31536000`（1 年） | 长期匿名身份；每次成功请求自动续期 |

---

### 13.5 后端变更

#### 13.5.1 `config.py` — 新增配置字段

```python
class Settings(BaseSettings):
    # ... 现有字段 ...
    allow_origins_list: list[str] = ["http://localhost:3000"]
    cookie_secure: bool = True   # .env 中开发环境设为 False
```

#### 13.5.2 `main.py` — CORS 白名单

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allow_origins_list,  # 替换原 ["*"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

#### 13.5.3 统一 Cookie 依赖：`dependencies/anon_id.py`（新建）

> **设计意图**：所有需要 `anon_id` 的 endpoint 注入同一个 Dependency，避免各 endpoint 重复读 Cookie 字段名和调用 `get_or_create_async`。

```python
"""FastAPI dependency — resolves anon_id from HttpOnly cookie."""

from typing import Annotated
from fastapi import Cookie, Depends
from db.repositories.user import IUserRepository, get_user_repository


async def resolve_anon_id_async(
    propertyai_anon_id: Annotated[str | None, Cookie()] = None,
    anon_repo: Annotated[IUserRepository, Depends(get_user_repository)] = ...,
) -> str:
    """Read anon_id from HttpOnly cookie and resolve to a DB-backed identity.

    On first request (no cookie): creates a new user row and returns the new anon_id.
    On subsequent requests: refreshes updated_at and returns the existing anon_id.
    On malformed cookie value: treats as absent, creates fresh identity.

    Returns:
        A non-None str guaranteed to correspond to an existing users row.
    """
    return await anon_repo.get_or_create_async(propertyai_anon_id)
```

路由注入方式：

```python
resolved_anon_id: Annotated[str, Depends(resolve_anon_id_async)]
```

#### 13.5.4 `routers/chat.py` — `POST /chat` 变更

```python
from fastapi import Response
from dependencies.anon_id import resolve_anon_id_async
from config import settings

@router.post("/chat", tags=["chat"])
async def chat_async(
    request: ChatRequest,
    response: Response,                   # 新增：用于 Set-Cookie
    background_tasks: BackgroundTasks,
    llm_client: Annotated[ILLMClient, Depends(lambda: _default_llm_client)],
    chat_repo: Annotated[SqlAlchemyChatRepository, Depends(get_chat_repository)],
    resolved_anon_id: Annotated[str, Depends(resolve_anon_id_async)],  # 替换 anon_repo 注入
) -> SuccessResponse[ChatResponse]:
    # 1. 设置 / 续期 Cookie（每次成功请求都续期 Max-Age）
    response.set_cookie(
        key="propertyai_anon_id",
        value=resolved_anon_id,
        httponly=True,
        samesite="strict",
        secure=settings.cookie_secure,
        path="/api/v1",
        max_age=31_536_000,
    )

    # 2. 原有 anon_repo.get_or_create_async 调用行删除
    # resolved_anon_id 已由 Dependency 注入

    # ... 其余逻辑不变 ...

    return SuccessResponse[ChatResponse](
        data=ChatResponse(
            reply=reply,
            extracted=extracted,
            session_id=state.session_id,
            # anon_id 字段已移除 — cookie 通过 Set-Cookie header 下发
            state=snapshot,
            routing=routing,
        )
    )
```

#### 13.5.5 `routers/chat.py` — `GET /chats` 变更

**原 API：** `GET /api/v1/chats?anon_id=<uuid>`（query param）  
**新 API：** `GET /api/v1/chats`（从 Cookie 读取，URL 不暴露 UUID）

```python
@router.get("/chats", tags=["chat"])
async def list_chats_async(
    chat_repo: Annotated[SqlAlchemyChatRepository, Depends(get_chat_repository)],
    resolved_anon_id: Annotated[str, Depends(resolve_anon_id_async)],
) -> SuccessResponse[list[ChatSessionDTO]]:
    """Return all chat sessions for the current anonymous user.

    anon_id is read from the HttpOnly cookie; no query parameter required.
    Returns an empty list when no sessions exist — avoids leaking enumeration info.
    """
    sessions: list[ChatSessionDTO] = await chat_repo.list_chats_by_anon_async(resolved_anon_id)
    logger.info("list_chats_response", count=len(sessions))
    return SuccessResponse[list[ChatSessionDTO]](data=sessions)
```

> **注意**：`resolve_anon_id_async` 在 Cookie 缺失时会为该请求创建新用户并返回新 `anon_id`。对于 `GET /chats`，这会导致返回空列表而非 400 错误，符合「防枚举」原则（§6.2 验收标准 AU-5 精神）。如果业务上更希望无 Cookie 时返回 400，可使用一个"仅读取不创建"的变体 Dependency（见 §13.6）。

#### 13.5.6 `models/chat.py` — 字段变更

```python
# 移除：
class ChatRequest(PropertyAIBaseModel):
    anon_id: str | None  # ← 删除此字段

# 移除：
class ChatResponse(PropertyAIBaseModel):
    anon_id: str         # ← 删除此字段
```

---

### 13.6 可选：`GET /chats` 严格模式 Dependency

如需在无 Cookie 时返回 400（而非创建新用户），可额外定义一个读取专用 Dependency：

```python
async def require_anon_id_cookie_async(
    propertyai_anon_id: Annotated[str | None, Cookie()] = None,
) -> str:
    """Require anon_id cookie; raise 400 if absent or malformed."""
    if propertyai_anon_id is None:
        raise BadRequestError("propertyai_anon_id cookie is required.")
    try:
        uuid.UUID(propertyai_anon_id)
    except ValueError:
        raise BadRequestError(f"Invalid anon_id cookie value: '{propertyai_anon_id}'.")
    return propertyai_anon_id
```

`GET /chats` 可在 §13.5.5 的 `resolve_anon_id_async` 位置换用此 Dependency，按产品决策选择。

---

### 13.7 前端变更

#### 13.7.1 `lib/request.ts` — withCredentials

```typescript
const instance = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_BASE_URL,
  withCredentials: true,   // 新增：每个请求自动携带 Cookie
  timeout: 30_000,
  // ... 其余配置不变 ...
})
```

#### 13.7.2 移除 `anonId` 相关代码

| 文件 | 变更 |
| ---- | ---- |
| `constants/storageKeys.ts` | 删除 `ANON_ID: 'propertyai.anonId'` |
| `stores/conversationStore.ts` | 删除 `anonId: string \| null` 状态字段、`setAnonId(anonId: string): void` action 及 `localStorage.setItem` 调用 |
| `services/chat.ts` | `postChat` 签名移除 `anonId: string \| null` 参数；body 不再发送 `anonId` |
| `hooks/useChat.ts` | 删除 `anonId` 水合 `useEffect`；删除 `store.anonId ?? localStorage.getItem(...)` 读取；删除 `store.setAnonId(response.data.anonId)` |
| `types/api.d.ts` | `ChatResponse` 接口删除 `anonId: string` 字段 |

#### 13.7.3 `services/chat.ts` 变更示例

```typescript
// Before
export function postChat(
  message: string,
  sessionId: string | null,
  anonId: string | null,
): Promise<APIResponse<ChatResponse>> {
  return request.post<ChatResponse>(ENDPOINTS.CHAT, { message, sessionId, anonId })
}

// After
export function postChat(
  message: string,
  sessionId: string | null,
): Promise<APIResponse<ChatResponse>> {
  return request.post<ChatResponse>(ENDPOINTS.CHAT, { message, sessionId })
}
```

#### 13.7.4 `hooks/useChat.ts` 变更要点

```typescript
// 删除：anonId 水合 useEffect
// 删除：const anonId = store.anonId ?? localStorage.getItem(STORAGE_KEY.ANON_ID)
// 删除：store.setAnonId(response.data.anonId)

// Before
const response = await postChat(content, sessionId, anonId)
// After
const response = await postChat(content, sessionId)
```

---

### 13.8 项目结构新增文件

```
backend/
└── routers/
    └── deps.py    ← 新建：resolve_anon_id_async / require_anon_id_cookie_async
```

---

### 13.9 测试策略变更

#### 13.9.1 后端

| 测试文件 | 变更 |
| -------- | ---- |
| `conftest.py` | `mock_anon_repo` 不变；`client_async` 改用 `AsyncClient(cookies={"propertyai_anon_id": "..."})` 传 cookie |
| `test_chat_endpoint.py` | 断言 response 含 `Set-Cookie: propertyai_anon_id=...` header；不再断言 `body.anonId`；新增无 Cookie 场景（首次创建） |
| `test_anon_id_dependency.py`（新建） | `resolve_anon_id_async` 单元测试：cookie 存在命中、不存在创建、非法 UUID 处理 |
| `test_chat_repository.py` | 不变 |

#### 13.9.2 前端

| 测试文件 | 变更 |
| -------- | ---- |
| `__tests__/msw/handlers.ts` | mock response 移除 `anonId` 字段 |
| `__tests__/hooks/useChat.test.ts` | 删除 localStorage `anonId` 相关断言；`postChat` mock 移除第三个参数 |
| `__tests__/stores/conversationStore.test.ts` | 删除 `setAnonId` / `anonId` 相关测试 case |

---

### 13.10 验收标准

| ID | 标准 |
| -- | ---- |
| CK-1 | 首次 `POST /chat`（无 Cookie）：response header 含 `Set-Cookie: propertyai_anon_id=<uuid>; HttpOnly; SameSite=Strict; Path=/api/v1` |
| CK-2 | 第二次 `POST /chat`（浏览器自动携带 Cookie）：`users.updated_at` 刷新，Set-Cookie 续期 Max-Age |
| CK-3 | `GET /api/v1/chats`（Cookie 自动携带，无 query param）：返回该用户历史对话列表 |
| CK-4 | `GET /api/v1/chats`（无 Cookie，使用严格模式 Dependency）：返回 HTTP 400 `BadRequestError` |
| CK-5 | XSS 验证：DevTools Console 中 `document.cookie` 不含 `propertyai_anon_id`（HttpOnly 生效） |
| CK-6 | `ChatRequest` body 不含 `anon_id` 字段；`ChatResponse` body 不含 `anon_id` 字段 |
| CK-7 | 前端 `localStorage` 不写入 / 读取 `propertyai.anonId` |
| CK-8 | Axios 每次请求自动携带 Cookie（DevTools Network 可见 `Cookie: propertyai_anon_id=...`） |
| CK-9 | `mypy --strict .` 通过，含新建 `dependencies/anon_id.py` |
| CK-10 | `pytest` 全部通过，覆盖率 ≥ 80%，含 `test_anon_id_dependency.py` |
| CK-11 | `pnpm test:run` 全部通过 |