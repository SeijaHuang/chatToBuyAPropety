# PropertyAI — 产品需求文档

**版本:** v1.1 · 机密  
**状态:** 草稿 — 供开发使用  
**目标市场:** 墨尔本，澳大利亚（VIC）— 后续全国扩展  
**房产类型:** 现有住宅（二手）  
**用户:** 购房者和投资者  
**部署:** AWS ap-southeast-2（悉尼）  
**最后更新:** 2026年5月3日

---

**v1.1 变更说明：** 更新了买家服务场景的护栏规则（非建筑商服务）。第2部分编排器重新设计为带两种执行模式的意图路由器。第1阶段Agent扩展至7个（新增邻里+交通Agent）。技术栈确认：Python + FastAPI + OpenRouter + shapely。

---

## 1. 产品概述

### 1.1 问题陈述

在澳大利亚购买房产是一个人做出的最重大财务决策之一，但现有工具对买家的服务极为不足。当前平台（Domain、REA）只是房源聚合器——它们展示可用房源，但不提供关于该房产是否适合买家、存在哪些风险或如何与备选方案比较的任何智能分析。

买家面临三大核心问题：

- **需求不清晰** — 要求在通过引导式对话结构化之前往往模糊不清
- **缺乏综合房产情报** — 叠加风险、学区、基础设施、建筑历史和价格趋势分散在十几个独立来源中
- **没有可信的中立顾问** — 传统买家中介价格昂贵，大多数买家无法获得

### 1.2 产品定位

> **核心价值主张**
>
> PropertyAI 是一款面向澳大利亚市场的 AI 驱动购房助手。它通过引导式对话帮助买家明确需求，推荐匹配的郊区和房产，并生成全面的房产情报报告——在购房全程充当博学、中立的顾问。

### 1.3 硬性边界（产品不做的事）

- 不提供投资建议或预测未来回报（ASIC / 2001年公司法边界）
- 不提供关于合同、产权或产权转让的法律建议
- 不替代持牌买家中介进行谈判
- 不生成平面图、3D渲染图或建筑设计
- 不促进房产交易或充当市场平台

### 1.4 目标用户

| 细分 | 描述 | 主要需求 |
|------|------|----------|
| 自住买家 | 购买自住房产的个人或夫妻 | 在合适的郊区找到适合其生活方式的房产 |
| 房产投资者 | 购买用于租金收入或资本增值 | 分析收益潜力、增长趋势和风险因素 |
| 换房/缩房者 | 从现有房产置换，有可动用资产 | 高效匹配适合人生阶段变化的房产 |

### 1.5 地理范围

- **第1阶段（MVP）：** 墨尔本大都市区
- **第2阶段：** 维多利亚州区域中心（吉朗、巴拉瑞特、本迪戈）
- **第3阶段：** 悉尼、布里斯班、珀斯

---

## 2. 系统架构

### 2.1 两部分系统

| 部分 | 名称 | 目的 | 输出 |
|------|------|------|------|
| 第1部分 | 对话层 | 引导式 AI 对话，通过4个模块明确买家需求 | 结构化 UserNeeds JSON |
| 第2部分 | 数据Agent层 | 意图驱动的专业Agent编排，检索和综合房产数据 | 房产推荐 + 详细报告 |

### 2.2 第1部分 — 对话层

#### 2.2.1 模块序列

| 模块 | 名称 | 收集的关键信息 | 敏感？ |
|------|------|----------------|--------|
| M1 | 房产需求 | 房产类型、卧室、浴室、车位、土地面积、特性、预期用途 | 否 |
| M2 | 生活方式 | 家庭规模、子女、学区需求、宠物、在家办公、租客画像（投资者） | 否 |
| M3 | 郊区偏好 | 通勤目的地、最长通勤时间、交通方式、生活氛围、排除区域 | 否 |
| M4 | 预算 | 预算范围、首付金额、税前薪资、联合申请、首次购房者状态 | 是 — 最后收集 |

M4（预算）最后收集，因为它包含敏感财务信息。先收集房产需求（M1）也使 AI 能够智能地将 M2 问题情境化——4卧室房屋买家会收到与1卧室公寓买家不同的生活方式问题。

