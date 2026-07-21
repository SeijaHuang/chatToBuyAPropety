# PropertyAI Part 2 — PTV Integration PRD

| 字段 | 内容 |
|---|---|
| 版本 | v0.4 |
| 状态 | Draft — 实现计划已拆分为 8 个 Subtask；Agent Endpoints 已设计 |
| 范围 | PTV API 集成 — 原子 Tool 设计、Connector、TransportComposer、缓存与容错 |
| 上游 | [PropertyAI Part 2 Agent Architecture](./PropertyAI_Part2_Agent_Architecture_PRD.md) §8-11；[Agent Prototype PRD](./PropertyAI_Part2_Prototype_PRD.md) |
| 下游 | TransportComposer → Synthesis Agent → Final Response |
| 非范围 | Google Routes Tool（独立 PRD）、Vicmap Planning Tool、Google Places Tool |

> **v0.4 变更摘要（vs v0.3）：**
> - §17 从 Phase-based 重写为 8 个 Subtask 分解（含依赖图、交付内容、测试要点、完成标准）
> - 新增 §18 Agent PTV Endpoints 详细设计（`routers/agent_ptv.py`，Swagger 可调测）
> - 新增 Subtask 8：Agent PTV Endpoints（`POST /agent/ptv/nearby-stops`, `/stop-detail`, `/transport-assessment`）
> - Subtask 7（Postgres 持久化）标记为独立 subtask，待 table 设计完成后实施

---

## 1. PTV 在 PropertyAI 中的定位

### 1.1 一句话职责

> **PTV 回答："这个房产周边有什么公共交通？方不方便？"**

当用户查看某个具体房产（property_detail）或对比多个房产（compare_properties）时，PTV 负责提供该房产周边的公共交通覆盖信息——附近的火车站、电车站、公交站，以及每条线路的班次频率。

### 1.2 PTV 不负责什么

| 不属于 PTV | 由谁负责 |
|---|---|
| 通勤时间计算（从家到公司要多久） | GoogleRoutesTool → TransportComposer |
| 步行距离内的咖啡馆、超市等生活设施 | GooglePlacesTool → AmenitiesComposer |
| 房产周边是否有学校 | SchoolAgent（data.vic.gov.au） |
| "这个区交通方便吗"的开放式主观判断 | Synthesis Agent（基于 TransportComposer 的结构化结果生成） |

### 1.3 用户视角的典型问题

PTV 数据最终回答以下用户关心的问题：

| 用户想知道 | PTV 提供的数据 |
|---|---|
| 最近的火车站在哪？多远？ | 周边站点列表 + 距离排序 |
| 这个区有电车吗？ | 按 route_type 分类（Train / Tram / Bus） |
| 高峰期班次多吗？ | 典型高峰时段 departure 频率 |
| 去 CBD 有直达线路吗？ | 途经线路列表 + 方向信息 |
| 周末/夜间有服务吗？ | 各线路的服务时段覆盖 |
| 这个站有停车位/无障碍设施吗？ | 站点设施信息（Metro/VLine 站） |

---

## 2. PTV API 概述

### 2.1 API 版本

使用 **PTV Timetable API v3**。

- **Base URL:** `https://timetableapi.ptv.vic.gov.au`
- **Swagger:** `https://timetableapi.ptv.vic.gov.au/swagger/docs/v3`
- **认证方式:** `devid` + HMAC-SHA1 `signature` 作为 query parameter
- **数据更新频率:** 火车每日更新，电车/公交每周更新
- **实时数据:** 大都市区火车、电车、公交提供实时 estimated departure

### 2.2 与本项目相关的 Endpoints

| Endpoint | 用途 | 本项目调用场景 |
|---|---|---|
| `GET /v3/route_types` | 获取 route_type 枚举（0=Train, 1=Tram, 2=Bus, 3=VLine, 4=NightBus） | 初始化时调用一次，缓存 |
| `GET /v3/stops/location/{latitude},{longitude}` | 查询某坐标周边的所有站点 | 每个 property 查询一次（核心） |
| `GET /v3/stops/{stop_id}/route_type/{route_type}` | 查询某个站点的设施和途经线路 | 获取最近 N 个站点的线路详情 |
| `GET /v3/departures/route_type/{route_type}/stop/{stop_id}` | 查询某站点某交通方式的发车时刻 | 获取典型通勤时段的发车频率 |
| `GET /v3/disruptions/route_type/{route_type}/stop/{stop_id}` | 查询影响某站点的服务中断 | 可选——实时提醒 |
| `GET /v3/search/{search_term}` | 搜索站点/线路名称 | 当用户提到具体站名或线路名时的解析 |

### 2.3 Endpoint 优先级分级

| 优先级 | Endpoint | 理由 |
|---|---|---|
| **P0 — 必须** | `stops/location` | 核心查询——周边有什么 |
| **P0 — 必须** | `stops/{id}/route_type/{type}` | 站点详情——经过哪些线路 |
| **P1 — 重要** | `departures/route_type/{type}/stop/{id}` | 班次频率——方不方便 |
| **P1 — 重要** | `route_types` | 枚举值映射 |
| **P2 — 增强** | `disruptions` | 实时服务中断提醒 |
| **P3 — 可选** | `search` | 站名/线路名解析 |

---

## 3. 数据模型

### 3.1 文件位置

PTV 内部数据模型定义在 `agent/tools/ptv/ptv_models.py`。遵循 backend coding-standards：

- 内部传递类型（不跨 HTTP）使用 `@dataclass(frozen=True)`
- 对外暴露的序列化 DTO（跨 Tool/Composer HTTP 边界）继承 `PropertyAIBaseModel`（来自 `models/base.py`），自动获得 camelCase alias

```python
# agent/tools/ptv/ptv_models.py
from dataclasses import dataclass
from enum import IntEnum

from models.base import PropertyAIBaseModel
```

### 3.2 Route Types（交通方式枚举）

```python
class EPTVRouteType(IntEnum):
    """PTV API v3 route_type values.

    IntEnum 而非 StrEnum——PTV API 使用整数 route_type。
    命名遵循 backend coding-standards：E 前缀 + PascalCase。
    """
    TRAIN = 0
    TRAM = 1
    BUS = 2
    VLINE = 3
    NIGHT_BUS = 4
```

### 3.3 Nearby Stop（单个周边站点）

```python
@dataclass(frozen=True)
class PTVNearbyStop:
    """A single PTV stop near the property, with distance and metadata.

    Note: walking_duration and walking_distance are NOT owned by PTV.
    They are computed by GoogleRoutesTool (walking directions) and merged
    into the final TransportAssessment by TransportComposer.
    """
    stop_id: str
    stop_name: str
    route_type: EPTVRouteType
    distance_metres: int               # 直线距离（来自 stops/location 返回的 stop_distance）
    suburb: str | None
```

### 3.4 Stop Routes（站点途经线路）

```python
@dataclass(frozen=True)
class PTVStopRoute:
    """A route that stops at a given PTV stop."""
    route_id: str
    route_name: str                    # e.g. "Belgrave", "Route 96"
    route_number: str | None           # e.g. "96" for trams
    route_type: EPTVRouteType
    direction_name: str | None         # e.g. "City (Flinders Street)"
```

### 3.5 Stop Detail（站点完整信息）

```python
@dataclass(frozen=True)
class PTVStopDetail:
    """Full stop detail including facilities and served routes."""
    stop_id: str
    stop_name: str
    route_type: EPTVRouteType
    routes: list[PTVStopRoute]
    has_parking: bool                  # 是否有停车换乘
    has_bike_rack: bool                # 是否有自行车架
    is_accessible: bool                # 无障碍通道（轮椅可达）
    has_toilet: bool | None
```

### 3.6 Departure Info（班次信息）

```python
@dataclass(frozen=True)
class PTDepartureInfo:
    """Scheduled or estimated departure from a stop."""
    route_id: str
    direction_id: int
    scheduled_departure_utc: str       # 时刻表发车时间
    estimated_departure_utc: str | None # 实时预估发车时间
    at_platform: bool | None           # 列车已到站
    platform_number: str | None        # 站台号
```

### 3.7 Stop Departure Summary（站点发车摘要）

```python
@dataclass(frozen=True)
class PTVStopDepartureSummary:
    """Aggregated departure frequency for a stop at a given time window."""
    stop_id: str
    route_type: EPTVRouteType
    peak_frequency_minutes: int | None    # 高峰期平均发车间隔（分钟）
    offpeak_frequency_minutes: int | None  # 非高峰期平均发车间隔（分钟）
    has_evening_service: bool              # 晚间（22:00后）是否有服务
    has_weekend_service: bool              # 周末是否有服务
    next_departure_minutes: int | None     # 下一班车还有几分钟
```

### 3.8 Disruption（服务中断）

```python
@dataclass(frozen=True)
class PTVDisruption:
    """A service disruption affecting a route or stop."""
    disruption_id: str
    title: str
    description: str
    affected_route_ids: list[str]
    affected_stop_ids: list[str]
    start_utc: str | None
    end_utc: str | None
    severity: str                       # "minor" | "major" | "planned"
```

### 3.9 Tool Result 输出模型

对外暴露的 DTO 继承 `PropertyAIBaseModel`，自动获得 camelCase 序列化：

```python
class PTVNearbyStopDTO(PropertyAIBaseModel):
    """Nearby stop serialised for API response / TransportComposer.

    Note: walking distance and walking time are NOT included here.
    They are computed by GoogleRoutesTool and merged into TransportAssessment
    by TransportComposer. PTV only provides straight-line distance (distance_metres)
    and stop-level metadata.
    """
    stop_id: str
    stop_name: str
    route_type: str                     # "train" | "tram" | "bus" | "vline" | "night_bus"
    distance_metres: int
    suburb: str | None
    routes_serving: list[str]           # 经过的线路名/号
    has_accessible_access: bool | None
    peak_frequency_minutes: int | None
    has_disruption: bool
    disruption_title: str | None


class PTVNearbyStopResult(PropertyAIBaseModel):
    """PTVNearbyStopsTool 的输出——房产周边公共交通覆盖。

    此对象序列化后存入 ToolResult.data。
    """
    property_lat: float
    property_lng: float
    nearby_stops: list[PTVNearbyStopDTO]

    # 按交通方式分组统计
    train_stops_nearby: int             # 1200m 内火车站数
    tram_stops_nearby: int              # 800m 内电车站数
    bus_stops_nearby: int               # 400m 内公交站数

    # 最近站点摘要（直线距离来自 PTV；步行距离/时间由 GoogleRoutes 提供）
    nearest_train_stop: PTVNearbyStopDTO | None
    nearest_train_distance_metres: int | None

    nearest_tram_stop: PTVNearbyStopDTO | None
    nearest_tram_distance_metres: int | None

    # 途经线路汇总
    train_lines: list[str]              # 经过附近火车站的所有火车线名称
    tram_routes: list[str]              # 经过附近电车站的所有电车线路号
    night_network_available: bool       # 是否有夜间公交/火车服务

    # 发车频率摘要
    peak_frequency_summary: str | None  # e.g. "高峰期 train ≤5min, tram ≤8min"
    offpeak_frequency_summary: str | None

    # 查询覆盖范围
    search_radius_metres: int           # 实际查询半径
    generated_at_utc: str
```

---

## 4. Atomic Tool 设计

### 4.1 设计原则回顾

来自 Agent Architecture PRD §9 和 Prototype PRD §4.2：

> - 一个 Tool ≈ 一个外部数据源下的一项完整查询能力
> - Tool 不调用 Tool
> - 统一接口：`build_params(context) → TToolParams` + `run_async(params) → ToolResult`
> - 所有 Tool 继承 `BaseTool[TToolParams]`（来自 `agent/tools/base.py`）
> - `run_async()` 是基类模板方法——子类不覆盖，只实现 `_execute_async()`

### 4.2 Tool 列表

