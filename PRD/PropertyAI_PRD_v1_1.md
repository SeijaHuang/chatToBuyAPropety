# PropertyAI — Product Requirements Document

**Version:** v1.1 · Confidential

---

| Field | Value |
|---|---|
| Version | v1.1 |
| Status | Draft — for development |
| Target Market | Melbourne, Australia (VIC) — expand nationally |
| Property Type | Established residential (second-hand) |
| Users | Home buyers & investors |
| Deployment | AWS ap-southeast-2 (Sydney) |
| Last Updated | 3 May 2026 |

**Changes in v1.1:** Updated guardrail rules for buyer-service context (not builder-service). Part 2 Orchestrator redesigned as intent router with two execution modes. Phase 1 agents expanded to 7 (added Neighbourhood + Transport). Technology stack confirmed: Python + FastAPI + OpenRouter + shapely.

---

# 1. Product Overview

## 1.1 Problem Statement

Buying property in Australia is one of the most significant financial decisions a person makes, yet buyers are poorly served by existing tools. Current platforms (Domain, REA) are listing aggregators — they show what is available but provide no intelligence about whether a property suits the buyer, what risks it carries, or how it compares to alternatives.

Buyers face three core problems:

- They cannot clearly articulate what they actually need — requirements remain vague until structured through guided dialogue
- They lack access to consolidated property intelligence — overlay risks, school zones, infrastructure, building history, and price trends are scattered across a dozen separate sources
- They have no trusted, neutral advisor — traditional buyer's agents are expensive and inaccessible to most buyers

## 1.2 Product Positioning

> **Core Value Proposition:** PropertyAI is an AI-powered property buying assistant for the Australian market. It helps buyers clarify their requirements through guided conversation, recommends matching suburbs and properties, and generates comprehensive property intelligence reports — acting as a knowledgeable, neutral advisor at every stage of the buying journey.

## 1.3 Hard Boundaries (What the Product Does NOT Do)

- Does not provide investment advice or predict future returns (ASIC / Corporations Act 2001 boundary)
- Does not provide legal advice on contracts, title, or conveyancing
- Does not replace a licensed buyer's agent for negotiation
- Does not generate floor plans, 3D renders, or building designs
- Does not facilitate property transactions or act as a marketplace

## 1.4 Target Users

| Segment | Description | Primary Need |
|---|---|---|
| Owner-occupier | Individual or couple buying a home to live in | Find the right property in the right suburb for their lifestyle |
| Property investor | Buying for rental income or capital growth | Analyse yield potential, growth trends, and risk factors |
| Upgrader / downsizer | Moving from existing property, has equity | Match property to life stage change efficiently |

## 1.5 Geographic Scope

- Phase 1 (MVP): Melbourne metropolitan area
- Phase 2: Victorian regional centres (Geelong, Ballarat, Bendigo)
- Phase 3: Sydney, Brisbane, Perth

---

# 2. System Architecture

## 2.1 Two-Part System

| Part | Name | Purpose | Output |
|---|---|---|---|
| Part 1 | Conversation Layer | Guided AI dialogue to clarify buyer requirements across 4 modules | Structured UserNeeds JSON |
| Part 2 | Data Agent Layer | Intent-driven orchestration of specialist agents to retrieve and synthesise property data | Property recommendations + detailed reports |

## 2.2 Part 1 — Conversation Layer

### 2.2.1 Module Sequence

| Module | Name | Key Information Collected | Sensitive? |
|---|---|---|---|
| M1 | Property Needs | Property type, bedrooms, bathrooms, car spaces, land size, features, intended use | No |
| M2 | Lifestyle | Household size, children, school zone needs, pets, WFH, tenant profile (investors) | No |
| M3 | Suburb Preference | Commute destination, max commute time, transport mode, lifestyle vibe, excluded areas | No |
| M4 | Budget | Budget range, deposit amount, pre-tax salary, joint application, first home buyer status | Yes — collected last |

Budget (M4) is collected last because it contains sensitive financial information. Collecting property needs first (M1) also allows the AI to contextualise M2 questions intelligently — a 4-bedroom house buyer receives different lifestyle questions than a 1-bedroom unit buyer.

### 2.2.2 Module Jump Logic

