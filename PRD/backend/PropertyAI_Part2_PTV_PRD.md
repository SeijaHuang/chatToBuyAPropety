# PropertyAI Part 2 — PTV Integration PRD

| 字段 | 内容 |
|---|---|
| 版本 | v0.2 |
| 状态 | Draft — Open Questions resolved; persistence model added |
| 范围 | PTV API 集成 — 原子 Tool 设计、Connector、TransportComposer、缓存与容错 |
| 上游 | [PropertyAI Part 2 Agent Architecture](./PropertyAI_Part2_Agent_Architecture_PRD.md) §8-11 |
| 下游 | TransportComposer → Synthesis Agent → Final Response |
| 非范围 | Google Routes Tool（独立 PRD）、Vicmap Planning Tool、Google Places Tool |

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

### 3.1 PTV 内部数据模型

```python
# === Route Types (transport mode) ===

class EPTVRouteType(int, Enum):
    """PTV API v3 route_type values."""
    TRAIN = 0
    TRAM = 1
    BUS = 2
    VLINE = 3
    NIGHT_BUS = 4


# === Nearby Stop (单个周边站点) ===

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


# === Stop Routes (站点途经线路) ===

@dataclass(frozen=True)
class PTVStopRoute:
    """A route that stops at a given PTV stop."""
    route_id: str
    route_name: str                    # e.g. "Belgrave", "Route 96"
    route_number: str | None           # e.g. "96" for trams
    route_type: EPTVRouteType
    direction_name: str | None         # e.g. "City (Flinders Street)"


# === Stop Detail (站点完整信息) ===

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


# === Departure Info (班次信息) ===

@dataclass(frozen=True)
class PTDepartureInfo:
    """Scheduled or estimated departure from a stop."""
    route_id: str
    direction_id: int
    scheduled_departure_utc: str       # 时刻表发车时间
    estimated_departure_utc: str | None # 实时预估发车时间
    at_platform: bool | None           # 列车已到站
    platform_number: str | None        # 站台号


# === Stop Departure Summary (站点发车摘要——不做逐条记录) ===

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


# === Disruption (服务中断) ===

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

### 3.2 Tool Result 输出模型

```python
from models.base import PropertyAIBaseModel


class PTVNearbyStopResult(PropertyAIBaseModel):
    """PTVNearbyStopsTool 的输出——房产周边公共交通覆盖。"""
    property_lat: float
    property_lng: float
    nearby_stops: list[PTVNearbyStopDTO]

    # 按交通方式分组统计
    train_stops_nearby: int             # 800m 内火车站数
    tram_stops_nearby: int              # 800m 内电车站数
    bus_stops_nearby: int               # 400m 内公交站数

    # 最近站点摘要（直线距离来自 PTV；步行距离/时间由 GoogleRoutes 提供，留待 TransportComposer 填充）
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
```

---

## 4. Atomic Tool 设计

### 4.1 设计原则回顾

来自 Agent Architecture PRD §9:

> - 一个 Tool ≈ 一个外部数据源下的一项完整查询能力
> - Tool 不调用 Tool
> - 统一接口：`build_params(context) → params` + `run(params) → ToolResult`

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
数据源: PTV API v3 → /v3/stops/location/{lat},{lng}

输入:
  - lat, lng              ← ExecutionContext.location (geocoded from address)
  - max_distance_metres    ← 默认 1000m (train/tram), 实际按 route_type 分层
  - route_types            ← [0,1,2,3,4] 全部，可配置

处理逻辑:
  1. 调用 stops/location，按 route_type 分层查询
     - Train:  半径 1200m（火车站覆盖范围大）
     - Tram:   半径 800m
     - Bus:    半径 400m（公交站密集，太远无意义）
  2. 合并去重（一个物理站点可能出现在多个 route_type 中）
  3. 按距离排序，分类统计
  4. 标记 nearest_train / nearest_tram / nearest_bus

输出: PTVNearbyStopResult

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

### 4.4 PTVStopDetailTool（P1）

```text
Tool: PTVStopDetailTool
─────────────────────────
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
数据源: PTV API v3 → /v3/disruptions/route_type/{route_type}/stop/{stop_id}

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

