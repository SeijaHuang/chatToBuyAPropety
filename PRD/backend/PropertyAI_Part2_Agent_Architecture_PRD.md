# PropertyAI Part 2 — Agent Architecture PRD

| 字段 | 内容 |
|---|---|
| 版本 | v0.3 |
| 状态 | Architecture Draft |
| 范围 | Part 2 执行编排、原子 Tool、数据汇总、LLM 合成 |
| 上游 | PropertyAI Part 1 |
| 非范围 | 各 Tool 的详细业务规则、API 字段、评分公式 |

---

## 1. 目标

Part 2 负责接收 Part 1 输出的结构化用户意图，并完成数据查询、结果组合和最终输出。

核心目标：

- 固定业务流程保持 deterministic（确定性）
- 开放式查询允许 LLM 动态选择 Tool
- Tool 保持原子化，避免变成小型 SubAgent
- 数据获取、业务合成、自然语言生成分层
- 支持并行执行、部分失败、SSE 进度预览和重连

---

## 2. 核心设计原则

1. Part 1 理解用户，Part 2 执行。
2. Orchestrator 不直接理解原始自然语言。
3. 固定 intent 使用代码驱动执行。
4. 开放式 intent 使用 LLM-driven execution。
5. Tool 对应单一数据源或单一查询能力。
6. Tool 不调用 Tool。
7. Connector 只负责访问外部 API。
8. 多个 Tool 结果由 Data Summary Layer 统一汇总。
9. 只有需要自然语言时才调用 Synthesis Agent。
10. 用户可见的是执行摘要，不暴露内部 chain-of-thought。

---

## 3. 三层架构

```text
┌──────────────────────────────────────────────┐
│ Layer 1 — Orchestrator                       │
│                                              │
│ RoutingPayload                              │
│      ↓                                       │
│ Orchestrator                                 │
│      ↓                                       │
│ ┌────────────────┬─────────────────────────┐ │
│ │ CodeDriven     │ LLMDriven              │ │
│ │ Executor       │ Executor               │ │
│ └────────────────┴─────────────────────────┘ │
│      ↓                                       │
│ Execution Plan / Intent Handler              │
└──────────────────────────────────────────────┘
                     ↓
┌──────────────────────────────────────────────┐
│ Layer 2 — Atomic Tools                       │
│                                              │
│ Domain Tools                                 │
│ PTV Tools                                    │
│ Google Routes Tools                          │
│ Vicmap Tools                                 │
│ Google Places Tools                          │
│ Other Source-Specific Tools                  │
│                                              │
│ 每个 Tool：                                  │
│ - 单一数据源或单一查询能力                   │
│ - 从 ExecutionContext 构建参数               │
│ - 调用对应 Connector                         │
│ - 返回统一 ToolResult                        │
└──────────────────────────────────────────────┘
                     ↓
┌──────────────────────────────────────────────┐
│ Layer 3 — Data Summary & Composition         │
│                                              │
│ ToolResult Aggregation                       │
│      ↓                                       │
│ Domain Composers                             │
│ - PriceComposer                              │
│ - TransportComposer                          │
│ - PlanningComposer                           │
│ - AmenitiesComposer                          │
│      ↓                                       │
│ Structured Intent Result                     │
│      ↓                                       │
│ Synthesis Agent（only when needed）          │
│      ↓                                       │
│ Final Response                               │
└──────────────────────────────────────────────┘
```

---

## 4. Part 1 → Part 2 输入

```python
class RoutingPayload(PropertyAIBaseModel):
    intent: EUserIntent
    session_id: str
    user_needs: CollectedData
    target_entity: TargetEntity | None = None
    triggered_at: datetime
    trigger_source: ETriggerSource
```

不再由 Part 1 传递：

```text
agents_hint
execution_mode
```

原因：

- Tool selection 属于 Part 2
- Execution mode 属于 Part 2
- 避免 Part 1 与 Part 2 产生冲突

---

## 5. Target Entity

```python
class EEntityType(str, Enum):
    SUBURB = "suburb"
    PROPERTY = "property"


class TargetEntity(PropertyAIBaseModel):
    entity_type: EEntityType
    entity_id: str | None = None
    label: str | None = None
```