Users may volunteer information from any module at any time. The AI accepts and records out-of-order information, then redirects back to the current incomplete module. This prevents users from feeling constrained by a rigid sequence while ensuring all required fields are eventually collected.

### 2.2.3 Redis Session Schema

```json
{
  "sessionId":         "uuid-v4",
  "userId":            "user_id | browser_fingerprint",
  "status":            "IN_PROGRESS | REQUIREMENTS_COMPLETE",
  "currentModule":     "M1_PROPERTY_NEEDS",
  "completionStatus":  { "M1": false, "M2": false, "M3": false, "M4": false },
  "collectedData":     { "...all fields, null until collected" },
  "conversationHistory": [ "...raw message array for LLM context" ],
  "finalNeeds":        null,
  "createdAt":         "ISO timestamp",
  "lastActiveAt":      "ISO timestamp",
  "ttl":               604800
}
```

### 2.2.4 Tool Use — Single API Call Pattern

Each user message triggers a single OpenRouter API call that simultaneously returns a conversational reply (`content` field) and structured field extraction (`tool_calls` field). Tool name: `extract_requirements`.

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

# 3. AI Guardrail Rules

> 🔄 **v1.1 Change:** Fully updated for buyer-service context. Removed builder-related rules. Added Rule 5: Investment Return Predictions (ASIC boundary).

The conversation AI acts as a knowledgeable, neutral property buying assistant — not a licensed buyer's agent, financial advisor, or legal professional. Six guardrail rules define the hard boundaries of AI behaviour.

## Rule 1 — Property Recommendation Requests

**Trigger:** "Should I buy this property?" / "Which suburb is best for me?" / "Is this a good buy?"

- **Never:** Give a direct recommendation ("I recommend you buy this property").
- **Always:** Present data and analysis dimensions. "Here is what the data shows about this suburb / property. The final decision is yours — I'm here to make sure you have all the information."

## Rule 2 — Market Information Requests

**Trigger:** "What do most people pay in this suburb?" / "What's the typical price for a 3-bed house in Hawthorn?"

- **Allowed:** Provide factual market data (median prices, recent sales, days on market, historical trends).
- **Required:** Always follow market data with a question that returns focus to the user's specific needs.

## Rule 3 — Budget Shortfall Detection

**Trigger:** User's stated budget is materially below market prices for their stated requirements and target area.

- **Never:** Record the mismatch silently and continue without alerting the user.
- **Always:** Directly and kindly flag the gap. "Based on current market data, your budget may not cover a [property type] in [area] — median prices are around $Y. Would you like to explore nearby areas, adjust the property type, or revisit the budget?"

## Rule 4 — Legal and Compliance Questions

**Trigger:** Contract terms, title issues, zoning compliance, easements, council regulations, overlay implications.

- **Allowed:** Explain what an overlay or zone type means in plain language. Flag it as a factor to investigate.
- **Never:** Give specific legal advice or confirm whether something is compliant.
- **Always:** Direct the user to a solicitor, conveyancer, or the relevant council.

## Rule 5 — Investment Return Predictions

**Trigger:** "Will this suburb go up in value?" / "What rental yield can I expect?" / "Is this a good investment?"

**Critical legal boundary:** Providing investment return predictions without an Australian Financial Services Licence (AFSL) may constitute unlicensed financial advice under the Corporations Act 2001.

- **Allowed:** Historical rental yield data, historical price growth, current vacancy rates.
- **Never:** "This is a good investment" or any prediction of future capital growth or rental returns.
- **Always append:** "Past performance is not an indicator of future returns. For investment advice, please consult a licensed financial advisor."

## Rule 6 — Role Identity

**Trigger:** "What are you?" / "Are you a real estate agent?" / "Can you guarantee this information?"

**Standard response:** "I'm an AI property research assistant. I help you understand your requirements, analyse suburbs and properties, and surface relevant data from public and licensed sources. I'm not a licensed buyer's agent, financial advisor, or legal professional — for those services please engage the appropriate professionals."

---

# 4. Part 2 — Data Agent Layer

> 🔄 **v1.1 Change:** Orchestrator redesigned as intent router with dynamic agent dispatch. Two execution modes introduced. Phase 1 agents expanded from 5 to 7.

## 4.1 Two Execution Modes

