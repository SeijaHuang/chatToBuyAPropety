# PropertyAI Part 2 — Agent Prototype PRD

| 字段 | 内容 |
|---|---|
| 版本 | v0.1 |
| 状态 | Prototype Design — 核心抽象已锁定 |
| 范围 | Layer 0–3 原型接口定义、设计决策及理由 |
| 上游 | [Agent Architecture PRD](./PropertyAI_Part2_Agent_Architecture_PRD.md) |
| 下游 | 各 Tool/Connector 具体实现（PTV、GoogleRoutes、Domain 等） |

---

## 1. 目标

本 PRD 定义 Part 2 Agent 架构中所有**跨 Tool 共享的原型接口和基础类**。每个原型解决一类共性问题，确保后续 6+ 个 Connector 和 10+ 个 Tool 的实现保持一致性。

核心原则：

- **原型先于实现** — 每个 Connector/Tool 的代码必须基于本文档定义的接口，不得自行发明替代方案
- **泛型模板方法** — 错误处理、重试、Schema 生成等重复逻辑集中在基类，子类只写业务差异
- **两条执行路径共享同一 `run()` 签名** — CodeDriven 和 LLMDriven 在 Tool 层面汇合

---

## 2. 分层架构

```
Layer 0 (共享类型)          ToolResult, ExecutionContext, ConnectorError
                                    ↑ 被所有层依赖
Layer 1 (基础契约)          BaseConnector, BaseTool[TParams]
                                    ↑ 每一个具体 Connector/Tool 的父类
Layer 2 (注册表)            ToolRegistry
                                    ↑ 连接 Handler/Executor 与 Tool 实例
Layer 3 (编排)              IntentHandler[TResult], IExecutor, Orchestrator
                                    ↑ Part 2 的入口
Layer 4 (具体实现)          PTVConnector, PTVNearbyStopsTool, PropertyDetailHandler...
                                    ↑ 不在本文档范围，由各自 PRD 定义
```

### 2.1 文件结构

```text
backend/
├── agent/
│   ├── __init__.py
│   ├── shared/
│   │   ├── __init__.py
│   │   ├── tool_result.py              # Layer 0 — ToolResult
│   │   ├── execution_context.py        # Layer 0 — ExecutionContext
│   │   ├── connector.py                # Layer 1 — BaseConnector + ConnectorError
│   │   ├── tool.py                     # Layer 1 — BaseTool[TParams]
│   │   ├── tool_registry.py            # Layer 2 — ToolRegistry
│   │   └── execution_events.py         # Layer 0 — SSE 事件枚举
│   │
│   ├── orchestration/
│   │   ├── __init__.py
│   │   ├── orchestrator.py             # Layer 3 — 入口
│   │   ├── context_resolver.py         # RoutingPayload → ExecutionContext
│   │   ├── executors/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                 # IExecutor
│   │   │   ├── code_driven_executor.py
│   │   │   └── llm_driven_executor.py
│   │   └── handlers/
│   │       ├── __init__.py
│   │       ├── base.py                 # IntentHandler[TResult]
│   │       ├── recommend_suburbs_handler.py
│   │       ├── list_properties_handler.py
│   │       └── property_detail_handler.py
│   │
│   ├── tools/                          # 每个子目录一个数据源
│   │   └── ...
│   ├── summary/                        # Data Summary Layer
│   │   └── ...
│   └── synthesis/                      # Synthesis Agent
│       └── ...
```

---

## 3. Layer 0 — 共享类型

### 3.1 `ToolResult`

**定位**: 所有 Atomic Tool 的统一返回类型。Composer 和 Executor 只消费 `ToolResult`，不关心哪个 Tool 产生的。

```python
# agent/shared/tool_result.py
from datetime import datetime
from models.base import PropertyAIBaseModel


class ToolResult(PropertyAIBaseModel):
    """Unified result from any Atomic Tool.

    Every Tool.run() returns this — success or failure.
    Composers and Executors consume this without knowing which Tool produced it.
    """
    success: bool
    data: dict | None = None               # Tool-specific structured output
    error_code: str | None = None           # e.g. "PTV_TIMEOUT", "GOOGLE_ROUTES_UNREACHABLE"
    error_message: str | None = None
    source: str                             # 与 BaseTool.name 一致，e.g. "ptv_nearby_stops"
    execution_time_ms: int
    fallback: bool = False                  # True when stale cache was used
    cached_at: datetime | None = None
```

**设计决策**: `data` 使用 `dict | None` 而非泛型 `T | None`。
- **理由**: Composer 用 `result.data.get("nearby_stops", [])` 消费，不关心类型。泛型会增加 ToolRegistry 的复杂度，且 LLMDrivenExecutor 无法在运行时解析泛型参数。后续可局部收窄，不影响接口。

---

### 3.2 `ExecutionContext`

**定位**: Part 2 的共享上下文。Orchestrator 从 Part 1 的 `RoutingPayload` + ContextResolver 的补充数据构建，传递给所有 Tool。

```python
# agent/shared/execution_context.py
from dataclasses import dataclass, field
from datetime import datetime
from models.shared.enums import EUserIntent
from models.shared.submodels import CollectedData


@dataclass(frozen=True)
class ExecutionContext:
    """Immutable context built by Orchestrator, passed to every Tool.

    - 通用字段直接从 RoutingPayload 复制
    - 坐标/地址由 ContextResolver 补充（geocode 一次，所有 Tool 共享）
    - Tool 通过 build_params() 提取自己需要的字段
    """

    # ── 来自 RoutingPayload ──
    session_id: str
    intent: EUserIntent
    user_needs: CollectedData               # M1–M4 所有用户偏好
    target_entity_id: str | None = None     # e.g. "domain_456"
    target_entity_type: str | None = None   # "suburb" | "property"
    target_entity_label: str | None = None  # "123 Swan St, Richmond"

    # ── 由 ContextResolver 补充 ──
    property_lat: float | None = None       # geocode 结果——所有位置 Tool 共享
    property_lng: float | None = None
    property_address: str | None = None

    # ── 执行元数据 ──
    triggered_at: datetime = field(default_factory=lambda: datetime.utcnow())
```

**设计决策**:

1. **`frozen=True` dataclass，非 Pydantic** — 内部传递，不跨 HTTP。遵循现有模式（`ModuleRequirements`）。
2. **坐标放在 Context 而非每个 Tool 各自 geocode** — ContextResolver 做一次 geocode，PTV、GoogleRoutes、GooglePlaces 三个 Tool 复用。避免重复 API 调用。
3. **`user_needs: CollectedData` 完整携带** — Tool 只提取自己需要的字段（如 TransportComposer 读 `commute_destination`），其余忽略。Context 不预设哪个字段有用。

---

### 3.3 `ConnectorError` 异常族

**定位**: Connector 层向 Tool 层抛出的结构化异常。

```python
# agent/shared/connector.py (部分)


class ConnectorError(Exception):
    """所有 Connector 层异常的基类。"""


class ConnectorHttpError(ConnectorError):
    """外部 API 返回了非 2xx 状态码。

    error_code 由子类 _map_error() 生成，如 "PTV_RATE_LIMITED"。
    """
    def __init__(self, status_code: int, error_code: str, response_body: str) -> None:
        self.status_code: int = status_code
        self.error_code: str = error_code
        self.response_body: str = response_body


class ConnectorTimeoutError(ConnectorError):
    """重试耗尽后仍然超时。"""
    def __init__(self, path: str, attempts: int) -> None:
        self.path: str = path
        self.attempts: int = attempts
```

**设计决策**: 两个子类明确区分 HTTP 错误和超时。Tool 层只 `except ConnectorError`，不感知具体 Connector 类型。

---

## 4. Layer 1 — 基础契约

### 4.1 `BaseConnector`

**定位**: 所有外部 API Connector 的共享父类。封装 HTTP 客户端、重试、错误映射。子类只写认证和错误码翻译。

**核心设计**: `_build_auth_async(request) → request`

选择修改整个 `httpx.Request` 对象，而非提供单独的 `_build_headers` / `_build_query_params` 钩子。原因见 4.1.1。

```python
# agent/shared/connector.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
import httpx
import structlog

logger = structlog.get_logger()


@dataclass(frozen=True)
class ConnectorConfig:
    """每个 Connector 的不可变配置。"""
    base_url: str
    default_timeout_secs: float = 5.0
    max_retries: int = 2
    retry_backoff_base_secs: float = 1.0


class BaseConnector(ABC):
    """Shared HTTP + retry + error-mapping for all external API connectors.

    子类:
      - PTVConnector       (HMAC-SHA1 query-param 签名)
      - GoogleRoutesConnector (X-Goog-Api-Key header)
      - DomainConnector    (Authorization: Bearer header)
      - VicmapConnector
      - GooglePlacesConnector

    子类必须覆盖:
      - _build_auth_async() → httpx.Request (施加认证)
      - _map_error()        → str            (HTTP 状态码 → error_code)

    子类通常暴露领域方法（如 get_stops_near_location_async），
    内部调 self._request_async()。
    """

    def __init__(self, config: ConnectorConfig) -> None:
        self._config: ConnectorConfig = config
        self._client: httpx.AsyncClient | None = None

    # ── 子类契约（必须覆盖） ──────────────────────────

    @abstractmethod
    async def _build_auth_async(self, request: httpx.Request) -> httpx.Request:
        """对即将发出的请求施加认证。

        子类可以修改 request 的任何部分：
          - PTVConnector: 修改 request.url（追加 devid + HMAC-SHA1 signature query params）
          - GoogleRoutesConnector: 修改 request.headers（加 X-Goog-Api-Key）
        """
        ...

    @abstractmethod
    def _map_error(self, status_code: int, response_body: str) -> str:
        """将 HTTP 错误响应映射为 ToolResult error_code。

        每个 Connector 定义自己的错误码命名空间：
          - PTVConnector → "PTV_TIMEOUT", "PTV_RATE_LIMITED", "PTV_AUTH_FAILED"...
          - GoogleRoutesConnector → "GOOGLE_ROUTES_TIMEOUT", ...
        """
        ...

    # ── 共享 HTTP 机制（子类不覆盖） ──────────────────

    async def _get_client_async(self) -> httpx.AsyncClient:
        """延迟初始化 httpx 客户端。"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._config.base_url,
                timeout=httpx.Timeout(self._config.default_timeout_secs),
            )
        return self._client

    async def _request_async(
        self,
        method: str,
        path: str,
        params: dict[str, str] | None = None,
        json_body: dict | None = None,
    ) -> dict:
        """执行 HTTP 请求：构建 → 认证 → 重试 → 错误映射。

        Returns:
            解析后的 JSON dict

        Raises:
            ConnectorHttpError: 非 2xx 响应（已含 error_code）
            ConnectorTimeoutError: 重试耗尽
        """
        client: httpx.AsyncClient = await self._get_client_async()
        last_exception: Exception | None = None

        for attempt in range(self._config.max_retries + 1):
            try:
                request: httpx.Request = client.build_request(
                    method, path, params=params, json=json_body,
                )
                request = await self._build_auth_async(request)
                response: httpx.Response = await client.send(request)
                response.raise_for_status()
                return response.json()

            except httpx.TimeoutException as exc:
                last_exception = exc
                logger.warning(
                    "connector_timeout",
                    connector=self.__class__.__name__,
                    path=path,
                    attempt=attempt,
                )
                # 超时也走重试循环
                continue

            except httpx.HTTPStatusError as exc:
                error_code: str = self._map_error(
                    exc.response.status_code, exc.response.text
                )
                raise ConnectorHttpError(
                    status_code=exc.response.status_code,
                    error_code=error_code,
                    response_body=exc.response.text,
                ) from exc

        raise ConnectorTimeoutError(
            path=path,
            attempts=self._config.max_retries + 1,
        ) from last_exception

    async def close_async(self) -> None:
        """关闭底层 HTTP 客户端。"""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
```

#### 4.1.1 设计决策: `_build_auth_async(request) → request` vs 分离的 headers/params 钩子

**选择**: 单一方法，修改完整 `httpx.Request` 对象。

**理由**:

| 认证方式 | 修改位置 | 示例 |
|---|---|---|
| PTV HMAC-SHA1 | `request.url` (query params) | 需要 path + 排序后 params 计算签名，签名本身也是 query param |
| Google API Key | `request.headers` | `X-Goog-Api-Key: AIzaSy...` |
| Domain Bearer Token | `request.headers` | `Authorization: Bearer eyJ...` |