#### 2.2.2 模块跳转逻辑

用户可以随时提供任何模块的信息。AI 接受并记录乱序信息，然后重定向回当前未完成的模块。这防止用户感到被僵化的序列所束缚，同时确保最终收集所有必填字段。

#### 2.2.3 Redis 会话 Schema

```json
{
  "sessionId":         "uuid-v4",
  "userId":            "user_id | browser_fingerprint",
  "status":            "IN_PROGRESS | REQUIREMENTS_COMPLETE",
  "currentModule":     "M1_PROPERTY_NEEDS",
  "completionStatus":  { "M1": false, "M2": false, "M3": false, "M4": false },
  "collectedData":     { "...所有字段，未收集前为null" },
  "conversationHistory": [ "...LLM上下文的原始消息数组" ],
  "finalNeeds":        null,
  "createdAt":         "ISO timestamp",
  "lastActiveAt":      "ISO timestamp",
  "ttl":               604800
}
```

#### 2.2.4 工具调用 — 单次 API 调用模式

每条用户消息触发一次 OpenRouter API 调用，同时返回对话回复（content 字段）和结构化字段提取（tool_calls 字段）。工具名称：`extract_requirements`。

```json
{
  "extracted": {
    "property_type":    "house|townhouse|unit|apartment|villa|any|null",
    "min_bedrooms":     "number | null",
    "max_bedrooms":     "number | null",
    "min_bathrooms":    "number | null",
    "min_carspaces":    "number | null",
    "min_land_size":    "number | null",
    "max_land_size":    "number | null",
    "wants_pool":       "boolean | null",
    "wants_outdoor":    "boolean | null",
    "wants_study":      "boolean | null",
    "intended_use":     "owner_occupier|investment|both|null",
    "household_size":   "number | null",
    "has_children":     "boolean | null",
    "needs_school_zone": "boolean | null",
    "has_pets":         "boolean | null",
    "work_from_home":   "boolean | null",
    "target_tenant":    "family|professional|student|any|null",
    "commute_destination": "string | null",
    "commute_max_mins": "number | null",
    "commute_mode":     "train|car|tram|bus|any|null",
    "preferred_suburbs": "list | null",
    "excluded_suburbs": "list | null",
    "lifestyle_vibe":   "inner_city|suburban|leafy|coastal|any|null",
    "budget_min":       "number | null",
    "budget_max":       "number | null",
    "deposit_amount":   "number | null",
    "pre_tax_salary":   "number | null",
    "is_joint":         "boolean | null",
    "partner_salary":   "number | null",
    "first_home_buyer": "boolean | null"
  },
  "module_complete":  "boolean",
  "next_question":    "string",
  "user_intent":      "answering|asking_question|changing_topic|confused|done"
}
```

---

## 3. AI 护栏规则

> 🔄 **v1.1 变更：** 针对买家服务场景全面更新。删除了与建筑商相关的规则。新增规则5：投资回报预测（ASIC边界）。

对话 AI 充当博学、中立的房产购买助手——而非持牌买家中介、财务顾问或法律专业人士。六条护栏规则定义了 AI 行为的硬性边界。

### 规则1 — 房产推荐请求

**触发：** "我应该买这处房产吗？" / "哪个郊区最适合我？" / "这是个好买卖吗？"

- **绝不：** 给出直接推荐（"我建议你购买此房产"）
- **始终：** 呈现数据和分析维度。"以下是关于此郊区/房产的数据显示。最终决定由您做出——我在这里确保您拥有所有信息。"

### 规则2 — 市场信息请求

**触发：** "这个郊区大多数人支付多少？" / "Hawthorn3居室的典型价格是多少？"

- **允许：** 提供真实市场数据（中位价、近期销售、市场天数、历史趋势）
- **必须：** 在市场数据之后始终提问，将焦点引回用户的具体需求

### 规则3 — 预算缺口检测

**触发：** 用户的预算明显低于其所述需求和目标区域的市场价格