```python
class PTVConnector:
    """Encapsulates all PTV API v3 HTTP communication.

    职责 (per Agent Architecture §10):
      - HTTP 调用 (httpx)
      - HMAC-SHA1 签名计算
      - URL / query params 组装
      - Timeout + retry
      - Response JSON parsing
      - External error mapping → ToolResult.error_code
    """

    # --- 配置 ---
    base_url: str = "https://timetableapi.ptv.vic.gov.au"
    devid: str                           # PTV Developer ID
    api_key: str                         # PTV API Key（用于 HMAC 签名，不直接发送）
    default_timeout_secs: int = 5
    max_retries: int = 2

    # --- 公开方法 ---
    async def get_route_types_async(self) -> list[dict]: ...
    async def get_stops_near_location_async(
        self, lat: float, lng: float,
        route_types: list[int] | None = None,
        max_distance: int = 1200,
    ) -> list[dict]: ...
    async def get_stop_detail_async(
        self, stop_id: str, route_type: int,
    ) -> dict: ...
    async def get_departures_async(
        self, stop_id: str, route_type: int,
        date_utc: str | None = None,
        max_results: int = 10,
    ) -> list[dict]: ...
    async def get_disruptions_for_stop_async(
        self, stop_id: str, route_type: int,
    ) -> list[dict]: ...
    async def search_async(self, term: str) -> list[dict]: ...

    # --- 私有方法 ---
    def _build_signature(self, path: str) -> str: ...
    def _build_url(self, path: str, params: dict) -> str: ...
    async def _request_async(self, path: str, params: dict) -> dict: ...
```

### 5.2 HMAC 签名认证

PTV API v3 使用 HMAC-SHA1 签名。每次请求的 query string 必须包含 `devid` 和 `signature`。

```python
import hashlib
import hmac
import urllib.parse

def _build_signature(self, path: str, params: dict[str, str]) -> str:
    """Build HMAC-SHA1 signature for PTV API v3.

    Signature = HMAC-SHA1(api_key, path + query_string_with_devid)
    but NOT including the signature parameter itself.
    """
    params_with_devid: dict[str, str] = {**params, "devid": self.devid}
    # Sort by key — PTV requires canonical ordering
    sorted_params: list[tuple[str, str]] = sorted(params_with_devid.items())
    query_string: str = urllib.parse.urlencode(sorted_params)

    # PTV uses the full path (with leading /) + ? + query_string
    message: str = f"{path}?{query_string}"

    digest: str = hmac.new(
        self.api_key.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha1,
    ).hexdigest().upper()

    return digest
```

### 5.3 Error Mapping

| PTV API Response | `ToolResult.error_code` | 处理 |
|---|---|---|
| 200 + valid JSON | — (success) | 正常 |
| 400 Bad Request | `PTV_BAD_REQUEST` | 参数错误——不重试，记录日志 |
| 403 Forbidden | `PTV_AUTH_FAILED` | devid 或 api_key 无效——告警 |
| 429 Too Many Requests | `PTV_RATE_LIMITED` | 指数退避 1s→2s→放弃 |
| 5xx Server Error | `PTV_UPSTREAM_ERROR` | 重试 2 次（间隔 1s） |
| Timeout (> 5s) | `PTV_TIMEOUT` | 重试 1 次 |
| Connection Error | `PTV_UNREACHABLE` | 不重试——标记 fallback |

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

### 6.2 输入

| 输入 | 来源 | 是否必需 |
|---|---|---|
| `PTVNearbyStopResult` | PTVNearbyStopsTool + PTVStopDetailTool | 是 |
| `GoogleRoutesResult` | GoogleRoutesTool（通勤路线 + 耗时） | 是（有 commute_destination 时） |
| `commute_destination` | UserNeeds.collected_data.M3 | 否 |
| `commute_max_mins` | UserNeeds.collected_data.M3 | 否 |
| `commute_mode` | UserNeeds.collected_data.M3 | 否（默认 any） |

