# PropertyAI — 后端（Part 1 对话层）

## 技术 PRD v2.0 — 合并版·当前状态参考文档

| 字段 | 值 |
| --- | --- |
| 版本 | v2.0 |
| 状态 | **当前有效 —— 反映本文档日期时后端的实际实现** |
| 取代 | `PropertyAI_Part1_Technical_PRD_v1_1.md`、`PropertyAI_Database_PRD_v1_0.md`、`PropertyAI_Anonymous_User_PRD_v1_0.md`、`PropertyAI_Session_Restore_PRD_v1_0.md`（四份文档已作废，内容合并并与 repo 现状核对后整理于此） |
| 父文档 | `PRD/PropertyAI_PRD_v1_1.md` |
| 范围 | 后端对话层：状态机、LLM 编排、Redis 会话存储、PostgreSQL 历史记录、匿名身份、会话恢复 |
| 配套文档 | [docs/backend-implementation.md](../../docs/backend-implementation.md) —— 权威的源文件地图与开发命令归属于此，本文档不重复 |
| 最后更新 | 03 Jul 2026 |

---

## 为什么需要这份文档

上面列出的四份 PRD 写于项目的不同阶段，描述的是同一系统在不同时间点的状态（前端持有状态 → Redis → Postgres → Cookie 匿名身份 → DB 兜底会话恢复），彼此有重叠甚至冲突。其中不少标记为 **Draft** 或 **Planned** 的章节，在当前代码中已经完整实现；也有一些原始字段/类型规格在实现过程中被替换。本文档用**当前 repo 中后端的真实状态**替代这四份文档，并附上仍未实现的 P1-B 规划。仅在能解释某个非显而易见的设计取舍时才保留历史决策说明；原始 PRD 中逐条的验收标准和单元测试清单不在此复述——最新覆盖范围见 `backend/tests/`。

---

## 目录