| Tool | Endpoint(s) | 职责 | 优先级 |
|---|---|---|---|
| **PTVNearbyStopsTool** | `stops/location` | 查询房产周边 N 米内的所有 PT 站点 | P0 |
| **PTVStopDetailTool** | `stops/{id}/route_type/{type}` + `departures/...` | 批量获取最近站点的途经线路 + 发车频率 | P0 |
| **PTVDisruptionsTool** | `disruptions/route_type/{type}/stop/{id}` | 查询影响附近站点的服务中断 | P2 |

> **为什么不合并为一个 Tool？**
>
> PTVNearbyStopsTool 的输出（有哪些站）是 PTVStopDetailTool 的输入（查询这些站的详情）。但按架构规则 §9——Tool 不调用 Tool——这个串联由 Intent Handler（PropertyDetailHandler）编排，不在 Tool 内部完成。
>
> 如果合并成一个 "do everything" 的 PTV Tool，调用方无法选择只查询"附近有站没站"而不查询发车频率（例如 budget-only 查询场景）。

### 4.3 PTVNearbyStopsTool（P0）

```text
Tool: PTVNearbyStopsTool
─────────────────────────
基类:    BaseTool[NearbyStopsParams]  (agent/tools/base.py)
数据源:  PTV API v3 → /v3/stops/location/{lat},{lng}
Connector: PTVConnector (agent/connectors/ptv/ptv_connector.py)

类属性:
  name = "ptv_nearby_stops"
  description = "查询指定坐标周边的公共交通站点（火车、电车、公交、VLine、夜间巴士）"
  params_model = NearbyStopsParams

build_params(context: ExecutionContext) → NearbyStopsParams:
  从 ExecutionContext 提取:
    - lat, lng              ← context.property_lat / property_lng (由 ContextResolver geocode)
    - max_distance_metres    ← 默认 1000m (train/tram), 实际按 route_type 分层
    - route_types            ← [0,1,2,3,4] 全部，可配置

_execute_async(params: NearbyStopsParams) → dict[str, object]:
  1. 调用 connector.get_stops_near_location_async()，按 route_type 分层查询
     - Train:  半径 1200m（火车站覆盖范围大）
     - Tram:   半径 800m
     - Bus:    半径 400m（公交站密集，太远无意义）
  2. 合并去重（一个物理站点可能出现在多个 route_type 中）
  3. 按距离排序，分类统计
  4. 标记 nearest_train / nearest_tram / nearest_bus
  5. 返回 PTVNearbyStopResult.model_dump()

输出: dict (PTVNearbyStopResult 序列化) → 被 run_async() 包装进 ToolResult.data

执行时间上限: 3s
```

#### 搜索半径策略

| route_type | 搜索半径 | 理由 |
|---|---|---|
| Train (0) | 1200m | 火车站通常步行 15 分钟可达，覆盖范围较广 |
| Tram (1) | 800m | 电车站间距约 250-400m，800m 内至少有 2-3 个站 |
| Bus (2) | 400m | 公交站密，400m 外步行体验显著下降 |
| VLine (3) | 2000m | 区域火车覆盖整个 suburb 级别 |
| Night Bus (4) | 400m | 同公交 |

> **注意:** 这些半径是 PTV API 的查询半径，不是最终"步行可达"判断。步行距离和步行时间由 GoogleRoutesTool 精确计算。

#### 完整实现示例

```python
# agent/tools/ptv/ptv_nearby_stops_tool.py
from pydantic import BaseModel, Field

from agent.shared.context import ExecutionContext
from agent.tools.base import BaseTool
from agent.connectors.ptv.ptv_connector import PTVConnector
from agent.tools.ptv.ptv_models import EPTVRouteType, PTVNearbyStopResult, PTVNearbyStopDTO


class NearbyStopsParams(BaseModel):
    """PTVNearbyStopsTool 的输入参数（Pydantic model——自动生成 JSON Schema）。"""
    lat: float
    lng: float
    train_radius_m: int = Field(default=1200)
    tram_radius_m: int = Field(default=800)
    bus_radius_m: int = Field(default=400)
    vline_radius_m: int = Field(default=2000)
    night_bus_radius_m: int = Field(default=400)


class PTVNearbyStopsTool(BaseTool[NearbyStopsParams]):
    """查询指定坐标周边的公共交通站点。"""

    name: str = "ptv_nearby_stops"
    description: str = "查询指定坐标周边的公共交通站点（火车、电车、公交、VLine、夜间巴士）"
    params_model: type[NearbyStopsParams] = NearbyStopsParams

    def __init__(self, connector: PTVConnector) -> None:
        self._connector: PTVConnector = connector

    def build_params(self, context: ExecutionContext) -> NearbyStopsParams:
        """从 ExecutionContext 提取坐标和搜索半径。

        纯函数——不做 I/O。
        如果坐标缺失（geocode 失败），返回的 params 中 lat/lng 为 0.0，
        由 Handler 在调用前检查并跳过执行。
        """
        return NearbyStopsParams(
            lat=context.property_lat or 0.0,
            lng=context.property_lng or 0.0,
        )

    async def _execute_async(self, params: NearbyStopsParams) -> dict[str, object]:
        """调 PTVConnector → 按 route_type 分层查询 → 解析 → 返回 dict。

        返回的 dict 由 BaseTool.run_async() 自动包装进 ToolResult.data。
        """
        all_stops: list[PTVNearbyStopDTO] = []

        # 按 route_type 分层查询，各自使用不同的半径
        route_configs: list[tuple[EPTVRouteType, int]] = [
            (EPTVRouteType.TRAIN, params.train_radius_m),
            (EPTVRouteType.TRAM, params.tram_radius_m),
            (EPTVRouteType.BUS, params.bus_radius_m),
            (EPTVRouteType.VLINE, params.vline_radius_m),
            (EPTVRouteType.NIGHT_BUS, params.night_bus_radius_m),
        ]

        for route_type, radius in route_configs:
            raw_stops: list[dict[str, object]] = (
                await self._connector.get_stops_near_location_async(
                    lat=params.lat,
                    lng=params.lng,
                    route_types=[route_type.value],
                    max_distance=radius,
                )
            )
            for raw in raw_stops:
                dto: PTVNearbyStopDTO = self._parse_stop(raw, route_type, radius)
                all_stops.append(dto)

        # 去重（同一个物理 stop_id 可能出现在多个 route_type 中）
        seen: set[str] = set()
        unique_stops: list[PTVNearbyStopDTO] = []
        for stop in sorted(all_stops, key=lambda s: s.distance_metres):
            if stop.stop_id not in seen:
                seen.add(stop.stop_id)
                unique_stops.append(stop)

        result: PTVNearbyStopResult = self._build_result(
            lat=params.lat, lng=params.lng, stops=unique_stops
        )
        return result.model_dump()

    def _parse_stop(
        self, raw: dict[str, object], route_type: EPTVRouteType, radius: int
    ) -> PTVNearbyStopDTO:
        """将 PTV API 原始响应解析为 DTO。"""
        distance: float = float(raw.get("stop_distance", 0))
        if distance > radius:
            distance = radius  # 超出搜索半径的截断
        return PTVNearbyStopDTO(
            stop_id=str(raw["stop_id"]),
            stop_name=str(raw.get("stop_name", "")),
            route_type=route_type.name.lower(),
            distance_metres=int(distance),
            suburb=raw.get("stop_suburb"),
            routes_serving=[],
            has_accessible_access=None,
            peak_frequency_minutes=None,
            has_disruption=False,
            disruption_title=None,
        )

    def _build_result(
        self, lat: float, lng: float, stops: list[PTVNearbyStopDTO]
    ) -> PTVNearbyStopResult:
        """组装最终 PTVNearbyStopResult，包括分类统计。"""
        train_stops: list[PTVNearbyStopDTO] = [
            s for s in stops if s.route_type == "train"
        ]
        tram_stops: list[PTVNearbyStopDTO] = [
            s for s in stops if s.route_type == "tram"
        ]
        bus_stops: list[PTVNearbyStopDTO] = [
            s for s in stops if s.route_type == "bus"
        ]

        return PTVNearbyStopResult(
            property_lat=lat,
            property_lng=lng,
            nearby_stops=stops,
            train_stops_nearby=len(train_stops),
            tram_stops_nearby=len(tram_stops),
            bus_stops_nearby=len(bus_stops),
            nearest_train_stop=train_stops[0] if train_stops else None,
            nearest_train_distance_metres=train_stops[0].distance_metres if train_stops else None,
            nearest_tram_stop=tram_stops[0] if tram_stops else None,
            nearest_tram_distance_metres=tram_stops[0].distance_metres if tram_stops else None,
            train_lines=[],
            tram_routes=[],
            night_network_available=False,
            peak_frequency_summary=None,
            offpeak_frequency_summary=None,
            search_radius_metres=1200,
            generated_at_utc="",
        )
```

### 4.4 PTVStopDetailTool（P1）

```text
Tool: PTVStopDetailTool
─────────────────────────
基类:    BaseTool[StopDetailParams]
数据源:
  - PTV API v3 → /v3/stops/{stop_id}/route_type/{route_type}
  - PTV API v3 → /v3/departures/route_type/{route_type}/stop/{stop_id}

输入:
  - stop_ids: list[tuple[str, EPTVRouteType]]  ← 从 PTVNearbyStopsTool 输出中提取
  - top_n: int                                  ← 只查询距离最近的 top_n 个站（默认 6）

处理逻辑:
  1. 取距离最近的 top_n 个站（按 PTVNearbyStopsTool 输出的距离排序）
  2. 对每个站并行调用:
     a. stops/{id}/route_type/{type} → 途经线路 + 设施信息
     b. departures/... → 提取发车频率
  3. 计算频率摘要:
     - 取 weekday 7:00-9:00（早高峰）的 departure 间隔，取中位数
     - 取 weekday 10:00-15:00（非高峰）的 departure 间隔，取中位数
     - 检查 22:00 后是否有 service
     - 检查 Saturday/Sunday 是否有 service
  4. 汇总 train_lines / tram_routes 列表（去重）

输出: 合并回 PTVNearbyStopResult 的 routes_serving & frequency 字段
      或者作为独立 ToolResult 供 TransportComposer 消费

执行时间上限: 4s（并行 6 个 stop 查询）
```

#### 发车频率分级

| 等级 | 高峰期发车间隔 | 说明 |
|---|---|---|
| Excellent | ≤ 5 min | 典型 Metro 火车频率 |
| Good | 5–10 min | 主要电车/公交线路 |
| Fair | 10–20 min | 普通公交 |
| Poor | > 20 min | 低密度区域 |
| Unknown | 无数据 | API 不返回时刻表或站点无服务 |

### 4.5 PTVDisruptionsTool（P2）

```text
Tool: PTVDisruptionsTool
─────────────────────────
基类:    BaseTool[DisruptionsParams]
数据源:  PTV API v3 → /v3/disruptions/route_type/{route_type}/stop/{stop_id}

输入:
  - stop_ids: list[tuple[str, EPTVRouteType]]  ← 附近站点列表
  - route_ids: list[str]                        ← 途经线路列表

处理逻辑:
  1. 批量查询附近站点 + 途经线路的 active 中断
  2. 按 severity 分级: minor（提醒） / major（避开） / planned（计划施工）
  3. 只保留影响当前通勤的（例如不是 3 周后的 planned 施工）

输出:
  - has_active_disruption: bool
  - disruption_summary: str | None     # e.g. "Belgrave Line: buses replacing trains, +15min"
  - affected_routes: list[str]

执行时间上限: 2s
```

---

## 5. Connector 设计

### 5.1 PTVConnector

PTVConnector 继承 `BaseConnector`（来自 `agent/connectors/base.py`），遵循 Prototype PRD §4.1 定义的契约：