### 6.3 输出: TransportAssessment

```python
@dataclass(frozen=True)
class TransportAssessment:
    """TransportComposer 的确定性输出——不包含自然语言。"""
    # 公共交通覆盖
    nearby_transport: TransportCoverage
    # 通勤评估（仅当用户有通勤目的地时）
    commute: CommuteAssessment | None
    # 综合评分（供前端雷达图 / 筛选排序）
    accessibility_score: AccessibilityScore
    # 数据可用性标记
    partial: bool                       # 是否有 Tool 失败导致部分数据缺失
    warnings: list[str]                 # e.g. "Bus stop data unavailable for this area"


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

    active_disruptions: list[PTVDisruption]


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

### 6.4 评分规则

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

来自 Agent Architecture PRD §8:

```text
PropertyDetailHandler
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
2. PTVStopDetailTool (依赖 PTVNearbyStopsTool.top_n_stop_ids)
   → 但与 DomainPropertyDetailTool / GooglePlacesTool 等无依赖关系，仍可并行
3. TransportComposer (依赖 PTV 两个 Tool + GoogleRoutesTool 全部完成)
```

### 7.2 最小可并行化策略

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

### 8.2 Failure Policy

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

来自 Agent Architecture PRD §15 的 SSE 事件流，PTV 相关的进度展示：

| SSE Event | 对应阶段 | 用户可见文案 |
|---|---|---|
| `tool_started` | PTVNearbyStopsTool 启动 | `⏳ 正在查询周边公共交通...` |
| `tool_completed` | PTVNearbyStopsTool 完成 | `✓ 已获取附近公共交通站点` |
| `tool_started` | PTVStopDetailTool 启动 | `⏳ 正在分析途经线路与班次...` |
| `tool_completed` | PTVStopDetailTool 完成 | `✓ 已分析公共交通线路与频率` |
| `tool_failed` | 任何 PTV Tool 失败 | `⚠ 公共交通数据暂时不可用` |
| `summary_started` | TransportComposer 启动 | `⏳ 正在整合交通评估...` |
| `summary_completed` | TransportComposer 完成 | `✓ 交通便利度评估完成` |

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

```python
# backend/config.py
class Settings(BaseSettings):
    # ... existing ...
    ptv_api_devid: str = ""
    ptv_api_key: str = ""
    ptv_api_base_url: str = "https://timetableapi.ptv.vic.gov.au"
    ptv_api_timeout_secs: int = 5
    ptv_api_max_retries: int = 2
    ptv_nearby_train_radius_m: int = 1200
    ptv_nearby_tram_radius_m: int = 800
    ptv_nearby_bus_radius_m: int = 400
```

---

## 12. 文件结构

```text
agent/
├── tools/
│   └── ptv/
│       ├── __init__.py
│       ├── connector.py                  # PTVConnector — HMAC 签名 + HTTP + retry
│       ├── nearby_stops_tool.py          # PTVNearbyStopsTool (P0)
│       ├── stop_detail_tool.py           # PTVStopDetailTool (P1)
│       ├── disruptions_tool.py           # PTVDisruptionsTool (P2)
│       └── models.py                     # PTV-specific data models (§3)