| Mode | Name | How It Works | Best For |
|---|---|---|---|
| A | Code-Driven Dispatch | Orchestrator classifies intent, selects a fixed agent set, runs them in parallel via `asyncio.gather()` | Known, structured tasks: property detail, suburb recommendations |
| B | LLM Agentic Loop | LLM receives all 7 agents as tools and autonomously decides which to call, in what order, until it has enough information | Open-ended questions: "Tell me about Carlton" / "Is this area good for families?" |

## 4.2 Intent Classification (Mode A)

> 🔄 **v1.1 Change:** Replaces the previous "launch all agents in parallel" approach with context-aware dispatch.

| User Intent | Example Trigger | Agents Dispatched | Mode |
|---|---|---|---|
| recommend_suburbs | "Show me matching suburbs" | Suburb + Price | A |
| list_properties | "Find properties for me" | Suburb + Price | A |
| property_detail | User selects a specific listing | Overlay + School + Building + Price + Neighbourhood + Transport | A (parallel) |
| compare_properties | "Compare these two properties" | Price + Overlay + School + Building + Neighbourhood + Transport | A (parallel) |
| open_ended_query | "Is Carlton good for families?" / "Tell me about this area" | LLM decides autonomously | B |

## 4.3 Phase 1 Agents (MVP — 7 Agents)

> 🔄 **v1.1 Change:** Added Neighbourhood Agent and Transport Agent to Phase 1. Originally 5 agents.

| Agent | Responsibility | Data Sources | LLM | Timeout |
|---|---|---|---|---|
| Suburb Agent | Recommend matching suburbs based on UserNeeds | Domain API (suburb profiles, median prices) | Yes (light) | 8s |
| Price Agent | Price analysis for suburb or specific property | Domain API + VIC govt quarterly data | Yes (light) | 8s |
| Overlay Agent | Planning zones and all overlay types for an address | Vicmap Planning REST API | No | 6s |
| School Agent | Government school zone catchments | data.vic.gov.au school zone GeoJSON + shapely spatial query | No | 5s |
| Building Agent | Construction year, permit history, material risk flags | VBA Permit Activity Data + Domain property attributes | Yes (light) | 6s |
| Neighbourhood Agent | Walkability, amenities within 500m–2km radius | Google Places API | Yes (light) | 8s |
| Transport Agent | Public transport options, commute time to destination | PTV API + Google Distance Matrix | No / light | 8s |

## 4.4 Data Connector Layer

All agents access external data via shared connector classes. Connectors handle authentication, rate limiting, retry logic, and caching. Changing a data source only requires updating the connector — agent business logic is unchanged.

| Connector | Used By | Auth |
|---|---|---|
| DomainConnector | Suburb, Price, Building agents | API key (env var) |
| GovernmentConnector | Overlay, School agents | None (public API) — fallback to local GeoJSON snapshot in S3 |
| VBAConnector | Building agent | None (public data) |
| GooglePlacesConnector | Neighbourhood agent | API key (env var) |
| PTVConnector | Transport agent | API key (env var) |

## 4.5 Error Handling

| Scenario | Priority | Strategy |
|---|---|---|
| Address geocode fails | Blocks all | Return candidate list to user — do not start agents |
| API rate limit (429) | Any agent | Exponential backoff 0.5s→1s→2s → serve from cache |
| Government API down | Overlay / School | Fallback to local GeoJSON snapshot (synced weekly to S3) |
| ≥3 critical agents fail | Suburb, Price, Overlay | Abort, return clear error message to user |
| LLM output malformed | Synthesis agent | Degrade to template render using raw agent data |

## 4.6 Cache Strategy (Redis)

| Data | Key Pattern | TTL |
|---|---|---|
| Overlay | `overlay:{lat}:{lng}` | 7 days |
| School zones | `school:{lat}:{lng}` | 30 days |
| Price data | `price:{suburb}` | 24 hours |
| Property report | `report:{property_id}` | 6 hours |
| Result cache (Phase 2) | `result:{type}:{beds}:{budget_bucket}:{vibe}` | 24 hours |

---

# 5. Agent Roadmap

> 🔄 **v1.1 Change:** Phase 2 and 3 consolidated from previous separate phases.

## 5.1 Phase 1 (MVP — current)

Suburb, Price, Overlay, School, Building, Neighbourhood, Transport.

## 5.2 Phase 2