- 覆盖 `_build_auth_async(request: httpx.Request) → httpx.Request` — 修改 `request.url` 追加 `devid` + HMAC-SHA1 `signature` query params
- 覆盖 `_map_error(status_code: int, response_body: str) → str` — 将 HTTP 状态码映射为 domain error_code（如 `"PTV_RATE_LIMITED"`）
- 暴露领域方法（如 `get_stops_near_location_async`），内部调用 `self._request_async()`

```python
# agent/connectors/ptv/ptv_connector.py
import hashlib
import hmac
import urllib.parse

import httpx

from agent.connectors.base import BaseConnector, ConnectorConfig


class PTVConnector(BaseConnector):
    """Encapsulates all PTV API v3 HTTP communication.

    继承 BaseConnector 的:
      - 延迟初始化 httpx.AsyncClient (_get_client_async)
      - 重试 + 错误映射 (_request_async)
      - 生命周期管理 (close_async)

    子类只需覆盖认证和错误码翻译两个方法。
    """

    def __init__(self, config: ConnectorConfig, devid: str, api_key: str) -> None:
        super().__init__(config)
        self._devid: str = devid
        self._api_key: str = api_key

    # ── BaseConnector 契约实现 ──────────────────────────────────────────

    async def _build_auth_async(self, request: httpx.Request) -> httpx.Request:
        """HMAC-SHA1 签名——修改 request.url 追加 devid + signature。

        设计决策 (Prototype PRD D4):
          单一 _build_auth_async(request) → request 钩子，
          而非分离的 _build_headers / _build_query_params。
          PTV 的签名需要 path + 排序后 params 计算 HMAC，
          且签名字段本身也是 query param——一个方法内聚所有逻辑。
        """
        params: dict[str, str] = dict(request.url.params)
        params["devid"] = self._devid

        # PTV 要求 key 排序
        sorted_params: list[tuple[str, str]] = sorted(params.items())
        query_string: str = urllib.parse.urlencode(sorted_params)
        message: str = f"{request.url.path}?{query_string}"

        signature: str = hmac.new(
            self._api_key.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha1,
        ).hexdigest().upper()

        # copy_merge_params 返回新 URL，签名追加在已有 params 之后
        request.url = request.url.copy_merge_params({"signature": signature})
        return request

    def _map_error(self, status_code: int, response_body: str) -> str:
        """将 HTTP 错误响应映射为 PTV 域错误码。

        设计决策 (Prototype PRD D5):
          _map_error 返回字符串，基类 _request_async 负责包装为 ConnectorHttpError 抛出。
          错误码是 ToolResult 的数据字段，不是类型——上层只需看 ToolResult.success。
        """
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

    # ── 领域方法 ────────────────────────────────────────────────────────

    async def get_route_types_async(self) -> list[dict[str, object]]:
        """获取所有 route_type 枚举。启动时调用一次，结果缓存。"""
        result: dict[str, object] = await self._request_async("GET", "/v3/route_types")
        return result.get("route_types", [])  # type: ignore[return-value]

    async def get_stops_near_location_async(
        self,
        lat: float,
        lng: float,
        route_types: list[int] | None = None,
        max_distance: int = 1200,
    ) -> list[dict[str, object]]:
        """查询指定坐标周边的公共交通站点。

        对应 PTV API: GET /v3/stops/location/{lat},{lng}
        """
        params: dict[str, str] = {
            "max_distance": str(max_distance),
        }
        if route_types:
            params["route_types"] = ",".join(str(r) for r in route_types)

        result: dict[str, object] = await self._request_async(
            "GET",
            f"/v3/stops/location/{lat},{lng}",
            params=params,
        )
        return result.get("stops", [])  # type: ignore[return-value]

    async def get_stop_detail_async(
        self, stop_id: str, route_type: int
    ) -> dict[str, object]:
        """查询某个站点的设施和途经线路。

        对应 PTV API: GET /v3/stops/{stop_id}/route_type/{route_type}
        """
        result: dict[str, object] = await self._request_async(
            "GET",
            f"/v3/stops/{stop_id}/route_type/{route_type}",
        )
        return result

    async def get_departures_async(
        self,
        stop_id: str,
        route_type: int,
        date_utc: str | None = None,
        max_results: int = 10,
    ) -> list[dict[str, object]]:
        """查询某站点某交通方式的发车时刻。

        对应 PTV API: GET /v3/departures/route_type/{route_type}/stop/{stop_id}
        """
        params: dict[str, str] = {"max_results": str(max_results)}
        if date_utc:
            params["date_utc"] = date_utc

        result: dict[str, object] = await self._request_async(
            "GET",
            f"/v3/departures/route_type/{route_type}/stop/{stop_id}",
            params=params,
        )
        return result.get("departures", [])  # type: ignore[return-value]

    async def get_disruptions_for_stop_async(
        self, stop_id: str, route_type: int
    ) -> list[dict[str, object]]:
        """查询影响某站点的服务中断。

        对应 PTV API: GET /v3/disruptions/route_type/{route_type}/stop/{stop_id}
        """
        result: dict[str, object] = await self._request_async(
            "GET",
            f"/v3/disruptions/route_type/{route_type}/stop/{stop_id}",
        )
        disruptions: dict[str, object] = result.get("disruptions", {})
        return disruptions.get("metro_train", [])  # type: ignore[return-value]

    async def search_async(self, term: str) -> list[dict[str, object]]:
        """搜索站点/线路名称。

        对应 PTV API: GET /v3/search/{search_term}
        """
        result: dict[str, object] = await self._request_async(
            "GET",
            f"/v3/search/{urllib.parse.quote(term)}",
        )
        return result.get("stops", [])  # type: ignore[return-value]
```

### 5.2 HMAC 签名认证

HMAC-SHA1 签名由 `_build_auth_async` 内部实现，调用方无需感知。签名算法参考 PTV 官方文档：

> `Signature = uppercase(hex(HMAC-SHA1(api_key, path + "?" + sorted_query_string_with_devid)))`

关键细节：
- Query params 按 key 字母序排序后编码
- 签名计算的消息是 `path?sorted_query_string`（不含 signature 参数本身）
- 签名结果取大写 hex digest
- 最终追加 `&signature={digest}` 到 URL

### 5.3 Error Mapping

| PTV API Response | `ToolResult.error_code` | 处理 |
|---|---|---|
| 200 + valid JSON | — (success) | 正常 |
| 400 Bad Request | `PTV_BAD_REQUEST` | 参数错误——不重试，记录日志 |
| 403 Forbidden | `PTV_AUTH_FAILED` | devid 或 api_key 无效——告警 |
| 429 Too Many Requests | `PTV_RATE_LIMITED` | 指数退避 1s→2s→放弃 |
| 5xx Server Error | `PTV_UPSTREAM_ERROR` | 重试 2 次（间隔 1s，由 BaseConnector._request_async 处理） |
| Timeout (> 5s) | `{NAME}_TIMEOUT` | 重试 max_retries 次后抛 ConnectorTimeoutError，BaseTool.run_async() 自动映射 |
| Connection Error | 由 httpx 抛出，BaseConnector 不专门捕获 | 不重试——标记 fallback |

### 5.4 Rate Limiting

PTV API 的默认 rate limit 为 **每分钟 1000 次调用**（免费 tier）。每个 property detail 查询预计产生 8-15 次 API 调用（取决于附近站点数量）。

| 场景 | 估算调用次数 | 压力 |
|---|---|---|
| 1 个 property detail | ~10 次 | 极小 |
| 10 个并发用户同时看房产 | ~100 次 | 正常 |
| 100 个并发用户 | ~1000 次 | 接近上限 |

**缓解策略:**
- P0 缓存: `stops/location` 结果对同一坐标 24h 有效
- P1 缓存: `departures` 结果对同一 weekday+hour 窗口 1h 有效
- `route_types` 在应用启动时获取一次并缓存

---

## 6. TransportComposer 设计

### 6.1 职责

TransportComposer 是 Data Summary Layer 的一部分（Agent Architecture PRD §11）。它消费 PTV 和 Google Routes 的 ToolResult，产出结构化的交通评估结果——不调用外部 API，不包含 LLM。

```text
PTVNearbyStopsTool result  ─┐
PTVStopDetailTool result   ─┤
GoogleRoutesTool result    ─┼──► TransportComposer ──► TransportAssessment
User commute limit         ─┘    (纯数据组合)
```

### 6.2 文件位置

```
agent/composers/transport_composer.py   # TransportComposer + TransportAssessment 数据模型
```

### 6.3 输入

| 输入 | 来源 | 是否必需 |
|---|---|---|
| `PTVNearbyStopResult` | PTVNearbyStopsTool + PTVStopDetailTool | 是 |
| `GoogleRoutesResult` | GoogleRoutesTool（通勤路线 + 耗时） | 是（有 commute_destination 时） |
| `commute_destination` | user_needs.M3.commute_destination | 否 |
| `commute_max_mins` | user_needs.M3.commute_max_mins | 否 |
| `commute_mode` | user_needs.M3.commute_mode | 否（默认 any） |

### 6.4 输出: TransportAssessment

```python
# agent/composers/transport_composer.py
from dataclasses import dataclass, field

from agent.tools.ptv.ptv_models import PTVDisruption


@dataclass(frozen=True)
class TransportAssessment:
    """TransportComposer 的确定性输出——不包含自然语言。

    此 dataclass 不跨 HTTP；序列化到 ToolResult.data / Postgres JSONB
    时通过 dataclasses.asdict() 转换。
    """
    # 公共交通覆盖
    nearby_transport: TransportCoverage
    # 通勤评估（仅当用户有通勤目的地时）
    commute: CommuteAssessment | None
    # 综合评分（供前端雷达图 / 筛选排序）
    accessibility_score: AccessibilityScore
    # 数据可用性标记
    partial: bool                       # 是否有 Tool 失败导致部分数据缺失
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TransportCoverage:
    """Property transit coverage summary."""
    has_train: bool
    has_tram: bool
    has_bus: bool
    has_night_service: bool

    nearest_train_name: str | None
    nearest_train_distance_metres: int | None       # PTV 直线距离
    nearest_train_walking_minutes: int | None       # Google Routes 填充

    nearest_tram_name: str | None
    nearest_tram_distance_metres: int | None        # PTV 直线距离
    nearest_tram_walking_minutes: int | None        # Google Routes 填充

    train_lines: list[str]              # 途经火车线
    tram_routes: list[str]              # 途经电车线

    peak_frequency_train_minutes: int | None
    peak_frequency_tram_minutes: int | None
    peak_frequency_bus_minutes: int | None

    active_disruptions: list[PTVDisruption] = field(default_factory=list)


@dataclass(frozen=True)
class CommuteAssessment:
    """通勤评估——由 GoogleRoutes result + user commute limit 共同决定。"""
    destination: str
    best_mode: str                      # "train" | "tram" | "bus" | "mixed"
    total_duration_minutes: int
    walking_to_stop_minutes: int
    waiting_time_estimate_minutes: int
    in_vehicle_minutes: int
    transfers: int                      # 换乘次数

    within_commute_limit: bool          # 是否在用户接受范围内
    exceeds_limit_by_minutes: int | None

    is_direct_route: bool               # 是否有直达（无换乘）


@dataclass(frozen=True)
class AccessibilityScore:
    """0-100 综合评分，供前端可视化和多房产排序比较。

    评分维度:
      - proximity:    最近站点距离 (0-40 分)
      - frequency:    高峰期发车频率 (0-30 分)
      - coverage:     交通方式多样性 (0-20 分)
      - night/weekend:夜间/周末服务 (0-10 分)
    """
    overall: int                        # 0-100
    proximity: int                      # 0-40
    frequency: int                      # 0-30
    coverage: int                       # 0-20
    night_weekend: int                  # 0-10
    score_label: str                    # "Excellent" | "Good" | "Fair" | "Limited" | "Poor"
```