PTV 的 HMAC 签名需要访问**完整 URL**（path + 排序后的 query string），且签名字段本身也是 query param 的一部分（但不能参与签名计算）。分离 headers/params 会迫使 PTVConnector 在两个钩子中拆分签名逻辑，而 `_build_auth_async` 让所有认证逻辑内聚在一个方法中。GoogleRoutes 等 header 认证也同样自然——直接修改 `request.headers`。

#### 4.1.2 设计决策: `_map_error` 返回字符串而非抛异常

**选择**: `_map_error(status_code, body) → str`，由基类 `_request_async` 包装为 `ConnectorHttpError` 抛出。

**理由**（关注点分离）:

| 层 | 职责 | 不该做的事 |
|---|---|---|
| `_map_error` | HTTP status code → domain 错误码字符串 | 决定是否重试、是否降级 |
| `_request_async` | 重试循环 + 抛出 `ConnectorHttpError` | 知道 PTV 的 429 和 Google 的 429 含义不同 |
| `Tool.run()` | `ConnectorError` → `ToolResult(success=False)` | 决定错误对整体 execution 的影响 |
| `IntentHandler` | 根据 Failure Policy 决定降级还是失败 | 知道具体 Connector 的错误码含义 |

如果 `_map_error` 直接抛 `PTVRateLimitedError`、`GoogleRoutesTimeoutError`...每加一个 Connector 都要更新 Tool 层的 catch 列表，违反开闭原则。错误码是 ToolResult 的**数据字段**，不需要变成类型。

---

### 4.2 `BaseTool[TParams]`

**定位**: 所有 Atomic Tool 的泛型基类。提供 `build_params` → `run` 的两步调用模式和错误处理模板。

**核心设计**: 泛型 `TParams` + 模板方法 `run()`

```python
# agent/shared/tool.py
import time
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from pydantic import BaseModel

from agent.shared.execution_context import ExecutionContext
from agent.shared.tool_result import ToolResult
from agent.shared.connector import ConnectorHttpError, ConnectorTimeoutError

TParams = TypeVar("TParams", bound=BaseModel)


class BaseTool(ABC, Generic[TParams]):
    """Atomic Tool 的抽象基类。

    一个 Tool ≈ 一个外部数据源下的一项完整查询能力。
    Tool 不调用 Tool。Tool 不包含 LLM。

    子类必须提供:
      - name:          全局唯一标识符（也是 ToolResult.source 的值）
      - description:   一句话描述，暴露给 LLM
      - params_model:  TParams 的具体类型，用于自动生成 JSON Schema
      - build_params(): 从 ExecutionContext 提取本 Tool 需要的参数
      - _execute_async(): 调 Connector + 解析返回数据

    子类不应覆盖 run()——错误处理模板已由基类提供。
    """

    name: str
    description: str
    params_model: type[TParams]

    @abstractmethod
    def build_params(self, context: ExecutionContext) -> TParams:
        """从 ExecutionContext 提取本 Tool 需要的参数。

        纯函数——不做 I/O，不调外部 API。
        如果前置条件不满足（如缺少坐标），返回的 params 中
        相关字段为 None，由 Handler 决定是否跳过执行。

        仅在 CodeDriven 路径下被调用。LLMDriven 路径下
        LLM 直接生成 params，不经过此方法。
        """
        ...

    @abstractmethod
    async def _execute_async(self, params: TParams) -> dict:
        """子类实现核心逻辑：调 Connector → 解析 → 返回 dict。

        Returns:
            解析后的业务数据 dict，会被自动包装进 ToolResult.data
        """
        ...

    async def run(self, params: TParams) -> ToolResult:
        """执行 Tool，自动捕获 Connector 层错误并转换为 ToolResult。

        模板方法——子类一般不需要覆盖。
        CodeDriven 和 LLMDriven 两条路径在此汇合。
        """
        start: float = time.monotonic()
        try:
            data: dict = await self._execute_async(params)
            return ToolResult(
                success=True,
                data=data,
                source=self.name,
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )
        except ConnectorHttpError as e:
            return ToolResult(
                success=False,
                error_code=e.error_code,
                error_message=str(e),
                source=self.name,
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )
        except ConnectorTimeoutError as e:
            return ToolResult(
                success=False,
                error_code=f"{self.name.upper()}_TIMEOUT",
                error_message=str(e),
                source=self.name,
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )

    def get_tool_schema(self) -> dict:
        """返回 provider-agnostic 的 Tool 元数据和参数 Schema。

        返回 {name, description, parameters}，其中 parameters 为
        params_model 的 JSON Schema（type, properties, required, 可选的 $defs）。

        OpenAI function-calling 的 {"type": "function", "function": ...}
        包装由 ToolRegistry.get_openai_tool_schemas() 负责——
        Tool 本身不绑定任何特定 LLM provider。
        """
        raw_schema: dict = cast(BaseModel, self.params_model).model_json_schema()
        parameters: dict = {
            "type": raw_schema.get("type", "object"),
            "properties": raw_schema.get("properties", {}),
            "required": raw_schema.get("required", []),
        }
        if "$defs" in raw_schema:
            parameters["$defs"] = raw_schema["$defs"]
        return {
            "name": self.name,
            "description": self.description,
            "parameters": parameters,
        }
```

#### 4.2.1 设计决策: `build_params` 与 `run` 分离

**选择**: Handler 分两步调用——先 `build_params(context)` 再 `run(params)`。而非一步 `run(context)`。

**理由**:

1. **LLMDriven 路径不经过 `build_params`**。LLM 从 prompt 中的 ExecutionContext 文本自行推理参数，生成 `{"lat": -37.82, "lng": 144.96}`。`run()` 必须接受具体 Params 而非 Context，这样两条路径在 `run()` 处汇合：

```
CodeDriven:  ExecutionContext → build_params() → TParams → run()
LLMDriven:   LLM tool_call → 反序列化 → TParams → run()
                                                    ↑
                                两条路径在 run() 汇合
```

2. **Handler 可以在执行前做决策**。`build_params` 返回后，Handler 可以检查前置条件（如 lat 为 None 则跳过 PTV），避免浪费调度资源。

