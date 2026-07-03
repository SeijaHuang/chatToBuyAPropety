# PropertyAI — 会话恢复（Redis 过期 → DB 兜底 + 欢迎消息）

## 技术 PRD v1.0

| 字段     | 值                                                       |
| -------- | -------------------------------------------------------- |
| 版本     | v1.0                                                     |
| 状态     | **Draft**                                                |
| 父文档   | PropertyAI_Database_PRD_v1_0.md                          |
| 范围     | `GET /chat/{session_id}` Redis 兜底 + LLM 欢迎消息生成   |
| 最后更新 | 01 Jul 2026                                              |

---

## 目录

1. [问题背景](#1-问题背景)
2. [目标与范围](#2-目标与范围)
3. [设计决策](#3-设计决策)
4. [恢复流程](#4-恢复流程)
5. [新 API 契约](#5-新-api-契约)
6. [状态重建](#6-状态重建)
7. [欢迎消息生成](#7-欢迎消息生成)
8. [新 Repository 方法](#8-新-repository-方法)
9. [新 Prompt Builder 函数](#9-新-prompt-builder-函数)
10. [新 DTO](#10-新-dto)
11. [错误处理](#11-错误处理)
12. [验收标准](#12-验收标准)
13. [不在范围内](#13-不在范围内)

---

## 1. 问题背景

`GET /chat/{session_id}` 当前只从 Redis 读取状态。Redis TTL 为**滑动 7 天**——每次 `save_session_async`（即每次 `POST /chat` 成功后）都会重置计时。若用户超过 7 天未对话，Redis key 过期，端点直接抛出 `SessionNotFoundError 404`。

但对话的结构化数据（`collected_data`、`borrowing_capacity` 等）已通过 `BackgroundTasks` 在模块完成时持久化到 `chats` 表。用户回来时不应看到 404——他们应该能看到之前收集内容的摘要，然后继续对话。

---

## 2. 目标与范围

### 2.1 目标

当 Redis miss 时，从 `chats` 表恢复结构化数据，在后端直接调用 LLM 生成一条欢迎消息，连同重建的状态快照一起返回给前端，让用户可以无缝继续 `POST /chat`。

### 2.2 范围内（本 PRD）

- 扩展 `GET /chat/{session_id}`：Redis miss → DB 查询 → 状态重建 → LLM 生成欢迎消息 → 将状态回写 Redis → 返回给前端
- 新增 `IChatRepository.get_chat_snapshot_async()` DB 读取方法
- 新增 `state_machine.recalculate_completion()` 辅助函数，从 `collected_data` 重新推导 `completion_status`
- 新增 `build_session_restore_prompt()` Prompt Builder 函数
- 新增 `SessionRestoreResponse` DTO，统一 Redis hit 和 DB restore 的响应结构

### 2.3 不在范围内

- 将 `conversation_history` 持久化到 DB（体积大，无结构化查询需求）
- 将 `completion_status` 持久化到 DB（派生自 `collected_data`，恢复时重推导即可）
- 恢复 `budget_gap`（派生值，下一次 `POST /chat` 有 `budget_max` 和 suburb 数据时自动重算）
- 前端改动（本 PRD 仅约定后端 API 契约）

---

## 3. 设计决策

### 3.1 全部在 GET 端点后端侧完成，不依赖前端二次请求

DB 恢复时，`GET /chat/{session_id}` 端点内部直接调用 `llm_client.complete_async()` 生成欢迎消息，将消息和状态快照一起返回。前端只需处理**一次**请求即可初始化 UI 并展示欢迎消息，无需额外调用 `POST /chat`。

### 3.2 统一响应结构 `SessionRestoreResponse`

Redis hit 和 DB restore 都通过同一端点返回 `SuccessResponse[SessionRestoreResponse]`：

```json
{ "resumeMessage": null, "state": { ... } }       // Redis hit：null，不调 LLM
{ "resumeMessage": "Welcome back！...", "state": { ... } } // DB restore：LLM 生成的字符串
```

前端通过 `resumeMessage` 是否为 `null` 区分两种情况，不需要额外的 `source` 枚举字段。

### 3.3 Redis TTL 是滑动 7 天

每次 `save_session_async` 调用都重置 TTL（见 `redis_store/session_store.py`），因此活跃用户永远不会触发 DB 恢复路径。DB restore 只针对超过 7 天未对话的用户。

DB 恢复成功后，重建的 `ConversationStateDTO` 立即通过 `session_store.save_session_async(state)` 写回 Redis，下一次 `GET` 或 `POST /chat` 将命中缓存。

### 3.4 `completion_status` 在恢复时从 `collected_data` 重新推导

`chats` 表不存 `completion_status`（M1/M2/M3/M4 布尔标志），原因：

- 它是 `collected_data` 的纯派生结果，`is_module_complete()` 在 `state_machine.py` 已有完整实现
- 存派生数据存在业务规则变更后 DB 与代码不一致的风险
- 重推导只需对四个模块各跑一次 `is_module_complete()`，计算代价可忽略

新增 `recalculate_completion(state)` 辅助函数（见 §6.1）负责原地更新 `CompletionStatus`。`current_module` 是 `CompletionStatus` 上的 `@computed_field`，标志更新后自动重算，无需额外操作。

### 3.5 欢迎消息作为历史的第一条 assistant turn 写入 Redis

DB 恢复时 `conversation_history` 为空列表（未持久化）。LLM 生成欢迎消息后，将 `{"role": "assistant", "content": resume_message}` 追加到 `state.conversation_history`，再写入 Redis。下一次 `POST /chat` 有先验 assistant 上下文，LLM 不会从零开始。

### 3.6 为什么需要 `get_chat_snapshot_async`

`IChatRepository` 现有的两个方法均无法满足需求：

| 现有方法 | 用途 |
| --- | --- |
| `upsert_chat_snapshot_async` | 写操作 |
| `list_chats_by_anon_async` | 按 `anon_id` 列举多行 |

恢复场景需要**按 `session_id` 精确读取单行**，这是一个全新的读取操作。

### 3.7 为什么需要 `build_session_restore_prompt`

欢迎消息的意图与现有 Builder 函数都不同：

| Builder 函数 | 用途 |
| --- | --- |
| `build_extraction_prompt` | Round 1 提取字段（极简，无角色/守则） |
| `build_question_prompt` | Round 2 生成下一个问题（完整堆栈） |
| `build_summary_prompt` | `/chat/summary` 最终需求总结 |
| **`build_session_restore_prompt`**（新增） | DB 恢复：承认回来 + 回顾已收集内容 + 引导继续 |

---

## 4. 恢复流程

```
GET /chat/{session_id}
    │
    ├─ UUID 格式校验失败 ──► BadRequestError 400
    │
    ├─ Redis hit
    │       └── 200 OK  SessionRestoreResponse(resume_message=None, state=snapshot)
    │
    └─ Redis miss
            │
            ├─ DB 查询：chat_repo.get_chat_snapshot_async(session_id)
            │
            ├─ DB miss ──► SessionNotFoundError 404
            │
            └─ DB hit (ChatRow)
                    │
                    ├── 反序列化 collected_data  → CollectedData.model_validate(row.collected_data)
                    ├── 反序列化 borrowing_capacity → BorrowingCapacityResult | None
                    ├── 构建 ConversationStateDTO(
                    │       session_id      = str(row.session_id),
                    │       status          = EStatus(row.status),
                    │       initial_intent  = EUserIntent(row.initial_intent) | None,
                    │       collected_data  = collected_data,
                    │       borrowing_capacity = borrowing_capacity,
                    │       conversation_history = []   ← 未持久化，从空开始
                    │   )
                    ├── recalculate_completion(state)
                    │       → M1/M2/M3/M4 标志从 collected_data 重新推导
                    │       → current_module 由 @computed_field 自动更新
                    ├── LLM 调用：
                    │       prompt = build_session_restore_prompt(state)
                    │       resume_message = await llm_client.complete_async(prompt, "")
                    ├── 追加 {"role":"assistant","content":resume_message}
                    │       到 state.conversation_history
                    ├── session_store.save_session_async(state)  ← 回写 Redis（滑动 7 天 TTL 重置）
                    └── 200 OK  SessionRestoreResponse(resume_message=resume_message, state=snapshot)
```

---

## 5. 新 API 契约

### 5.1 端点

```
GET /api/v1/chat/{session_id}
```

**路径参数：** `session_id` — UUID v4 字符串。

**成功响应 `200 OK`（Redis hit）：**

```json
{
  "data": {
    "resumeMessage": null,
    "state": {
      "sessionId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "currentModule": "M3_SUBURB_PREFERENCE",
      "status": "IN_PROGRESS",
      "completionStatus": { "M1": true, "M2": true, "M3": false, "M4": false, "allComplete": false, "currentModule": "M3_SUBURB_PREFERENCE" },
      "collectedData": { ... },
      "borrowingCapacity": null,
      "budgetGap": null
    }
  }
}
```

**成功响应 `200 OK`（DB restore）：**

```json
{
  "data": {
    "resumeMessage": "Welcome back！Last time you told me that you are looking for a 3-bedroom house for you and your child. We can continue with your commuting preference——where do you work?",
    "state": {
      "sessionId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "currentModule": "M3_SUBURB_PREFERENCE",
      "status": "IN_PROGRESS",
      "completionStatus": { "M1": true, "M2": true, "M3": false, "M4": false, "allComplete": false, "currentModule": "M3_SUBURB_PREFERENCE" },
      "collectedData": { ... },
      "borrowingCapacity": null,
      "budgetGap": null
    }
  }
}
```

**错误响应：**

| 场景 | HTTP 状态 | Error Code |
| --- | --- | --- |
| `session_id` 非合法 UUID | 400 | `BAD_REQUEST` |
| Redis miss + DB miss | 404 | `SESSION_NOT_FOUND` |
| DB 行存在但 `collected_data` 反序列化失败 | 404 | `SESSION_NOT_FOUND` |
| LLM 调用失败（DB restore 路径） | 503 | `LLM_SERVICE_UNAVAILABLE` |

> LLM 失败时**不**回写 Redis，下次请求会再次走 DB 恢复路径重试。

---

## 6. 状态重建

### 6.1 新辅助函数：`recalculate_completion()`

在 `conversation/state_machine.py` 新增：

```python
def recalculate_completion(state: ConversationStateDTO) -> None:
    """根据 collected_data 原地重新推导 completion_status。

    DB 恢复时调用，因为 completion_status 未持久化到 DB。
    对四个模块各运行一次 is_module_complete()；
    current_module 是 CompletionStatus 的 @computed_field，
    标志更新后自动重算，无需额外操作。

    Args:
        state: 需要原地更新 completion_status 的 ConversationStateDTO。
    """
    for submodel in ESubmodel:
        req: ModuleRequirements = MODULE_COMPLETION_RULES[submodel]
        state.completion_status.__dict__[submodel.name] = is_module_complete(
            state.collected_data, req
        )
```

### 6.2 `collected_data` 反序列化

DB 以 snake_case JSONB 存储（通过 `model_dump(by_alias=False)` 写入）：

```python
collected_data: CollectedData = CollectedData.model_validate(row.collected_data)
```

反序列化失败时记录日志并抛出 `SessionNotFoundError`。

### 6.3 `borrowing_capacity` 反序列化

DB 以 `dataclasses.asdict()` 序列化存储：

```python
borrowing_capacity: BorrowingCapacityResult | None = (
    BorrowingCapacityResult(**row.borrowing_capacity)
    if row.borrowing_capacity is not None
    else None
)
```

### 6.4 `status` 和 `initial_intent`

```python
status: EStatus = EStatus(row.status)
initial_intent: EUserIntent | None = (
    EUserIntent(row.initial_intent) if row.initial_intent is not None else None
)
```

---

## 7. 欢迎消息生成

### 7.1 按会话状态的消息意图

| `status` | LLM 任务 | 示例输出 |
| --- | --- | --- |
| `IN_PROGRESS` | 简洁回顾已收集内容；针对 `current_module` 提出下一个自然问题 | "欢迎回来！我们聊到你在找 3 卧室的 house 自住，家里有孩子。接下来聊通勤偏好——你平时去哪上班？" |
| `REQUIREMENTS_COMPLETE` | 告知已完成全部采集；引导查看总结或开始找房 | "欢迎回来！你的购房需求我们已经全部确认了。你是想回顾需求总结，还是直接开始搜索合适的房源？" |

### 7.2 Prompt 组装

`build_session_restore_prompt` 复用现有 section 库：

```
sections = [
    ROLE_DEFINITION,
    build_state_section(state),        # 现有：模块进度
    build_collected_summary(state),    # 现有：已采集字段摘要
    GUARDRAIL_RULES,
    SESSION_RESTORE_INSTRUCTION,       # 新增常量，见 §9.2
]
```

### 7.3 `SESSION_RESTORE_INSTRUCTION` 约束

- 最多 3 句话
- 第 1 句：自然承认用户是回来继续的（不得出现"数据库"、"缓存"、"会话"等技术词汇）
- 第 2 句：用口语简短回顾已知关键需求（不逐字复述每个字段）
- 第 3 句：`IN_PROGRESS` → 针对 `current_module` 提出最自然的下一个问题；`REQUIREMENTS_COMPLETE` → 提供下一步选项

---

## 8. 新 Repository 方法

在 `db/repositories/chat.py` 中为 `IChatRepository` Protocol 和 `SqlAlchemyChatRepository` 新增：

### 8.1 Protocol 新增方法

```python
async def get_chat_snapshot_async(self, session_id: str) -> ChatRow | None:
    """按 session_id 返回原始 ORM 行，不存在或 session_id 格式非法时返回 None。

    直接返回 ChatRow 对象，由调用方按需提取列，避免中间 DTO 映射。
    异常不向上传播——返回 None，由调用方决定是否 404。
    """
    ...
```

### 8.2 `SqlAlchemyChatRepository` 实现

```python
async def get_chat_snapshot_async(self, session_id: str) -> ChatRow | None:
    """按 session_id 查询单行 DB 记录，不存在返回 None。"""
    try:
        session_uuid: uuid.UUID = uuid.UUID(session_id)
    except ValueError:
        return None

    async with self._session_factory() as session:
        result = await session.execute(
            select(ChatRow).where(ChatRow.session_id == session_uuid)
        )
        return result.scalar_one_or_none()
```

---

## 9. 新 Prompt Builder 函数

### 9.1 `prompts/system_prompt_builder.py` 新增

```python
def build_session_restore_prompt(state: ConversationStateDTO) -> str:
    """为 DB 恢复路径组装欢迎消息的系统提示。

    意图不同于 build_question_prompt（正常对话轮次）和
    build_summary_prompt（最终需求总结）——专门用于生成
    用户回来时的简短欢迎 + 回顾 + 引导消息。

    Args:
        state: 从 DB 重建的 ConversationStateDTO（conversation_history 为空）。

    Returns:
        供 llm_client.complete_async() 使用的系统提示字符串。
    """
    sections: list[str] = [
        ROLE_DEFINITION,
        build_state_section(state),
        build_collected_summary(state),
        GUARDRAIL_RULES,
        SESSION_RESTORE_INSTRUCTION,
    ]
    return "\n\n".join(sections)
```

### 9.2 `prompts/sections/instructions.py` 新增常量

```python
SESSION_RESTORE_INSTRUCTION: str = """\
Task: The user is returning to a previous conversation restored from storage. \
Write a warm, concise welcome-back message in no more than 3 sentences:
1. Naturally acknowledge the user is returning. \
   Do NOT mention "database", "cache", "session", or any technical terms.
2. Briefly recap the key requirements already collected in plain language \
   (do not list every field verbatim).
3. If the conversation status is IN_PROGRESS: ask the single most natural \
   next question for the current module.
   If the conversation status is REQUIREMENTS_COMPLETE: acknowledge completion \
   and offer to review the summary or proceed to property search."""
```

---

## 10. 新 DTO

在 `models/chat.py` 新增：

```python
class SessionRestoreResponse(PropertyAIBaseModel):
    """GET /chat/{session_id} 的统一响应体。

    Attributes:
        resume_message: Redis hit 时为 None；DB restore 时为 LLM 生成的欢迎消息字符串。
            前端根据此字段是否为 null 决定是否将其渲染为第一条 assistant 消息。
        state: 与 ChatResponse.state 字段类型相同的轻量状态快照，
            供前端初始化进度条和已采集数据面板。
    """

    resume_message: str | None
    state: ConversationSnapshotDTO
```

### 10.1 端点返回类型变更

| 变更项 | Before | After |
| --- | --- | --- |
| 返回类型 | `SuccessResponse[ConversationStateDTO]` | `SuccessResponse[SessionRestoreResponse]` |
| `state` 字段类型 | `ConversationStateDTO`（含 `conversation_history`） | `ConversationSnapshotDTO`（不含，与 `ChatResponse.state` 一致） |

> `conversation_history` 从未暴露给前端（不在 `ChatResponse` 里），此次变更不影响前端对历史消息的处理。

---

## 11. 错误处理

| 条件 | 处理方式 |
| --- | --- |
| `session_id` 非合法 UUID 格式 | 在任何 IO 之前抛出 `BadRequestError` |
| Redis miss + DB miss | 抛出 `SessionNotFoundError(session_id)` |
| DB 行存在但 `collected_data` `model_validate` 失败 | `logger.exception("db_restore_validation_failed", session_id=session_id)` 后抛出 `SessionNotFoundError` |
| LLM 调用失败（DB restore 路径） | 抛出 `LLMServiceError`，**不**回写 Redis |
| Redis 回写失败（LLM 已成功） | `logger.warning("redis_reseed_failed", session_id=session_id)` 后吞噬——状态已返回前端，DB 行完整 |

---

## 12. 验收标准

| ID   | 标准 |
| ---- | ---- |
| SR-1 | Redis key 有效时，`GET /chat/{session_id}` 返回 `resumeMessage: null`，`state` 与 Redis 中状态一致，不发起 LLM 调用 |
| SR-2 | Redis key 过期但 DB 有记录时，返回非空 `resumeMessage` 和与 DB 持久化数据一致的 `state`（`collectedData`、`borrowingCapacity`）|
| SR-3 | DB restore 完成后，再次 `GET /chat/{session_id}` 返回 `resumeMessage: null`（状态已回写 Redis）|
| SR-4 | DB restore 后，用同一 `session_id` 正常调用 `POST /chat`，从恢复的状态继续推进模块，`resume_message` 出现在 `conversation_history` 里作为第一条 assistant turn |
| SR-5 | Redis miss + DB miss 返回 HTTP 404，`code: SESSION_NOT_FOUND` |
| SR-6 | 非法 UUID 格式的 `session_id` 返回 HTTP 400，`code: BAD_REQUEST`，不访问 Redis 或 DB |
| SR-7 | DB restore 路径 LLM 失败返回 HTTP 503，`code: LLM_SERVICE_UNAVAILABLE`，不写 Redis |
| SR-8 | 恢复的 `state.completionStatus` 与对应 `collectedData` 经 `recalculate_completion()` 推导的结果一致 |
| SR-9 | 恢复的 `state.borrowingCapacity` 与 `chats.borrowing_capacity` 存储值一致 |
| SR-10 | `IN_PROGRESS` 会话的 `resumeMessage` 包含针对 `currentModule` 的提问 |
| SR-11 | `REQUIREMENTS_COMPLETE` 会话的 `resumeMessage` 不再追问数据采集问题 |
| SR-12 | `mypy --strict` 对所有修改文件通过，无类型错误 |
| SR-13 | 新测试文件 `tests/test_session_restore.py` 覆盖所有成功路径和错误场景（LLM 调用 mock，不访问真实 API）|

---

## 13. 不在范围内

- `conversation_history` 持久化到 DB
- `completion_status` 持久化到 DB（派生自 `collected_data`，恢复时重推导）
- `budget_gap` 恢复（派生值，`POST /chat` 有 `budget_max` 和 suburb 数据时自动重算）
- 前端实现（本 PRD 仅约定后端 API 契约）
  - 前端参考：`resumeMessage !== null` → 将其渲染为 chat window 的第一条 assistant 气泡；`state` 用于初始化 Zustand store 和进度条，与 `ChatResponse.state` 处理方式相同