> **为什么不包含 commute 在 accessibility_score 里？**
>
> accessibility_score 衡量的是房产本身的 PT 资源禀赋（不依赖用户个人情况）。
> commute 是否达标是与用户个人需求相关的——两个用户看同一套房，一个在 CBD 上班（满意），一个在远郊上班（不满意）。这两层逻辑分开。

### 6.5 评分规则

#### Proximity 评分（0–40 分）

以**最近火车站的步行时间**为主要指标（火车站对房价影响最大），fallback 到最近电车站或公交站。

| 最近火车站步行时间 | 得分 |
|---|---|
| ≤ 5 min (≤ 400m) | 40 |
| 6–10 min (400–800m) | 32 |
| 11–15 min (800–1200m) | 20 |
| 16–20 min (1200–1600m) | 10 |
| > 20 min (> 1600m) | 0 |
| 无火车站，有电车站 ≤ 800m | 24 |
| 无火车/电车，仅公交 | 12 |

#### Frequency 评分（0–30 分）

以**高峰期主要交通方式的发车频率**计算：

| 高峰期发车间隔 | 得分 |
|---|---|
| ≤ 3 min | 30 |
| 4–5 min | 25 |
| 6–10 min | 18 |
| 11–15 min | 10 |
| 16–20 min | 5 |
| > 20 min 或无数据 | 0 |

#### Coverage 评分（0–20 分）

| 交通方式覆盖 | 得分 |
|---|---|
| Train + Tram + Bus 均覆盖 | 20 |
| Train + Bus（无 Tram） | 16 |
| Tram + Bus（无 Train） | 12 |
| Train only | 10 |
| Tram only | 8 |
| Bus only | 4 |

#### Night/Weekend 评分（0–10 分）

| 夜间/周末服务 | 得分 |
|---|---|
| 周末白天 + 夜间服务 | 10 |
| 仅周末白天有服务 | 6 |
| 仅工作日白天有服务 | 2 |
| 无可判断数据 | 0 |

#### Score Label 映射

| 总分 | Label |
|---|---|
| 85–100 | Excellent |
| 65–84 | Good |
| 45–64 | Fair |
| 20–44 | Limited |
| 0–19 | Poor |

---

## 7. Intent Handler 中的 PTV 编排

### 7.1 PropertyDetailHandler

PropertyDetailHandler 实现 `IntentHandler` Protocol（来自 `agent/orchestration/handlers/base.py`）：

```python
# agent/orchestration/handlers/property_detail_handler.py
from agent.orchestration.handlers.base import IntentHandler
from agent.shared.context import ExecutionContext
from models.shared.enums import EUserIntent


class PropertyDetailHandler:
    """PROPERTY_DETAIL intent 的确定性执行计划。

    实现 IntentHandler Protocol（structural subtyping——无需显式继承）。
    """

    @property
    def intent(self) -> EUserIntent:
        return EUserIntent.PROPERTY_DETAIL

    async def execute_async(self, context: ExecutionContext) -> object:
        """编排 PTV + Domain + GoogleRoutes + Vicmap + GooglePlaces 的并行执行。"""
        ...
```

来自 Agent Architecture PRD §8 的编排树：

```text
PropertyDetailHandler.execute_async(context)
├── DomainPropertyDetailTool        ← 并行
├── DomainMarketStatisticsTool     ← 并行
├── PTVNearbyStopsTool             ← 并行 ─┐
├── PTVStopDetailTool              ← 依赖 PTVNearbyStopsTool（顺序）
├── GoogleRoutesTool               ← 并行
├── VicmapPlanningTool             ← 并行
└── GooglePlacesTool               ← 并行
```

**PTV 内部执行顺序:**

```text
1. PTVNearbyStopsTool (可与其他 Tool 并行——仅依赖 geocoded lat/lng)
     ↓
2. PTVStopDetailTool (依赖 PTVNearbyStopsTool 返回的 top_n stop_ids)
   → 但与 DomainPropertyDetailTool / GooglePlacesTool 等无依赖关系，可提前启动
     ↓
3. TransportComposer (依赖 PTV 两个 Tool + GoogleRoutesTool 全部完成)
```

### 7.2 Handler 中的 Tool 调用模式

遵循 Prototype PRD §4.2.1 的两步调用模式——`build_params()` 与 `run_async()` 分离：

```python
# PropertyDetailHandler.execute_async() 内部（伪代码）

# Step 1: build_params — 纯函数，无 I/O
ptv_params: NearbyStopsParams = ptv_nearby_stops_tool.build_params(context)

# Step 2: 检查前置条件——如果坐标缺失，跳过 PTV
if ptv_params.lat == 0.0 and ptv_params.lng == 0.0:
    ptv_result: ToolResult = ToolResult(
        success=False,
        error_code="PTV_SKIPPED_NO_COORDINATES",
        error_message="Cannot query PTV — property not geocoded",
        source="ptv_nearby_stops",
        execution_time_ms=0,
    )
else:
    ptv_result = await ptv_nearby_stops_tool.run_async(ptv_params)
```

### 7.3 最小可并行化策略

```
Phase 1 (全部并行启动):
  ├── DomainPropertyDetailTool
  ├── DomainMarketStatisticsTool
  ├── PTVNearbyStopsTool          ← 最快 1-2 秒
  ├── GoogleRoutesTool
  ├── VicmapPlanningTool
  └── GooglePlacesTool

Phase 2 (Phase 1 各自完成后立即启动):
  └── PTVStopDetailTool           ← 仅依赖 PTVNearbyStopsTool，不需等 Phase 1 全部完成

Phase 3 (全部 Tool 完成后):
  ├── PriceComposer
  ├── TransportComposer
  ├── PlanningComposer
  └── AmenitiesComposer
```

这样 PTVStopDetailTool 不需要等待其他 Tool（Domain、Vicmap 等），最大化利用率。

---

## 8. 错误处理与降级策略

### 8.1 降级矩阵

Property Detail 场景使用 **Graceful Degradation**（Agent Architecture §14）：

| 失败组件 | 处理方式 | 用户感知 |
|---|---|---|
| PTV API 完全不可达 | `ToolResult(success=False, fallback=True)` | TransportComposer 返回 `partial=True`，Transport 部分显示 "Public transport data unavailable" |
| `stops/location` 成功但 `departures` 超时 | 保留站点列表，频率字段标记为 `None` | Transport coverage 显示站点，但不显示班次频率 |
| 单个 stop 的 detail 查询失败 | 跳过该 stop，继续汇总其余 | 微小的信息缺失，用户不可感知 |
| `disruptions` 查询失败 | 不发起该查询，标记 `active_disruptions=[]` | 无影响（此功能 P2） |
| GoogleRoutesTool 也失败 | TransportComposer 仅输出 coverage，不输出 commute | Commute section 显示 "Commute time unavailable" |
| 所有 Transport Tool 均失败 | `TransportComposer` 返回空的 `TransportAssessment` + warnings | 报告中 Transport 段落不渲染 |

### 8.2 Error 转换链路

遵循 Prototype PRD 的三层错误转换：

```
PTV API HTTP Error
    ↓
BaseConnector._map_error() → "PTV_RATE_LIMITED" (str)
    ↓
BaseConnector._request_async() → 包装为 ConnectorHttpError(error_code="PTV_RATE_LIMITED")
    ↓
BaseTool.run_async() 模板方法 → ToolResult(success=False, error_code="PTV_RATE_LIMITED")
    ↓
PropertyDetailHandler → 根据 Failure Policy 决定降级 vs 失败
```

### 8.3 Failure Policy

| 场景 | Policy |
|---|---|
| PTV API 全挂 | Graceful — 其他 Agent 结果不受影响 |
| PTV rate limit 触发 | 退避 → 降级（使用缓存或跳过） |
| 地址无法 geocode | 阻断全部——不启动任何 Agent（见 PRD v1.1 §4.5） |

---

## 9. 缓存策略

### 9.1 PTV 数据的特性

| 数据 | 变化频率 | 缓存价值 |
|---|---|---|
| Route types 枚举 | 年级别 | 极高——启动时加载一次 |
| 周边站点列表（stops/location） | 月级别（站址基本不变） | 高——同坐标 24h 缓存 |
| 途经线路（routes at stop） | 月级别 | 高——同日查询可直接复用 |
| 发车时刻表（departures） | 日级别（时刻表按 term/semester 更新） | 中——同一 weekday+时段 1h 内复用 |
| 实时 departure estimate | 秒级别 | 低——不缓存，每次都查 |
| 服务中断（disruptions） | 分钟-小时级别 | 中——5 分钟 TTL |

### 9.2 Redis Key Schema

```text
# Route types (startup — in-memory cache, not Redis)
ptv:route_types                            → JSON (应用启动时加载，内存常驻)

# Stops near location (24h TTL — 站址几乎不变)
ptv:stops:{lat_3dp}:{lng_3dp}:{radius}     → JSON

# Stop detail: routes serving a stop (24h TTL)
ptv:stop_detail:{stop_id}:{route_type}      → JSON

# Departure frequency summary (1h TTL — 同一时段复用)
ptv:freq:{stop_id}:{route_type}:{weekday}:{hour}  → JSON

# Disruptions (5min TTL)
ptv:disruptions:{stop_id}:{route_type}      → JSON
```

> **坐标精度取 3 位小数**（~111m 网格），避免同一栋楼的不同 geocode 结果产生不同缓存 key。

---

## 10. SSE 事件与进度预览

来自 Agent Architecture PRD §15 的 SSE 事件流。事件类型枚举定义在 `agent/shared/events.py`（`EExecutionEvent`）：

| SSE Event (`EExecutionEvent`) | 对应阶段 | 用户可见文案 |
|---|---|---|
| `TOOL_STARTED` | PTVNearbyStopsTool 启动 | `⏳ 正在查询周边公共交通...` |
| `TOOL_COMPLETED` | PTVNearbyStopsTool 完成 | `✓ 已获取附近公共交通站点` |
| `TOOL_STARTED` | PTVStopDetailTool 启动 | `⏳ 正在分析途经线路与班次...` |
| `TOOL_COMPLETED` | PTVStopDetailTool 完成 | `✓ 已分析公共交通线路与频率` |
| `TOOL_FAILED` | 任何 PTV Tool 失败 | `⚠ 公共交通数据暂时不可用` |
| `SUMMARY_STARTED` | TransportComposer 启动 | `⏳ 正在整合交通评估...` |
| `SUMMARY_COMPLETED` | TransportComposer 完成 | `✓ 交通便利度评估完成` |

---

## 11. 配置

### 11.1 环境变量

```bash
# backend/.env
PTV_API_DEVID=3001234
PTV_API_KEY=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
PTV_API_BASE_URL=https://timetableapi.ptv.vic.gov.au
PTV_API_TIMEOUT_SECS=5
PTV_API_MAX_RETRIES=2
PTV_NEARBY_TRAIN_RADIUS_M=1200
PTV_NEARBY_TRAM_RADIUS_M=800
PTV_NEARBY_BUS_RADIUS_M=400
```

### 11.2 Settings 扩展

遵循 backend coding-standards：所有配置集中在 `backend/config.py` 的 `Settings` pydantic-settings 类中。不调用 `os.getenv`。

```python
# backend/config.py — 追加以下字段
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ... existing fields ...

    # ── PTV API ───────────────────────────────────────────────────────
    ptv_api_devid: str = ""
    ptv_api_key: str = ""
    ptv_api_base_url: str = "https://timetableapi.ptv.vic.gov.au"
    ptv_api_timeout_secs: float = 5.0
    ptv_api_max_retries: int = 2
    ptv_nearby_train_radius_m: int = 1200
    ptv_nearby_tram_radius_m: int = 800
    ptv_nearby_bus_radius_m: int = 400

    class Config:
        env_file = ".env"
```

---

## 12. 文件结构

