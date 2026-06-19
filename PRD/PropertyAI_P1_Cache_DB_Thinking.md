# PropertyAI — Cache Strategy Thinking

## 缓存策略技术思考记录

| Field        | Value                      |
| ------------ | -------------------------- |
| Version      | v0.1                       |
| Status       | Living Document — 持续更新 |
| Scope        | Part 1 — P1-A（匿名会话）  |
| Last Updated | 11 Jun 2026                |

> **说明**：本文档记录 PropertyAI 所有缓存相关的技术决策与取舍理由。涵盖 Session 状态缓存、数据库渐进快照、Agent 结果缓存、LLM Prompt Cache 等。是 `PropertyAI_Technical_Thinking.md` 中 §2–4 的专项展开。

---

## 目录

1. [总体架构：Redis 的两个用途](#1-总体架构redis-的两个用途)
2. [Session 状态缓存（Redis）](#2-session-状态缓存redis)
3. [PostgreSQL 渐进快照](#3-postgresql-渐进快照)
4. [Budget Gap Price Cache（唯一外部 API 缓存）](#4-budget-gap-price-cache唯一外部-api-缓存)
5. [Anthropic Prompt Cache](#5-anthropic-prompt-cache)
6. [P0 / P1-A 实施路线](#6-p0--p1-a-实施路线)

---

## 1 总体架构：Redis 的两个用途

**决策：Redis 承担两个完全独立的职责，必须在命名和 TTL(Time To Live) 上严格区分。**

`PropertyAI_PRD_v1_1.md` §7.1 Technology Stack 将 Redis 描述为"Session store + agent result cache"，但两者的性质截然不同，不能混用同一套设计思路：

| 用途                   | 存什么                                                   | Key 前缀       | TTL 策略              | 丢失影响                     |
| ---------------------- | -------------------------------------------------------- | -------------- | --------------------- | ---------------------------- |
| **Session Store**      | `ConversationStateDTO`（对话进度、已收集字段、对话历史） | `session:`     | 滑动窗口，7天         | 用户丢失对话进度，体验差     |
| **Agent Result Cache** | 外部 API 返回的数据（Overlay、School、Price 等）         | 各类型专属前缀 | 固定过期，6小时～30天 | 降级到重新调用 API，性能下降 |

**原则：**

- Session Store 是"工作内存"，Redis 是主要存储，PostgreSQL 是备份快照
- Agent Cache 是纯性能优化，Redis 缺失时直接穿透到外部 API
- 两者 key 前缀不重叠，互不干扰

---

## 2 Session 状态缓存（Redis）

**决策：Redis 存储完整 `ConversationStateDTO`，以 `session:{session_id}` 为 key，7天滑动 TTL。**

### 2.1 背景

P0 后端完全无状态——客户端每次请求都带上完整的 `ConversationStateDTO`（含 `conversationHistory`、已收集字段、模块状态等）。随着对话推进，payload 线性增长，最终可达数十 KB。同时，用户刷新浏览器或切换设备即丢失所有进度。

Session 状态缓存解决两个问题：

1. 减小请求 payload（从"带完整 state"变为"带 session_id"）
2. 支持跨浏览器、跨设备的对话恢复

### 2.2 完整对话流程（P1）

**路径 A：开始新对话**

```
用户点击"开始新对话"
  → uuid() 生成新 sessionId
  → localStorage 追加 { sessionId, title: null, lastActiveAt: now }
  → router.push(`/chat/${sessionId}`)

/chat/[sessionId] 页面加载
  → restoreFromStorage(sessionId)                          → null（新 session，无记录）
  → restoreFromServer(sessionId)                           → GET /api/v1/chat/{sessionId} → 404（Redis 无记录）
  → 显示空白对话界面

用户发消息
  → POST /api/v1/chat { session_id, message }
  → 后端：Redis 无此 key → 初始化新 ConversationStateDTO → 处理 → 存入 Redis → 返回响应
```

**路径 B：从历史列表进入旧对话**

```
用户在首页选择历史对话（P1 来源：localStorage）
  → router.push(`/chat/${existingSessionId}`)

/chat/[sessionId] 页面加载
  → restoreFromStorage(sessionId)                          成功 → 渲染历史对话 ✓（同一浏览器）
        ↓ sessionStorage 已清除（重启浏览器 / 换标签页）
  → restoreFromServer(sessionId) → GET /api/v1/chat/{sessionId}
        ↓ 200                                              成功 → 渲染历史对话 ✓（从 Redis 恢复）
        ↓ 404（Redis TTL 已过期，7 天未活跃）
  → 告知用户"对话已过期"，提示开始新对话

用户发消息
  → POST /api/v1/chat { session_id, message }
  → 后端：Redis 读取 → 处理 → 写回 Redis（TTL 重置）→ 返回响应
```

**历史列表的数据来源（P1 vs P2）：**

| 阶段             | 历史列表存在哪                          | 是否需要新 API               |
| ---------------- | --------------------------------------- | ---------------------------- |
| P1（无用户账户） | 浏览器 `localStorage`，换设备丢失       | ❌ 不需要                    |
| P2（有用户账户） | 服务端 `GET /api/v1/sessions`（需鉴权） | ✅ P2 新增，属于用户账户模块 |

两条路径都不需要 `POST /session`：新对话由前端 `uuid()` 生成 sessionId，旧对话的 sessionId 已存在于 localStorage。

### 2.3 前端恢复优先级

**P1 没有用户账户，"用户"等价于"持有这个 `session_id` 的浏览器"。**

`session_id` 由前端 `uuid()` 生成，保存在浏览器 `localStorage`，URL 路径 `/chat/[sessionId]` 决定展示哪个对话，后端凭 `session:{sessionId}` 从 Redis 取状态。Redis 里的 `ConversationStateDTO` 不含 `userId` 字段，跨设备识别同一用户要等 P2 引入用户账户（届时通过独立的 `user_sessions` 关联表映射 `user_id → session_id`）。

**不同场景下的恢复能力：**

| 场景                         | 结果                                                |
| ---------------------------- | --------------------------------------------------- |
| 同一浏览器、同一标签页刷新   | 从 sessionStorage 恢复 ✅                           |
| 换标签页 / 关闭重开          | 从 Redis 恢复 ✅                                    |
| 换设备                       | 历史列表在 localStorage，换设备丢失 ❌（P2 才解决） |
| Redis TTL 过期（7 天不活跃） | 提示"对话已过期"，无法恢复                          |

页面加载时按以下顺序尝试恢复（在 `ChatSessionPage` 的 `useEffect` 中）：

```
1. restoreFromStorage(sessionId)   → 读 sessionStorage，无网络，最快
         ↓ 失败（key 不存在）
2. restoreFromServer(sessionId)    → GET /api/v1/chat/{id}，从 Redis 恢复
         ↓ 失败（404，session 已过期或不存在）
3. 显示空白对话界面，等用户发首条消息，服务端自动初始化
```

### 2.4 UI 消息重建

**目的**

从 Redis 恢复的数据是服务端格式（`conversation_history: {role, content}[]`），前端无法直接渲染。需要把它翻译成 `UIMessage[]`（含 `id`、`timestamp`、`isLoading`、结果卡片等字段），用户才能看到之前的聊天记录。

**已存在**

`restoreFromStorage`（`conversationStore.ts:138–167`）已实现完整的翻译逻辑，是当前同一标签页刷新后能看到历史消息的原因：

```
conversation_history 每一条 → UIMessage:
  id        : uuid()        ← 重新生成
  role      : entry.role
  content   : entry.content
  isLoading : false
  timestamp : new Date()

追加结果卡片：
  borrowingCapacity !== null   → 追加空 content 的 assistant message（带借贷能力卡片）
  budgetGap?.has_gap === true  → 追加空 content 的 assistant message（带预算缺口卡片）
```

**需要新增**

`restoreFromServer` 方法（`conversationStore.ts`，目前不存在）：调 `GET /api/v1/chat/{sessionId}` 从 Redis 拿回 `ConversationStateDTO`，然后复用上述翻译逻辑重建 `UIMessage[]`。换标签页或换设备后能看到历史消息，靠的就是这个方法。

### 2.5 Redis Key Schema

```
Key:   session:{session_id}
Value: JSON 序列化的 ConversationStateDTO（snake_case，内部格式）
TTL:   604800 秒（7天，每次写入时重置）
```

```json
{
  "session_id": "uuid-v4",
  "status": "IN_PROGRESS | REQUIREMENTS_COMPLETE",
  "current_module": "M1_PROPERTY_NEEDS",
  "completion_status": { "M1": false, "M2": false, "M3": false, "M4": false },
  "collected_data": { "m1": {}, "m2": {}, "m3": {}, "m4": {} },
  "final_needs": null,
  "conversation_history": [],
  "borrowing_capacity": null,
  "budget_gap": null
}
```

> **注意**：`userId` 字段不存在于 P0/P1。P0 是匿名会话，用户账户是 P2 功能。届时通过独立的 `user_sessions` 关联表映射 `user_id → session_id`，不修改此 schema。

**已存在**

| 文件                                   | 行数    | 状态      | 说明                                                          |
| -------------------------------------- | ------- | --------- | ------------------------------------------------------------- |
| `backend/models/conversation_state.py` | 213–228 | ✅ 已存在 | `ConversationStateDTO` 定义了 schema 中所有字段，类型完全匹配 |

### 2.6 序列化方案

**目的**

字段名：`ConversationStateDTO` 同时有 snake_case（Python 内部）和 camelCase（HTTP 传输）两套名字。Redis 是后端内部存储，必须统一用 snake_case，否则存入和读出格式不一致会导致字段丢失。

**计划**

```python
# 存入 Redis — snake_case，不加 by_alias=True
state.model_dump_json()

# 从 Redis 读出 — populate_by_name=True 已设置，接受 snake_case
ConversationStateDTO.model_validate_json(raw)
```

**已存在 / 需要新增**

| 文件                          | 行数 | 状态          | 说明                                                                                                                                                                                                                                                                                      |
| ----------------------------- | ---- | ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `backend/models/base.py`      | —    | ✅ 已存在     | `PropertyAIBaseModel` 设置了 `alias_generator=to_camel` 和 `populate_by_name=True`，序列化用 snake_case 存入、读出时两种格式都能解析                                                                                                                                                      |
| `backend/models/financial.py` | —    | ⚠️ 需新增测试 | `BorrowingCapacityResult` / `BudgetGapResult` 是 `@dataclass` 而非 Pydantic model，Pydantic v2 序列化 dataclass 的反序列化路径不同——上线前必须写单元测试验证 `model_dump_json()` → `model_validate_json()` 往返能正确重建这两个字段，否则从 Redis 读出的值会是 `dict` 而非 dataclass 实例 |

### 2.7 TTL 策略

**目的**

控制 Redis 里会话数据的存活时间。活跃用户不应因为 TTL 到期丢失对话进度；长期不用的会话应自动清理，不持续占用 Redis 内存。

**计划**

- **滑动窗口**：每次写入（`save_state_async`）都用 `SETEX` 重置 TTL 为 7 天，而不是 `SET`。用户只要在用，计时器就持续刷新；7 天内完全没有操作才真正过期。
- **不主动删除**：用户点击"清除对话"时，前端只清 sessionStorage 和 Zustand 本地状态，不调删除 API，Redis key 等 TTL 自然过期。P0 用户量小，Redis 内存压力不大，不值得为此引入一个删除端点。

> P1 评估：若用户量上升、Redis 内存成为瓶颈，再加 `DELETE /api/v1/chat/{session_id}` 端点。

**已存在 / 需要新增**

| 文件                                       | 行数    | 状态      | 说明                                                                                                    |
| ------------------------------------------ | ------- | --------- | ------------------------------------------------------------------------------------------------------- |
| `frontend/src/stores/conversationStore.ts` | 170–176 | ✅ 已存在 | `clearSession()` 只清本地 sessionStorage + Zustand，P0 不需要调服务端删除接口，行为与计划一致，无需修改 |
| `backend/config.py`                        | 27      | ⚠️ 需新增 | `session_ttl_seconds: int = 604800`，将 TTL 值集中在配置里，避免 `RedisSessionStore` 内硬编码           |
| `backend/chat/_redis_store.py`             | —       | ⚠️ 需新建 | `save_state_async` 实现中必须用 `SETEX(key, ttl, value)` 而非 `SET`，才能在每次写入时重置 TTL           |

### 2.8 API 契约变化

**目的**

P0 后端无状态，前端每次请求都要带完整的 `ConversationStateDTO`，随对话增长 payload 越来越大，敏感字段（薪资、预算）也长期留在客户端。P1 加了 Redis 之后，服务端自己持有状态，前端只需要告诉服务端"我是谁"和"我说了什么"。

**计划**

```
POST /api/v1/chat

Request（P1 简化后）:
  - session_id: str        新增，前端生成的 UUID
  - message:    str        不变

Response（不变）:
  - reply, extracted, updated_state, routing
```

服务端收到请求后：

1. 用 `session_id` 查 Redis
2. 有数据 → 继续已有对话
3. 没数据 → 用这个 `session_id` 创建全新的 `ConversationStateDTO`，首条消息自动初始化

**新增：`GET /api/v1/chat/{session_id}`**

用于从 Redis 恢复 session 状态，涵盖三种场景：页面刷新、换标签页、从历史列表进入旧对话（见 §2.3 恢复优先级）。

```
→ 200: SuccessResponse<ConversationStateDTO>   （Redis 中存在）
→ 404: ErrorResponse SessionNotFoundError       （不存在或已过期）
```

**已存在 / 需要修改**

| 文件                                                | 行数    | 状态      | 说明                                                                                                   |
| --------------------------------------------------- | ------- | --------- | ------------------------------------------------------------------------------------------------------ |
| `frontend/src/lib/utils.ts`                         | 22–84   | ✅ 已存在 | `createInitialState(sessionId)` — 仅用于前端 UI 初始状态，不再发往服务端                               |
| `frontend/src/stores/conversationStore.ts`          | 62–79   | ✅ 已存在 | `setUpdatedState` — 无需修改                                                                           |
| `frontend/src/stores/conversationStore.ts`          | 138–167 | ✅ 已存在 | `restoreFromStorage` — 无需修改                                                                        |
| `frontend/src/stores/conversationStore.ts`          | 170–176 | ✅ 已存在 | `clearSession` — 无需修改                                                                              |
| `frontend/src/app/(main)/chat/[sessionId]/page.tsx` | 1–7     | ✅ 已存在 | 路由存在，可读 `params.sessionId`                                                                      |
| `frontend/src/app/(main)/page.tsx`                  | —       | ⚠️ 需修改 | 目前是占位符，添加"开始对话"按钮：`uuid()` 生成 sessionId → `router.push(/chat/${sessionId})`          |
| `frontend/src/app/(main)/chat/[sessionId]/page.tsx` | —       | ⚠️ 需修改 | 添加 `useEffect`：`restoreFromStorage` → `restoreFromServer` → 空界面                                  |
| `frontend/src/constants/endpoints.ts`               | 1–4     | ⚠️ 需修改 | 新增 `SESSION: (sessionId) => \`api/v1/chat/${sessionId}\``                                            |
| `frontend/src/services/chat.ts`                     | 5–9     | ⚠️ 需修改 | `postChat(message, state)` 改为 `postChat(message, sessionId)`                                         |
| `frontend/src/stores/conversationStore.ts`          | —       | 🆕 需新增 | `restoreFromServer(sessionId)` 方法：调 `getSession`，重建 `UIMessage[]`                               |
| `frontend/src/services/session.ts`                  | —       | 🆕 需新建 | `getSession(sessionId): Promise<APIResponse<ConversationStateDTO>>`                                    |
| `backend/models/chat.py`                            | 63–95   | ⚠️ 需修改 | `ChatRequest` 删除 `state: ConversationStateDTO`，新增 `session_id: str`                               |
| `backend/routers/chat.py`                           | —       | ⚠️ 需修改 | 不再从 `request.state` 取状态，改为 `session_store.load_state_async(session_id)`；未找到时初始化新状态 |

### 2.9 Redis 存储汇总

P1 中 Redis 存两类数据：

| 类型              | Key                            | Value 格式                                                    | TTL                         |
| ----------------- | ------------------------------ | ------------------------------------------------------------- | --------------------------- |
| 对话 session 状态 | `session:{session_id}`         | `ConversationStateDTO` 整体序列化为 JSON 字符串（snake_case） | 滑动窗口，7天，每次写入重置 |
| 郊区中位价        | `price:{suburb}:{type}:{beds}` | `{"median_price": int}` JSON 对象                             | 固定，24小时                |

Session DTO（`session:` key 的 value）内包含的字段：

| 字段                                                             | 说明                                                                |
| ---------------------------------------------------------------- | ------------------------------------------------------------------- |
| `session_id` / `status` / `current_module` / `completion_status` | 对话进度                                                            |
| `collected_data`                                                 | M1–M4 所有已收集字段                                                |
| `conversation_history`                                           | 每轮 `{role, content}`，供 LLM 上下文和前端消息恢复                 |
| `borrowing_capacity`                                             | M4 后计算，前端借贷卡片 + system prompt 使用；不单独建 key，不存 DB |
| `budget_gap`                                                     | M4 后计算，前端预算缺口卡片使用；不单独建 key，不存 DB（§3.5）      |
| `final_needs`                                                    | M4 完成后写入的完整 `UserNeeds` 快照                                |

不进 Redis（也不进 DB）：

| 内容                    | 原因                                   |
| ----------------------- | -------------------------------------- |
| LLM 对话回复 raw text   | 已追加进 `conversation_history` 持久化 |
| 每轮字段提取 raw dict   | 已合并进 `collected_data`              |
| 健康检查 `/health` 响应 | 无状态端点，缓存无意义                 |

---

## 3 PostgreSQL 渐进快照

**决策：每个模块完成时异步 upsert 一次，不仅仅在最终完成时归档。**

### 3.1 概览

如果只在 `REQUIREMENTS_COMPLETE`（M4 完成）时写库：

- 用户填到 M2 就放弃 → 什么数据都没有，无法用于统计或后续改进
- Redis TTL 期间 session 过期（对话横跨超过 7 天）→ 无法从 PostgreSQL 恢复
- 无法计算各模块的完成率（`PropertyAI_PRD_v1_1.md` §11 Success Metrics）

每模块写一次（累计快照）：

- M1 完成 → upsert：含 m1 的 CollectedData 快照
- M2 完成 → upsert：含 m1 + m2 的 CollectedData 快照
- M3 完成 → upsert：含 m1 + m2 + m3 的 CollectedData 快照
- M4 完成 → upsert：完整 UserNeeds（含所有模块 + initial_intent）

同一 `session_id` 覆盖更新，不产生多行。

### 3.2 触发点

`state_machine.py` 的 `merge_extracted_fields` 执行后，检测到某模块状态从 `False → True` 时，在 `routers/chat.py` 中使用 FastAPI `BackgroundTasks` 异步触发写库：

```python
background_tasks.add_task(db_archive.upsert_session_snapshot_async, state)
```

使用 `BackgroundTasks` 而非 `asyncio.create_task`——前者由 FastAPI 生命周期托管，服务器关闭时不会丢失任务；后者在服务器关闭时可能静默丢失。

### 3.3 表结构

```sql
CREATE TABLE IF NOT EXISTS sessions (
    session_id         UUID        PRIMARY KEY,
    status             TEXT        NOT NULL DEFAULT 'IN_PROGRESS',
    schema_version     TEXT        NOT NULL DEFAULT '1.1',
    initial_intent     TEXT,
    collected_data     JSONB       NOT NULL,
    final_needs        JSONB,
    borrowing_capacity JSONB,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sessions_status
    ON sessions (status);
CREATE INDEX IF NOT EXISTS idx_sessions_updated_at
    ON sessions (updated_at DESC);
```

> `final_needs`、`borrowing_capacity` 两个字段允许为 null——M4 完成前借贷能力可能尚未计算，对话未完成时 `final_needs` 也尚未生成。

### 3.4 upsert SQL

```sql
INSERT INTO sessions (
    session_id, status, initial_intent,
    collected_data, final_needs, borrowing_capacity,
    updated_at
)
VALUES ($1, $2, $3, $4, $5, $6, now())
ON CONFLICT (session_id)
DO UPDATE SET
    status             = EXCLUDED.status,
    initial_intent     = EXCLUDED.initial_intent,
    collected_data     = EXCLUDED.collected_data,
    final_needs        = EXCLUDED.final_needs,
    borrowing_capacity = EXCLUDED.borrowing_capacity,
    updated_at         = now();
```

### 3.5 不存 budget_gap

`budget_gap` 是由 `budget_max`（用户输入）加 Domain API 中位价计算得出的派生值。中位价每天更新，存入 PG 的快照隔天即过时，意义不大。

计算所需的原材料（`budget_max` 在 `collected_data`，郊区/房型在 `collected_data.m3/m1`）均已在 PG 中，Part 2 需要时可按需重算。活跃对话期间 Redis Session 里已有完整的 `budget_gap` 结果供前端展示。

### 3.6 不存 conversation_history

`conversation_history` 是每一轮对话的原始文字记录（`{"role": "user", "content": "..."}` 数组）。不写入 PG 的原因：

- **体积大且增长不可控**：每轮对话追加一条，长对话可能几十条，每次 upsert 都要写大量文本
- **不是结构化业务数据**：PG 归档的目的是存 `CollectedData` / `UserNeeds` 这类可查询、可分析的字段；原始聊天记录是 LLM 上下文，不是业务数据
- **Part 2 不需要它**：下游 agent 依赖的是 `UserNeeds` JSON，不需要看完整对话过程
- **Redis 已经够用**：活跃对话期间 Redis 完整持有历史，7 天 TTL 覆盖绝大多数使用场景

> 如果未来需要完整对话历史（调试 AI 质量、用于模型微调），应单独建一张 `conversation_messages` 表，按 `(session_id, turn_index)` 存储，而不是塞进 `sessions` 表的 JSONB 列。

### 3.7 P0 不做的部分

- `user_id` 字段不存在（P2 用户账户上线后加列 + backfill，additive 改动）
- Session 历史列表 API 不做（P1 随用户账户一起实现）

### 3.8 P1 数据库概览

P1 只有一张表：`sessions`。

| 字段                 | 类型        | 可空 | 说明                                    |
| -------------------- | ----------- | ---- | --------------------------------------- |
| `session_id`         | UUID        | ❌   | UUID v4，主键                           |
| `status`             | TEXT        | ❌   | `IN_PROGRESS` / `REQUIREMENTS_COMPLETE` |
| `schema_version`     | TEXT        | ❌   | 当前固定 `'1.1'`                        |
| `initial_intent`     | TEXT        | ✅   | M1 完成后首次写入                       |
| `collected_data`     | JSONB       | ❌   | 所有模块已收集字段的累计快照            |
| `final_needs`        | JSONB       | ✅   | M4 完成后写入完整 `UserNeeds`           |
| `borrowing_capacity` | JSONB       | ✅   | M4 完成后写入借贷能力估算结果           |
| `created_at`         | TIMESTAMPTZ | ❌   | 行创建时间，自动生成                    |
| `updated_at`         | TIMESTAMPTZ | ❌   | 每次 upsert 更新                        |

写入时机：M1→M4 每个模块完成时各异步 upsert 一次，同一 `session_id` 覆盖更新（见 §3.2）。完整 DDL 见 §3.3。

---

## 4 Budget Gap Price Cache（唯一外部 API 缓存）

**决策：P1 中唯一的外部 API 调用（Domain API 郊区中位价）值得加缓存。**

`budget_gap_detector.py` 调用 Domain API 查询 `suburb + property_type + min_bedrooms` 组合的中位价。同一组合一天内结果不变，但每次对话都会触发调用。

```
Key:   price:{suburb}:{property_type}:{min_bedrooms}
Value: {"median_price": 850000}   ← JSON 对象，非裸 int（留扩展空间）
TTL:   86400 秒（24小时，固定过期）
```

这个 `price:` cache 属于 §1 定义的 **Agent Result Cache** 类型，是 P1 阶段引入的唯一一条 Agent 结果缓存。加入 Redis 连接后顺带实现，不需要额外基础设施。

> Value 使用 JSON 对象而非裸 int，为 Part 2 将来在同一 key 里追加字段（如趋势、置信区间）预留扩展空间——Part 1 只读 `median_price` 字段，不受影响。

---

## 5 Anthropic Prompt Cache

### 5.1 目的与原理

**目的**：减少每次 LLM 调用中重复发送的静态 token，降低 API 费用。

**原理**：正常情况下，每次调用 Claude API 都要发送完整的 system prompt。我们的 system prompt 分四段：

```
Section 1 — Role Definition     ← 静态，每轮完全相同
Section 2 — Current State       ← 每轮变化（当前模块、已收集字段）
Section 3 — M1→M2 Context       ← M1 完成后固定，此前每轮变化
Section 4 — Guardrail Rules     ← 静态，每轮完全相同
```

Section 1 + Section 4 每轮都原样发送，但内容永远不变，这部分 token 是纯浪费。

Anthropic Prompt Cache 允许在请求体里给某段内容加 `cache_control` 标记。Anthropic 服务器收到后，把这段内容缓存 5 分钟（存在 Anthropic 服务器上，和我们的 Redis 无关）。5 分钟内的后续请求命中缓存，这部分 token 按缓存读价格计费（约为正常价格的 1/10）。

对于一个 30 轮的对话，Section 1 + 4 大约 500 token，没有 cache 时每轮都付 500 token，有 cache 后只有第一轮付正常价，后续都按缓存价，成本可降约 30–40%。

### 5.2 现有代码能否实现

**不能直接在现有代码上实现，需要替换 HTTP 层。**

原因分两层：

**问题一：SDK 不支持透传 `cache_control`**

现有 `OpenRouterClient`（`domain/llm_client.py`）使用 OpenAI Python SDK 发请求：

```python
# 当前代码，content 是纯字符串
full_messages: list[Any] = [{"role": "system", "content": system_prompt}, *messages]
```

要启用 Prompt Cache，`content` 必须改为内容块数组：

```python
{"role": "system", "content": [
    {"type": "text", "text": "...", "cache_control": {"type": "ephemeral"}},
    {"type": "text", "text": "..."}
]}
```

`cache_control` 是 Anthropic 的私有扩展字段，OpenAI SDK 的类型定义里没有它。即使通过 `list[Any]` 传入 dict，SDK 在序列化时会做类型校验，未知字段可能被静默丢弃。行为不可靠，不能依赖。

**问题二：`ILLMClient` 接口和 `system_prompt_builder` 都假设 system prompt 是单一字符串**

`ILLMClient.chat_with_tools_async(system_prompt: str, ...)` 接收的是拼好的完整字符串，无法区分哪段是静态的。要支持 cache，需要让调用方能传入"静态部分"和"动态部分"，或者让 client 内部知道怎么切分。

### 5.3 P1 实现方案

三处改动，互不影响现有 P0 测试：

**改动一：`system_prompt_builder.py` 暴露静态段**

新增 `get_static_sections() -> str`，返回 Section 1 + Section 4 拼接结果。现有 `build_question_prompt` 等函数不变，`get_static_sections` 只供新 client 使用。

**改动二：新建 `HttpxOpenRouterClient` 实现 `ILLMClient`**

在 `domain/llm_client.py` 新增一个用 httpx 构造原始 HTTP 请求的实现类，替代 OpenAI SDK：

```python
class HttpxOpenRouterClient(ILLMClient):
    async def chat_with_tools_async(self, system_prompt: str, messages, tools):
        static = get_static_sections()           # Section 1 + 4
        dynamic = system_prompt.replace(static, "").strip()  # Section 2 + 3

        payload = {
            "model": settings.model_strong,
            "messages": [
                {
                    "role": "system",
                    "content": [
                        {"type": "text", "text": static,
                         "cache_control": {"type": "ephemeral"}},
                        {"type": "text", "text": dynamic},
                    ],
                },
                *messages,
            ],
            "tools": tools,
            "tool_choice": "auto",
        }
        # httpx 直接发 JSON，不经过 OpenAI SDK
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                settings.llm_base_url + "/chat/completions",
                headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
                json=payload,
            )
        ...
```

`OpenRouterClient`（OpenAI SDK）保留不动，P0 测试继续跑原来的 mock，无需修改。

**改动三：`main.py` lifespan 换注入的实现**

```python
# P0
llm_client = OpenRouterClient()

# P1（改这一行）
llm_client = HttpxOpenRouterClient()
```

> **前提**：实施前需确认 OpenRouter 是否将 `cache_control` 透传给 Anthropic（见 §7 待讨论议题 #3）。若不透传，则 `HttpxOpenRouterClient` 的 `base_url` 改为直连 Anthropic API，OpenRouter 作为备选路由。

---

## 6 P0 / P1-A 实施路线

### P0 — 当前已实现

| 功能                       | 说明                                                        |
| -------------------------- | ----------------------------------------------------------- |
| 后端无状态                 | 每次请求客户端携带完整 `ConversationStateDTO`，无服务端存储 |
| 前端 `sessionStorage` 缓存 | `restoreFromStorage` 已实现，同一标签页刷新可恢复对话       |

换标签页、换设备、刷新浏览器（清缓存）会丢失对话进度——这是 P1 要解决的问题。

### P1-A — 待实现（本文档覆盖范围，匿名会话）

| 功能                   | 详见 | 说明                                                                                     |
| ---------------------- | ---- | ---------------------------------------------------------------------------------------- |
| Redis Session Store    | §2   | `session:{id}` 存 ConversationStateDTO，7天滑动 TTL                                      |
| PostgreSQL 渐进快照    | §3   | 每模块完成时 upsert，`BackgroundTasks` 异步写                                            |
| `GET /chat/{id}` 端点  | §2.8 | 跨设备 / 跨标签页恢复对话                                                                |
| Budget Gap Price Cache | §4   | `price:{suburb}:{type}:{beds}`，24小时固定 TTL                                           |
| Anthropic Prompt Cache | §5   | 静态 prompt 段加 `cache_control`，通过 httpx 实现                                        |
| 流式响应（SSE）        | —    | 文字实时流式，`updated_state` 作为末尾 event（见 `PropertyAI_Technical_Thinking.md` §1） |

### P1-B / P2 — 暂不实现（留存理由）

| 功能                           | P1-A 不做的理由                                                                                                                                                                                 | 触发条件                                                                                                                                                                                                |
| ------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **用户账户 / 认证（P1-B）**    | P1-A 是匿名会话，"用户"等价于"持有 session_id 的浏览器"，无需身份体系；引入账户会增加注册/登录流程，超出当前 MVP 范围                                                                           | 需要跨设备同步对话历史、用户画像持久化、或用户主动管理历史会话时实现                                                                                                                                    |
| **SESSION_SECRET_KEY（P1-B）** | P1-A 的 session_id 是 UUID v4（122 位随机熵），本身不可猜测，无需额外签名；无用户账户则无需防止 A 访问 B 的数据                                                                                 | P1-B 引入 JWT 认证后，`SESSION_SECRET_KEY` 用于签发 token，保护会话端点                                                                                                                                 |
| **Session 历史列表（P1-B）**   | 需要用户 ID 作为 key（`user:{user_id}:sessions`），P1-A 无用户账户，无法关联                                                                                                                    | P1-B 实现用户注册/登录后，同步建立 Redis ZSET 历史索引                                                                                                                                                  |
| **Request Signature（P2）**    | P1-A 是匿名会话，没有用户身份可证明；`session_id` 本身是 122 位随机 UUID，充当 secret，猜中概率为 2⁻¹²²，暴力枚举不可行；session 里存的是房产偏好，敏感度低，signature 的保护收益远小于引入成本 | P2 引入用户账户后，需要防止用户 A 读取用户 B 的会话；届时在 HTTP 请求头加 `Authorization: Bearer <JWT>`，JWT 含 `user_id`，后端校验 `session.user_id == jwt.user_id`，而不是给 `session_id` 本身加 HMAC |