- **绝不：** 默默记录差距并继续而不提醒用户
- **始终：** 直接而友善地指出差距。"根据当前市场数据，您的预算可能无法覆盖[区域]的[房产类型]——中位价约为$Y。您是否希望探索附近区域、调整房产类型或重新考虑预算？"

### 规则4 — 法律和合规问题

**触发：** 合同条款、产权问题、分区合规、地役权、议会法规、叠加层影响

- **允许：** 用通俗语言解释叠加层或区域类型的含义，将其标记为需调查的因素
- **绝不：** 提供具体法律建议或确认某事是否合规
- **始终：** 引导用户联系律师、产权转让师或相关议会

### 规则5 — 投资回报预测

**触发：** "这个郊区会升值吗？" / "我可以期待什么样的租金收益？" / "这是个好投资吗？"

**关键法律边界：** 在没有澳大利亚金融服务许可证（AFSL）的情况下提供投资回报预测，可能构成2001年《公司法》下的无证金融建议。

- **允许：** 历史租金收益数据、历史价格增长、当前空置率
- **绝不：** "这是个好投资"或任何对未来资本增长或租金回报的预测
- **始终附加：** "过去的表现不代表未来的回报。如需投资建议，请咨询持牌财务顾问。"

### 规则6 — 角色身份

**触发：** "你是什么？" / "你是房地产中介吗？" / "你能保证这些信息吗？"

**标准回应：** "我是一个 AI 房产研究助手。我帮助您了解自己的需求、分析郊区和房产，并从公共和授权来源中提取相关数据。我不是持牌买家中介、财务顾问或法律专业人士——如需这些服务，请联系相应的专业人士。"

---

## 4. 第2部分 — 数据Agent层

> 🔄 **v1.1 变更：** 编排器重新设计为带动态Agent调度的意图路由器。引入两种执行模式。第1阶段Agent从5个扩展至7个。

### 4.1 两种执行模式

| 模式 | 名称 | 工作方式 | 最适用于 |
|------|------|----------|----------|
| A | 代码驱动调度 | 编排器分类意图，选择固定Agent集，通过 `asyncio.gather()` 并行运行 | 已知的结构化任务：房产详情、郊区推荐 |
| B | LLM 自主循环 | LLM 将全部7个Agent作为工具，自主决定调用哪些、以何种顺序，直至获得足够信息 | 开放性问题："告诉我关于Carlton的情况" / "这个区域适合家庭吗？" |

### 4.2 意图分类（模式A）

> 🔄 **v1.1 变更：** 取代之前的"并行启动所有Agent"方式，改为上下文感知调度。

| 用户意图 | 示例触发 | 调度的Agent | 模式 |
|----------|----------|-------------|------|
| recommend_suburbs | "显示匹配的郊区" | 郊区 + 价格 | A |
| list_properties | "为我寻找房产" | 郊区 + 价格 | A |
| property_detail | 用户选择特定房源 | 叠加层+学校+建筑+价格+邻里+交通 | A（并行） |
| compare_properties | "比较这两处房产" | 价格+叠加层+学校+建筑+邻里+交通 | A（并行） |
| open_ended_query | "Carlton适合家庭吗？" / "告诉我关于这个区域" | LLM 自主决定 | B |

### 4.3 第1阶段Agent（MVP — 7个Agent）

> 🔄 **v1.1 变更：** 邻里Agent和交通Agent加入第1阶段。原为5个Agent。

| Agent | 职责 | 数据源 | 使用LLM | 超时 |
|-------|------|--------|---------|------|
| 郊区Agent | 根据UserNeeds推荐匹配郊区 | Domain API（郊区档案、中位价） | 是（轻量） | 8秒 |
| 价格Agent | 郊区或特定房产的价格分析 | Domain API + 维州政府季度数据 | 是（轻量） | 8秒 |
| 叠加层Agent | 地址的规划区域和所有叠加层类型 | Vicmap Planning REST API | 否 | 6秒 |
| 学校Agent | 政府学校学区划定 | data.vic.gov.au 学区GeoJSON + shapely空间查询 | 否 | 5秒 |
| 建筑Agent | 建造年份、许可历史、材料风险标志 | VBA许可活动数据 + Domain房产属性 | 是（轻量） | 6秒 |
| 邻里Agent | 500m–2km半径内的步行性、便利设施 | Google Places API | 是（轻量） | 8秒 |
| 交通Agent | 公共交通选择、到目的地的通勤时间 | PTV API + Google距离矩阵 | 否/轻量 | 8秒 |