```text
backend/
├── agent/
│   ├── shared/
│   │   ├── context.py                     # ExecutionContext (Layer 0)
│   │   └── events.py                      # EExecutionEvent (Layer 0)
│   │
│   ├── tools/
│   │   ├── base.py                        # BaseTool[TToolParams] (Layer 1)
│   │   ├── result.py                      # ToolResult (Layer 0)
│   │   └── ptv/
│   │       ├── __init__.py
│   │       ├── ptv_models.py              # EPTVRouteType, PTVNearbyStop, PTVStopDetail, etc. (§3)
│   │       ├── ptv_nearby_stops_tool.py   # PTVNearbyStopsTool (P0)
│   │       ├── ptv_stop_detail_tool.py    # PTVStopDetailTool (P1)
│   │       └── ptv_disruptions_tool.py    # PTVDisruptionsTool (P2)
│   │
│   ├── connectors/
│   │   ├── base.py                        # BaseConnector + ConnectorConfig + ConnectorError (L0+L1)
│   │   └── ptv/
│   │       ├── __init__.py
│   │       └── ptv_connector.py           # PTVConnector — HMAC-SHA1 + HTTP + retry (§5)
│   │
│   ├── composers/
│   │   └── transport_composer.py          # TransportComposer + TransportAssessment (§6)
│   │
│   ├── tool_registry/
│   │   └── registry.py                    # IToolRegistry + ToolRegistry (Layer 2)
│   │
│   └── orchestration/
│       ├── orchestrator.py                # Orchestrator — Part 2 入口 (Layer 3)
│       ├── context_resolver.py            # ContextResolver — RoutingPayload → ExecutionContext
│       ├── executors/
│       │   ├── base.py                    # IExecutor Protocol
│       │   ├── code_driven_executor.py    # Intent → IntentHandler → Result
│       │   └── llm_driven_executor.py     # LLM + Tool calling loop
│       └── handlers/
│           ├── base.py                    # IntentHandler[TIntentResult] Protocol
│           ├── property_detail_handler.py # PropertyDetailHandler — PTV 编排 (§7)
│           ├── recommend_suburbs_handler.py
│           └── list_properties_handler.py
│
├── routers/
│   └── agent_ptv.py                       # PTV Agent Test Endpoints (§18) — Swagger 可调测
│
└── tests/
    ├── test_tool_result.py
    ├── test_execution_context.py
    ├── test_execution_events.py
    ├── test_connector.py
    ├── test_tool.py
    ├── test_tool_registry.py
    ├── test_code_driven_executor.py
    ├── test_llm_driven_executor.py
    ├── test_context_resolver.py
    ├── test_orchestrator.py
    ├── test_execution_response.py
    └── ptv/
        ├── test_ptv_models.py             # PTV 数据模型单元测试
        ├── test_ptv_connector.py          # PTVConnector 单元测试
        ├── test_ptv_nearby_stops_tool.py  # PTVNearbyStopsTool 单元测试
        ├── test_ptv_stop_detail_tool.py   # PTVStopDetailTool 单元测试
        ├── test_ptv_disruptions_tool.py   # PTVDisruptionsTool 单元测试
        ├── test_transport_composer.py     # TransportComposer 全场景测试
        ├── test_property_detail_handler.py # PropertyDetailHandler PTV 编排集成测试
        ├── test_agent_ptv_endpoints.py    # Agent PTV Endpoints 测试
        └── test_transport_persistence.py  # Postgres 持久化测试 (Subtask 7)
```

> **与 Prototype PRD v0.1 的差异：**
> - `agent/tool/` → `agent/tools/`（重命名为复数，与 Prototype PRD §2.1 对齐）
> - `agent/connector/` → `agent/connectors/`（重命名为复数）
> - 新增 `agent/composers/`（TransportComposer 及未来的 PriceComposer、PlanningComposer、AmenitiesComposer）
> - PTV 文件集中在 `agent/tools/ptv/` 和 `agent/connectors/ptv/`（每个数据源一个子包）
>
> **文件命名约定：** 工具/Connector/模型文件使用 `{datasource}_{descriptor}.py` 模式（lowercase snake_case）：
> - `ptv_nearby_stops_tool.py`、`ptv_stop_detail_tool.py`、`ptv_disruptions_tool.py`
> - `ptv_connector.py`、`ptv_models.py`
> - 测试文件对应：`test_ptv_nearby_stops_tool.py`

---

## 13. 测试策略

### 13.1 单元测试

| 测试对象 | 测试文件 | 测试内容 |
|---|---|---|
| `EPTVRouteType` / dataclass 不可变性 | `tests/ptv/test_ptv_models.py` | 所有 enum 成员值正确；frozen dataclass 赋值抛异常；DTO camelCase 序列化 |
| `PTVConnector._build_auth_async()` | `tests/ptv/test_ptv_connector.py` | 给定已知 devid + api_key + path + params，验证签名与 PTV 文档示例一致 |
| `PTVConnector._map_error()` | `tests/ptv/test_ptv_connector.py` | 各 HTTP 状态码映射到正确的 error_code |
| `PTVConnector` HTTP 方法 | `tests/ptv/test_ptv_connector.py` | Mock `httpx.AsyncClient.send`，验证重试、超时、错误映射全链路 |
| `PTVNearbyStopsTool.build_params()` | `tests/ptv/test_ptv_nearby_stops_tool.py` | 从 ExecutionContext 正确构建 lat/lng/radius params |
| `PTVNearbyStopsTool._execute_async()` | `tests/ptv/test_ptv_nearby_stops_tool.py` | Mock Connector 返回示例 JSON，验证 PTVNearbyStopResult 解析 + 分类统计 |
| `PTVNearbyStopsTool.run_async()` | `tests/ptv/test_ptv_nearby_stops_tool.py` | 验证模板方法：ConnectorHttpError → ToolResult(success=False)；ConnectorTimeoutError → ToolResult(success=False, error_code="PTV_NEARBY_STOPS_TIMEOUT") |
| `PTVStopDetailTool._execute_async()` | `tests/ptv/test_ptv_stop_detail_tool.py` | Mock Connector，验证 departure → frequency 聚合逻辑 |
| `TransportComposer` | `tests/ptv/test_transport_composer.py` | 给定 mock PTVNearbyStopResult + GoogleRoutesResult + user needs，验证以下场景正确输出 TransportAssessment: |
| | | - 满分场景：火车站 300m + 高峰期 ≤3min + Train+Tram+Bus + 夜间服务 |
| | | - 低分场景：仅公交，无火车站，发车间隔 > 20min |
| | | - 部分数据：PTV 有结果但 GoogleRoutes 失败 → partial=True |
| | | - 无通勤需求：commute_destination=None → commute=None |
| | | - commute 超限：总耗时 > commute_max_mins → within_commute_limit=False |
| Agent PTV Endpoints | `tests/ptv/test_agent_ptv_endpoints.py` | 所有 `/agent/ptv/*` 端点返回正确的 response model；Connector 失败 → 502；Swagger 可见 |

### 13.2 集成测试

| 测试场景 | 验证点 |
|---|---|
| PTV API mock — `stops/location` 返回示例 Melbourne CBD 数据 | Tool → Connector → Parser 全链路 |
| PTV API mock — 429 rate limit | 退避 + 降级到缓存 |
| PropertyDetailHandler + PTV tools | Phase 1/2/3 编排顺序、partial 结果传递 |
| Agent PTV Endpoints — `/agent/ptv/nearby-stops` | 真实 HTTP 请求 → PTVConnector → Tool → Response |
| TransportAssessment 持久化 | 写入 → 读取 JSONB 往返一致性；过期数据刷新 |

### 13.3 手工验证

使用 PTV 提供的 Swagger UI 手工验证以下典型 Melbourne 坐标：

| 场景 | 坐标 | 预期 |
|---|---|---|
| CBD 公寓 | -37.8142, 144.9631 | 多个火车站 + 电车站 + 公交站，频率 Excellent |
| 远郊 house | -37.8500, 145.1500 | 可能只有公交，频率 Fair/Poor |
| 无 PT 覆盖区 | 待定 | stops/location 返回空列表 |

---

## 14. 与其他 Composer 的数据交互

TransportComposer 的 `TransportAssessment` 会被传递到 Synthesis Agent（Agent Architecture §12），与以下 Composer 的结果一起生成最终的 NL 报告：

```text
PropertyDetailResult
├── PriceComposer        → PriceAssessment
├── TransportComposer    → TransportAssessment    ← 本 PRD 范围
├── PlanningComposer     → PlanningAssessment
└── AmenitiesComposer    → AmenitiesAssessment
```

Synthesis Agent 可能会做以下自然语言整合：

- "This property is a **7-minute walk** from **Richmond Station**, served by the **Belgrave, Lilydale, Alamein, Glen Waverley lines**. Peak-hour trains depart every **3 minutes**."
- "Your commute to **CBD** would take approximately **22 minutes** by train with **no transfers** — within your 30-minute limit."
- "⚠️ Note: The **Cranbourne line** has planned maintenance this weekend — buses replace trains."

> **Synthesis Agent 不允许**修改 TransportAssessment 中的数字或结论，只能将结构化结果转为自然语言并附加 context。

---

## 15. Open Questions — 已决议

| # | 问题 | 决议 | 决议日期 |
|---|---|---|---|
| Q1 | PTV API devid/key 是否已申请？ | **尚未申请。** 需要在开发 PTVConnector 之前完成申请。免费 tier rate limit（1000 req/min）经评估满足 MVP 需求。**阻塞项——Sprint 启动前必须完成。** | 2026-07-16 |
| Q2 | 步行距离用直线距离还是实际步行距离？ | **使用 Google Routes 实际步行距离。** PTV 只提供直线距离（`stop_distance`），步行距离/时间由 GoogleRoutesTool 计算，TransportComposer 合并。PTV 数据模型已移除 `walking_*` 字段。 | 2026-07-16 |
| Q3 | accessibility_score 的评分权重是否需要按用户类型个性化？ | **MVP 使用统一权重**（Proximity 40 / Frequency 30 / Coverage 20 / Night 10）。个性化评分（投资者偏 Train、自住者偏 Tram）进 Phase 2。 | 2026-07-16 |
| Q4 | VLine 和 Night Bus 的权重？ | VLine 等同于 Train 计入 Coverage；Night Bus 仅计入 Night/Weekend 维度。维持原设计。 | 2026-07-16 |
| Q5 | 高峰时段定义？ | **固定为 7:00–9:00 和 16:00–18:00**（Melbourne local time），不做动态调整。 | 2026-07-16 |
| Q6 | TransportAssessment 是否持久化到 Postgres？ | **是——见 §16 持久化设计。** | 2026-07-16 |
| Q7 | agent/ 子目录命名（单数 vs 复数）？ | **统一为复数：** `agent/tools/`、`agent/connectors/`、`agent/composers/`。`agent/tool_registry/` 保持现有命名（`registry` 是单数概念）。 | 2026-07-21 |
| Q8 | PTVConnector 文件位置？ | **`agent/connectors/ptv/ptv_connector.py`** — 与 BaseConnector（`agent/connectors/base.py`）同层，每个数据源一个子包。 | 2026-07-21 |
| Q9 | TransportComposer 文件位置？ | **`agent/composers/transport_composer.py`** — 新建 `agent/composers/` 目录，后续 Price/Planning/Amenities Composer 同目录。 | 2026-07-21 |
| Q10 | PTV 相关文件的命名约定？ | **`ptv_{descriptor}.py`**（lowercase snake_case，统一 `ptv_` 前缀）：`ptv_nearby_stops_tool.py`、`ptv_connector.py`、`ptv_models.py`。不使用 dot 分隔（Python 不支持点号模块名）。已在 PRD §12 文件命名约定中记录。 | 2026-07-21 |

---

## 16. TransportAssessment 持久化设计

### 16.1 持久化动机

`TransportAssessment` 需要持久化到 Postgres，原因：