#### 4.2.2 设计决策: 模板方法 `run()` + 抽象 `_execute_async()`

**选择**: `run()` 在基类实现（try/catch 包装），子类只写 `_execute_async()`。

**理由**: `ConnectorError → ToolResult` 的转换逻辑对所有 Tool 完全一致。模板方法消除了 N 个 Tool 中重复的 try/catch 代码。

#### 4.2.3 参数类型声明: `params_model` 类变量

**选择**: 子类显式声明 `params_model = NearbyStopsParams`，而非通过 `__orig_bases__` 反射推导泛型。

**理由**: Python 的 `__orig_bases__` 在多层继承和运行时动态类创建场景下不可靠。显式声明更简单、类型安全，且代码意图一目了然。

---

## 5. Layer 2 — ToolRegistry

**定位**: 全局 name → Tool 实例的注册表。两个消费者：
- CodeDriven Handler: `registry.get("ptv_nearby_stops")` 获取实例
- LLMDriven Executor: `registry.get_openai_tool_schemas()` 获取 OpenAI function-calling 格式的 Tool 定义

```python
# agent/shared/tool_registry.py

class ToolRegistry:
    """Tool 的全局注册表。

    所有 Tool 实例在应用启动时注册。不支持运行时动态增删。
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """注册一个 Tool 实例。重复注册同名 Tool 抛出 ValueError。"""
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool:
        """按名称获取 Tool 实例。不存在抛出 KeyError。"""
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' not found in registry")
        return self._tools[name]

    def list_names(self) -> list[str]:
        """返回所有已注册 Tool 的名称。"""
        return list(self._tools.keys())

    def get_tool_schemas(self) -> list[dict]:
        """返回所有 Tool 的 provider-agnostic 元数据列表。
        
        每个元素为 {name, description, parameters}，不含 provider 特定包装。
        """
        return [tool.get_tool_schema() for tool in self._tools.values()]

    def get_openai_tool_schemas(self) -> list[dict]:
        """以 OpenAI function-calling 格式返回所有 Tool 的定义。

        在 get_tool_schemas() 的结果外包装 {"type": "function", "function": ...}。
        供 LLMDrivenExecutor 使用。
        """
        return [
            {"type": "function", "function": schema}
            for schema in self.get_tool_schemas()
        ]
```

---

## 6. Layer 3 — 编排

### 6.1 `IntentHandler[TResult]`

**定位**: 一个固定 intent 的确定性执行计划。代码写死的 workflow，不是 LLM Agent。

来自 Agent Architecture PRD §8:

- 定义该 intent 使用哪些原子 Tool
- 并行执行 Tool（内部处理依赖顺序）
- 调用对应 Composer
- 应用 intent-specific failure policy
- 决定是否调用 Synthesis Agent

```python
# agent/orchestration/handlers/base.py
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from agent.shared.execution_context import ExecutionContext

TResult = TypeVar("TResult")


class IntentHandler(ABC, Generic[TResult]):
    """一个固定 intent 的确定性执行计划。

    子类: RecommendSuburbsHandler, ListPropertiesHandler, PropertyDetailHandler
    """

    @abstractmethod
    async def execute_async(self, context: ExecutionContext) -> TResult:
        """执行该 intent 的完整计划。

        编排步骤:
          1. 从 ToolRegistry 获取所需 Tool
          2. 各 Tool.build_params(context) 构建参数
          3. 按依赖关系并行/顺序执行 Tool.run(params)
          4. 将 ToolResult 传给 Composer 组合
          5. 决定是否调 Synthesis Agent
          6. 返回结构化结果
        """
        ...

    @property
    @abstractmethod
    def intent(self) -> EUserIntent:
        """此 Handler 处理的 intent。"""
        ...
```

### 6.2 `IExecutor`

**定位**: Orchestrator 委托的执行单元。根据 intent 选择实现。

来自 Agent Architecture PRD §7:

| Executor | 适用 intent | 执行方式 |
|---|---|---|
| `CodeDrivenExecutor` | recommend_suburbs, list_properties, property_detail | intent → IntentHandler → 确定性 workflow |
| `LLMDrivenExecutor` | open_ended_query | LLM 循环 + Tool calling |

```python
# agent/orchestration/executors/base.py
from abc import ABC, abstractmethod
from agent.shared.execution_context import ExecutionContext


class IExecutor(ABC):
    """Executor 是 Orchestrator 委托的执行单元。"""

    @abstractmethod
    async def execute_async(self, context: ExecutionContext) -> ExecutionResponse:
        """执行并返回最终结果。

        CodeDrivenExecutor: 查 IntentHandler → 确定性执行
        LLMDrivenExecutor:  LLM 循环 + Tool calling
        """
        ...
```

#### 6.2.1 `CodeDrivenExecutor`

```python
# agent/orchestration/executors/code_driven_executor.py
class CodeDrivenExecutor(IExecutor):
    """固定 intent 的确定性执行。

    根据 context.intent 查找对应的 IntentHandler，委托执行。
    """

    def __init__(self, handlers: dict[EUserIntent, IntentHandler]) -> None:
        self._handlers: dict[EUserIntent, IntentHandler] = handlers

    async def execute_async(self, context: ExecutionContext) -> ExecutionResponse:
        handler: IntentHandler | None = self._handlers.get(context.intent)
        if handler is None:
            raise ValueError(f"No handler registered for intent: {context.intent}")
        result = await handler.execute_async(context)
        return ExecutionResponse(data=result)
```

#### 6.2.2 `LLMDrivenExecutor`