Part 1 负责把“第二套”“刚才那个 Brunswick 的房子”等自然语言引用解析成标准化 target entity。

---

## 6. Orchestrator

职责：

- 接收 RoutingPayload
- 构建 ExecutionContext
- 根据 intent 选择 Executor
- 启动执行计划
- 发送 SSE 事件
- 返回最终 ExecutionResponse

Orchestrator 不负责：

- 直接调用外部 API
- 理解 Tool-specific 参数
- 执行业务计算
- 生成自然语言报告

---

## 7. Executor

### 7.1 CodeDrivenExecutor

用于固定 intent：

```text
recommend_suburbs
list_properties
property_detail
```

执行方式：

```text
intent
↓
Intent Handler / Execution Plan
↓
并行调用原子 Tools
↓
Data Summary
↓
Final Response
```

### 7.2 LLMDrivenExecutor

用于：

```text
open_ended_query
```

职责：

- 向 LLM 暴露允许使用的原子 Tools
- 执行 tool call
- 将 ToolResult 返回给 LLM
- 限制最大轮数和总超时
- 输出最终回答

---

## 8. Intent Handler

Intent Handler 负责一个固定 intent 的执行计划。

示例：

```text
PropertyDetailHandler
├── DomainPropertyDetailTool
├── DomainMarketStatisticsTool
├── PTVNearbyTool
├── GoogleRoutesTool
├── VicmapPlanningTool
└── GooglePlacesTool
```

Intent Handler：

- 定义该 intent 使用哪些原子 Tool
- 并行执行 Tool
- 调用对应 Composer
- 应用 intent-specific failure policy
- 决定是否调用 Synthesis Agent

它是 deterministic workflow，不是 LLM Agent。

---

## 9. Atomic Tool

推荐粒度：

```text
一个 Tool ≈ 一个外部数据源下的一项完整查询能力
```

示例：

```text
DomainPropertyDetailTool
DomainMarketStatisticsTool
PTVNearbyTool
GoogleRoutesTool
VicmapPlanningTool
GooglePlacesTool
```

统一接口：

```python
class DomainTool(ABC):
    name: str

    def build_params(
        self,
        context: ExecutionContext,
    ) -> BaseModel:
        ...

    async def run(
        self,
        params: BaseModel,
    ) -> ToolResult:
        ...
```

统一结果：

```python
class ToolResult(PropertyAIBaseModel):
    success: bool
    data: dict | None = None
    error_code: str | None = None
    error_message: str | None = None
    source: str
    execution_time_ms: int
    fallback: bool = False
    cached_at: datetime | None = None
```

---

## 10. Connector

Connector 负责访问单一外部系统。

示例：

```text
DomainConnector
PTVConnector
GoogleRoutesConnector
VicmapConnector
GooglePlacesConnector
```

职责：

- HTTP / SDK 调用
- Authentication
- URL、headers、query params
- Timeout
- Retry
- Response parsing
- External error mapping

Connector 不负责：

- 跨数据源组合
- 用户需求比较
- 价格或交通评分
- 最终业务结论

---

## 11. Data Summary Layer

Data Summary Layer 将多个原子 ToolResult 转换成稳定的业务结果。

```text
Atomic Tool Results
↓
Aggregation
↓
Domain Composers
↓
Structured Intent Result
```

### PriceComposer

输入：

```text
DomainMarketStatisticsTool result
PropertyDetailTool result
User budget
```

输出：

```text
median_price
listing_price
market_alignment
budget_alignment
trend
```

### TransportComposer

输入：

```text
PTVNearbyTool result
GoogleRoutesTool result
User commute limit
```

输出：

```text
nearby_transport
commute_time
within_commute_limit
accessibility_score
```

Composer：

- 不调用外部 API
- 不调用 Tool
- 不包含 LLM
- 只消费 ToolResult
- 执行确定性数据组合和业务计算

---

## 12. Synthesis Agent

仅在需要自然语言整合时调用。

```text
recommend_suburbs → structured result
list_properties   → structured result
property_detail   → Synthesis Agent
open_ended_query  → LLMDrivenExecutor directly answers
```

Synthesis Agent 输入：

```text
user_needs
target_entity
property_context
composed domain results
warnings
```

输出：