1. **历史报告回看** — 用户查看 3 天前生成的 property report，应看到当时的交通评估数据（而非重新查询，因为 PTV 时刻表可能已更新）
2. **跨 Session 复用** — 同一用户在不同 session 中查看同一房产，如果缓存未命中，可从 Postgres 恢复（减少 PTV API 调用）
3. **多房产对比** — compare_properties 需要同时展示多个房产的交通评分，从 DB 加载比重新调用 PTV API 更快且一致
4. **Synthesis Agent 不需要在每次展示时重新运行** — 结构化数据已落库，只有用户显式请求"重新分析"才触发重新查询

### 16.2 存储策略

**不单独建表。** `TransportAssessment` 作为 `property_reports` 表的 JSONB 字段的一部分存储，与 Price/Planning/Amenities 评估一起序列化。

```sql
-- 在现有 property_reports 表中扩展（或新建）
CREATE TABLE IF NOT EXISTS property_reports (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES sessions(id),
    property_id     VARCHAR(255) NOT NULL,          -- Domain property ID
    target_lat      DOUBLE PRECISION,
    target_lng      DOUBLE PRECISION,

    -- Composer 结果（JSONB）
    price_assessment        JSONB,                  -- PriceComposer 输出
    transport_assessment    JSONB,                  -- TransportComposer 输出 ← 本次新增
    planning_assessment     JSONB,                  -- PlanningComposer 输出
    amenities_assessment    JSONB,                  -- AmenitiesComposer 输出

    -- Synthesis 结果
    report_text     TEXT,                           -- Synthesis Agent NL 输出
    key_metrics     JSONB,

    -- 元数据
    generated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    data_valid_until TIMESTAMPTZ,                   -- 评估数据有效期（过期建议刷新）
    is_partial      BOOLEAN NOT NULL DEFAULT FALSE,  -- 是否有 Tool 失败导致部分数据缺失
    warnings        JSONB DEFAULT '[]',

    -- 数据溯源
    tool_versions   JSONB,                          -- {"ptv_nearby": "1.0", "google_routes": "1.0"}
    source_cache_hits JSONB                          -- {"ptv_stops": true, "ptv_departures": false}
);
```

### 16.3 JSONB 存储格式

`transport_assessment` 列存储的是 `TransportAssessment` dataclass 的 JSON 序列化结果（通过 `dataclasses.asdict()`）：

```json
{
  "nearby_transport": {
    "has_train": true,
    "has_tram": true,
    "has_bus": true,
    "has_night_service": true,
    "nearest_train_name": "Richmond Railway Station",
    "nearest_train_distance_metres": 342,
    "nearest_train_walking_minutes": 4,
    "nearest_tram_name": "Swan St/Richmond",
    "nearest_tram_distance_metres": 210,
    "nearest_tram_walking_minutes": 3,
    "train_lines": ["Belgrave", "Lilydale", "Alamein", "Glen Waverley"],
    "tram_routes": ["70", "48"],
    "peak_frequency_train_minutes": 3,
    "peak_frequency_tram_minutes": 6,
    "peak_frequency_bus_minutes": 10,
    "active_disruptions": []
  },
  "commute": {
    "destination": "Melbourne CBD",
    "best_mode": "train",
    "total_duration_minutes": 22,
    "walking_to_stop_minutes": 4,
    "waiting_time_estimate_minutes": 3,
    "in_vehicle_minutes": 12,
    "transfers": 0,
    "within_commute_limit": true,
    "exceeds_limit_by_minutes": null,
    "is_direct_route": true
  },
  "accessibility_score": {
    "overall": 95,
    "proximity": 40,
    "frequency": 30,
    "coverage": 20,
    "night_weekend": 5,
    "score_label": "Excellent"
  },
  "partial": false,
  "warnings": []
}
```

### 16.4 读写流程

```
Write Path (property_detail 请求):
  TransportComposer.compose(...) → TransportAssessment
      ↓
  写入 property_reports.transport_assessment (JSONB)
  写入 property_reports.data_valid_until = now() + 6h (与 PRD v1.1 §4.6 一致)
      ↓
  Synthesis Agent 读取 TransportAssessment → 生成 report_text

Read Path (历史报告 / 对比):
  SELECT transport_assessment FROM property_reports WHERE property_id = $1
      ↓
  data_valid_until > now()
    ├── YES → 直接反序列化返回
    └── NO  → 触发后台刷新（stale-while-revalidate），先返回旧数据
```

### 16.5 TTL 与刷新策略

| 数据 | TTL | 刷新触发 |
|---|---|---|
| TransportAssessment (整体) | 6 小时 | 用户显式点"刷新报告" / TTL 过期后自动 |
| PTV stops/location 缓存 (Redis) | 24 小时 | 独立于 Assessment TTL |
| PTV departures 缓存 (Redis) | 1 小时 | 独立于 Assessment TTL |

> **注意区分两层 TTL：** Redis 缓存控制 PTV API 调用频率；Postgres `data_valid_until` 控制何时提示用户"数据可能过期"。两者独立运作。

### 16.6 对比场景的读取优化

`compare_properties` 需要同时展示 2-3 个房产的 `accessibility_score`，每套房产独立查询：

```sql
SELECT property_id, transport_assessment->'accessibility_score' AS score
FROM property_reports
WHERE property_id IN ('domain_123', 'domain_456', 'domain_789')
  AND (data_valid_until > NOW() OR data_valid_until IS NULL)
ORDER BY (transport_assessment->'accessibility_score'->>'overall')::int DESC;
```

如果某房产的 report 已过期或不存在，仅对该房产触发 Tool 重新查询，其余房产复用 DB 数据。

---

## 17. 实现计划 — Subtask 分解

### 依赖关系

```
Subtask 1 (PTV Models)
    ↓
Subtask 2 (PTVConnector)
    ↓
┌──────┴──────┐
↓             ↓
Subtask 3     Subtask 4          ← 可并行
(NearbyStops) (StopDetail)
└──────┬──────┘
       ↓
Subtask 5 (TransportComposer)
       ↓
Subtask 6 (PropertyDetailHandler — PTV only)
       ↓
Subtask 8 (Agent PTV Endpoints / Swagger)
       ↓
Subtask 7 (Postgres 持久化 — table 设计待定)
```

---

### Subtask 1 — PTV Data Models (§3)

| | |
|---|---|
| **源文件** | `agent/tools/ptv/ptv_models.py` |
| **测试文件** | `tests/ptv/test_ptv_models.py` |
| **覆盖率** | **100%** |
| **依赖** | `models/base.py`（`PropertyAIBaseModel`） |

**交付内容：**

- `EPTVRouteType(IntEnum)` — Train=0, Tram=1, Bus=2, VLine=3, NightBus=4
- 6 个 frozen dataclass：`PTVNearbyStop`, `PTVStopRoute`, `PTVStopDetail`, `PTDepartureInfo`, `PTVStopDepartureSummary`, `PTVDisruption`
- 2 个 Pydantic DTO（继承 `PropertyAIBaseModel`）：`PTVNearbyStopDTO`, `PTVNearbyStopResult`
- DTO 自动获得 camelCase 别名（`route_type` → `routeType`, `stop_id` → `stopId`）

**测试要点：**

- Frozen dataclass 不可变（赋值抛 `FrozenInstanceError`）
- DTO `model_dump(by_alias=True)` 输出 camelCase keys
- `PTVNearbyStopResult` 分类统计字段正确初始化（`train_stops_nearby`, `tram_stops_nearby` 等）
- `PTVNearbyStopResult.model_validate(ptv_api_dict)` 正确解析 PTV API 原始响应

**完成标准：**
- **100%** 覆盖率
- `ruff check` + `mypy --strict` 通过

---

### Subtask 2 — PTVConnector (§5)

| | |
|---|---|
| **源文件** | `agent/connectors/ptv/ptv_connector.py` |
| **测试文件** | `tests/ptv/test_ptv_connector.py` |
| **覆盖率** | **100%** |
| **依赖** | Subtask 1（`ptv_models.py` 中的 `EPTVRouteType`）+ 现有 `agent/connectors/base.py` |

**交付内容：**

- `PTVConnector(BaseConnector)` 类
- 覆盖 `_build_auth_async(request: httpx.Request) → httpx.Request` — HMAC-SHA1 签名追加到 `request.url`（`devid` + `signature` query params）
- 覆盖 `_map_error(status_code: int, response_body: str) → str` — 映射表：400→`PTV_BAD_REQUEST`, 403→`PTV_AUTH_FAILED`, 429→`PTV_RATE_LIMITED`, 5xx→`PTV_UPSTREAM_ERROR`
- 6 个领域方法（内部均调 `self._request_async()`）：

| 方法 | PTV Endpoint |
|---|---|
| `get_route_types_async()` | `GET /v3/route_types` |
| `get_stops_near_location_async(lat, lng, route_types, max_distance)` | `GET /v3/stops/location/{lat},{lng}` |
| `get_stop_detail_async(stop_id, route_type)` | `GET /v3/stops/{stop_id}/route_type/{route_type}` |
| `get_departures_async(stop_id, route_type, date_utc, max_results)` | `GET /v3/departures/route_type/{route_type}/stop/{stop_id}` |
| `get_disruptions_for_stop_async(stop_id, route_type)` | `GET /v3/disruptions/route_type/{route_type}/stop/{stop_id}` |
| `search_async(term)` | `GET /v3/search/{search_term}` |

- `close_async()` — 清理底层 `httpx.AsyncClient`

**测试要点：**

- HMAC 签名 vs PTV 官方文档示例（给定 devid + api_key + path + params，验证签名 hex digest）
- `_map_error` 覆盖 400/403/429/500/502/503 → 正确 error_code
- Mock `httpx.AsyncClient.send` 覆盖：
  - 200 → 返回解析后 JSON dict
  - 403 → `ConnectorHttpError(error_code="PTV_AUTH_FAILED")`
  - 429 → `ConnectorHttpError(error_code="PTV_RATE_LIMITED")`
  - Timeout × 3 次 → `ConnectorTimeoutError(attempts=3)`
- `_get_client_async` 延迟初始化（两次调用返回同一 client 实例）
- `close_async` 后 `_client` 为 None

**完成标准：**
- **100%** 覆盖率
- Mock httpx 覆盖：成功 2xx、客户端错误 4xx、服务端错误 5xx、超时重试成功、超时重试耗尽
- `ruff check` + `mypy --strict` 通过

---

### Subtask 3 — PTVNearbyStopsTool (P0) (§4.3)

| | |
|---|---|
| **源文件** | `agent/tools/ptv/ptv_nearby_stops_tool.py` |
| **测试文件** | `tests/ptv/test_ptv_nearby_stops_tool.py` |
| **覆盖率** | **≥80%** |
| **依赖** | Subtask 1（models）+ Subtask 2（connector）+ 现有 `agent/tools/base.py` |

**交付内容：**

- `NearbyStopsParams(BaseModel)` — `lat: float`, `lng: float`, `train_radius_m: int = 1200`, `tram_radius_m: int = 800`, `bus_radius_m: int = 400`, `vline_radius_m: int = 2000`, `night_bus_radius_m: int = 400`
- `PTVNearbyStopsTool(BaseTool[NearbyStopsParams])`
  - `name = "ptv_nearby_stops"`, `params_model = NearbyStopsParams`
  - `build_params(context: ExecutionContext) → NearbyStopsParams` — 纯函数，提取坐标
  - `_execute_async(params) → dict[str, object]` — 按 route_type 分层查询 → 去重 → 分类统计 → 返回 `PTVNearbyStopResult.model_dump()`
  - 继承 `run_async()` 模板方法（不覆盖）— 自动捕获 ConnectorError → ToolResult

**测试要点：**

- `build_params` 正确提取 `context.property_lat`/`property_lng`（含 None → 0.0 fallback）
- `_execute_async` mock connector 返回示例 Melbourne CBD JSON → 验证：
  - `train_stops_nearby` / `tram_stops_nearby` / `bus_stops_nearby` 计数正确
  - `nearest_train_stop.distance_metres` 为最短距离
  - 去重：同一 `stop_id` 不重复出现