agent/
├── summary/
│   └── transport_composer.py             # TransportComposer (§6)
```

---

## 13. 测试策略

### 13.1 单元测试

| 测试对象 | 测试内容 |
|---|---|
| `PTVConnector._build_signature()` | 给定已知 devid + api_key + path + params，验证签名与 PTV 文档示例一致 |
| `PTVNearbyStopsTool.build_params()` | 从 ExecutionContext 正确构建 lat/lng/radius params |
| `PTVNearbyStopsTool.run()` | Mock Connector 返回示例 JSON，验证 PTVNearbyStopResult 解析正确 |
| `PTVStopDetailTool.run()` | Mock Connector，验证 departure → frequency 聚合逻辑 |
| `TransportComposer` | 给定 mock PTVNearbyStopResult + GoogleRoutesResult + user needs，验证以下场景正确输出 TransportAssessment: |
| | - 满分场景：火车站 300m + 高峰期 ≤3min + Train+Tram+Bus + 夜间服务 |
| | - 低分场景：仅公交，无火车站，发车间隔 > 20min |
| | - 部分数据：PTV 有结果但 GoogleRoutes 失败 → partial=True |
| | - 无通勤需求：commute_destination=None → commute=None |
| | - commute 超限：总耗时 > commute_max_mins → within_commute_limit=False |

### 13.2 集成测试

| 测试场景 | 验证点 |
|---|---|
| PTV API mock — `stops/location` 返回示例 Melbourne CBD 数据 | Tool → Connector → Parser 全链路 |
| PTV API mock — 429 rate limit | 退避 + 降级到缓存 |
| PropertyDetailHandler + PTV tools | Phase 1/2/3 编排顺序、partial 结果传递 |

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
    source_cache_hits JSONB                         -- {"ptv_stops": true, "ptv_departures": false}
);
```

### 16.3 JSONB 存储格式

`transport_assessment` 列存储的是 `TransportAssessment` dataclass 的 JSON 序列化结果：

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

## 17. 实现优先级与分阶段交付

### Phase 1 — MVP（必须）

| 交付物 | 内容 |
|---|---|
| PTVConnector | 签名计算 + HTTP 调用 + 错误映射 |
| PTVNearbyStopsTool | `stops/location` 调用 + 结果解析 |
| PTVStopDetailTool | 最近 N 站的线路 + 班次频率摘要 |
| TransportComposer | `TransportAssessment` 全部字段 |
| Postgres 持久化 | `property_reports` 表 + `transport_assessment` JSONB 列的读写 |
| SSE 事件 | 进度预览文案 |
| 单元测试 | Connector 签名 + Tool 参数 + Composer 全场景 |
| 集成测试 | Tool → Connector → Parser 全链路 + 持久化读写 |

### Phase 2 — 增强

| 交付物 | 内容 |
|---|---|
| PTVDisruptionsTool | 服务中断检测 |
| Redis 缓存 | 坐标 + stop_detail + frequency 缓存 |
| TransportComposer V2 | 个性化评分权重（用户偏好） |
| Stale-while-revalidate | Postgres 数据过期后的后台刷新 |

### Phase 3 — 可选

| 交付物 | 内容 |
|---|---|
| PTV search | `search/{term}` 站名/线路名自动补全 |
| 历史趋势 | 同一坐标多次查询的频率变化（判断 "service 是否在改善"） |
| PTV API key 申请 | **Sprint 启动前必须完成** |

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
import hashlib
import hmac
import urllib.parse
from datetime import UTC, datetime


def build_ptv_url(
    base_url: str,
    path: str,
    devid: str,
    api_key: str,
    extra_params: dict[str, str] | None = None,
) -> str:
    """Build a fully signed PTV API v3 URL.

    Reference: https://www.ptv.vic.gov.au/footer/data-and-reporting/datasets/ptv-timetable-api/
    """
    params: dict[str, str] = {"devid": devid}
    if extra_params:
        params.update(extra_params)

    # Canonical ordering: sort by key
    sorted_params: list[tuple[str, str]] = sorted(params.items())
    query_string: str = urllib.parse.urlencode(sorted_params)

    # Signature = uppercase hex of HMAC-SHA1(api_key, path + ? + query_string)
    message: str = f"{path}?{query_string}"
    signature: str = hmac.new(
        api_key.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha1,
    ).hexdigest().upper()

    return f"{base_url}{path}?{query_string}&signature={signature}"
```

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

> **下一文档:** Google Routes Integration PRD（待编写）