```python
# agent/orchestration/executors/llm_driven_executor.py
class LLMDrivenExecutor(IExecutor):
    """开放式查询的 LLM 驱动执行。

    向 LLM 暴露可用 Tools，LLM 自主决定调用哪些 Tool、
    以什么参数调用、何时结束。

    职责（来自 Agent Architecture PRD §7.2）:
      - 向 LLM 暴露允许使用的原子 Tools
      - 执行 tool call
      - 将 ToolResult 返回给 LLM
      - 限制最大轮数和总超时
      - 输出最终回答
    """

    def __init__(
        self,
        llm: ILLMClient,
        registry: ToolRegistry,
        max_rounds: int = 5,
        timeout_secs: float = 30.0,
    ) -> None:
        self._llm: ILLMClient = llm
        self._registry: ToolRegistry = registry
        self._max_rounds: int = max_rounds
        self._timeout_secs: float = timeout_secs

    async def execute_async(self, context: ExecutionContext) -> ExecutionResponse:
        # 将 ExecutionContext 序列化进 system prompt
        messages: list[dict] = [self._build_system_message(context)]
        tool_schemas: list[dict] = self._registry.get_openai_tool_schemas()

        for _round in range(self._max_rounds):
            response = await self._llm.chat_with_tools_async(
                system_prompt="",
                messages=messages,
                tools=tool_schemas,
            )

            # LLM 选择直接回答
            if not response.get("tool_calls"):
                return ExecutionResponse(data={"reply": response["content"]})

            # LLM 选择调 Tool → 执行 → 结果返回 LLM
            for tool_call in response["tool_calls"]:
                tool: BaseTool = self._registry.get(tool_call["name"])
                params: BaseModel = tool.params_model.model_validate(
                    tool_call["arguments"]
                )
                result: ToolResult = await tool.run(params)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": result.model_dump_json(),
                })

        # 超过最大轮数
        return ExecutionResponse(
            data={"reply": "抱歉，查询超时。请尝试更具体的问题。"}
        )
```

**注意**: LLMDriven 路径**不调用 `build_params()`**。LLM 从 system prompt 中的 Context 文本自行理解并生成参数。两条路径在 `tool.run(params)` 汇合。

---

## 7. 两条执行路径对比

```
CodeDriven 路径 (固定 intent):
────────────────────────────────────────────────
  RoutingPayload
      ↓
  Orchestrator
      ↓
  ContextResolver.resolve(routing) → ExecutionContext
      ↓
  CodeDrivenExecutor
      ↓
  IntentHandler.execute_async(context)
      ├── tool.build_params(context) → TParams   ← 代码计算参数
      ├── 检查前置条件
      └── await tool.run(params) → ToolResult    ← 执行

LLMDriven 路径 (open_ended_query):
────────────────────────────────────────────────
  RoutingPayload
      ↓
  Orchestrator
      ↓
  ContextResolver.resolve(routing) → ExecutionContext
      ↓
  LLMDrivenExecutor
      ├── ExecutionContext → system prompt       ← Context 转自然语言
      ├── tool_schemas = registry.get_openai_tool_schemas()
      │
      ├── LLM 推理: tool_call("ptv_nearby_stops", {lat:-37.82, lng:144.96})
      │     ↓
      ├── tool = registry.get("ptv_nearby_stops")
      ├── params = tool.params_model.model_validate(llm_args)  ← LLM 生成参数
      ├── result = await tool.run(params) → ToolResult        ← 执行
      │     ↓
      └── LLM 看结果 → 决定继续调 Tool 还是直接回答
```

| | CodeDriven | LLMDriven |
|---|---|---|
| 谁决定调哪个 Tool？ | Handler（代码写死） | LLM（运行时推理） |
| 参数从哪来？ | `build_params(context)` 确定性计算 | LLM 生成的 `tool_call.arguments` |
| `build_params()` 是否调用？ | ✅ 是 | ❌ 否 |
| `run()` 签名 | `(params: TParams) → ToolResult` | **同一个** `(params: TParams) → ToolResult` |
| 适用场景 | 固定 intent，流程已知 | open_ended_query，流程不可预知 |

---

## 8. 具体 Tool 示例（PTV）

以下是一个完整的具体 Tool 实现，验证原型设计的可用性。

### 8.1 Params Model

```python
# agent/tools/ptv/nearby_stops_tool.py
from pydantic import BaseModel, Field


class NearbyStopsParams(BaseModel):
    """PTVNearbyStopsTool 的参数。"""
    lat: float
    lng: float
    train_radius_m: int = Field(default=1200)
    tram_radius_m: int = Field(default=800)
    bus_radius_m: int = Field(default=400)
```

### 8.2 Tool 实现

```python
class PTVNearbyStopsTool(BaseTool[NearbyStopsParams]):
    name = "ptv_nearby_stops"
    description = "查询指定坐标周边的公共交通站点（火车、电车、公交）"
    params_model = NearbyStopsParams

    def __init__(self, connector: PTVConnector) -> None:
        self._connector: PTVConnector = connector

    def build_params(self, context: ExecutionContext) -> NearbyStopsParams:
        """从 ExecutionContext 构建参数。

        包括业务逻辑：用户偏好火车时扩大搜索半径。
        """
        train_radius: int = 1200
        user_mode: str | None = context.user_needs.m3.commute_mode
        if user_mode == "train":
            train_radius = 2000

        return NearbyStopsParams(
            lat=context.property_lat,   # type: ignore[arg-type]
            lng=context.property_lng,   # type: ignore[arg-type]
            train_radius_m=train_radius,
        )

    async def _execute_async(self, params: NearbyStopsParams) -> dict:
        """调 PTVConnector → 解析 → 返回 dict。"""
        raw_stops: list[dict] = await self._connector.get_stops_near_location_async(
            lat=params.lat,
            lng=params.lng,
            route_types=[0, 1, 2],
            max_distance=params.train_radius_m,
        )
        return PTVNearbyStopResult(
            nearby_stops=[self._parse_stop(s) for s in raw_stops],
            # ... 分类统计 ...
        ).model_dump()
```

### 8.3 Connector 实现