- `run_async` 模板方法覆盖：
  - `ConnectorHttpError` → `ToolResult(success=False, error_code=e.error_code)`
  - `ConnectorTimeoutError` → `ToolResult(success=False, error_code="PTV_NEARBY_STOPS_TIMEOUT")`
  - `_execute_async` 成功 → `ToolResult(success=True, execution_time_ms > 0)`
- `get_tool_schema()` 返回正确的 `{name, description, parameters}` provider-agnostic 格式

**完成标准：**
- **≥80%** 覆盖率
- `ruff check` + `mypy --strict` 通过

---

### Subtask 4 — PTVStopDetailTool (P0) (§4.4)

| | |
|---|---|
| **源文件** | `agent/tools/ptv/ptv_stop_detail_tool.py` |
| **测试文件** | `tests/ptv/test_ptv_stop_detail_tool.py` |
| **覆盖率** | **≥80%** |
| **依赖** | Subtask 1（models）+ Subtask 2（connector）+ 现有 `agent/tools/base.py` |

**交付内容：**

- `StopDetailParams(BaseModel)` — `stop_ids: list[StopIdEntry]`, `top_n: int = 6`
- `StopIdEntry(BaseModel)` — `stop_id: str`, `route_type: int`
- `PTVStopDetailTool(BaseTool[StopDetailParams])`
  - `name = "ptv_stop_detail"`, `params_model = StopDetailParams`
  - `build_params(context, nearby_result) → StopDetailParams` — 从 PTVNearbyStopResult 提取 top_n 站
  - `_execute_async(params) → dict[str, object]` — 对每个 stop 并行调用 `get_stop_detail_async` + `get_departures_async` → 计算频率摘要 → 返回更新后的 `PTVNearbyStopDTO` 列表

**频率聚合规则（§4.4）：**

| 高峰期发车间隔 | 等级 |
|---|---|
| ≤ 5 min | Excellent |
| 5–10 min | Good |
| 10–20 min | Fair |
| > 20 min | Poor |
| 无数据 | Unknown |

- 高峰时段：weekday 7:00–9:00 + 16:00–18:00（Melbourne local time）
- 非高峰时段：weekday 10:00–15:00
- 晚间服务：22:00 后是否有 departure
- 周末服务：Saturday/Sunday 是否有 departure

**测试要点：**

- departure → frequency 聚合：给定 7 个 departure 在 7:00-8:30 间隔 3min → `peak_frequency_minutes = 3`
- `has_evening_service` / `has_weekend_service` 检测正确
- 并行查询：mock connector 验证 `get_stop_detail_async` 和 `get_departures_async` 被并发调用
- 单个 stop 失败 → 跳过该 stop，继续汇总其余（`warnings` 列表记录）
- `run_async` 模板方法（同 Subtask 3 的 ConnectorError/Timeout 路径）

**完成标准：**
- **≥80%** 覆盖率
- `ruff check` + `mypy --strict` 通过

---

### Subtask 5 — TransportComposer (§6)

| | |
|---|---|
| **源文件** | `agent/composers/transport_composer.py` |
| **测试文件** | `tests/ptv/test_transport_composer.py` |
| **覆盖率** | **100%** |
| **依赖** | Subtask 1（models：`PTVDisruption`, `PTVNearbyStopDTO` 类型引用） |

**交付内容：**

- 4 个 frozen dataclass：
  - `TransportAssessment` — 顶层（`nearby_transport`, `commute`, `accessibility_score`, `partial`, `warnings`）
  - `TransportCoverage` — 公交覆盖摘要
  - `CommuteAssessment` — 通勤评估
  - `AccessibilityScore` — 0-100 综合评分（`overall`, `proximity` 0-40, `frequency` 0-30, `coverage` 0-20, `night_weekend` 0-10, `score_label`）
- `TransportComposer` 类（纯函数，无 I/O，无 LLM）：
  - `compose(ptv_result, google_routes_result, user_needs) → TransportAssessment`
  - Proximity/Frequency/Coverage/Night-Weekend 评分逻辑（§6.5）
  - `CommuteAssessment` 仅在 `commute_destination` 非空时填充

**测试要点（5 个场景，100% 覆盖评分逻辑）：**

| # | 场景 | 预期 |
|---|---|---|
| 1 | 满分：火车站 300m + ≤3min + Train+Tram+Bus + 夜间服务 | `overall ≈ 95`, `score_label = "Excellent"` |
| 2 | 低分：仅公交 + 发车间隔 > 20min + 无夜间/周末 | `overall ≈ 16`, `score_label = "Poor"` |
| 3 | 部分数据：PTV 成功但 GoogleRoutes 失败 | `partial = True`, `commute = None` |
| 4 | 无通勤需求：`commute_destination = None` | `commute = None`, `accessibility_score` 仍然有效 |
| 5 | 通勤超限：总耗时 > `commute_max_mins` | `within_commute_limit = False`, `exceeds_limit_by_minutes > 0` |

**完成标准：**
- **100%** 覆盖率（所有评分分支 + 边界条件）
- `ruff check` + `mypy --strict` 通过

---

### Subtask 6 — PropertyDetailHandler + SSE (§7, §10)

| | |
|---|---|
| **源文件** | `agent/orchestration/handlers/property_detail_handler.py` |
| **测试文件** | `tests/ptv/test_property_detail_handler.py` |
| **覆盖率** | **≥80%** |
| **依赖** | Subtask 1-5 全部 + 现有 `IntentHandler` Protocol + 现有 `EExecutionEvent` + 现有 `ToolRegistry` |

**交付内容：**

- `PropertyDetailHandler` 实现 `IntentHandler` Protocol
  - `intent` property → `EUserIntent.PROPERTY_DETAIL`
  - `execute_async(context) → PropertyDetailResult`
- **仅关注 PTV 编排**——其他 Tool（Domain、GoogleRoutes、Vicmap、GooglePlaces）用 mock/占位，等各自 PRD 实现后再集成
- PTV 执行顺序：
  1. `PTVNearbyStopsTool.build_params(context)` → 检查坐标（`lat == 0.0` → 跳过 PTV）
  2. `PTVNearbyStopsTool.run_async(params)` → 获取附近站点
  3. 从 result 提取 top_n stop_ids
  4. `PTVStopDetailTool.build_params(context, nearby_result)` → 构建 stop detail params
  5. `PTVStopDetailTool.run_async(params)` → 获取线路 + 频率
  6. `TransportComposer.compose(...)` → TransportAssessment
- **SSE 事件 emit**（`EExecutionEvent`）：
  - `TOOL_STARTED` / `TOOL_COMPLETED` — 每个 Tool 执行前后
  - `TOOL_FAILED` — Tool 失败时
  - `SUMMARY_STARTED` / `SUMMARY_COMPLETED` — TransportComposer 执行前后
- **降级策略**：
  - PTV 坐标缺失 → 跳过所有 PTV Tool，`TransportAssessment(partial=True)`
  - PTV API 全挂 → `partial=True`, `warnings=["Public transport data unavailable"]`
  - 单个 Tool 失败 → 继续其余 Tool

**测试要点：**

- Phase 1/2 编排顺序验证（mock Tool.run_async 记录调用时序）
- PTV 全挂 → `TransportAssessment.partial = True`，不抛异常
- 坐标缺失（`lat=0.0, lng=0.0`）→ 跳过 PTV，返回 partial
- SSE 事件顺序：`TOOL_STARTED(nearby)` → `TOOL_COMPLETED(nearby)` → `TOOL_STARTED(detail)` → `TOOL_COMPLETED(detail)` → `SUMMARY_STARTED` → `SUMMARY_COMPLETED`

**完成标准：**
- **≥80%** 覆盖率
- PTV 编排路径 + 降级路径均可通过 mock 测试验证
- `ruff check` + `mypy --strict` 通过

---

### Subtask 7 — Postgres 持久化 (§16)

| | |
|---|---|
| **源文件** | migration + repository（具体文件待 table 设计完成后确定） |
| **测试文件** | `tests/ptv/test_transport_persistence.py` |
| **覆盖率** | **≥80%** |
| **依赖** | Subtask 5（TransportAssessment 类型）+ Subtask 6（Handler write path） |

> ⚠️ **此 subtask 独立，待 `property_reports` 表设计最终确定后再实施。** 当前先完成 Subtask 1-6 + 8。

**交付内容：**

- `property_reports` 表 DDL migration（含 `transport_assessment JSONB` 列）
- `TransportAssessment` → JSONB 序列化 / 反序列化
- Write path：PropertyDetailHandler 执行完成后写入 `property_reports`
- Read path：按 `property_id` 查询 + `data_valid_until` 过期检查（stale-while-revalidate）

**测试要点：**

- `TransportAssessment` → `dataclasses.asdict()` → JSONB 往返一致性
- 过期数据（`data_valid_until < now()`）→ 触发刷新
- 多房产对比查询 SQL：`WHERE property_id IN (...)` → 按 `accessibility_score.overall` 排序

---

### Subtask 8 — Agent PTV Endpoints（Swagger 可调测）🆕

| | |
|---|---|
| **源文件** | `routers/agent_ptv.py` |
| **测试文件** | `tests/ptv/test_agent_ptv_endpoints.py` |
| **覆盖率** | **≥80%** |
| **依赖** | Subtask 2-5 全部 |

#### 目的

提供独立于主 `/api/v1/chat` 流程的 agent router，挂在 Swagger UI（`/docs`）上，让前端和后端可以直接：

1. **测试每个 PTV Tool 对真实外部 API 的调用**——填入参数 → 看实际返回数据
2. **测试 TransportComposer 的编排结果**——填入 mock/真实 PTV 数据 → 看评分 + 通勤评估结构
3. **明确数据 contract**——前端不需要跑完整 agent 流程就能看到每个字段的 shape、取值范围、null 条件

#### 端点设计

```
POST /agent/ptv/nearby-stops
  输入: NearbyStopsParams { lat, lng, train_radius_m?, tram_radius_m?, ... }
  输出: PTVNearbyStopResult (真实 PTV API 调用)
  Swagger 描述: "PTVNearbyStopsTool — 查询坐标周边公共交通站点"

POST /agent/ptv/stop-detail
  输入: StopDetailParams { stop_ids: [{stop_id, route_type}], top_n? }
  输出: list[PTVNearbyStopDTO] (routes_serving + peak_frequency_minutes 已填充)
  Swagger 描述: "PTVStopDetailTool — 获取站点途经线路和发车频率"

POST /agent/ptv/transport-assessment
  输入: {
    ptv_result: PTVNearbyStopResult,    // 可直接粘贴 /agent/ptv/nearby-stops 的输出
    commute_destination?: str,
    commute_max_mins?: int,
    commute_mode?: str
  }
  输出: TransportAssessment (含 accessibility_score + commute)
  Swagger 描述: "TransportComposer — PTV 数据 → 交通评估（GoogleRoutes 部分暂用 mock）"
```

> **注意：** `/agent/ptv/transport-assessment` 中 GoogleRoutes 结果暂用 mock（标注在 Swagger description 中）。等 GoogleRoutesTool 实现后，增加一个可选输入字段 `google_routes_result` 供调用方手动填入真实数据。

#### 实现要点