### 4.4 数据连接器层

所有Agent通过共享连接器类访问外部数据。连接器处理认证、速率限制、重试逻辑和缓存。更改数据源只需更新连接器——Agent业务逻辑不变。

| 连接器 | 使用方 | 认证 |
|--------|--------|------|
| DomainConnector | 郊区、价格、建筑Agent | API密钥（环境变量） |
| GovernmentConnector | 叠加层、学校Agent | 无（公共API）— 回退到S3的本地GeoJSON快照 |
| VBAConnector | 建筑Agent | 无（公开数据） |
| GooglePlacesConnector | 邻里Agent | API密钥（环境变量） |
| PTVConnector | 交通Agent | API密钥（环境变量） |

### 4.5 错误处理

| 场景 | 优先级 | 策略 |
|------|--------|------|
| 地址地理编码失败 | 阻塞所有 | 向用户返回候选列表——不启动Agent |
| API速率限制（429） | 任意Agent | 指数退避 0.5s→1s→2s → 从缓存提供 |
| 政府API宕机 | 叠加层/学校 | 回退到本地GeoJSON快照（每周同步至S3） |
| ≥3个关键Agent失败 | 郊区、价格、叠加层 | 中止，向用户返回明确错误消息 |
| LLM输出格式错误 | 综合Agent | 降级为使用原始Agent数据的模板渲染 |

### 4.6 缓存策略（Redis）

| 数据 | 键模式 | TTL |
|------|--------|-----|
| 叠加层 | overlay:{lat}:{lng} | 7天 |
| 学区 | school:{lat}:{lng} | 30天 |
| 价格数据 | price:{suburb} | 24小时 |
| 房产报告 | report:{property_id} | 6小时 |
| 结果缓存（第2阶段） | result:{type}:{beds}:{budget_bucket}:{vibe} | 24小时 |

---

## 5. Agent路线图

> 🔄 **v1.1 变更：** 第2和第3阶段从之前的独立阶段合并。

### 5.1 第1阶段（MVP — 当前）

郊区、价格、叠加层、学校、建筑、邻里、交通。

### 5.2 第2阶段

| Agent | 职责 | 数据源 |
|-------|------|--------|
| 犯罪Agent | 按郊区和罪行类型统计犯罪数据 | 维多利亚警察犯罪统计局 |
| 开发Agent | 已批准的DA、房产附近基础设施管道 | 维州规划开发申请（公开） |
| 可比销售Agent | 近期可比销售，用于验证房产定价 | Domain API（已售房源） |
| 结果缓存 | 为相似买家画像返回缓存郊区推荐 | Redis — 键：type+beds+budget_bucket+vibe |

### 5.3 第3阶段

| Agent | 职责 | 数据源 |
|-------|------|--------|
| 物业/OC Agent | OC费用、特别征费、会议记录（用户上传文件） | 用户上传的PDF，由LLM解析 |
| 拍卖Agent | 成交率、流拍统计、拍卖vs私售价差 | Domain API（拍卖结果） |
| 租金收益Agent | 当前租房房源、空置率、增长趋势（投资者） | Domain API + SQM Research |
| 保险Agent | 洪水、山火、风暴风险评级 | 保险委员会澳大利亚风险地图 |

---

## 6. 数据源

