# PropertyAI — Technical Thinking
## 开发决策与技术思考记录

| Field | Value |
|-------|-------|
| Version | v0.2 |
| Status | Living Document — 持续更新 |
| Scope | Part 1 Conversation Layer |
| Last Updated | 10 May 2026 |

> **说明**：本文档记录开发过程中的关键技术决策、取舍理由和注意事项。不是规范文档，是思考过程的沉淀，供开发和回顾时参考。

---

## 目录

1. [流式响应（SSE）](#1-流式响应sse)
2. [Cache 策略](#2-cache-策略)
3. [Redis 与 PostgreSQL 职责划分](#3-redis-与-postgresql-职责划分)
4. [Session 生命周期与数据持久化](#4-session-生命周期与数据持久化)
5. [用户画像持久化](#5-用户画像持久化)
6. [Session Title](#6-session-title)
7. [待讨论议题](#待讨论议题)

---

## 1 流式响应（SSE）

**决策：P0 不做流式，P1 再引入。**

### 背景

Part 1 每次 `/chat` 调用需要同时处理两件事：
- 返回 AI 的自然语言回复（文字部分）
- 解析 `tool_call` 提取结构化字段，更新会话状态

这两件事在流式场景下会产生冲突。

### 核心问题

OpenRouter 的流式响应中，`tool_call` 的 JSON 是分块传输的，必须等所有分块到齐才能解析。这意味着：

- 文字可以流式推送给前端
- 但 `extracted` 字段和 `updated_state` 必须等流结束后才能确定

如果 P0 就做流式，需要在后端实现"文字流转发 + tool_call 拼装"的双轨逻辑，调试复杂度显著上升。

### 三种实现方式对比

| 方式 | 描述 | 复杂度 | 用户体验 |
|------|------|--------|---------|
| 完全非流式 | 后端等全部返回，一次性响应 | 低 | 用户等待 5–10s 无反馈 |
| 后端拼装后流式 | 后端接收流、拼完 tool_call 后再向前端转发文字流，状态在流结束后推送 | 中 | 较好 |
| 混合 SSE | 文字部分实时推送，状态作为最后一个 SSE event | 中高 | 最好 |

### 决策

- **P0**：完全非流式。主链路优先，体验优化延后。
- **P1**：混合 SSE 方案（方式 3）。文字实时流式，状态作为末尾 event 推送。目标首 token < 1s。

---

## 2 Cache 策略

### 2.1 LLM 响应 Cache

**决策：不做。**

Part 1 是个性化需求收集对话，每个用户的会话状态不同，系统提示每轮都在变化。同样一句"我要三房"，在 M1 和 M3 阶段的处理完全不同。

缓存命中率极低，工程成本不划算。此外，缓存错误状态还会导致字段提取出错，风险大于收益。

### 2.2 Anthropic Prompt Cache

**决策：有价值，但受限于当前 SDK 选型，P0 暂缓。**

#### 为什么值得做

系统提示四段式结构中，Section 1（Role Definition）和 Section 4（Guardrail Rules）是完全静态的，每轮对话都相同，是天然的 cache 候选。随着 `conversationHistory` 增长，每轮的 token 消耗也会线性上升，cache 能有效压缩成本。

```
Section 1 — Role Definition     ← 静态，适合 cache
Section 2 — Current State       ← 每轮变化，不 cache
Section 3 — M1→M2 Inference     ← M1 完成后固定，可考虑 cache
Section 4 — Guardrail Rules     ← 静态，适合 cache
```

#### 当前的限制

项目使用 **OpenAI Python SDK** 通过 OpenRouter 调用 Claude。`cache_control` 是 Anthropic 的扩展字段，OpenAI SDK 不会透传，即使路由到 Claude 模型也不生效。

#### 三种解决路径

| 选项 | 描述 | 代价 |
|------|------|------|
| A — 维持现状 | 继续用 OpenAI SDK，放弃 Prompt Cache | 无改动，token 成本略高 |
| B — 换 Anthropic SDK | 能用 cache，但需维护两套 client（Claude / GPT / DeepSeek 各不同） | 违背 OpenRouter 统一网关的初衷 |
| C — httpx 直接构造请求 | 手动加 `cache_control`，保持 OpenRouter 入口 | 需自己处理 retry、流解析等 |

#### 决策

**P0 选 A**，不引入额外复杂度。等 P1 阶段用户量和 LLM 成本上升后，再评估是否值得切换方案。届时优先考虑选项 C，保留 OpenRouter 统一入口的灵活性。

#### 实现参考（P1 备用）

如果 P1 决定通过 httpx 实现，静态部分加 `cache_control` 的结构如下：

```python
messages = [
    {
        "role": "system",
        "content": [
            {
                "type": "text",
                "text": static_section_1 + static_section_4,
                "cache_control": {"type": "ephemeral"}  # 静态部分 cache
            },
            {
                "type": "text",
                "text": dynamic_section_2 + dynamic_section_3  # 动态部分不 cache
            }
        ]
    },
    *conversation_history
]
```

> 注意：使用前需确认 OpenRouter 是否透传 `cache_control` 到 Anthropic，若不透传则需直连 Anthropic API。

---

## 3 Redis 与 PostgreSQL 职责划分

**决策：Redis 管活跃状态，PostgreSQL 管持久记录。**

### 背景

用户使用模式类似 Claude.ai / ChatGPT——可能今天开一个对话框，明天再开一个，不限于单一 session。需要明确两个存储层各自的职责边界。

### 职责划分

| 数据 | 存哪里 | 理由 |
|------|--------|------|
| 当前活跃 session 的对话状态 | Redis | 需要快速读写，每轮对话都在更新 |
| 完整对话历史（所有 session） | PostgreSQL | 需要长期保留，支持列表查询 |
| 用户画像（CollectedData） | PostgreSQL | 跨 session 持久化，用户下次回来可以预填 |
| Agent 结果 cache（Part 2） | Redis | 短期缓存，TTL 控制 |

### 原则

- Redis 的数据是"工作内存"，允许丢失（TTL 到期自然过期）
- PostgreSQL 的数据是"档案"，需要保证写入成功
- 两者不互相替代，各司其职

---

## 4 Session 生命周期与数据持久化

**决策：每个模块完成时异步写库一次（upsert），P0 不做完整对话历史持久化。**

### Session 结束的定义

以下任一条件满足即视为 session 结束：
- 用户关闭对话框
- 四个模块全部完成（`all_complete == True`）

### 数据流向

```
用户开新 session
       │
       ├─ 读 user_profile → 预填数据 → 用户确认/修改（P1）
       │
       ▼
对话进行中
       │
       ├─ 活跃状态 → Redis（快速读写）
       ├─ 每模块完成 → 异步 upsert → PostgreSQL sessions 表
       │
       ▼
session 结束
       │
       ├─ 若有 CollectedData → 覆盖写入 user_profile（P1）
       └─ Redis key → 等 TTL 自然过期（不主动清除）
```

### P0 数据库写入规范

**触发点**：`update_completion()` 执行后，检测到模块状态从 `False → True` 时触发。

**写入内容**：当前已完成模块的 CollectedData 累计快照。

```
M1 完成 → 写入 m1 snapshot
M2 完成 → 写入 m1 + m2 snapshot
M3 完成 → 写入 m1 + m2 + m3 snapshot
M4 完成 → 写入完整 UserNeeds
```

**写入方式**：upsert，同一 `session_id` 覆盖更新，不插入新行。

```sql
INSERT INTO sessions (session_id, user_id, status, final_needs, updated_at)
VALUES ($1, $2, $3, $4, now())
ON CONFLICT (session_id)
DO UPDATE SET
    status      = EXCLUDED.status,
    final_needs = EXCLUDED.final_needs,
    updated_at  = now();
```

**异步执行**：写库不阻塞主响应，失败只记日志，不影响对话流程。

```python
async def on_module_complete(module_id: ModuleID, state: ConversationStateDTO):
    asyncio.create_task(
        db.upsert_session_snapshot(state.sessionId, module_id, state.collectedData)
    )
    # 主流程继续，不等待写库结果
```

### P0 不做的部分

- 完整 `conversationHistory` 不写库（Redis TTL 到期后自然丢失）
- 用户画像（`user_profile`）不写库，P1 再做
- Session 历史列表 API 不做，P1 再做

---

## 5 用户画像持久化

**决策：P1 实现，P0 不做。**

### 设计方向（P1 备用）

用户画像存储在独立的 `user_profiles` 表，与 `sessions` 表分离：

```sql
CREATE TABLE user_profiles (
    user_id        UUID PRIMARY KEY REFERENCES users(user_id),
    collected_data JSONB,       -- CollectedData，每次覆盖更新
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**更新策略**：新 session 的数据覆盖旧画像，不保留版本历史。

**预填逻辑**：用户开新 session 时，读取 `user_profile` 预填到对话上下文，AI 在 M1 开始时向用户确认："我看到你上次的需求是……这次是否相同？"

---

## 6 Session Title

**决策：有价值，但属于用户账户模块，不在 Part 1 P0 范围内。**

### 理由

Session title 是 UI/UX 功能，不影响需求收集主链路，也不影响 Part 2 的数据输入。Part 1 的核心交付物是 `UserNeeds JSON`，session 管理（title、历史列表）属于用户账户层，应单独作为功能模块实现。

### 功能归属

| 功能 | 归属 | 阶段 |
|------|------|------|
| Session title 自动生成 | 用户账户模块 | P1 |
| 对话历史列表 API | 用户账户模块 | P1 |
| user_profile 持久化 | 用户账户模块 | P1 |

### 实现设计（P1 备用）

**触发时机**：M1 完成后的下一次 `/chat` 响应时，后台异步生成，不阻塞主流程。

**生成方式**：单独一次轻量 LLM 调用，使用 `MODEL_FAST`（Haiku）。

```python
prompt = f"""
根据以下买家需求，生成一个简短的对话标题（10字以内，中文）。
只返回标题本身，不要任何解释。

property_type: {m1.property_type}
min_bedrooms: {m1.min_bedrooms}
intended_use: {m1.intended_use}
preferred_suburbs: {m3.preferred_suburbs}

示例输出：南墨尔本三房自住、投资公寓预算80万
"""
```

**Fallback**：LLM 调用失败或字段不足时，默认用创建时间："新对话 · 10 May"。

---

## 待讨论议题

> 以下问题尚未形成决策，待后续讨论补充。已决策项移入下方"已决议"表。

| # | 议题 | 背景 |
|---|------|------|
| 3 | OpenRouter 数据留存确认 | 用户对话数据是否会被 OpenRouter 用于训练，需确认隐私条款 |
| 4 | Domain API 中位价数据粒度 | 预算缺口检测所需的 suburb+property_type+bedrooms 组合，Domain 免费 tier 是否支持 |

---

## 已决议

| # | 议题 | 决策 | 原因 |
|---|------|------|------|
| 1 | 前端状态管理方案 | Zustand（UI 状态） + 后端 Redis（权威状态） | P0 用 Zustand 持有前端副本；P1-A 改为后端 Redis 持有权威状态，前端 Zustand 只保留 `UIMessage[]`（消息渲染用）和 `state` 展示快照（只读，每次响应覆盖替换，不 merge） |
| 2 | session_id 生成方式 | **后端生成** | 唯一性保证归属后端；前端不引入 `uuid` 依赖；与 P1-B 账户体系行为一致。实现：`ChatRequest.session_id` 为可选字段（`str \| None`），`None` 时后端生成 UUID v4 并在 `ChatResponse.session_id` 中返回，前端导航至 `/chat/:session_id` |