```python
# routers/agent_ptv.py
from fastapi import APIRouter, Depends, HTTPException
from agent.connectors.ptv.ptv_connector import PTVConnector
from agent.tools.ptv.ptv_nearby_stops_tool import PTVNearbyStopsTool, NearbyStopsParams
from agent.tools.ptv.ptv_stop_detail_tool import PTVStopDetailTool, StopDetailParams
from agent.composers.transport_composer import TransportComposer, TransportAssessment
from agent.tool.result import ToolResult

router = APIRouter(prefix="/agent/ptv", tags=["agent-ptv"])


def _get_ptv_connector() -> PTVConnector:
    """FastAPI dependency — 创建 PTVConnector 实例（从 Settings 读取 devid/api_key）。"""
    ...


@router.post("/nearby-stops", response_model=PTVNearbyStopResult)
async def agent_nearby_stops_async(
    params: NearbyStopsParams,
    connector: PTVConnector = Depends(_get_ptv_connector),
) -> PTVNearbyStopResult:
    """直接调用 PTVNearbyStopsTool —— 测试真实 PTV API 返回数据。"""
    tool: PTVNearbyStopsTool = PTVNearbyStopsTool(connector=connector)
    result: ToolResult = await tool.run_async(params)
    if not result.success:
        raise HTTPException(status_code=502, detail=result.error_message)
    return PTVNearbyStopResult.model_validate(result.data)


@router.post("/transport-assessment", response_model=TransportAssessment)
async def agent_transport_assessment_async(
    ptv_result: PTVNearbyStopResult,
    commute_destination: str | None = None,
    commute_max_mins: int | None = None,
) -> TransportAssessment:
    """测试 TransportComposer —— 验证评分逻辑。GoogleRoutes 部分暂用 mock。"""
    composer: TransportComposer = TransportComposer()
    return composer.compose(
        ptv_result=ptv_result,
        google_routes_result=None,  # TODO: 替换为真实 GoogleRoutes 结果
        commute_destination=commute_destination,
        commute_max_mins=commute_max_mins,
    )
```

**测试要点：**

- Mock PTV API → 端到端验证 endpoint 返回正确的 response model
- Connector 失败时 endpoint 返回 502 + `error_code` 详情
- 3 个端点均在 Swagger UI `/docs` 下可见（`"agent-ptv"` tag）
- TransportAssessment endpoint 在多种输入组合下返回正确的评分（0-100）

**完成标准：**
- **≥80%** 覆盖率
- 3 个端点均可通过 Swagger UI 手动调测
- `ruff check` + `mypy --strict` 通过

---

### Phase 2 — 后续增强（不在本次 Sprint 范围）

| Subtask | 内容 |
|---|---|
| PTVDisruptionsTool | 服务中断检测（`agent/tools/ptv/ptv_disruptions_tool.py`） |
| Redis 缓存 | 坐标 + stop_detail + frequency 缓存（key schema 见 §9.2） |
| TransportComposer V2 | 个性化评分权重（用户偏好——投资者偏 Train，自住偏 Tram） |
| Stale-while-revalidate | Postgres 数据过期后的后台刷新 |
| Agent Endpoint 扩展 | 添加 `/agent/ptv/disruptions` + `/agent/ptv/stop-detail` 中真实的频率测试 |

### Phase 3 — 可选

| 交付物 | 内容 |
|---|---|
| PTV search | `search/{term}` 站名/线路名自动补全 |
| 历史趋势 | 同一坐标多次查询的频率变化 |
| PTV API key 申请 | **Sprint 启动前必须完成** |

---

## 18. Agent PTV Endpoints — 详细设计

### 18.1 定位

`routers/agent_ptv.py` 是一个开发/调试工具，不属于 Part 1（chat）或 Part 2（agent execution）的核心流程。它单独挂载到 FastAPI app，前缀 `/agent/ptv/`，在 Swagger UI 中以 `agent-ptv` tag 分组展示。

### 18.2 路由注册

```python
# backend/main.py
from routers.agent_ptv import router as agent_ptv_router

app.include_router(agent_ptv_router)  # 挂载 /agent/ptv/*
```

### 18.3 端点详细规格

#### `POST /agent/ptv/nearby-stops`

| | |
|---|---|
| **目的** | 测试 PTVNearbyStopsTool 对真实 PTV API 的调用 |
| **Request Body** | `NearbyStopsParams` (Pydantic) |
| **Response** | `200`: `PTVNearbyStopResult` |
| | `502`: `{"error_code": "PTV_TIMEOUT", "message": "..."}` |
| **Swagger 示例** | `{"lat": -37.8142, "lng": 144.9631}` (Melbourne CBD) |

#### `POST /agent/ptv/stop-detail`

| | |
|---|---|
| **目的** | 测试 PTVStopDetailTool — 查看 real departure + route data |
| **Request Body** | `StopDetailParams` |
| **Response** | `200`: `list[PTVNearbyStopDTO]` (routes + frequency 已填充) |
| | `502`: upstream error |
| **Swagger 示例** | `{"stop_ids": [{"stop_id": "19840", "route_type": 0}], "top_n": 3}` |

#### `POST /agent/ptv/transport-assessment`

| | |
|---|---|
| **目的** | 测试 TransportComposer 输出结构 + 评分——前端可直接看到 `TransportAssessment` 的完整 JSON shape |
| **Request Body** | `PTVNearbyStopResult` (可直接粘贴 `/agent/ptv/nearby-stops` 输出) + 可选通勤参数 |
| **Response** | `200`: `TransportAssessment` |
| **Mock 标注** | GoogleRoutes 部分暂用 mock——`commute` 字段使用假步行时间/换乘数据，确保 Composer 逻辑可验证 |

### 18.4 与核心流程的关系

```
核心 Agent 流程:
  PropertyDetailHandler → PTVNearbyStopsTool.run_async() → ToolResult
                        → PTVStopDetailTool.run_async()   → ToolResult
                        → TransportComposer.compose()     → TransportAssessment
                        → Synthesis Agent                 → NL report

Agent Endpoints (调试):
  POST /agent/ptv/nearby-stops         → PTVNearbyStopsTool.run_async() → PTVNearbyStopResult
  POST /agent/ptv/stop-detail          → PTVStopDetailTool.run_async()  → list[PTVNearbyStopDTO]
  POST /agent/ptv/transport-assessment → TransportComposer.compose()    → TransportAssessment
```

两端点调用的是**同一套 Tool/Composer 实例和同一套 Connector**——Agent Endpoints 返回的是未经 Synthesis Agent 包装的原始结构化数据，可以直接用于前端开发和数据 contract 验证。

---

## Appendix A — PTV API v3 Response Snippets

### A.1 `stops/location` 响应

```json
{
  "stops": [
    {
      "stop_id": 19840,
      "stop_name": "Richmond Railway Station (Richmond)",
      "stop_suburb": "Richmond",
      "route_type": 0,
      "stop_latitude": -37.82391,
      "stop_longitude": 144.98985,
      "stop_distance": 342.5
    }
  ],
  "status": { "version": "3.0", "health": 1 }
}
```

### A.2 `departures` 响应

```json
{
  "departures": [
    {
      "stop_id": 19840,
      "route_id": 6,
      "run_id": 12345,
      "direction_id": 1,
      "scheduled_departure_utc": "2026-07-16T22:15:00Z",
      "estimated_departure_utc": "2026-07-16T22:17:30Z",
      "at_platform": false,
      "platform_number": "4",
      "flags": "",
      "disruption_ids": []
    }
  ],
  "status": { "version": "3.0", "health": 1 }
}
```

### A.3 `disruptions` 响应

```json
{
  "disruptions": {
    "metro_train": [
      {
        "disruption_id": 123456,
        "title": "Buses replacing trains: Belgrave Line",
        "description": "Buses replace trains between Ringwood and Belgrave due to level crossing removal works.",
        "disruption_status": "Planned",
        "disruption_type": "Planned Works",
        "from_date": "2026-07-18T01:00:00Z",
        "to_date": "2026-07-20T01:00:00Z",
        "routes": [{"route_id": 6, "route_name": "Belgrave"}]
      }
    ]
  },
  "status": { "version": "3.0", "health": 1 }
}
```

---

## Appendix B — PTV API 认证完整示例

```python
# HMAC-SHA1 签名由 PTVConnector._build_auth_async() 内部实现。
# 调用方无需手动构建签名 URL——直接使用 Connector 的领域方法即可。

# 示例：在 Tool 层使用 PTVConnector
connector: PTVConnector = PTVConnector(
    config=ConnectorConfig(
        base_url="https://timetableapi.ptv.vic.gov.au",
        default_timeout_secs=5.0,
        max_retries=2,
    ),
    devid="3001234",
    api_key="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
)

# 领域方法自动处理签名
stops: list[dict[str, object]] = await connector.get_stops_near_location_async(
    lat=-37.8142,
    lng=144.9631,
    route_types=[0, 1, 2],
    max_distance=1200,
)

await connector.close_async()
```

签名算法参考（来自 `PTVConnector._build_auth_async`）：

1. 复制 request.url 的 query params 到新 dict
2. 追加 `devid={self._devid}`
3. 按 key 字母序排序
4. URL encode → query_string
5. 消息 = `{request.url.path}?{query_string}`
6. 签名 = `uppercase(hex(HMAC-SHA1(api_key, message)))`
7. 追加 `&signature={digest}` 到 request.url

---

## Appendix C — 与 GoogleRoutesTool 的职责边界

这是最容易混淆的地方，在此明确画线：

| | PTV Tools | GoogleRoutesTool |
|---|---|---|
| 数据源 | PTV Timetable API v3 | Google Routes / Distance Matrix API |
| 回答的问题 | "附近有什么公共交通？" | "从 A 到 B 要多久？" |
| 核心输出 | 站点列表、途经线路、发车频率 | 路线方案、总耗时、换乘次数、步行段 |
| 输入 | 经纬度 + 搜索半径 | 出发经纬度 + 目的地（地址或经纬度）+ 交通方式偏好 |
| 强依赖 | 房产地址 → geocode → lat/lng | 房产地址 + 用户通勤目的地 |
| 独立可用？ | 是——不需要用户有通勤需求 | 否——需要 commute_destination 不为空 |

**合并点:** TransportComposer 同时消费两者。PTV 提供"资源供给"信息（这个区本身交不方便），Google Routes 提供"需求匹配"信息（是否满足你的通勤需求）。

---

## Appendix D — 原型接口速查

以下接口/类已由 Prototype PRD 锁定并由实际代码库实现。PTV 实现必须遵循这些契约：

| 接口/类 | 位置 | 角色 |
|---|---|---|
| `BaseTool[TToolParams]` | `agent/tools/base.py` | 所有 Atomic Tool 的泛型基类。提供 `run_async(params)` 模板方法 + `get_tool_schema()` |
| `ToolResult` | `agent/tools/result.py` | 统一返回类型。`success`, `data`, `error_code`, `source`, `execution_time_ms`, `fallback` |
| `BaseConnector` | `agent/connectors/base.py` | 所有外部 API Connector 的基类。提供 `_request_async()` 重试循环 + `_build_auth_async()` / `_map_error()` 抽象契约 |
| `ConnectorConfig` | `agent/connectors/base.py` | frozen dataclass: `base_url`, `default_timeout_secs`, `max_retries`, `retry_backoff_base_secs` |
| `ConnectorHttpError` | `agent/connectors/base.py` | 非 2xx → ToolResult(success=False) 的异常 |
| `ConnectorTimeoutError` | `agent/connectors/base.py` | 超时耗尽 → ToolResult(success=False) 的异常 |
| `ExecutionContext` | `agent/shared/context.py` | frozen dataclass，由 ContextResolver 构建，传递给所有 Tool |
| `EExecutionEvent` | `agent/shared/events.py` | SSE 事件类型枚举（StrEnum） |
| `IToolRegistry` | `agent/tool_registry/registry.py` | Tool 注册表 Protocol。`register()`, `get()`, `get_openai_tool_schemas()` |
| `IntentHandler[TIntentResult]` | `agent/orchestration/handlers/base.py` | Protocol: `execute_async(context)` + `intent` property |
| `IExecutor` | `agent/orchestration/executors/base.py` | Protocol: `execute_async(context) → ExecutionResponse` |

---

> **下一文档:** Google Routes Integration PRD（待编写）