```python
class PTVConnector(BaseConnector):
    """PTV Timetable API v3 的 HTTP 封装。"""

    def __init__(self, config: ConnectorConfig, devid: str, api_key: str) -> None:
        super().__init__(config)
        self._devid: str = devid
        self._api_key: str = api_key

    async def _build_auth_async(self, request: httpx.Request) -> httpx.Request:
        """HMAC-SHA1 签名——修改 request.url 追加 devid + signature。"""
        params: dict[str, str] = dict(request.url.params)
        params["devid"] = self._devid

        sorted_params: list[tuple[str, str]] = sorted(params.items())
        query_string: str = urllib.parse.urlencode(sorted_params)
        message: str = f"{request.url.path}?{query_string}"

        signature: str = hmac.new(
            self._api_key.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha1,
        ).hexdigest().upper()

        request.url = request.url.copy_merge_params({"signature": signature})
        return request

    def _map_error(self, status_code: int, response_body: str) -> str:
        mapping: dict[int, str] = {
            400: "PTV_BAD_REQUEST",
            403: "PTV_AUTH_FAILED",
            429: "PTV_RATE_LIMITED",
        }
        if status_code in mapping:
            return mapping[status_code]
        if status_code >= 500:
            return "PTV_UPSTREAM_ERROR"
        return "PTV_UNKNOWN_ERROR"

    async def get_stops_near_location_async(
        self, lat: float, lng: float,
        route_types: list[int] | None = None,
        max_distance: int = 1200,
    ) -> list[dict]:
        """查询指定坐标周边的公共交通站点。"""
        params: dict[str, str] = {
            "max_distance": str(max_distance),
        }
        if route_types:
            params["route_types"] = ",".join(str(r) for r in route_types)

        result: dict = await self._request_async(
            "GET",
            f"/v3/stops/location/{lat},{lng}",
            params=params,
        )
        return result.get("stops", [])
```

---

## 9. 设计决策速查表

| # | 决策 | 方案 | 理由 |
|---|---|---|---|
| D1 | `ToolResult.data` 类型 | `dict \| None` | 简单；Composer 用 key 取值；LLM 路径下无法在运行时解析泛型 |
| D2 | `ExecutionContext` 类型 | frozen dataclass | 内部传递不跨 HTTP，遵循现有模式 |
| D3 | 坐标放在哪？ | `ExecutionContext`，ContextResolver 做一次 geocode | 避免 PTV、GoogleRoutes、GooglePlaces 各自 geocode |
| D4 | Connector 认证方法 | `_build_auth_async(request) → request` | 支持 query-param 签名 (PTV) 和 header 认证 (Google/Domain)，一个方法统一 |
| D5 | 错误码归属 | `_map_error` 返回字符串，基类包装为异常 | 错误码是数据不是控制流；上层只看 `ToolResult.success`，不 catch 具体异常 |
| D6 | `build_params` 与 `run` 关系 | 分离——两步调用 | LLM 路径不经过 `build_params`，两条路径在 `run(params)` 汇合 |
| D7 | `run()` 的实现位置 | 基类模板方法 | 错误→ToolResult 转换对所有 Tool 一致，避免重复 |
| D8 | 泛型参数声明方式 | `params_model` 类变量 | 比 `__orig_bases__` 反射更可靠，意图更清晰 |
| D9 | LLM 路径是否用 `build_params` | 否 | LLM 从 system prompt 中的 Context 文本自行推理参数 |
| D10 | `TParams` 的 JSON Schema | Pydantic `model_json_schema()` 自动生成 | Tool 层只输出 provider-agnostic 的 {name, description, parameters}；OpenAI envelope 由 ToolRegistry.get_openai_tool_schemas() 统一包装，Tool 不绑定任何 LLM provider |

---

## 10. 非目标

当前原型不包含：

- Tool-to-Tool 调用（架构规则禁止）
- DAG/工作流引擎
- 运行时动态注册/卸载 Tool
- `build_params` 的缓存或 memoization
- 具体的 Composer / Synthesis Agent 原型
- 具体的 Failure Policy 实现（属于 IntentHandler 子类）
- SSE 事件的具体发送机制
- ExecutionState 的 Redis 持久化

---

## 11. 实施决策记录

以下决策在代码实施前做出，与 Architecture PRD 或早期设计讨论中的选择可能存在差异。

| # | 决策 | 方案 | 理由 |
|---|---|---|---|
| I1 | `ExecutionContext.user_needs` 类型 | `CollectedData`（非 `UserNeeds`） | `UserNeeds` 在 Part 1 服务于 summary 快照接口；Part 2 的 Tool 只需要 `CollectedData` 字段，`ContextResolver` 从 `RoutingPayload.user_needs.collected` 提取；`UserNeeds` 的 `session_id`/`generated_at`/`schema_version`/`initial_intent` 对 Tool 无意义 |
| I2 | `ConnectorError` 基类 | `Exception`（非 `PropertyAIException`） | ConnectorError 在 `BaseTool.run()` 模板方法中被捕获并转为 `ToolResult`，永远不到达 HTTP handler；PRD 决策 D5：错误码是数据不是控制流；`PropertyAIException` 的 `status_code`/`details` 字段语义与 Connector 层不匹配 |
| I3 | `ExecutionResponse` 定义位置 | `models/shared/execution_response.py`，继承 `PropertyAIBaseModel` | 跨 Executor / Orchestrator / 未来 HTTP 边界共用；遵循现有 models 分层规范 |
| I4 | ILLMClient 扩展 | 不纳入原型阶段 | 现有 `chat_with_tools_async` 为 Part 1 单次提取设计；LLMDrivenExecutor 使用现有 Protocol + `# TODO(agent)` 标记，多轮 tool calling 支持后续单独 PR |
| I5 | PTV 验证实现 | 不纳入原型阶段 | 用户反馈只需原型搭建，具体 Connector/Tool 由各自 PRD 覆盖 |
| I6 | `pyproject.toml` 包注册 | 纳入 Subtask 1 | `[tool.setuptools.packages.find]` 追加 `"agent*"`；`[tool.ruff.lint.isort]` 追加 `"agent"`；否则 ruff/mypy 无法正确识别 agent 包 |

---

## 12. 实施计划

所有原型接口定义来自本文档 §3–§6。按 Layer 拆分为 4 个 Subtask，跨层的 `ExecutionResponse` 放入 Subtask 4。

### 12.1 文件结构总览