```text
report_text
key_metrics
follow_up_suggestions
```

Synthesis Agent 不允许：

- 调用 Tool
- 自动扩展当前执行计划
- 重试失败 Tool
- 修改 Failure Policy

---

## 13. Property Detail 示例

```text
User
↓
Part 1
intent = property_detail
target_entity = property/domain_456
↓
Orchestrator
↓
ContextResolver
↓
PropertyContext
↓
PropertyDetailHandler
↓
并行执行
├── DomainPropertyDetailTool
├── DomainMarketStatisticsTool
├── PTVNearbyTool
├── GoogleRoutesTool
├── VicmapPlanningTool
└── GooglePlacesTool
↓
ToolResults
↓
Data Summary
├── PriceComposer
├── TransportComposer
├── PlanningComposer
└── AmenitiesComposer
↓
PropertyDetailResult
↓
Synthesis Agent
↓
Final Natural-Language Report
```

---

## 14. Failure Policy

| Intent | Policy |
|---|---|
| recommend_suburbs | Strict |
| list_properties | Strict |
| property_detail | Graceful Degradation |
| open_ended_query | LLM-managed |

### Strict

必需 Tool 失败时整体失败。

### Graceful Degradation

部分 Tool 失败时：

- 保留可用结果
- Composer 跳过不可用数据
- 返回 `partial`
- 附带 warnings

### LLM-managed

Tool failure 作为结构化结果返回 LLM，由 LLM 决定继续、跳过或说明数据不可用。

---

## 15. Execution Preview

SSE 事件：

```text
execution_started
tool_started
tool_completed
tool_failed
summary_started
summary_completed
synthesis_started
synthesis_chunk
synthesis_completed
execution_completed
execution_failed
```

用户可见示例：

```text
✓ 已读取房产基础信息
✓ 已获取区域价格数据
✓ 已检查附近公共交通
⏳ 正在计算通勤时间
✓ 正在整合分析结果
```

文案由静态 `ExecutionPreviewRegistry` 管理。

---

## 16. Execution State

Redis 保存短生命周期 execution state：

```text
execution_id
idempotency_key
status
event sequence
event history
final response
expires_at
```

用途：

- SSE reconnect
- Event replay
- Request deduplication
- Multi-instance deployment

---

## 17. 推荐文件结构

```text
agent/
├── orchestration/
│   ├── orchestrator.py
│   ├── context_resolver.py
│   ├── execution_context.py
│   ├── executors/
│   │   ├── code_driven_executor.py
│   │   └── llm_driven_executor.py
│   └── handlers/
│       ├── recommend_suburbs_handler.py
│       ├── list_properties_handler.py
│       └── property_detail_handler.py
│
├── tools/
│   ├── domain/
│   │   ├── property_detail_tool.py
│   │   ├── market_statistics_tool.py
│   │   └── connector.py
│   ├── ptv/
│   │   ├── nearby_tool.py
│   │   └── connector.py
│   ├── google_routes/
│   │   ├── commute_tool.py
│   │   └── connector.py
│   ├── vicmap/
│   │   ├── planning_tool.py
│   │   └── connector.py
│   └── google_places/
│       ├── amenities_tool.py
│       └── connector.py
│
├── summary/
│   ├── price_composer.py
│   ├── transport_composer.py
│   ├── planning_composer.py
│   └── amenities_composer.py
│
├── synthesis/
│   ├── agent.py
│   ├── prompt.py
│   └── models.py
│
└── shared/
    ├── tool_result.py
    ├── tool_registry.py
    ├── execution_events.py
    └── execution_state_store.py
```

---

## 18. Non-Goals

当前版本不包含：

- Tool-to-Tool calls
- Domain SubAgents
- Durable workflow engine
- DAG orchestration
- Long-term conversation storage
- Dynamic progress wording
- LLM chain-of-thought exposure
- User-defined plugins

---

## 19. 架构结论

```text
Part 1
负责理解用户

Orchestrator
负责决定执行路径

Intent Handler
负责固定 intent 的 execution plan

Atomic Tools
负责访问单一数据源或单一查询能力

Connectors
负责外部 API 通信

Data Summary Layer
负责组合 ToolResult 和执行业务计算

Synthesis Agent
负责必要时生成自然语言报告
```