| 数据 | 来源 | 费用 | 更新频率 |
|------|------|------|----------|
| 房源+已售数据 | Domain Developer API | 免费套餐（MVP） | 实时 |
| 郊区中位价 | Domain Developer API | 免费套餐（MVP） | 每日 |
| 规划区域+叠加层 | Vicmap Planning REST API | 免费 | 每周 |
| 洪水+灾害风险 | data.vic.gov.au GeoJSON | 免费 | 定期 |
| 遗产叠加层 | 维多利亚遗产局 | 免费 | 定期 |
| 学区边界 | data.vic.gov.au | 免费 | 每年 |
| 建筑许可记录 | VBA许可活动数据 | 免费 | 每月 |
| 郊区季度价格 | 维州政府统计数据 | 免费 | 每季度 |
| 邻里便利设施 | Google Places API | 按使用量付费 | 实时 |
| 交通/通勤时间 | PTV API + Google Maps | 免费/按使用量付费 | 实时 |

### 6.1 已知限制

- **每套房产历史价格曲线：** 需要Domain商业套餐或PropTrack（约$79/月）。MVP使用郊区级别的政府季度数据作为替代。
- **结构图纸/基础平面图：** 未经业主授权无法通过程序获取。以建造年份+许可历史+材料风险推断代替。
- **私立学校学区：** 无统一数据集。以Google Places API半径搜索补充。

---

## 7. 技术栈

> 🔄 **v1.1 变更：** 完整技术栈已确认。选择Python而非TypeScript。选择OpenRouter作为统一LLM网关。明确不使用LangChain。

### 7.1 栈概览

| 层级 | 技术 | 理由 |
|------|------|------|
| 后端框架 | Python 3.11+ + FastAPI | 异步优先，IO密集型工作负载，最佳AI生态，空间库支持 |
| LLM网关 | OpenRouter | Claude（Anthropic）、GPT-4o（OpenAI）、DeepSeek的统一API — 仅通过配置切换模型 |
| LLM SDK | OpenAI Python SDK | OpenRouter兼容OpenAI；DeepSeek也使用OpenAI格式；一个SDK涵盖全部三个提供商 |
| Agent框架 | 无（自定义） | 不使用LangChain — 代码控制所有调度逻辑，LLM仅处理对话和开放性查询 |
| 会话存储 | Redis（redis-py async） | 快速内存会话状态、TTL管理、Agent结果缓存 |
| 数据库 | PostgreSQL（asyncpg） | 用户账户、会话历史、保存的报告 |
| 空间查询 | shapely + geopandas | 叠加层和学校Agent的点在多边形内判断 — TS无可行替代方案 |
| HTTP客户端 | httpx（async） | 所有数据连接器的异步外部API调用 |
| 前端 | React（TypeScript） | Web优先，桌面端优先，响应式 |
| 容器 | Docker + docker-compose | 单EC2部署，所有服务共处一机 |

### 7.2 LLM提供商配置

```python
# 通过OpenRouter接入全部三个提供商 — 相同代码，不同模型字符串
from openai import AsyncOpenAI
client = AsyncOpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)

# 仅通过更改模型字符串来切换提供商
MODEL_STRONG = "anthropic/claude-sonnet-4-5"   # 默认：最强推理
MODEL_STRONG = "openai/gpt-4o"                  # 备选
MODEL_STRONG = "deepseek/deepseek-chat"         # 成本优化选项

MODEL_FAST   = "anthropic/claude-haiku-4-5"    # 默认：数据提取
MODEL_FAST   = "openai/gpt-4o-mini"             # 备选
MODEL_FAST   = "deepseek/deepseek-chat"         # 成本优化选项
```

### 7.3 为什么不使用LangChain

LangChain 专为 LLM 驱动的控制流设计（由LLM决定调用哪些工具及顺序）。PropertyAI 对结构化任务使用代码驱动的控制流——编排器决定调用哪些Agent。LangChain 在此架构中增加了抽象而不增加价值。

LangChain 适用于：在大型文档语料库上构建RAG管道、实现带可复用组件的多步推理链，或在不考虑生产可维护性的情况下快速原型开发。

模式B（LLM自主循环）直接使用OpenRouter / OpenAI SDK的原生工具调用循环实现——无需框架。

---

## 8. 部署架构

### 8.1 MVP基础设施

> **策略：** 单EC2实例运行Docker Compose。所有服务共处一机。部署简单，易于调试，约$43–$74/月。当规模需要时有明确的升级路径至ECS Fargate。