```text
backend/
├── agent/
│   ├── __init__.py
│   ├── shared/
│   │   ├── __init__.py
│   │   ├── tool_result.py              # Subtask 1 — ToolResult (Layer 0)
│   │   ├── execution_context.py        # Subtask 1 — ExecutionContext (Layer 0)
│   │   ├── execution_events.py         # Subtask 1 — SSE 事件枚举 (Layer 0)
│   │   ├── connector.py                # Subtask 1+2 — ConnectorError (L0) + BaseConnector (L1)
│   │   ├── tool.py                     # Subtask 2 — BaseTool[TParams] (Layer 1)
│   │   └── tool_registry.py            # Subtask 3 — ToolRegistry (Layer 2)
│   │
│   ├── orchestration/
│   │   ├── __init__.py
│   │   ├── orchestrator.py             # Subtask 4 — 入口 (Layer 3)
│   │   ├── context_resolver.py         # Subtask 4 — RoutingPayload → ExecutionContext (Layer 3)
│   │   ├── executors/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                 # Subtask 4 — IExecutor (Layer 3)
│   │   │   ├── code_driven_executor.py # Subtask 4
│   │   │   └── llm_driven_executor.py  # Subtask 4
│   │   └── handlers/
│   │       ├── __init__.py
│   │       └── base.py                 # Subtask 4 — IntentHandler[TResult] (Layer 3)
│   │
│   ├── tools/                          # 不在本次范围
│   ├── summary/                        # 不在本次范围
│   └── synthesis/                      # 不在本次范围
│
├── models/shared/
│   └── execution_response.py           # Subtask 4 — ExecutionResponse (跨层)
│
└── tests/
    ├── test_tool_result.py             # Subtask 1
    ├── test_execution_context.py       # Subtask 1
    ├── test_execution_events.py        # Subtask 1
    ├── test_connector.py               # Subtask 1+2
    ├── test_tool.py                    # Subtask 2
    ├── test_tool_registry.py           # Subtask 3
    ├── test_code_driven_executor.py    # Subtask 4
    ├── test_llm_driven_executor.py     # Subtask 4
    ├── test_context_resolver.py        # Subtask 4
    ├── test_orchestrator.py            # Subtask 4
    └── test_execution_response.py      # Subtask 4
```

### 12.2 Subtask 1 — Layer 0：共享类型

**范围**: 本文档 §3 — `ToolResult`、`ExecutionContext`、`ExecutionEventType`、`ConnectorError` 异常族。

**目标**: 零外部依赖的纯数据结构，被所有后续层引用。

| # | 源文件 | 测试文件 | 覆盖率 | 测试要点 |
|---|---|---|---|---|
| S1.1 | `agent/shared/tool_result.py` | `tests/test_tool_result.py` | **100%** | success/failure 两种状态构造；camelCase 序列化（继承 `PropertyAIBaseModel`）；`fallback=True` + `cached_at` 路径；`error_code` / `error_message` 仅在 `success=False` 时有值 |
| S1.2 | `agent/shared/execution_context.py` | `tests/test_execution_context.py` | **100%** | frozen dataclass 不可变性（赋值抛 `FrozenInstanceError`）；默认值行为；`triggered_at` 自动填充；`property_lat`/`property_lng` 为 None 时表示未 geocode |
| S1.3 | `agent/shared/execution_events.py` | `tests/test_execution_events.py` | **100%** | 枚举成员值唯一；可 JSON 序列化（`isinstance(member, str)` 或 `member.value`） |
| S1.4 | `agent/shared/connector.py`（异常部分） | `tests/test_connector.py`（异常测试） | **100%** | `ConnectorHttpError` 各字段正确赋值（`status_code`, `error_code`, `response_body`）；`ConnectorTimeoutError` 各字段（`path`, `attempts`）；两者均为 `ConnectorError` 子类 |

**依赖**: `models/base.py`（`PropertyAIBaseModel`）、`models/shared/enums.py`（`EUserIntent`）、`models/shared/submodels.py`（`CollectedData`）

**完成标准**:
- 4 个模块达到 **100%** 覆盖率
- `ruff check` + `mypy --strict` 通过
- `agent/shared/connector.py` 仅含异常类，不含 BaseConnector
- `pyproject.toml` 更新：`[tool.setuptools.packages.find]` include 追加 `"agent*"`；`[tool.ruff.lint.isort]` known-first-party 追加 `"agent"`

---

### 12.3 Subtask 2 — Layer 1：基础契约

**范围**: 本文档 §4 — `ConnectorConfig`、`BaseConnector`、`BaseTool[TParams]`。

**目标**: 所有 Connector/Tool 的泛型基类，封装 HTTP 重试和错误转换模板。

| # | 源文件 | 测试文件 | 覆盖率 | 测试要点 |
|---|---|---|---|---|
| S2.1 | `agent/shared/connector.py`（追加 BaseConnector + ConnectorConfig） | `tests/test_connector.py`（追加） | **100%** | `ConnectorConfig` frozen dataclass；`_get_client_async` 延迟初始化；`_request_async` 重试逻辑（mock `httpx.AsyncClient.send`）：成功返回 JSON、HTTP 4xx/5xx → `ConnectorHttpError`（含 `_map_error` 生成的 error_code）、超时耗尽 → `ConnectorTimeoutError`；`_build_auth_async` 抽象方法；`close_async` 清理 |
| S2.2 | `agent/shared/tool.py` | `tests/test_tool.py` | **100%** | `run()` 模板方法：`_execute_async` 成功 → `ToolResult(success=True, data=...)`；`ConnectorHttpError` → `ToolResult(success=False, error_code=e.error_code)`；`ConnectorTimeoutError` → `ToolResult(success=False, error_code="..._TIMEOUT")`；`execution_time_ms` 正确计算；`get_tool_schema()` 返回 provider-agnostic 的 {name, description, parameters}（不含 OpenAI envelope）；`build_params` / `_execute_async` 抽象方法 |

**依赖**: Subtask 1（`ToolResult`、`ExecutionContext`、`ConnectorError`）+ `httpx` + `pydantic`

**完成标准**:
- `connector.py` + `tool.py` 达到 **100%** 覆盖率
- mock `httpx.AsyncClient.send` 覆盖：成功 2xx、客户端错误 4xx、服务端错误 5xx、超时重试成功、超时重试耗尽

---

### 12.4 Subtask 3 — Layer 2：注册表

**范围**: 本文档 §5 — `ToolRegistry`。

**目标**: 全局 name → Tool 实例的注册表，连接 Handler/Executor 与 Tool。