1. [目标与范围](#1-目标与范围)
2. [技术栈](#2-技术栈)
3. [系统架构](#3-系统架构)
4. [请求流程 —— 双轮 LLM 架构](#4-请求流程--双轮-llm-架构)
5. [数据模型](#5-数据模型)
6. [模块状态机](#6-模块状态机)
7. [API 契约](#7-api-契约)
8. [身份与持久化模型](#8-身份与持久化模型)
9. [会话恢复（Redis 未命中 → DB 兜底）](#9-会话恢复redis-未命中--db-兜底)
10. [金融服务 —— 借款能力与预算缺口](#10-金融服务--借款能力与预算缺口)
11. [意图路由与 Part 2 交接](#11-意图路由与-part-2-交接)
12. [数据库 Schema](#12-数据库-schema)
13. [错误处理](#13-错误处理)
14. [环境变量](#14-环境变量)
15. [值得记录的设计决策](#15-值得记录的设计决策)
16. [范围外 / P1-B 规划](#16-范围外--p1-b-规划)

---

## 1. 目标与范围

### 1.1 目标

通过自然语言对话引导用户完成四个连续的对话模块（M1→M4），采集结构化的购房需求，最终将结构化的 `UserNeeds` 交给 Part 2（房源/郊区 agent）。后端持有全部对话状态权威，前端只是只读展示客户端。

### 1.2 已实现（P0 + P1-A）

- 四模块顺序对话，支持非线性字段提取（用户在 M1 阶段也可以主动提供 M3/M4 信息）
- 每轮对话双轮 LLM 调用架构（先提取，后生成回复）
- 会话状态由**服务端 Redis** 持有（滑动 7 天 TTL）——前端不再持有或传输 `ConversationStateDTO`
- **PostgreSQL**（`chats` 表）渐进式结构化数据快照，在新建会话和每次模块完成时尽力写入
- 基于 **HttpOnly Cookie**（`propertyai_anon_id`）的匿名身份，依托 `users` 表——无需登录
- **会话恢复**：`GET /chat/{session_id}` 在 Redis key 过期时回退到 PostgreSQL，并由 LLM 生成一条欢迎回来的消息
- 聊天历史侧边栏（`GET /chats`），按匿名身份范围查询
- 借款能力估算（RBA F5 实时利率，24 小时缓存）与预算缺口检测（Domain API，Redis 缓存）
- 需求摘要生成（`POST /chat/summary`）与供 Part 2 使用的 `UserNeeds` 交接契约

### 1.3 尚未实现

- 用户注册 / 登录 / JWT 认证（P1-B）
- SSE 流式响应
- `chats.user_id`——列已存在并已建索引，但在 P1-B 登录功能上线前不会被写入

---

## 2. 技术栈

| 层 | 技术 |
| --- | --- |
| 语言 | Python 3.12、FastAPI、Pydantic v2 |
| LLM 网关 | OpenRouter（通过 `openai` SDK），模型通过 `MODEL_STRONG` 可配置 |
| 会话存储 | Redis —— 完整 `ConversationStateDTO`，滑动 7 天 TTL |
| 历史存储 | PostgreSQL —— `users` + `chats` 表，SQLAlchemy 2.0 async（`asyncpg`），Alembic 迁移 |
| 身份 | 匿名，HttpOnly Cookie（`propertyai_anon_id`）——无需登录 |
| 依赖管理 | uv + `pyproject.toml`（同步镜像至 `requirements.txt`） |
| Lint/格式化/类型检查 | Ruff、mypy `--strict` |
| 测试 | pytest（`asyncio_mode = auto`）；所有 LLM/Redis/Postgres 调用均被 mock |
| 日志 | structlog（JSON 输出） |

完整源文件地图、各模块覆盖率目标、开发命令均在 [docs/backend-implementation.md](../../docs/backend-implementation.md)——此处不重复。

---

## 3. 系统架构

### 3.1 部署视角 —— 外部依赖

```
                         ┌────────────────────────┐
                         │  Frontend (Next.js)     │
                         │  withCredentials: true  │
                         └───────────┬─────────────┘
                                     │ HTTPS + Cookie(propertyai_anon_id)
                                     ▼
                         ┌────────────────────────┐
                         │  FastAPI app (main.py)  │
                         │  CORS 白名单 + 全局异常处理│
                         └──┬──────┬──────┬────────┘
                            │      │      │
              ┌─────────────┘      │      └─────────────┐
              ▼                    ▼                     ▼
     ┌──────────────┐     ┌───────────────┐     ┌──────────────────┐
     │    Redis      │     │  PostgreSQL   │     │   OpenRouter      │
     │ session store │     │ users / chats │     │ (LLM 网关，双轮调用)│
     │ + price cache │     │  SQLAlchemy   │     └──────────────────┘
     └──────────────┘     │   + Alembic   │
                           └───────────────┘

     domain/ 内还会按需外呼：
       - RBA F5 statistics CSV（借款能力参考利率，24h 缓存）
       - Domain API（郊区中位价，Redis 24h 缓存）
```

Redis 和 PostgreSQL 是两个职责完全不同的存储（详见 [§8](#8-身份与持久化模型)），OpenRouter 是唯一的 LLM 网关，RBA F5 和 Domain API 是两个可选的、失败时静默降级的外部数据源——它们的不可用不会阻断主对话流程。

### 3.2 应用内部分层

```
routers/            HTTP 层 —— 路由、依赖注入、请求/响应编排（chat_async、get_session_async …）
  │
  ├── routers/deps.py                Cookie 身份解析（resolve_anon_id_async / require_anon_id_cookie_async）
  │
  ▼
conversation/  +  domain/            业务逻辑层 —— 不感知 HTTP，只操作领域对象
  ├── state_machine.py               模块推进、字段合并、null 安全（唯一的完成度权威）
  ├── intent_router.py               意图分类、Part 2 路由载荷组装
  ├── llm_client.py                  OpenRouter 封装（ILLMClient Protocol）
  ├── borrowing_capacity.py          借款能力估算
  ├── budget_gap_detector.py         预算缺口检测
  └── user_needs_builder.py          UserNeeds 快照组装
  │
  ▼
prompts/system_prompt_builder.py     LLM prompt 组装的唯一入口 —— 全部 prompt 字面量只存在于 prompts/ 包内
  │
  ▼
models/                              Pydantic DTO —— HTTP 契约与领域对象形状（camelCase 别名）
  │
  ▼
redis_store/  +  db/                 持久化层
  ├── redis_store/session_store.py   ISessionStore Protocol + RedisSessionStore
  ├── redis_store/price_cache.py     Domain API 中位价缓存
  ├── db/repositories/chat.py        IChatRepository Protocol + SqlAlchemyChatRepository
  └── db/repositories/user.py        IUserRepository Protocol + SqlAlchemyUserRepository
```

依赖方向永远自上而下——`routers/` 依赖 `conversation/`/`domain/`，后者依赖 `models/` 和持久化层的 Protocol，从不反向依赖。每个跨层依赖点都通过 `typing.Protocol` 定义（`ILLMClient`、`IChatRepository`、`IUserRepository`、`ISessionStore`），具体实现类可在测试中被替换为 mock；所有 `(Protocol, 实现类)` 组合登记在 `scripts/check_protocols.py` 的 `PAIRS` 表中，由 pre-commit 和 CI 校验完整性。

### 3.3 单次请求的横切关注点

- **身份解析**在路由层最先发生（`routers/deps.py`），解析结果（`resolved_anon_id`）以参数形式向下传递，业务逻辑层不直接读取 Cookie。
- **日志**使用模块级 `structlog` logger，仅在请求处理函数内部通过 `.bind(session_id=..., current_module=...)` 生成请求作用域的子 logger，绝不在模块顶层绑定请求相关字段（避免跨请求串号）。
- **异常**统一由 `error_handlers.py` 中的全局处理器转换为标准信封（详见 [§13](#13-错误处理)）；业务逻辑层只抛出 `PropertyAIException` 子类，从不在路由层 `try/except` 后手工拼装 HTTP 响应。

---

## 4. 请求流程 —— 双轮 LLM 架构

每次 `POST /chat` 调用会发起**两次** LLM 调用，而非原始设计草图中的单次合并调用（属于有意的偏离，理由见 [§15](#15-值得记录的设计决策)）：

```
POST /api/v1/chat  { sessionId: string | null, message: string }
    │
    ├─ resolve_anon_id_async（Cookie 依赖）—— cookie 缺失/非法时自动创建 users 行
    ├─ 按 session_id 从 Redis 加载 ConversationStateDTO；不存在则新建
    ├─ 将用户消息追加到 conversation_history
    │
    ├─ Round 1 —— 提取
    │     build_extraction_prompt(state) → chat_with_tools_async(..., [extract_requirements 工具])
    │     → merge_extracted_fields()（推进模块、重算完成度、null-safe 合并）
    │     tool_call JSON 解析失败会被捕获并记录日志；提取结果降级为 {}，当前轮次不因此失败
    │
    ├─ 重新计算 borrowing_capacity（若 pre_tax_salary 存在）与 budget_gap（若 budget_max + 郊区信息存在）
    │
    ├─ Round 2 —— 生成回复
    │     build_question_prompt(state) → complete_async() → 回复文本
    │     将 assistant 回复追加到 conversation_history
    │
    ├─ save_session_async(state) —— Redis SET，重置 7 天滑动 TTL
    ├─ classify_intent() → RoutingPayload | None（供 Part 2 使用）
    ├─ [新建会话 或 本轮有模块首次完成] → BackgroundTasks: chat_repo.upsert_chat_snapshot_async
    ├─ response.set_cookie(propertyai_anon_id, ...)
    └─ 返回 ChatResponse { reply, extracted, sessionId, state: ConversationSnapshotDTO, routing }
```

Round 1 使用极简 prompt（不含角色定义/守卫规则）以最大化提取准确性；Round 2 使用完整 prompt 堆栈（角色、状态、意图上下文、金融板块、守卫规则）以最大化回复质量。Postgres 写入通过 FastAPI `BackgroundTasks` 调度（而非 `asyncio.create_task`），以保证进程退出前任务不丢失、且不阻塞 HTTP 响应；只在新建会话或某模块本轮由 `False→True` 时触发，绝不会每轮都写。

---

## 5. 数据模型

所有对外 DTO 继承 `PropertyAIBaseModel`（`models/base.py`）——线上使用 camelCase 别名，内部使用 snake_case（`populate_by_name=True`）。唯一例外是 `CompletionStatus`（普通 `BaseModel`），因为 `to_camel` 会把它的 `M1`–`M4` 字段名转成小写。

### 5.1 枚举（`models/conversation_state.py`）

`EModule`、`EStatus`、`ESubmodel`（`m1`–`m4`，用作 computed dict key）、`ESubmodelLabel`、`EPropertyType`、`EIntendedUse`、`ETargetTenant`、`ECommuteMode`、`ELifestyleVibe`、`EUserIntent`（`recommend_suburbs | list_properties | property_detail | compare_properties | open_ended_query`）。

### 5.2 采集字段（M1–M4）

| 模块 | 字段 |
| --- | --- |
| M1 — `M1PropertyNeeds` | `property_type`、`min_bedrooms`、`max_bedrooms`、`min_bathrooms`、`min_carspaces`、`min_land_size`、`max_land_size`、`wants_pool`、`wants_outdoor`、`wants_study`、`intended_use` |
| M2 — `M2Lifestyle` | `household_size`、`has_children`、`needs_school_zone`、`has_pets`、`work_from_home`、`target_tenant` |
| M3 — `M3SuburbPreference` | `commute_destination`、`commute_max_mins`、`commute_mode`、`preferred_suburbs`、`excluded_suburbs`、`lifestyle_vibe` |
| M4 — `M4Budget` | `budget_min`、`budget_max`、`deposit_amount`、`pre_tax_salary`、`partner_salary`、`is_joint`、`first_home_buyer`、`loan_term_years` |

所有字段均为 `Optional`，提取前默认 `None`。`CollectedData` 打包 `m1`–`m4`，并支持 `data[ESubmodel.M1]` 这类按索引访问。

### 5.3 会话状态

```python
class CompletionStatus(BaseModel):       # M1: bool, M2: bool, M3: bool, M4: bool
    all_complete: bool                    # computed_field
    current_module: EModule               # computed_field —— 第一个未完成的模块

class ConversationStateDTO(PropertyAIBaseModel):
    session_id: str
    status: EStatus = IN_PROGRESS
    current_module: EModule = M1_PROPERTY_NEEDS
    completion_status: CompletionStatus
    collected_data: CollectedData
    conversation_history: list[dict[str, object]]
    initial_intent: EUserIntent | None
    final_needs: CollectedData | None
    borrowing_capacity: BorrowingCapacityResult | None
    budget_gap: BudgetGapResult | None
```

### 5.4 金融计算结果（`models/financial.py`）—— frozen dataclass，**非** Pydantic

内部对象，从不直接跨越 HTTP 边界（只作为 `ConversationSnapshotDTO` 的嵌套字段出现）。冻结语义正是 `BudgetGapResult.suggested_actions` 使用 `tuple[str, ...]` 而非 `list[str]` 的原因。

```python
@dataclass(frozen=True)
class BorrowingCapacityResult:
    estimated_capacity: int      # AUD，四舍五入至最近 $10,000
    monthly_repayment: int
    based_on_salary: int
    is_joint: bool
    annual_rate: float
    loan_term_years: int
    rate_source: str
    disclaimer: str               # 恒非空；必须始终渲染（合规要求）

@dataclass(frozen=True)
class BudgetGapResult:
    has_gap: bool
    budget_max: int
    market_median: int
    gap_amount: int
    gap_percentage: float
    reference_suburb: str
    suggested_actions: tuple[str, ...]   # has_gap 为 True 时至少 2 项
```

### 5.5 Part 1 → Part 2 交接契约（`models/user_needs.py`）

```python
class UserNeeds(PropertyAIBaseModel):
    session_id: str
    generated_at: datetime
    schema_version: str = "1.1"
    collected: CollectedData
    initial_intent: EUserIntent
```

### 5.6 API DTO（`models/chat.py`、`models/summary.py`）

| DTO | 用途 |
| --- | --- |
| `ChatRequest` | `session_id: str \| None`、`message: str`（最小长度 1）——从不携带会话状态 |
| `ChatResponse` | `reply`、`extracted`、`session_id`、`state: ConversationSnapshotDTO`、`routing: RoutingPayload \| None` |
| `ConversationSnapshotDTO` | 只读展示快照 —— 镜像 `ConversationStateDTO` 但**省略** `conversation_history`，保持响应体精简 |
| `SessionRestoreResponse` | `resume_message: str \| None`、`state: ConversationSnapshotDTO`、`conversation_history: list[dict]` —— `GET /chat/{session_id}` 的响应体 |
| `ChatSessionDTO` | `GET /chats` 的单行：`session_id`、`status`、`initial_intent`、`created_at`、`updated_at`、`completed_at` |
| `RoutingPayload` | `intent`、`session_id`、`user_needs: UserNeeds`、`execution_mode`、`agents_hint: list[str]`、`triggered_at`、`trigger_source` |
| `SummaryRequest` / `SummaryResponse` | `{ collected_data, session_id, initial_intent }` → `{ summary_text, structured: UserNeeds }` |

所有成功响应包裹在 `SuccessResponse[T]`（`{ ok: true, data: T }`）中；所有错误使用 `ErrorResponse`（`{ ok: false, error: { code, message, details } }`）——详见 [§13](#13-错误处理)。

---

## 6. 模块状态机

完全由 `conversation/state_machine.py` 拥有。字段级完成度规则集中在 `MODULE_COMPLETION_RULES` 注册表中——不要在其他任何地方硬编码模块完成条件。

| 模块 | 推进所需字段 | 特殊规则 |
| --- | --- | --- |
| M1 | `property_type`、`min_bedrooms`、`intended_use` | — |
| M2 | `household_size`、`has_children` | `intended_use == "investment"` 时还需 `target_tenant` |
| M3 | `commute_destination`、`commute_max_mins` | — |
| M4 | `budget_max` | — |

```
EModule:  M1_PROPERTY_NEEDS → M2_LIFESTYLE → M3_SUBURB_PREFERENCE → M4_BUDGET → COMPLETE
EStatus:  IN_PROGRESS ────────────────────────────────────────────► REQUIREMENTS_COMPLETE
```

- **非线性跳跃**：`merge_extracted_fields()` 会将每个新提取字段路由到其归属的子模型，与当前激活模块无关（用户在 M1 阶段也可以直接说出预算）。
- **Null 安全**（不变量）：已有的非 `None` 字段值永远不会被新传入的 `None` 覆盖。
- `recalculate_completion(data) -> CompletionStatus` 纯粹从 `CollectedData` 重新推导完成度——每次 merge 之后、以及会话恢复路径（§9）都会调用它，因为 `completion_status` 从不持久化到 Postgres。
- `get_current_module(completion) -> EModule` 返回第一个未完成的模块，或 `COMPLETE`。

---

## 7. API 契约

| Method | Path | 用途 |
| --- | --- | --- |
| `POST` | `/api/v1/chat` | 处理一轮对话；`session_id` 为 `null` 时新建会话 |
| `GET` | `/api/v1/chat/{session_id}` | 恢复会话状态 —— Redis 命中，或 DB 兜底 + LLM 生成的欢迎回来消息 |
| `GET` | `/api/v1/chats` | 列出当前匿名用户的会话，按最新排序 |
| `POST` | `/api/v1/chat/summary` | 生成自然语言需求摘要 |
| `GET` | `/health` | 存活检查 —— 同时检查 Redis 和 Postgres 连通性 |

### 7.1 `POST /api/v1/chat`

`session_id` 可选；为 `null` 时后端生成 UUID v4 并在响应中返回，供前端跳转到 `/chat/:sessionId`。完整处理顺序见 [§4](#4-请求流程--双轮-llm-架构)。

### 7.2 `GET /api/v1/chat/{session_id}`

完整流程见 [§9](#9-会话恢复redis-未命中--db-兜底)。Redis 命中和 DB 恢复两条路径返回的响应结构完全一致——前端通过 `resumeMessage !== null` 来区分。

### 7.3 `GET /api/v1/chats`

身份来自 `propertyai_anon_id` Cookie，依赖 `require_anon_id_cookie_async`——与 `POST /chat` 使用的依赖不同，它**从不自动创建**新身份；Cookie 缺失/非法直接返回 `400`。对合法但未知的 `anon_id` 返回 `[]`（而非 `404`），避免泄露枚举信息。

### 7.4 `POST /api/v1/chat/summary`

无状态——直接接收 `CollectedData`，不依赖 `session_id` 查询。当四个子模型所有字段均为 `None` 时抛出 `SummaryValidationError`（422）。

---

## 8. 身份与持久化模型

两套存储服务于两个不同目的，从不混用：

| 存储 | 内容 | 写入时机 | 权威范围 |
| --- | --- | --- | --- |
| **Redis**（`redis_store/session_store.py`） | 完整 `ConversationStateDTO`，含 `conversation_history` | 每轮同步写入 | 实时会话——`GET /chat/{session_id}` 命中时恢复的内容 |
| **PostgreSQL `chats`**（`db/repositories/chat.py`） | 轻量渐进快照（`status`、`initial_intent`、`collected_data`、`final_needs`、`borrowing_capacity`、时间戳） | 通过 `BackgroundTasks` 尽力写入，仅在新建会话或模块完成时触发 | 侧边栏历史（`GET /chats`）和会话恢复兜底路径（§9）——除 Redis 未命中外从不回读进实时对话 |

Redis key `session:{session_id}` → `ConversationStateDTO.model_dump_json()`。TTL 为**滑动窗口**——每次 `save_session_async` 调用都会重置为 `redis_session_ttl`（默认 `604800` 秒 / 7 天）。

### 8.1 匿名身份

单张 `users` 表同时覆盖匿名用户和（未来的）注册用户——不设独立的 `anonymous_users` 表。`user_id` 是首次访问时生成、永不改变的内部锚点；`anon_id` 是通过 Cookie 往返传递的值；`email` 在 P1-B 注册前保持 `NULL`，注册时写入**同一行**（届时无需迁移数据）。

| 依赖（`routers/deps.py`） | 行为 | 使用方 |
| --- | --- | --- |
| `resolve_anon_id_async` | Cookie 缺失/非法 → 静默创建新 `users` 行和新 `anon_id`。从不失败。 | `POST /chat` |
| `require_anon_id_cookie_async` | Cookie 缺失/非法 → `BadRequestError`（400）。从不自动创建。 | `GET /chats` |

Cookie（`propertyai_anon_id`）只在 `POST /chat` 的响应中设置：`HttpOnly`、`SameSite=Strict`、`Secure` 由 `settings.cookie_secure` 控制、`path=/api/v1`、`Max-Age` 由 `settings.cookie_max_age` 控制（默认 1 年，每次成功 `POST /chat` 都会续期）。前端发起请求时携带 `withCredentials: true`（`lib/request.ts`），且不在客户端保留 `anon_id` 的任何副本——这正是原 Anonymous User PRD v1.1 §13 规划的 HttpOnly Cookie 方案，现在是唯一实现（该 PRD §2.4/§7 描述的更早期 localStorage + request body 方案，即 v1.0 方案，已不存在于代码中）。

`chats.anon_id` 是 `users.anon_id` 的**去规范化、无约束**副本（无 FK）——靠部分索引（`WHERE anon_id IS NOT NULL`）支持查询性能。不加 FK 的原因：后台任务的写入可能领先于测试环境的 setup 或 `users` 行的提交；同时省去了测试中"写 `chats` 行前必须先插入 `users` 行"的前置要求。`chats.user_id` 采用相同的无 FK + 部分索引模式，为 P1-B 预留。

---

## 9. 会话恢复（Redis 未命中 → DB 兜底）

### 9.1 动机

Redis TTL 是**滑动**的 7 天——每次 `save_session_async` 调用都会重置。若用户超过 7 天未回访，Redis key 会过期，即便结构化数据（`collected_data`、`borrowing_capacity`）早已在每次模块完成时持久化到 `chats` 表。没有兜底机制的话，`GET /chat/{session_id}` 会直接 404，用户会误以为进度全部丢失。

### 9.2 流程（`routers/chat.py::get_session_async`）

```
GET /api/v1/chat/{session_id}
    │
    ├─ session_id 格式非法 ──────────────────────► 400 BadRequestError
    │
    ├─ Redis 命中
    │       └─ 200  SessionRestoreResponse(resumeMessage=null, state=snapshot,
    │                                       conversationHistory=<完整历史>)
    │
    └─ Redis 未命中
            ├─ chat_repo.get_chat_snapshot_async(session_id)
            ├─ DB 未命中 ────────────────────────► 404 SessionNotFoundError
            └─ DB 命中
                    ├─ 从 JSONB 反序列化 collected_data（CollectedData.model_validate）
                    │     和 borrowing_capacity 为领域对象
                    ├─ recalculate_completion(collected_data) → CompletionStatus
                    ├─ get_current_module(completion_status) → EModule
                    ├─ build_session_restore_prompt(state) → complete_async() → resume_message
                    ├─ 将 {"role": "assistant", "content": resume_message} 追加到 conversation_history
                    ├─ save_session_async(state) —— 回写 Redis；失败仅记录日志并吞噬
                    │     （状态已经返回给调用方；无论 Redis 回写是否成功，DB 行都完整）
                    └─ 200  SessionRestoreResponse(resumeMessage=<生成文本>, state=snapshot,
                                                    conversationHistory=[])
```

前端通过 `resumeMessage !== null` 区分两种情况；DB 恢复场景下将 `resumeMessage` 渲染为第一条 assistant 气泡（因为 `conversationHistory` 为空——原始对话历史从不持久化到 Postgres）。

### 9.3 哪些内容不会被恢复（有意为之）

- `conversation_history` —— 不持久化到 Postgres（体积不可控，且无结构化查询需求）；DB 恢复的会话以空历史 + 生成的欢迎消息开始。
- `budget_gap` —— 派生值；下次 `POST /chat` 检测到 `budget_max` 和郊区信息时会自动重新计算。
- 没有其他需要恢复的内容：`completion_status` **始终**从 `collected_data` 重新推导（从不持久化，也就不存在不同步的风险）。

### 9.4 Prompt

`build_session_restore_prompt`（`prompts/system_prompt_builder.py`）组装 `ROLE_DEFINITION`、`build_state_section(state)`、`GUARDRAIL_RULES`、`SESSION_RESTORE_INSTRUCTION`（`prompts/sections/instructions.py`）——不同于 `build_question_prompt`（进行中的对话轮次）和 `build_summary_prompt`（最终摘要）。该指令约束 LLM：自然地承认用户是回来继续的（不出现"数据库"/"缓存"/"会话"等技术词汇），用口语简短回顾已知需求，然后针对 `current_module` 提出下一个自然问题（`IN_PROGRESS`），或提供下一步选项（`REQUIREMENTS_COMPLETE`）。

### 9.5 错误处理

| 情况 | 行为 |
| --- | --- |
| `session_id` 格式非法 | 在任何 I/O 之前抛出 `BadRequestError`（400） |
| Redis 未命中 + DB 未命中 | `SessionNotFoundError`（404） |
| DB 恢复路径中 LLM 调用失败 | `LLMServiceError`（503）；**不**回写 Redis——下次请求会再次走 DB 恢复路径重试 |
| LLM 调用成功后 Redis 回写失败 | 记录日志并吞噬——响应已经准备好返回给调用方；DB 行保持完整 |

---

## 10. 金融服务 —— 借款能力与预算缺口

### 10.1 借款能力估算（`domain/borrowing_capacity.py`）

在 `M4Budget.pre_tax_salary` 变为非 `None` 时触发。使用从 RBA F5 统计表（系列 `FILRHLBVD`）获取的实时参考利率，缓存 24 小时；获取失败时回退到 `settings.standard_variable_rate`（默认 6.30%），并在 `rate_source` 中体现该回退。按标准年金公式，以税前 67% 净月收入乘以 `settings.borrowing_capacity_dti`（默认 0.28）为月还款上限，套用 `loan_term_years`（默认 `settings.default_loan_term`，30 年）；若存在 `partner_salary`，联合申请则翻倍。`estimated_capacity` 四舍五入至最近 $10,000。`disclaimer` 恒非空，且在任何展示该结果的地方**都必须渲染**——这是合规要求，不是可选的 UI 细节。

### 10.2 预算缺口检测（`domain/budget_gap_detector.py`）

在 `budget_max` 已设置、且 `preferred_suburbs` 或 `commute_destination` 至少有一个可用时触发。查询 Domain API（Redis 缓存 24 小时，key 为 `price:{suburb}:{property_type}:{min_bedrooms}`）获取候选郊区列表中第一个郊区的中位价；当 `budget_max` 低于中位价超过 `settings.budget_gap_threshold`（默认 15%）时标记为存在缺口。当 `DOMAIN_API_KEY` 未设置或 API 调用失败时，静默返回 `None`——从不抛出异常，确保这一功能永远不会阻断主对话流程。

---

## 11. 意图路由与 Part 2 交接

`conversation/intent_router.py::classify_intent` 每轮都会运行，除非满足以下任一条件否则返回 `None`：(a) `completion_status.all_complete` 为 `True`；(b) 消息命中触发词。

| 优先级 | 意图 | 触发条件 |
| --- | --- | --- |
| 1 | `recommend_suburbs` | 关键词：suburb / area / recommend / 推荐 / 区域 |
| 2 | `property_detail` | 街道地址模式或 "property id" 关键词 |
| 3 | `list_properties` | 关键词：property / listing / find / 找房 / 房源 |
| 4 | `open_ended_query` | `all_complete` 为真且未命中其他规则时的兜底 |

`RoutingPayload.execution_mode` 和 `agents_hint` 按意图查表（`_ROUTING_CONFIG`）得出：`recommend_suburbs`/`list_properties` → `code_driven` + `[suburb_agent, price_agent]`；`property_detail` → `code_driven` + 6 个详情类 agent；`open_ended_query` → `agentic_loop` + `[]`（由 LLM 自主编排）。`RoutingPayload.user_needs` 携带完整 `UserNeeds` 快照，Part 2 无需二次往返即可拿到已采集数据。

---

## 12. 数据库 Schema

### 12.1 `chats`

```sql
CREATE TABLE chats (
    session_id         UUID        PRIMARY KEY,
    anon_id            UUID        NULL,   -- users.anon_id 的去规范化副本，无 FK
    user_id            UUID        NULL,   -- 为 P1-B 预留，无 FK
    status             TEXT        NOT NULL DEFAULT 'IN_PROGRESS',
    schema_version     TEXT        NOT NULL DEFAULT '1.1',
    initial_intent     TEXT        NULL,
    collected_data     JSONB       NOT NULL DEFAULT '{}',
    final_needs        JSONB       NULL,
    borrowing_capacity JSONB       NULL,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at       TIMESTAMPTZ NULL
);

CREATE INDEX idx_chats_status     ON chats (status);
CREATE INDEX idx_chats_updated_at ON chats (updated_at DESC);
CREATE INDEX idx_chats_anon_id    ON chats (anon_id) WHERE anon_id IS NOT NULL;
CREATE INDEX idx_chats_user_id    ON chats (user_id) WHERE user_id IS NOT NULL;
```

从不在此持久化：`conversation_history`（体积不可控，无结构化查询需求）和 `budget_gap`（派生值，重算成本很低）。Upsert 使用 `INSERT ... ON CONFLICT (session_id) DO UPDATE`，并用 `COALESCE` 保护 `initial_intent` 和 `completed_at` 一旦写入就不会被后续 upsert 覆盖为 `NULL`；`anon_id`/`user_id` 有意不出现在 `DO UPDATE SET` 子句中——会话归属一旦写入即不可变。upsert 内部所有异常都会被捕获并记录日志——Postgres 故障绝不能导致某一轮对话失败，因为该写入是在 HTTP 响应已经准备好之后，通过 `BackgroundTasks` 执行的。

### 12.2 `users`

```sql
CREATE TABLE users (
    user_id    UUID        PRIMARY KEY,
    anon_id    UUID        NOT NULL UNIQUE,
    email      TEXT        UNIQUE,      -- NULL = 匿名用户；P1-B 注册时写入
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_users_anon_id ON users (anon_id);
```

单表设计（而非 `users` + `anonymous_users` 两表）：注册只需一次 `UPDATE users SET email = ... WHERE anon_id = ...`，`user_id` 从始至终不变，用户注册时也无需迁移任何 `chats` 行。

### 12.3 迁移

| Revision | 内容 |
| --- | --- |
| `993128e7e195_create_chats` | 创建 `chats`（含 `anon_id`/`user_id` 列） |
| `2f156e1dbbc7_add_users_and_clean_chats_constraints` | 创建 `users`；删除旧的 `chk_chats_single_owner` CHECK 约束（单表设计下该约束已过时——P1-B 登录后，`anon_id` 和 `user_id` 允许同时非 `NULL`） |

Alembic 通过**同步** psycopg2 引擎运行迁移（`db/alembic/env.py` 会剥离 `database_url` 中的 `+asyncpg` 后缀），而应用层使用 async 引擎——两者刻意分离，迁移脚本永远不需要嵌套 `asyncio.run()`。

---

## 13. 错误处理

```
PropertyAIException          ← 基类；携带 status_code + details
├── LLMServiceError          ← 503 —— OpenRouter / 模型调用失败
├── StateTransitionError     ← 500 —— 非法的模块推进
├── SummaryValidationError   ← 422 —— 请求摘要时所有字段均为 None
├── BadRequestError          ← 400 —— 业务级校验失败（非法 UUID、缺失 Cookie）
├── RateLimitError           ← 429 —— 上游 LLM 速率限制；含 retry_after
└── SessionNotFoundError     ← 404 —— session_id 在 Redis 和 Postgres 中均不存在
```

`error_handlers.py` 中的单一处理器将每个 `PropertyAIException` 子类转换为 `{"error": {"code", "message", "details"}}`，键值取自实例上的 `status_code`；`RequestValidationError`（Pydantic 422）由第二个处理器转换为相同的信封结构。业务错误从不返回原生 FastAPI 的 `{"detail": "..."}`。

---

## 14. 环境变量

| 变量 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `OPENROUTER_API_KEY` | 是 | — | OpenRouter API key |
| `MODEL_STRONG` | 否 | `anthropic/claude-sonnet-4-5` | 对话轮次使用的模型 |
| `MODEL_FAST` | 否 | `anthropic/claude-haiku-4-5` | 轻量提取使用的模型 |
| `LLM_BASE_URL` | 否 | SDK 默认值 | 覆盖 LLM API base URL |
| `STANDARD_VARIABLE_RATE` | 否 | `6.30` | RBA F5 不可用时的 fallback 年利率（%） |
| `DEFAULT_LOAN_TERM` | 否 | `30` | 默认贷款年限（年） |
| `BORROWING_CAPACITY_DTI` | 否 | `0.28` | 借款能力计算的 DTI 上限 |
| `DOMAIN_API_KEY` | 否 | `""` | Domain API key，用于预算缺口的中位价查询；未设置时该功能静默禁用 |
| `BUDGET_GAP_THRESHOLD` | 否 | `0.15` | 预算缺口触发阈值 |
| `DATABASE_URL` | 是（P1-A） | `postgresql+asyncpg://user:password@localhost:5432/propertyai` | Postgres DSN；`postgresql://` 会自动升级为 `+asyncpg` |
| `REDIS_URL` | 是（P1-A） | `redis://localhost:6379` | Redis 连接地址 |
| `REDIS_SESSION_TTL` | 否 | `604800` | 会话 key TTL（秒），7 天 |
| `ALLOW_ORIGINS_LIST` | 否 | `["http://localhost:3000"]` | CORS 白名单（`.env` 中用逗号分隔）；Cookie 身份认证必需（`allow_credentials=True` 时不允许 `"*"`） |
| `COOKIE_SECURE` | 否 | `True` | anon-id Cookie 的 `Secure` 标志；本地 HTTP 开发时设为 `False` |
| `COOKIE_MAX_AGE` | 否 | `31536000` | anon-id Cookie 的 Max-Age（秒），1 年 |

---

## 15. 值得记录的设计决策

只保留能解释某个非显而易见的偏离早期规格或某个细微不变量的条目——不是历史草案的流水账。

- **每轮两次 LLM 调用**，而非一次。让同一个 system prompt 既承担 tool-calling 又承担对话回复，很难同时优化两者；拆分为提取（极简 prompt）和回复生成（完整 prompt）后两者质量都提升了。
- **提取工具 schema 中不含控制字段**。`module_complete`/`user_intent`/`next_question` 已从 `extract_requirements` 的 schema 中移除——模块推进完全靠规则引擎（`state_machine.py`），路由完全靠关键词匹配（`intent_router.py`），再让 LLM 额外判断这些字段只会增加 token 成本而不提升可靠性。
- **`session_id` 由服务端生成**，从不由客户端生成——省去前端 UUID 依赖，并集中保证唯一性/格式；也与未来登录态下由服务端分配 session 的行为保持一致。
- **前端对状态只读**。每次 `POST /chat` 或 `GET /chat/{id}` 响应后，前端都对展示状态做完整替换（从不做 merge）——Redis（或恢复场景下的 Postgres）是唯一的状态权威来源。
- **Postgres upsert 是尽力而为的异步操作**。`upsert_chat_snapshot_async` 会捕获并记录所有异常；由于写入发生在 HTTP 响应已经准备好之后（通过 `BackgroundTasks`），Postgres 故障绝不能导致某一轮对话失败或延迟。
- **`chats.anon_id`/`user_id` 不加 FK 约束**，只建部分索引——避免后台任务写入与 `users` 行之间产生写入顺序依赖，也简化了测试 setup（写 `chats` 行前无需预先插入 `users` 行）。
- **`completion_status` 从不持久化到 Postgres**。它是 `collected_data` 的纯派生结果（`recalculate_completion`）；持久化它会有业务规则变更后与 `state_machine.py` 逻辑不同步的风险。每次 merge 之后、以及会话恢复时，它都会被重新计算。

---

## 16. 范围外 / P1-B 规划

尚未实现，明确推迟：

| 功能 | 说明 |
| --- | --- |
| 用户注册 / 登录 / JWT | `users.email`、`password_hash`（尚未添加的列）、OAuth 账号表——均为 P1-B |
| `chats.user_id` 写入路径 | 列和索引已存在；登录功能上线后才会写入，届时无需改表结构 |
| 跨设备用户画像 / 预填 | 需要经过认证的身份，仅 `anon_id` 不够 |
| 超出当前侧边栏范围的会话历史 UI | 类似 `user:{user_id}:sessions` 的聚合方式，P1-B |
| SSE 流式响应 | 规划中：混合方案——文字逐 token 流式推送，状态更新作为最后一个 `done` event |
| `DELETE /session` 端点 | 现有规模下 Redis TTL 自然过期已足够；仅在内存压力真正成为瓶颈时才补充主动删除端点 |
| 多城市扩展、Crime/Development agent、PDF 导出 | Phase 2，完全在 Part 1 范围之外 |

---

## 相关文档

- [docs/backend-implementation.md](../../docs/backend-implementation.md) —— 源文件地图、开发命令、各模块测试覆盖率目标
- [CLAUDE.md](../../CLAUDE.md) —— 编码规范、关键不变量（项目全局）
- [.claude/rules/backend/backend-patterns.md](../../.claude/rules/backend/backend-patterns.md) —— 配置/日志/异常/prompt 归属规则
- [PRD/PropertyAI_PRD_v1_1.md](../PropertyAI_PRD_v1_1.md) —— 父级产品 PRD（P0 stories S-A→S-H、守卫规则、数据模型）