| 组件 | 技术 | 月成本 |
|------|------|--------|
| 计算 | EC2 t3.small（2vCPU / 2GB） | ~$17 |
| 存储 | EBS gp3 20GB | ~$2 |
| CDN+前端 | CloudFront + S3 | ~$2 |
| DNS | Route 53 | ~$1 |
| 密钥 | AWS Secrets Manager | <$1 |
| 监控 | CloudWatch日志+告警 | <$1 |
| LLM API | OpenRouter（Claude/GPT/DeepSeek） | ~$20–$50 |
| **合计** | | **~$43–$74/月** |

### 8.2 Docker Compose服务

```yaml
services:
  nginx:     # 反向代理、HTTPS、静态文件服务
  app:       # FastAPI后端
             #   - 第1部分：对话服务 + 会话管理
             #   - 第2部分：编排器（模式A + 模式B）
             #   - 全部7个Agent + 数据连接器
             #   - OpenRouter API调用
  redis:     # 会话存储 + Agent结果缓存
  postgres:  # 用户账户、历史记录、保存的报告
```

### 8.3 升级路径

| 触发条件 | 升级方案 |
|----------|----------|
| 流量增长 | EC2+Docker Compose → ECS Fargate（拆分为独立服务） |
| 需要高可用 | Redis容器 → ElastiCache多可用区 |
| 需要高可用 | Postgres容器 → RDS PostgreSQL多可用区 |
| 规模化后的成本+安全 | OpenRouter → Amazon Bedrock（VPC内部、IAM认证、无API密钥） |

---

## 9. 功能优先级（MoSCoW）

### 9.1 必须有 — MVP

- AI 对话界面（4模块引导式对话 M1→M4）
- 带 Redis 会话持久化的工具调用字段提取（TTL 7天）
- 模块跳转逻辑 — 接受并记录乱序信息
- 系统提示中强制执行全部6条护栏规则
- 第1部分到第2部分的 UserNeeds JSON 交接
- Agent调度前的意图分类（模式A）
- 全部7个第1阶段Agent实现，含数据连接器
- 开放性查询的模式B LLM自主循环
- 编排器错误处理（地理编码预检、超时、失败阈值）
- 房产推荐列表（郊区+房源结果）
- 房产详情报告（7个Agent综合）
- Web前端（React/TS，桌面优先，响应式）
- 用户账户（保存的搜索、保存的房产、报告历史）

### 9.2 应该有 — v1发布

- 新匹配房源的保存搜索邮件提醒
- 房产对比视图（并排，最多3处房产）
- 报告导出为PDF
- 预算缺口检测，含备选郊区建议
- 根据薪资输入估算借款能力

### 9.3 可以有 — 第2阶段

- 相似买家画像的结果级缓存
- 犯罪Agent、开发Agent、可比销售Agent
- 中文界面选项
- 用于在 Domain/REA 上分析房产的浏览器扩展

### 9.4 不会有 — 明确排除

- 投资回报预测（ASIC / 公司法边界）
- 房产交易促成或市场平台
- 买家中介谈判服务
- 平面图或3D渲染生成
- 合同或产权法律建议

---

## 10. 非功能性需求

| 类别 | 需求 | 目标 |
|------|------|------|
| 性能 | AI对话首个token | < 3秒（启用流式传输） |
| 性能 | 房产详情报告（所有Agent） | < 15秒 |
| 性能 | 页面首次内容绘制 | < 2秒 |
| 可用性 | MVP正常运行时间 | 99%（单EC2，无高可用） |
| 安全 | API密钥 | 仅限AWS Secrets Manager — 永不存入代码或提交至git的.env文件 |
| 安全 | 静态数据 | 启用EBS加密 |
| 安全 | 传输 | 仅HTTPS（nginx + Let's Encrypt） |
| 隐私 | 1988年澳大利亚隐私法 | 发布时需要隐私政策页面 |
| 隐私 | AI训练使用 | 用户数据不得用于模型训练 — 在隐私政策中声明 |
| 法律 | 财务建议 | 投资预测被护栏规则5阻止 |
| 法律 | 房地产许可证 | 不得越入持牌买家中介领域 |
| 浏览器 | 桌面端 | Chrome、Safari、Edge — 最新2个版本 |
| 浏览器 | 移动端 | iOS Safari、Android Chrome — 响应式布局 |