| # | 源文件 | 测试文件 | 覆盖率 | 测试要点 |
|---|---|---|---|---|
| S3.1 | `agent/shared/tool_registry.py` | `tests/test_tool_registry.py` | **100%** | `register` / `get` / `list_names` 正常路径；重复注册同名 Tool → `ValueError`；`get` 不存在的名称 → `KeyError`；`get_tool_schemas()` 返回 provider-agnostic schema 列表（空注册表 → 空列表）；`get_openai_tool_schemas()` 为每个 schema 包装 {"type": "function", "function": ...} |

**依赖**: Subtask 2（`BaseTool`）

**完成标准**:
- **100%** 覆盖率
- 所有边界条件有对应测试

---

### 12.5 Subtask 4 — Layer 3 + 跨层：编排核心 + ExecutionResponse

**范围**: 本文档 §6 — `IntentHandler`、`IExecutor`、`CodeDrivenExecutor`、`LLMDrivenExecutor`、`ContextResolver`、`Orchestrator`；加上跨层的 `ExecutionResponse`。

**目标**: Part 2 编排骨架——intent 路由、两条执行路径、上下文解析、入口。

| # | 源文件 | 测试文件 | 覆盖率 | 测试要点 |
|---|---|---|---|---|
| S4.1 | `agent/orchestration/handlers/base.py` | (抽象基类，子类测试覆盖) | — | `IntentHandler[TResult].execute_async(context) → TResult`；`intent` property 返回 `EUserIntent` |
| S4.2 | `agent/orchestration/executors/base.py` | (Protocol，子类测试覆盖) | — | `IExecutor.execute_async(context) → ExecutionResponse` |
| S4.3 | `agent/orchestration/executors/code_driven_executor.py` | `tests/test_code_driven_executor.py` | **≥80%** | 根据 `context.intent` 路由到正确 Handler（mock Handler）；未注册 intent → `ValueError`；Handler 返回值正确包装为 `ExecutionResponse` |
| S4.4 | `agent/orchestration/executors/llm_driven_executor.py` | `tests/test_llm_driven_executor.py` | **≥80%** | 无 tool_call → 直接返回 LLM 回答；有 tool_call → 调 `Tool.run(params)` 并回传结果给 LLM；超出 `max_rounds` → 返回超时消息；`_build_system_message(context)` 将 Context 文本化；mock ILLMClient 覆盖多轮路径 |
| S4.5 | `agent/orchestration/context_resolver.py` | `tests/test_context_resolver.py` | **100%** | `RoutingPayload` → `ExecutionContext` 字段逐一映射正确；`session_id`/`intent`/`user_needs` 直接复制；`target_entity_*` 字段透传；geocode 结果补充 `property_lat`/`property_lng`/`property_address`（mock）；geocode 失败时不抛异常、坐标保持 None |
| S4.6 | `agent/orchestration/orchestrator.py` | `tests/test_orchestrator.py` | **≥80%** | 接收 `RoutingPayload` → 调 `ContextResolver.resolve()` → 根据 `execution_mode` 选择 Executor（`CODE_DRIVEN` → `CodeDrivenExecutor` / `AGENTIC_LOOP` → `LLMDrivenExecutor`）；mock Executor 验证调用链 |
| S4.7 | `models/shared/execution_response.py` | `tests/test_execution_response.py` | **100%** | 序列化/反序列化；camelCase alias；`status` 枚举值（`"success"` / `"partial"` / `"failed"`）；`data: dict` + `error: ErrorDetail | None` |

**依赖**: Subtask 1–3 全部 + 现有 `ILLMClient` Protocol + 现有 `RoutingPayload` + 现有 `ErrorDetail`

**LLMDrivenExecutor 已知缺口**（不在本次范围，代码中以 `# TODO(agent)` 标记）:
- 现有 `ILLMClient.chat_with_tools_async` 只返回单次 tool call 的解析参数，不支持多 tool_calls 返回 + tool result 回传
- 需要新增方法支持多轮对话（返回 `content` + `tool_calls[]` + `tool_call_id`）
- 原型阶段使用现有 Protocol 定义调用签名，mock 测试中使用自定义 fake `ILLMClient`

**完成标准**:
- 所有模块达到指定覆盖率
- `ruff check` + `mypy --strict` 通过
- CodeDriven + LLMDriven 两条路径均可通过 mock 测试端到端走通
- `testing.md` 覆盖率表新增 `agent/` 模块条目

---

### 12.6 依赖关系

```
Subtask 1 (Layer 0 — 共享类型)
    │
    ▼
Subtask 2 (Layer 1 — 基础契约, 依赖 L0)
    │
    ▼
Subtask 3 (Layer 2 — 注册表, 依赖 L1 BaseTool)
    │
    ▼
Subtask 4 (Layer 3 + 跨层 — 编排 + ExecutionResponse, 依赖 L0–L2)
```

每个 Subtask 只依赖前序 Subtask + 现有模块，不跳跃依赖。

### 12.7 非本次范围

以下内容明确排除，由各自 PRD 或后续迭代覆盖：

- 具体 Connector 实现（PTVConnector、GoogleRoutesConnector、DomainConnector 等）
- 具体 Tool 实现（PTVNearbyStopsTool、GoogleRoutesTool 等）
- 具体 IntentHandler 子类（RecommendSuburbsHandler、ListPropertiesHandler 等）
- Composer / Data Summary Layer / Synthesis Agent
- Failure Policy 具体实现（属于 IntentHandler 子类）
- SSE 事件的实际发送机制（`execution_events.py` 只定义枚举）
- ExecutionState 的 Redis 持久化
- ILLMClient 协议扩展（多轮 tool calling）

---

## 13. 阶段标记

| 阶段 | 状态 |
|---|---|
| Layer 0 — ToolResult, ExecutionContext, ConnectorError | ✅ 已锁定 |
| Layer 1 — BaseConnector, BaseTool | ✅ 已锁定 |
| Layer 2 — ToolRegistry | ✅ 已锁定 |
| Layer 3 — IntentHandler, IExecutor | ✅ 已锁定 |
| Subtask 1 — Layer 0 原型实现 + 测试 | 🔲 待实施 |
| Subtask 2 — Layer 1 原型实现 + 测试 | 🔲 待实施 |
| Subtask 3 — Layer 2 原型实现 + 测试 | 🔲 待实施 |
| Subtask 4 — Layer 3 + 跨层 原型实现 + 测试 | 🔲 待实施 |