| Agent | Responsibility | Data Source |
|---|---|---|
| Crime Agent | Crime statistics by suburb and offence type | Victoria Police Crime Statistics Agency |
| Development Agent | Approved DAs, infrastructure pipeline near property | VIC Planning Development Applications (public) |
| Comparable Sales Agent | Recent comparable sales to validate property pricing | Domain API (sold listings) |
| Result Cache | Return cached suburb recommendations for similar buyer profiles | Redis — key: type+beds+budget_bucket+vibe |

## 5.3 Phase 3

| Agent | Responsibility | Data Source |
|---|---|---|
| Strata / OC Agent | OC fees, special levies, meeting minutes (user uploads document) | User-uploaded PDFs parsed by LLM |
| Auction Agent | Clearance rates, passed-in stats, auction vs private price differential | Domain API (auction results) |
| Rental Yield Agent | Current rental listings, vacancy rates, growth trends (investors) | Domain API + SQM Research |
| Insurance Agent | Flood, bushfire, storm risk ratings | Insurance Council of Australia risk maps |

---

# 6. Data Sources

| Data | Source | Cost | Update Freq |
|---|---|---|---|
| Listings + sold data | Domain Developer API | Free tier (MVP) | Real-time |
| Suburb median prices | Domain Developer API | Free tier (MVP) | Daily |
| Planning zones + overlays | Vicmap Planning REST API | Free | Weekly |
| Flood + disaster risk | data.vic.gov.au GeoJSON | Free | Periodic |
| Heritage overlays | Heritage Victoria | Free | Periodic |
| School zone boundaries | data.vic.gov.au | Free | Annual |
| Building permit records | VBA Permit Activity Data | Free | Monthly |
| Suburb quarterly prices | VIC Government stats | Free | Quarterly |
| Neighbourhood amenities | Google Places API | Pay-per-use | Real-time |
| Transit / commute times | PTV API + Google Maps | Free / Pay-per-use | Real-time |

## 6.1 Known Limitations

- **Per-property historical price curves:** Requires Domain commercial tier or PropTrack (~$79/month). MVP uses suburb-level quarterly government data as substitute.
- **Structural drawings / foundation plans:** Cannot be obtained programmatically without owner authorisation. Replaced by building year + permit history + material risk inference.
- **Private school catchments:** No unified dataset. Supplement with Google Places API radius search.

---

# 7. Technology Stack

> 🔄 **v1.1 Change:** Full technology stack confirmed. Python selected over TypeScript. OpenRouter selected as unified LLM gateway. LangChain explicitly not used.

## 7.1 Stack Overview

| Layer | Technology | Rationale |
|---|---|---|
| Backend framework | Python 3.11+ + FastAPI | Async-first, IO-intensive workload, best AI ecosystem, spatial library support |
| LLM gateway | OpenRouter | Unified API for Claude (Anthropic), GPT-4o (OpenAI), DeepSeek — model switching via config only |
| LLM SDK | OpenAI Python SDK | OpenRouter is OpenAI-compatible; DeepSeek also uses OpenAI format; one SDK covers all three providers |
| Agent framework | None (custom) | LangChain not used — code controls all dispatch logic, LLM only handles dialogue and open-ended queries |
| Session store | Redis (redis-py async) | Fast in-memory session state, TTL management, agent result cache |
| Database | PostgreSQL (asyncpg) | User accounts, session history, saved reports |
| Spatial queries | shapely + geopandas | Point-in-polygon for Overlay and School agents — no viable TS equivalent |
| HTTP client | httpx (async) | Async external API calls for all data connectors |
| Frontend | React (TypeScript) | Web-first, desktop priority, responsive |
| Container | Docker + docker-compose | Single EC2 deployment, all services co-located |

## 7.2 LLM Provider Configuration

```python
# All three providers via OpenRouter — same code, different model string
from openai import AsyncOpenAI

client = AsyncOpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)

# Switch provider by changing model string only
MODEL_STRONG = "anthropic/claude-sonnet-4-5"   # default: best reasoning
MODEL_STRONG = "openai/gpt-4o"                  # alternative
MODEL_STRONG = "deepseek/deepseek-chat"         # cost-optimised option

MODEL_FAST   = "anthropic/claude-haiku-4-5"    # default: data extraction
MODEL_FAST   = "openai/gpt-4o-mini"             # alternative
MODEL_FAST   = "deepseek/deepseek-chat"         # cost-optimised option
```