---

## 11. 成功指标（MVP）

| 指标 | 目标 | 测量方式 |
|------|------|----------|
| 对话完成率 | > 40% 完成全部4个模块 | Redis/Postgres中的会话状态 |
| 平均对话时长 | 第1部分 < 15分钟 | 会话中的时间戳差值 |
| 报告生成率 | > 60% 的完成对话生成≥1份报告 | 报告创建事件 |
| 报告有用性 | 用户评分为有用或非常有用 | 报告生成后的应用内评分 |
| Agent成功率 | > 95% 的Agent调用返回可用数据 | CloudWatch Agent错误指标 |
| 会话恢复率 | > 20% 的未完成会话被恢复 | 具有多个lastActiveAt值的会话 |

---

## 12. 待解问题

| 问题 | 影响 | 截止时间 |
|------|------|----------|
| OpenRouter数据驻留 | 用户对话数据经过OpenRouter服务器 — 确认在隐私法下可接受 | 发布前 |
| Domain API商业套餐时机 | 发布时提供每套房产历史价格图表？ | v1发布前 |
| Google Places API成本模型 | 邻里Agent每次房产查看时运行 — 估算规模化成本 | v1发布前 |
| 用户认证方式 | 邮箱/密码 vs Google OAuth vs 魔法链接 | Sprint 1 |
| 免费增值vs付费模式 | 免费对话、付费报告？完全免费MVP？ | 发布前 |
| 规则5法律审查 | 确认ASIC / 2001年公司法边界是否充分 | 发布前 |
| PTV API访问 | 确认API密钥申请已批准且速率限制充足 | Sprint 2 |

---

## 附录A — 覆盖的叠加层类型

| 代码 | 名称 | 买家相关性 |
|------|------|------------|
| FO | 河道叠加层 | 高 — 重大事件中房产可能被淹 |
| LSIO | 洪水区域叠加层 | 高 — 洪水风险区域 |
| SBO | 特殊建筑叠加层 | 高 — 排水/洪水风险 |
| BMO / WMO | 山火/野火管理叠加层 | 高 — 火灾风险，建筑要求 |
| HO | 遗产叠加层 | 中 — 对房产改造的限制 |
| VPO | 植被保护叠加层 | 中 — 树木移除限制 |
| ESO | 环境重要性叠加层 | 中 — 环境约束 |
| EMO | 侵蚀管理叠加层 | 中 — 土壤不稳定风险 |
| EAO | 环境审计叠加层 | 高 — 潜在污染 |
| DDO | 设计和开发叠加层 | 低-中 — 未来开发指引 |

---

## 附录B — 系统提示结构

```
# 系统提示每次请求动态生成

1. 角色定义
   "你是澳大利亚市场的AI房产购买助手。"
   "你的职责是通过自然对话收集买家需求。"
   "你不是持牌买家中介、财务顾问或法律专业人士。"

2. 当前状态注入
   "当前模块：{M1_PROPERTY_NEEDS}"
   "已完成模块：{completed_list}"
   "已收集：{collected_data_summary}"
   "缺失必填字段：{missing_fields}"

3. M1→M2推断上下文（M1完成时注入）
   例："用户想要4+卧室住宅 — M2聚焦家庭、子女、学区。"
   例："用户想要投资房产 — M2聚焦租客画像、收益优先级。"

4. 全部6条护栏规则（缩略）
   规则1：房产推荐 → 拒绝，仅呈现数据
   规则2：市场信息 → 提供，然后提出跟进问题
   规则3：预算缺口 → 直接友善地指出
   规则4：法律/合规 → 解释，转介给专业人士
   规则5：投资预测 → 仅历史数据 + ASIC免责声明
   规则6：角色身份 → 透明说明边界
```