## 7.3 Why Not LangChain

LangChain is designed for LLM-driven control flow (the LLM decides which tools to call and in what sequence). PropertyAI uses code-driven control flow for structured tasks — the Orchestrator decides which agents to call. LangChain adds abstraction without adding value for this architecture.

LangChain is appropriate when: building RAG pipelines over large document corpora, implementing multi-step reasoning chains with reusable components, or rapidly prototyping without caring about production maintainability.

Mode B (LLM Agentic Loop) is implemented directly using the OpenRouter / OpenAI SDK's native tool use loop — no framework required.

---

# 8. Deployment Architecture

## 8.1 MVP Infrastructure

> **Strategy:** Single EC2 instance running Docker Compose. All services co-located on one host. Simple to deploy, easy to debug, ~$43–$74/month. Clear upgrade path to ECS Fargate when scale requires.

| Component | Technology | Monthly Cost |
|---|---|---|
| Compute | EC2 t3.small (2vCPU / 2GB) | ~$17 |
| Storage | EBS gp3 20GB | ~$2 |
| CDN + Frontend | CloudFront + S3 | ~$2 |
| DNS | Route 53 | ~$1 |
| Secrets | AWS Secrets Manager | <$1 |
| Monitoring | CloudWatch Logs + Alerts | <$1 |
| LLM API | OpenRouter (Claude / GPT / DeepSeek) | ~$20–$50 |
| **Total** | | **~$43–$74/month** |

## 8.2 Docker Compose Services

```yaml
services:
  nginx:     # Reverse proxy, HTTPS, static file serving
  app:       # FastAPI backend
             #   - Part 1: Conversation service + session management
             #   - Part 2: Orchestrator (Mode A + Mode B)
             #   - All 7 agents + data connectors
             #   - OpenRouter API calls
  redis:     # Session store + agent result cache
  postgres:  # User accounts, history, saved reports
```

## 8.3 Upgrade Path

| Trigger | Upgrade |
|---|---|
| Traffic grows | EC2 + Docker Compose → ECS Fargate (split into separate services) |
| HA required | Redis container → ElastiCache Multi-AZ |
| HA required | Postgres container → RDS PostgreSQL Multi-AZ |
| Cost + security at scale | OpenRouter → Amazon Bedrock (VPC internal, IAM auth, no API key) |

---

# 9. Feature Priority (MoSCoW)

## 9.1 Must Have — MVP

- AI conversation interface (4-module guided dialogue M1→M4)
- Tool use field extraction with Redis session persistence (TTL 7 days)
- Module jump logic — accept and record out-of-order information
- All 6 guardrail rules enforced in system prompt
- UserNeeds JSON handoff from Part 1 to Part 2
- Intent classification before agent dispatch (Mode A)
- All 7 Phase 1 agents implemented with data connectors
- Mode B LLM Agentic Loop for open-ended queries
- Orchestrator error handling (geocode pre-check, timeout, failure threshold)
- Property recommendation list (suburb + listing results)
- Property detail report (all 7 agents synthesised)
- Web frontend (React/TS, desktop-first, responsive)
- User accounts (saved searches, saved properties, report history)

## 9.2 Should Have — v1 Launch

- Saved searches with email alerts for new matching listings
- Property comparison view (side-by-side, up to 3 properties)
- Report export as PDF
- Budget shortfall detection with alternative suburb suggestions
- Borrowing capacity estimate from salary inputs

## 9.3 Could Have — Phase 2

- Result-level caching for similar buyer profiles
- Crime Agent, Development Agent, Comparable Sales Agent
- Chinese language interface option
- Browser extension to analyse properties on Domain/REA

## 9.4 Won't Have — Explicitly Excluded

- Investment return predictions (ASIC / Corporations Act boundary)
- Property transaction facilitation or marketplace
- Buyer's agent negotiation services
- Floor plan or 3D render generation
- Legal advice on contracts or title

---

# 10. Non-Functional Requirements

| Category | Requirement | Target |
|---|---|---|
| Performance | AI conversation first token | < 3 seconds (streaming enabled) |
| Performance | Property detail report (all agents) | < 15 seconds |
| Performance | Page first contentful paint | < 2 seconds |
| Availability | MVP uptime | 99% (single EC2, no HA) |
| Security | API keys | AWS Secrets Manager only — never in code or .env files committed to git |
| Security | Data at rest | EBS encryption enabled |
| Security | Transport | HTTPS only (nginx + Let's Encrypt) |
| Privacy | Australian Privacy Act 1988 | Privacy policy page required at launch |
| Privacy | AI training use | User data must NOT be used for model training — state in privacy policy |
| Legal | Financial advice | Investment predictions blocked by guardrail Rule 5 |
| Legal | Real estate licence | Must not cross into licensed buyer's agent territory |
| Browser | Desktop | Chrome, Safari, Edge — latest 2 versions |
| Browser | Mobile | iOS Safari, Android Chrome — responsive layout |

---

# 11. Success Metrics (MVP)

| Metric | Target | How Measured |
|---|---|---|
| Conversation completion rate | > 40% complete all 4 modules | Session status in Redis / Postgres |
| Avg conversation duration | < 15 minutes for Part 1 | Timestamp delta in session |
| Report generation rate | > 60% of completed conversations generate ≥1 report | Report creation events |
| Report usefulness | User rates useful or very useful | In-app rating after report generation |
| Agent success rate | > 95% of agent calls return usable data | CloudWatch agent error metrics |
| Session resume rate | > 20% of incomplete sessions resumed | Sessions with multiple lastActiveAt values |

---

# 12. Open Questions

| Question | Impact | By |
|---|---|---|
| OpenRouter data residency | User conversation data passes through OpenRouter servers — confirm acceptable under Privacy Act | Before launch |
| Domain API commercial tier timing | Per-property historical price charts at launch? | Before v1 launch |
| Google Places API cost model | Neighbourhood Agent runs per property view — model cost at scale | Before v1 launch |
| User auth method | Email/password vs Google OAuth vs magic link | Sprint 1 |
| Freemium vs paid model | Free conversations, paid reports? Fully free MVP? | Before launch |
| Legal review of Rule 5 | Confirm ASIC / Corporations Act 2001 boundary is sufficient | Before launch |
| PTV API access | Confirm API key application approved and rate limits sufficient | Sprint 2 |

---

# Appendix A — Overlay Types Covered

| Code | Name | Buyer Relevance |
|---|---|---|
| FO | Floodway Overlay | High — property may flood in major events |
| LSIO | Land Subject to Inundation Overlay | High — flood risk area |
| SBO | Special Building Overlay | High — drainage / flood risk |
| BMO / WMO | Bushfire / Wildfire Management Overlay | High — fire risk, building requirements |
| HO | Heritage Overlay | Medium — restrictions on property modifications |
| VPO | Vegetation Protection Overlay | Medium — tree removal restrictions |
| ESO | Environmental Significance Overlay | Medium — environmental constraints |
| EMO | Erosion Management Overlay | Medium — soil instability risk |
| EAO | Environmental Audit Overlay | High — potential contamination |
| DDO | Design and Development Overlay | Low-Medium — future development guidelines |

---

# Appendix B — System Prompt Structure

```
# System prompt is dynamically generated per request

1. ROLE DEFINITION
   "You are an AI property buying assistant for the Australian market."
   "Your role is to collect buyer requirements through natural conversation."
   "You are NOT a licensed buyer's agent, financial advisor, or legal professional."

2. CURRENT STATE INJECTION
   "Current module: {M1_PROPERTY_NEEDS}"
   "Completed modules: {completed_list}"
   "Already collected: {collected_data_summary}"
   "Missing required fields: {missing_fields}"

3. M1→M2 INFERENCE CONTEXT (injected when M1 complete)
   e.g. "User wants 4+ bed house — focus M2 on family, children, school zones."
   e.g. "User wants investment property — focus M2 on tenant profile, yield priority."

4. ALL 6 GUARDRAIL RULES (abbreviated)
   Rule 1: Property recommendations → decline, present data only
   Rule 2: Market info → provide, then ask follow-up question
   Rule 3: Budget shortfall → flag directly and kindly
   Rule 4: Legal/compliance → explain, refer to professional
   Rule 5: Investment predictions → historical data only + ASIC disclaimer
   Rule 6: Role identity → transparent explanation of boundaries
```
