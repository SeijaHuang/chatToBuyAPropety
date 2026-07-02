# PropertyAI — 前端工程 PRD & Story Specifications

**Version:** v1.3 · 配套后端 Part 1 Technical PRD v1.2  
**技术栈:** Next.js 14 (App Router) + TypeScript + Tailwind CSS 4  
**设计系统:** Homi Lux Modern (Dark Mode)  
**最后更新:** 2026-05

> **v1.3 变更说明：** 将前端 PRD v1.2 与 Story Specifications v1.0 合并为单一文档。§1–§8 为架构规范，§9 为 Story 实现任务拆分（S-A 至 S-O）。

---

## 目录

**架构规范**

1. [技术栈与工程规范](#1-技术栈与工程规范)
2. [设计系统 Token](#2-设计系统-token)
3. [页面清单与路由](#3-页面清单与路由)
4. [共用组件规范](#4-共用组件规范)
5. [页面级规范](#5-页面级规范)
6. [状态管理](#6-状态管理)
7. [API 对接约定](#7-api-对接约定)
8. [非功能要求](#8-非功能要求)

**Story Specifications**

9. [Story 清单与执行顺序](#9-story-清单与执行顺序)
   - [S-A: Project Scaffold](#s-a-project-scaffold)
   - [S-B: Design System](#s-b-design-system)
   - [S-C: Type Definitions](#s-c-type-definitions)
   - [S-D: Axios Request Layer](#s-d-axios-request-layer)
   - [S-E: API Functions](#s-e-api-functions)
   - [S-F: Utility Functions](#s-f-utility-functions)
   - [S-G: Conversation Store](#s-g-conversation-store)
   - [S-H: UI Store](#s-h-ui-store)
   - [S-I: Shared UI Components](#s-i-shared-ui-components)
   - [S-J: Chat Components](#s-j-chat-components)
   - [S-K: Layout Components](#s-k-layout-components)
   - [S-L: HomePage](#s-l-homepage)
   - [S-M: ChatPage](#s-m-chatpage)
   - [S-N: Test Infrastructure](#s-n-test-infrastructure)
   - [S-O: Unit Tests](#s-o-unit-tests)

---

## 1. 技术栈与工程规范

### 1.1 核心依赖

| 包                          | 版本 | 用途                                                |
| --------------------------- | ---- | --------------------------------------------------- |
| next                        | 14.x | App Router SSR 框架                                 |
| react                       | 18.x | UI 库                                               |
| typescript                  | 5.x  | 类型系统                                            |
| tailwindcss                 | 4.x  | 样式工具类（CSS-first，无 JS config）               |
| @tailwindcss/postcss        | 4.x  | Next.js PostCSS 桥接插件                            |
| zustand                     | 4.x  | 客户端全局状态（P0 主要状态容器）                   |
| @tanstack/react-query       | 5.x  | 服务端数据请求（P1 起为主要状态管理）               |
| zod                         | 3.x  | Schema 验证，与后端 Pydantic 模型对应               |
| uuid                        | 9.x  | 客户端生成 session_id                               |
| axios                       | 1.x  | HTTP 客户端（统一封装，见 §7）                      |
| **测试相关**                |      |                                                     |
| vitest                      | 2.x  | 单元测试运行器（与 Next.js 14 兼容，速度优于 Jest） |
| @testing-library/react      | 16.x | React 组件测试                                      |
| @testing-library/user-event | 14.x | 用户交互模拟                                        |
| @testing-library/jest-dom   | 6.x  | DOM 断言扩展（`toBeInTheDocument` 等）              |
| @vitejs/plugin-react        | 4.x  | Vitest 的 React JSX 支持                            |
| msw                         | 2.x  | API Mock（Service Worker，用于 hook 集成测试）      |

### 1.2 目录结构

```
src/
├── app/                                   # Next.js App Router
│   ├── (main)/
│   │   ├── layout.tsx                     # 含 SideNavBar 的主布局
│   │   ├── page.tsx                       # P0 MVP: Home — AI Chat 首页
│   │   └── chat/
│   │       └── [sessionId]/page.tsx       # P0 MVP: 对话会话页
│   └── layout.tsx                         # Root Layout（字体、全局样式）
├── components/
│   ├── layout/
│   │   ├── SideNavBar.tsx
│   │   ├── TopNavBar.tsx                  # 移动端顶部栏
│   │   └── BottomNavBar.tsx               # 移动端底部导航
│   ├── chat/
│   │   ├── ChatInput.tsx
│   │   ├── ChatMessage.tsx
│   │   ├── ModuleProgress.tsx
│   │   ├── BorrowingCapacityCard.tsx
│   │   ├── BudgetGapCard.tsx
│   │   └── TypingIndicator.tsx
│   ├── ui/
│   │   ├── Button.tsx
│   │   ├── Chip.tsx
│   │   ├── AIBadge.tsx
│   │   ├── FormInput.tsx
│   │   ├── Skeleton.tsx
│   │   └── Modal.tsx
│   └── icons/
│       └── MaterialSymbol.tsx
├── hooks/
│   ├── useChat.ts
│   └── useSession.ts
├── lib/
│   ├── api.ts
│   └── utils.ts
├── stores/
│   ├── conversationStore.ts
│   └── uiStore.ts
├── types/
│   ├── conversation.ts
│   └── routing.ts
├── styles/
│   └── globals.css                        # @import "tailwindcss" + @theme + 工具 class
└── __tests__/                             # 测试文件（与 src 同级或按模块就近放置）
    ├── components/
    │   ├── chat/
    │   │   ├── ChatInput.test.tsx
    │   │   ├── ChatMessage.test.tsx
    │   │   ├── ModuleProgress.test.tsx
    │   │   ├── BorrowingCapacityCard.test.tsx
    │   │   └── BudgetGapCard.test.tsx
    │   └── ui/
    │       ├── Button.test.tsx
    │       └── Chip.test.tsx
    ├── hooks/
    │   ├── useChat.test.ts
    │   └── useSession.test.ts
    ├── lib/
    │   └── utils.test.ts
    └── stores/
        └── conversationStore.test.ts

# 项目根目录
vitest.config.ts                           # Vitest 配置
vitest.setup.ts                            # 全局测试 setup（jest-dom、msw）
postcss.config.mjs                         # @tailwindcss/postcss 插件
```

**目录设计原则：**

- P0 MVP 只有 `/` 和 `/chat/[sessionId]` 两个页面，其余页面待 Part 2 后端实现后再加
- `report/`、`property/`、`suburbs/` 等目录**暂不创建**，避免未完成页面进入路由
- 认证相关（`(auth)/login`、`register`）P1 才加入，P0 匿名访问
- 测试文件可选择集中放 `__tests__/` 或与源文件同级（`.test.tsx`），全项目统一一种风格

### 1.3 命名规范

| 类型          | 规范                                       | 示例                                     |
| ------------- | ------------------------------------------ | ---------------------------------------- |
| 组件文件      | PascalCase                                 | `SideNavBar.tsx`                         |
| Hook          | camelCase + use 前缀                       | `useChat.ts`                             |
| 类型 / 接口   | PascalCase                                 | `ConversationStateDTO`、`RoutingPayload` |
| Zustand store | camelCase + Store 后缀                     | `conversationStore.ts`                   |
| CSS class     | Tailwind 工具类优先，语义 class 小写连字符 | `.glass-panel`、`.ai-glow`               |
| 环境变量      | `NEXT_PUBLIC_` 前缀（客户端）              | `NEXT_PUBLIC_API_BASE_URL`               |

### 1.4 环境变量

```env
# .env.local
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000   # FastAPI 后端，无 /api/v1 前缀
NEXT_PUBLIC_APP_NAME=Homi AI
NEXT_PUBLIC_APP_ENV=development
```

---

## 2. 设计系统 Token

> **Tailwind CSS v4 CSS-first 方案：** 所有 token 全部定义在 `globals.css` 的 `@theme` 块中，不再需要 `tailwind.config.ts` 定义颜色、字体、间距。`tailwind.config.ts` 只在需要插件时保留（当前 P0 无需插件，可删除该文件）。

### 2.1 postcss.config.mjs

```js
// postcss.config.mjs — Tailwind v4 的 PostCSS 桥接
export default {
  plugins: {
    "@tailwindcss/postcss": {},
  },
};
```

### 2.2 globals.css（设计系统全量定义）

**Tailwind v4 命名空间规则：**

| `@theme` 变量前缀   | 生成的工具类                                 |
| ------------------- | -------------------------------------------- |
| `--color-*`         | `bg-*` / `text-*` / `border-*` / `ring-*` 等 |
| `--font-*`          | `font-*`（字体族）                           |
| `--text-*`          | `text-*`（字体大小，含 line-height）         |
| `--spacing-*`       | `p-*` / `m-*` / `gap-*` / `w-*` / `h-*` 等   |
| `--radius-*`        | `rounded-*`                                  |
| `--shadow-*`        | `shadow-*`                                   |
| `--backdrop-blur-*` | `backdrop-blur-*`                            |

```css
/* ============================================================
   src/styles/globals.css
   Tailwind CSS v4 — 单文件设计系统
   ============================================================ */

@import "tailwindcss";

/* ------------------------------------------------------------
   @theme — 所有 design token
   变量在此定义后，Tailwind 自动生成对应工具类
   ------------------------------------------------------------ */
@theme {
  /* --- 字体 --- */
  --font-sans: "Plus Jakarta Sans", sans-serif;

  /* --- 字体大小（text-display-lg / text-headline-md 等） --- */
  --text-display-lg: 3rem; /* 48px */
  --text-display-md: 2.25rem; /* 36px */
  --text-headline-lg: 1.875rem; /* 30px */
  --text-headline-md: 1.5rem; /* 24px */
  --text-title-lg: 1.25rem; /* 20px */
  --text-title-md: 1.125rem; /* 18px */
  --text-body-lg: 1rem; /* 16px */
  --text-body-md: 0.875rem; /* 14px */
  --text-label-lg: 0.875rem; /* 14px */
  --text-label-md: 0.75rem; /* 12px */
  --text-caption: 0.75rem; /* 12px */

  /* --- 间距（p-xs / gap-md / m-lg 等） --- */
  --spacing-xs: 0.25rem; /* 4px  */
  --spacing-base: 0.5rem; /* 8px  */
  --spacing-sm: 0.75rem; /* 12px */
  --spacing-md: 1.5rem; /* 24px */
  --spacing-lg: 3rem; /* 48px */
  --spacing-xl: 5rem; /* 80px */
  --spacing-gutter: 1.5rem; /* 24px */
  --spacing-margin: 2.5rem; /* 40px */

  /* --- 圆角（rounded-card / rounded-chip 等） --- */
  --radius-sm: 0.25rem;
  --radius-DEFAULT: 0.5rem;
  --radius-md: 0.75rem;
  --radius-lg: 1rem;
  --radius-xl: 1.5rem;
  --radius-full: 9999px;

  /* --- 阴影 --- */
  --shadow-ai-glow: 0 0 20px rgb(173 198 255 / 0.15);
  --shadow-card: 0 8px 32px rgb(0 0 0 / 0.4);

  /* --- backdrop-blur --- */
  --backdrop-blur-glass: 12px;

  /* --- 颜色：Surface --- */
  --color-surface: #10131a;
  --color-surface-dim: #121317;
  --color-surface-bright: #38393d;
  --color-surface-container-lowest: #0d0e11;
  --color-surface-container-low: #1a1b1f;
  --color-surface-container: #1d2027;
  --color-surface-container-high: #292a2d;
  --color-surface-container-highest: #343538;
  --color-surface-variant: #32353c;

  /* --- 颜色：On Surface --- */
  --color-on-surface: #e3e2e7;
  --color-on-surface-variant: #c2c6d6;
  --color-inverse-surface: #e3e2e7;
  --color-inverse-on-surface: #2f3034;

  /* --- 颜色：Outline --- */
  --color-outline: #8e909a;
  --color-outline-variant: #424754;

  /* --- 颜色：Primary（Fidelity Blue） --- */
  --color-primary: #d8e2ff;
  --color-primary-container: #adc6ff;
  --color-primary-fixed: #d8e2ff;
  --color-primary-fixed-dim: #adc6ff;
  --color-on-primary: #122f5f;
  --color-on-primary-container: #385283;
  --color-on-primary-fixed: #001a42;
  --color-on-primary-fixed-variant: #2c4677;
  --color-inverse-primary: #455e90;
  --color-surface-tint: #adc6ff;

  /* --- 颜色：Secondary --- */
  --color-secondary: #b7c8e1;
  --color-secondary-container: #38485d;
  --color-secondary-fixed: #d3e4fe;
  --color-secondary-fixed-dim: #b7c8e1;
  --color-on-secondary: #213145;
  --color-on-secondary-container: #a6b6cf;
  --color-on-secondary-fixed: #0b1c2f;
  --color-on-secondary-fixed-variant: #38485d;

  /* --- 颜色：Tertiary（Accent Gold — AI 指标专用） --- */
  --color-tertiary: #ffdbc4;
  --color-tertiary-container: #feb685;
  --color-tertiary-fixed: #ffdcc6;
  --color-tertiary-fixed-dim: #ffb786;
  --color-on-tertiary: #502501;
  --color-on-tertiary-container: #79451e;
  --color-on-tertiary-fixed: #301400;
  --color-on-tertiary-fixed-variant: #6b3a14;

  /* --- 颜色：Error --- */
  --color-error: #ffb4ab;
  --color-error-container: #93000a;
  --color-on-error: #690005;
  --color-on-error-container: #ffdad6;

  /* --- 颜色：Background --- */
  --color-background: #121317;
  --color-on-background: #e3e2e7;

  /* --- 颜色：Semantic --- */
  --color-success-match: #adc6ff; /* AI Match 置信度 */
  --color-warning-cut: #93000a; /* 价格降幅警告 */
}

/* ------------------------------------------------------------
   :root — 非 Tailwind 工具类用途的 CSS 变量
   （glass effect 等复合值，不需要生成工具类）
   ------------------------------------------------------------ */
:root {
  --glass-bg: rgb(30 41 59 / 0.4);
  --glass-border: rgb(66 71 84 / 0.3);
  --glass-blur: 12px;
  --ai-glow: 0 0 20px rgb(173 198 255 / 0.15);
}

/* ------------------------------------------------------------
   @layer base — 全局基础样式
   ------------------------------------------------------------ */
@layer base {
  html {
    color-scheme: dark;
  }

  body {
    background-color: var(--color-surface);
    color: var(--color-on-surface);
    font-family: var(--font-sans);
    -webkit-font-smoothing: antialiased;
  }

  /* 字体大小的 line-height 和 letter-spacing 补充
     （@theme 的 --text-* 只设大小，精细排版在此补充） */
  .text-display-lg {
    line-height: 3.5rem;
    letter-spacing: -0.02em;
    font-weight: 700;
  }
  .text-display-md {
    line-height: 2.75rem;
    letter-spacing: -0.02em;
    font-weight: 700;
  }
  .text-headline-lg {
    line-height: 2.375rem;
    font-weight: 600;
  }
  .text-headline-md {
    line-height: 2rem;
    font-weight: 600;
  }
  .text-title-lg {
    line-height: 1.75rem;
    font-weight: 600;
  }
  .text-title-md {
    line-height: 1.625rem;
    font-weight: 500;
  }
  .text-body-lg {
    line-height: 1.5rem;
    font-weight: 400;
  }
  .text-body-md {
    line-height: 1.25rem;
    font-weight: 400;
  }
  .text-label-lg {
    line-height: 1.25rem;
    letter-spacing: 0.01em;
    font-weight: 600;
  }
  .text-label-md {
    line-height: 1rem;
    letter-spacing: 0.01em;
    font-weight: 600;
  }
  .text-caption {
    line-height: 1rem;
    font-weight: 400;
  }

  /* 自定义滚动条 */
  ::-webkit-scrollbar {
    width: 6px;
    height: 6px;
  }
  ::-webkit-scrollbar-thumb {
    background: #32353c;
    border-radius: 10px;
  }
  ::-webkit-scrollbar-track {
    background: transparent;
  }

  /* Material Symbols */
  .material-symbols-outlined {
    font-variation-settings:
      "FILL" 0,
      "wght" 400,
      "GRAD" 0,
      "opsz" 24;
    vertical-align: middle;
    user-select: none;
  }
}

/* ------------------------------------------------------------
   @layer utilities — 语义 class（glass effect 等）
   ------------------------------------------------------------ */
@layer utilities {
  /* Glassmorphism — 标准浮层 */
  .glass-panel {
    background: var(--glass-bg);
    backdrop-filter: blur(var(--glass-blur));
    border: 1px solid var(--glass-border);
  }

  /* AI 激活状态玻璃（primary 色边框 + glow） */
  .glass-ai {
    background: var(--glass-bg);
    backdrop-filter: blur(var(--glass-blur));
    border: 1px solid rgb(173 198 255 / 0.2);
    box-shadow: var(--ai-glow);
  }
}
```

**使用示例：**

```tsx
// Tailwind v4 生成的工具类，直接用于 JSX
<div className="bg-surface-container text-on-surface rounded-md p-md gap-sm">
  <h2 className="text-headline-md text-primary">Analysis</h2>
  <p className="text-body-md text-on-surface-variant">...</p>
</div>

// glass-panel / glass-ai 使用自定义工具类
<div className="glass-ai rounded-xl p-md shadow-ai-glow">
  <span className="text-tertiary-container text-label-md">98.2% Match</span>
</div>
```

---

## 3. 页面清单与路由

### 3.1 P0 MVP（当前后端已支持）

| 路由                | 组件       | 描述                                         |
| ------------------- | ---------- | -------------------------------------------- |
| `/`                 | `HomePage` | AI Chat 欢迎首页，新建会话并发送第一条消息   |
| `/chat/[sessionId]` | `ChatPage` | 活跃对话，M1→M4 引导，完成后展示路由结果入口 |

### 3.2 P1（后端 P1 接口实现后）

| 路由     | 组件        | 描述                            | 依赖后端    |
| -------- | ----------- | ------------------------------- | ----------- |
| `/login` | `LoginPage` | Magic Link 或 Google OAuth 登录 | P1 用户认证 |

### 3.3 P2+（待 Part 2 后端实现）

| 路由                       | 描述                        |
| -------------------------- | --------------------------- |
| `/properties`              | 房源推荐列表（Part 2 输出） |
| `/properties/[propertyId]` | 房源详情 + 7 Agent 报告     |
| `/suburbs/[suburb]`        | 郊区概况                    |
| `/saved`                   | 已保存房源 / 搜索记录       |
| `/settings`                | 账户设置                    |

### 3.4 布局说明

- `(main)/layout.tsx`：左侧固定 `SideNavBar`（桌面 260px，折叠 72px），移动端隐藏
- 移动端：`TopNavBar`（顶部） + `BottomNavBar`（固定底部）
- P0 阶段 `SideNavBar` 展示会话历史列表（从 `conversationStore` 读取，本地存储）

---

## 4. 共用组件规范

### 4.1 SideNavBar

**文件：** `components/layout/SideNavBar.tsx`

**Props：**

```ts
interface SideNavBarProps {
  collapsed: boolean;
  onToggleCollapse: () => void;
  activePath: string;
}
```

**结构：**

```
nav (fixed, 260px / 72px collapsed)
  ├── Header：Logo "Homi AI" + 折叠按钮
  ├── New Chat 按钮 → 清空 conversationStore，生成新 sessionId，跳转 /
  ├── 会话历史列表（调用 GET /api/v1/chats 获取，最多 10 条，按 updatedAt 倒序）
  │     每项：intent 显示标签（见 INTENT_LABELS 映射）+ formatRelativeTime(updatedAt)
  │           initialIntent 为 null 时显示 "New Conversation"
  │           当前 activePath 匹配时高亮显示
  └── 底部：Settings 图标（P2）+ 用户区域（P1 加入）
```

**折叠态：** 宽度 72px，只显示图标，hover 展示 Tooltip；文字全部隐藏。

**导航项（P0 仅显示可用项）：**

```ts
const NAV_ITEMS = [
  { label: "Home", icon: "chat", href: "/", available: true },
  { label: "Search", icon: "home_work", href: "/properties", available: false }, // P2，显示但 disabled
];
```

---

### 4.2 ChatInput

**文件：** `components/chat/ChatInput.tsx`

**Props：**

```ts
interface ChatInputProps {
  onSend: (message: string) => void;
  isLoading: boolean; // POST /chat 请求进行中
  disabled?: boolean;
  placeholder?: string;
}
```

**行为：**

- `textarea` 自动扩展高度（min 56px，max 160px）
- `Enter` 发送，`Shift+Enter` 换行
- `isLoading` 为 true 时：发送按钮显示 spinner，输入框 disabled
- **P0 注意：** 后端响应约 5–10 秒（双轮 LLM 调用，非流式），loading 状态需清晰展示

**结构：**

```
div.glass-ai.rounded-3xl (focus-within 时激活 glow)
  textarea (auto-resize, min-h-14, max-h-40)
  div.toolbar
    button.attach (left, P1 实现，P0 显示但 disabled)
    button.mic   (right, P1 实现，P0 显示但 disabled)
    button.send  (right, bg-primary-container, rounded-full)
```

---

### 4.3 ChatMessage

**文件：** `components/chat/ChatMessage.tsx`

**Props：**

```ts
interface ChatMessageProps {
  role: "user" | "assistant";
  content: string;
  timestamp?: Date;
  isLoading?: boolean; // assistant 消息正在等待后端响应时
}
```

**视觉规则：**

- **user**：右对齐，`bg-surface-container-high`，`rounded-2xl rounded-br-md`
- **assistant**：左对齐，无背景，左侧 `auto_awesome` 图标（`tertiary` 色，`FILL 1`）
- **isLoading**：显示 `TypingIndicator`（P0 等待整个 JSON 响应，非 SSE）

**Markdown 渲染：** assistant 消息支持基础 Markdown（粗体、列表、换行），使用轻量解析器。

---

### 4.4 ModuleProgress

**文件：** `components/chat/ModuleProgress.tsx`

**Props：**

```ts
interface ModuleProgressProps {
  completionStatus: { M1: boolean; M2: boolean; M3: boolean; M4: boolean };
  currentModule: ModuleID;
}
```

**视觉：** 4 个节点的横向 stepper，节点说明：

| 模块 | 标签      | 图标              |
| ---- | --------- | ----------------- |
| M1   | Property  | `home`            |
| M2   | Lifestyle | `people`          |
| M3   | Location  | `location_on`     |
| M4   | Budget    | `account_balance` |

- 完成：`primary-container` 填充圆 + 对勾
- 当前：`primary-container` 边框 + 脉冲动画
- 待完成：`outline-variant` 空心圆

**位置：** 固定于 ChatPage 顶部，粘性定位，滚动时不消失。

---

### 4.5 BorrowingCapacityCard

**文件：** `components/chat/BorrowingCapacityCard.tsx`

**触发条件：** `conversationStore.state.borrowing_capacity` 首次变为非 null（用户首次提供薪资后，后端自动计算并在 `updated_state` 中返回）。

**Props：**

```ts
interface BorrowingCapacityCardProps {
  data: BorrowingCapacityResult;
}
```

**结构：**

```
div.glass-panel.rounded-xl （内联在消息列表中，assistant 消息之后）
  header: auto_awesome 图标 + "Borrowing Estimate"
  主体:   estimated_capacity 大字显示（formatAUD）
          monthly_repayment、annual_rate、loan_term_years 次要信息
  footer: disclaimer 文字（caption 字级，outline 色）⚠️ 合规要求，必须展示
```

---

### 4.6 BudgetGapCard

**文件：** `components/chat/BudgetGapCard.tsx`

**触发条件：** `conversationStore.state.budget_gap?.has_gap === true`。AI reply 已包含告知文字，此卡片作为视觉强化。

**Props：**

```ts
interface BudgetGapCardProps {
  data: BudgetGapResult;
}
```

**结构：**

```
div（内联在消息列表中，assistant 消息之后）
  header: warning 图标（error 色）+ "Budget Gap Detected"
  主体:   budget_max vs market_median 对比（formatAUD）
          gap_percentage 百分比
  footer: suggested_actions 列表（Chip 形式展示）
```

---

### 4.7 AIBadge

**文件：** `components/ui/AIBadge.tsx`

**Props：**

```ts
interface AIBadgeProps {
  label?: string; // 默认 "AI"
  size?: "sm" | "md";
}
```

**视觉：** `glass-ai` 样式，`auto_awesome` 图标（`FILL 1`，`tertiary` 色），用于标注 AI 生成内容。

---

### 4.8 Button

**文件：** `components/ui/Button.tsx`

```ts
type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md" | "lg";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant; // 默认 'secondary'
  size?: ButtonSize; // 默认 'md'
  loading?: boolean;
  icon?: string; // Material Symbol 名（前置图标）
}
```

| 变体        | 样式                                                                        |
| ----------- | --------------------------------------------------------------------------- |
| `primary`   | `bg-primary-container text-on-primary-container`                            |
| `secondary` | `border border-outline-variant/30 text-on-surface hover:bg-surface-variant` |
| `ghost`     | `text-primary hover:bg-primary/10`                                          |
| `danger`    | `bg-error-container text-on-error-container`                                |

---

### 4.9 Chip

**文件：** `components/ui/Chip.tsx`

```ts
interface ChipProps {
  label: string;
  color?: "primary" | "tertiary" | "error" | "neutral";
  icon?: string;
  onRemove?: () => void;
}
```

规则：始终 `rounded-full`，背景为对应色 `/10` 透明度，文字为对应色。

---

### 4.10 Skeleton

**文件：** `components/ui/Skeleton.tsx`

`animate-pulse bg-surface-container-high rounded` 基础实现，导出：

- `SkeletonText` — 单行文字占位
- `SkeletonMessage` — ChatMessage 骨架（P0 loading 用）

---

### 4.11 TypingIndicator

**文件：** `components/chat/TypingIndicator.tsx`

三个 `●` 交错淡入淡出，`tertiary` 色调，用于 assistant 消息等待状态（P0 等待完整 JSON 响应，P1 改为流式 token 渲染）。

---

## 5. 页面级规范

### 5.1 HomePage（`/`）

**用途：** 新建会话的入口，用户第一次打开或点击 "New Chat" 时展示。

**布局：** 全屏居中，无列表内容，主内容区最大宽度 768px。

**核心元素：**

- `auto_awesome` 图标（tertiary 色，64px，`animate-pulse`）
- 问候语 `display-lg`（P0 固定为 `"How can I help you today?"`，P1 接入用户名后改为 `"{name} returns!"`）
- `ChatInput`（全宽，placeholder: "Tell me what you're looking for..."）
- 底部免责声明（`caption` 字级，outline 色）：`"Homi AI can make mistakes. Verify important property or financial information."`

**交互流程：**

```
1. 用户打开页面
2. 前端生成新 session_id (uuid v4)，初始化 ConversationStateDTO，存入 conversationStore
3. 用户输入并提交
4. 立即跳转 /chat/{sessionId}（乐观导航，不等后端响应）
5. ChatPage 接管后续对话
```

---

### 5.2 ChatPage（`/chat/[sessionId]`）

**布局：**

```
fixed: ModuleProgress (top)
flex-col h-screen:
  ├── ModuleProgress (sticky top-0, z-10)
  ├── 消息列表 (flex-1, overflow-y-auto, pb-32)
  │     ChatMessage 列表 + BorrowingCapacityCard + BudgetGapCard
  └── ChatInput (fixed bottom-0, bg-surface/80 backdrop-blur)
```

**P0 数据流（前端持有状态架构）：**

```
用户提交消息
  │
  ▼
1. 乐观 UI：立即在消息列表追加 user 消息，追加 assistant loading 消息
2. 从 conversationStore 取当前完整 state
3. POST /chat { message, state } → 后端处理（约 5–10s，无 SSE）
4. 响应到达：
     a. 用 response.updated_state 完整替换 conversationStore.state（不做 merge）
     b. 用 response.reply 替换 loading 的 assistant 消息内容
     c. 若 response.updated_state.borrowing_capacity 首次非 null → 追加 BorrowingCapacityCard
     d. 若 response.updated_state.budget_gap?.has_gap → 追加 BudgetGapCard
     e. 若 response.routing 非 null → 显示"查看推荐房源"CTA 按钮
5. 同步到 sessionStorage（防刷新丢失）
```

**路由完成后的 CTA：**

当 `response.routing` 非 null 时，在消息列表底部追加一个特殊卡片：

```
div.glass-ai.rounded-xl
  text: "I've collected everything I need. Ready to find properties?"
  button: "View Matching Properties" (primary variant)
  → 点击后：将 routing payload 存入 sessionStorage，跳转 /properties（P2 实现后激活）
  → P2 未上线时：显示 "Coming soon" toast
```

**会话恢复（刷新页面）：**

```
1. 从 URL 取 sessionId
2. 从 sessionStorage 读取 `conversation_state_{sessionId}`
3. 若存在 → 恢复到 conversationStore，渲染历史消息
4. 若不存在 → conversationStore 为空，显示空对话界面（用户重新开始）
```

---

## 6. 状态管理

### 6.1 架构概述

**P0 架构核心原则：前端是状态的唯一持有者。**

```
conversationStore (Zustand)
  └── state: ConversationStateDTO      ← 每次 POST /chat 后用 updated_state 完整替换
  └── messages: UIMessage[]            ← 前端 UI 消息列表（含 loading 状态等 UI 专属字段）
  └── routing: RoutingPayload | null   ← Part 2 路由负载

uiStore (Zustand)
  └── sidebarCollapsed: boolean
  └── activeModal: string | null
```

### 6.2 ConversationStore 完整定义

```ts
// stores/conversationStore.ts

// UI 专用消息类型（包含 loading 状态，不存入后端）
interface UIMessage {
  id: string; // 前端生成的临时 ID
  role: "user" | "assistant";
  content: string;
  isLoading: boolean; // true 表示等待后端响应
  timestamp: Date;
  // 可选附件（卡片）
  borrowingCapacity?: BorrowingCapacityResult;
  budgetGap?: BudgetGapResult;
}

interface ConversationStore {
  // 核心状态
  sessionId: string | null;
  state: ConversationStateDTO | null; // 后端 ConversationStateDTO 完整对象
  messages: UIMessage[];
  routing: RoutingPayload | null;
  isLoading: boolean; // POST /chat 进行中

  // Actions
  initSession: (sessionId: string) => void; // 初始化空 state
  sendMessage: (content: string) => Promise<void>;
  restoreFromStorage: (sessionId: string) => boolean;
  clearSession: () => void;
}
```

### 6.3 ConversationStateDTO TypeScript 类型

```ts
// types/conversation.ts — 与后端 models/schemas.py 严格对应

type ModuleID =
  | "M1_PROPERTY_NEEDS"
  | "M2_LIFESTYLE"
  | "M3_SUBURB_PREFERENCE"
  | "M4_BUDGET"
  | "COMPLETE";

type SessionStatus = "IN_PROGRESS" | "REQUIREMENTS_COMPLETE";

interface M1PropertyNeeds {
  property_type:
    | "house"
    | "townhouse"
    | "unit"
    | "apartment"
    | "villa"
    | "any"
    | null;
  min_bedrooms: number | null;
  max_bedrooms: number | null;
  min_bathrooms: number | null;
  min_carspaces: number | null;
  min_land_size: number | null; // sqm
  max_land_size: number | null; // sqm
  wants_pool: boolean | null;
  wants_outdoor: boolean | null;
  wants_study: boolean | null;
  intended_use: "owner_occupier" | "investment" | "both" | null;
}

interface M2Lifestyle {
  household_size: number | null;
  has_children: boolean | null;
  needs_school_zone: boolean | null;
  has_pets: boolean | null;
  work_from_home: boolean | null;
  target_tenant: "family" | "professional" | "student" | "any" | null;
}

interface M3SuburbPreference {
  commute_destination: string | null;
  commute_max_mins: number | null;
  commute_mode: "train" | "car" | "tram" | "bus" | "any" | null;
  preferred_suburbs: string[] | null;
  excluded_suburbs: string[] | null;
  lifestyle_vibe:
    | "inner_city"
    | "suburban"
    | "leafy"
    | "coastal"
    | "any"
    | null;
}

interface M4Budget {
  budget_min: number | null; // AUD 整数
  budget_max: number | null; // AUD 整数
  deposit_amount: number | null; // AUD 整数
  pre_tax_salary: number | null; // AUD/年 税前
  is_joint: boolean | null;
  partner_salary: number | null; // AUD/年 税前
  first_home_buyer: boolean | null;
  loan_term_years: number | null; // 用户期望贷款年限
}

interface CollectedData {
  m1: M1PropertyNeeds;
  m2: M2Lifestyle;
  m3: M3SuburbPreference;
  m4: M4Budget;
}

interface BorrowingCapacityResult {
  estimated_capacity: number; // AUD，四舍五入至最近 $10,000
  monthly_repayment: number; // AUD/月
  based_on_salary: number; // 税前薪资总额
  is_joint: boolean;
  annual_rate: number; // 利率 %
  loan_term_years: number;
  rate_source: string; // 利率来源描述
  disclaimer: string; // ⚠️ 必须展示，合规要求
}

interface BudgetGapResult {
  has_gap: boolean;
  budget_max: number;
  market_median: number;
  gap_amount: number;
  gap_percentage: number;
  reference_suburb: string;
  suggested_actions: string[]; // ≥ 2 项
}

interface ConversationStateDTO {
  sessionId: string;
  status: SessionStatus;
  currentModule: ModuleID;
  completionStatus: { M1: boolean; M2: boolean; M3: boolean; M4: boolean };
  collectedData: CollectedData;
  conversationHistory: Array<{ role: "user" | "assistant"; content: string }>;
  finalNeeds: CollectedData | null;
  borrowing_capacity: BorrowingCapacityResult | null; // S-G 新增
  budget_gap: BudgetGapResult | null; // S-H 新增
}
```

### 6.4 RoutingPayload TypeScript 类型

```ts
// types/routing.ts

type EUserIntent =
  | "recommend_suburbs"
  | "list_properties"
  | "property_detail"
  | "compare_properties"
  | "open_ended_query";

type EExecutionMode = "code_driven" | "agentic_loop";
type ETriggerSource = "auto_complete" | "keyword" | "manual";

interface UserNeeds {
  session_id: string;
  generated_at: string; // ISO 8601
  schema_version: string; // "1.1"
  collected: CollectedData;
  initial_intent: EUserIntent;
}

interface RoutingPayload {
  intent: EUserIntent;
  session_id: string;
  user_needs: UserNeeds;
  execution_mode: EExecutionMode;
  agents_hint: string[];
  triggered_at: string; // ISO 8601
  trigger_source: ETriggerSource;
}
```

### 6.5 ConversationStateDTO 初始值工厂

```ts
// lib/utils.ts
export function createInitialState(sessionId: string): ConversationStateDTO {
  return {
    sessionId,
    status: "IN_PROGRESS",
    currentModule: "M1_PROPERTY_NEEDS",
    completionStatus: { M1: false, M2: false, M3: false, M4: false },
    collectedData: {
      m1: {
        property_type: null,
        min_bedrooms: null,
        max_bedrooms: null,
        min_bathrooms: null,
        min_carspaces: null,
        min_land_size: null,
        max_land_size: null,
        wants_pool: null,
        wants_outdoor: null,
        wants_study: null,
        intended_use: null,
      },
      m2: {
        household_size: null,
        has_children: null,
        needs_school_zone: null,
        has_pets: null,
        work_from_home: null,
        target_tenant: null,
      },
      m3: {
        commute_destination: null,
        commute_max_mins: null,
        commute_mode: null,
        preferred_suburbs: null,
        excluded_suburbs: null,
        lifestyle_vibe: null,
      },
      m4: {
        budget_min: null,
        budget_max: null,
        deposit_amount: null,
        pre_tax_salary: null,
        is_joint: null,
        partner_salary: null,
        first_home_buyer: null,
        loan_term_years: null,
      },
    },
    conversationHistory: [],
    finalNeeds: null,
    borrowing_capacity: null,
    budget_gap: null,
  };
}
```

---

## 7. API 对接约定

### 7.1 基础约定

| 项目     | 值                                                   |
| -------- | ---------------------------------------------------- |
| Base URL | `http://localhost:8000`（无 `/api/v1` 前缀）         |
| 认证     | P0 无认证，P1 加入 `browser_fp` 字段                 |
| 请求格式 | `Content-Type: application/json`                     |
| 金额单位 | **AUD 整数**（`1200000` = $1,200,000），**不是**澳分 |
| 日期格式 | ISO 8601（`"2026-05-19T10:00:00"`）                  |

### 7.2 Axios 实例封装（`lib/request.ts`）

所有 HTTP 请求统一通过 `lib/request.ts` 导出的 axios 实例发出，不直接使用 `axios` 或 `fetch`。

**文件：** `src/lib/request.ts`

```ts
import axios, {
  type AxiosInstance,
  type AxiosRequestConfig,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
  AxiosError,
} from "axios";

// ─── 自定义错误类 ───────────────────────────────────────────
export class APIError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    public readonly detail?: string,
    public readonly retryAfter?: number, // 429 时后端返回的重试等待秒数
  ) {
    super(detail ?? code);
    this.name = "APIError";
  }
}

// ─── 后端错误响应体类型 ──────────────────────────────────────
interface BackendError {
  error: string;
  detail?: string;
  retry_after?: number;
}

// ─── 创建 axios 实例 ─────────────────────────────────────────
const instance: AxiosInstance = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_BASE_URL, // e.g. http://localhost:8000
  timeout: 30_000, // 30s（P0 双轮 LLM 约 10s，留余量）
  headers: {
    "Content-Type": "application/json",
    Accept: "application/json",
  },
});

// ─── 请求拦截器 ──────────────────────────────────────────────
instance.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // P1：在此注入 Authorization header 或 browser_fp
    // const token = getToken()
    // if (token) config.headers.Authorization = `Bearer ${token}`
    return config;
  },
  (error) => Promise.reject(error),
);

// ─── 响应拦截器 ──────────────────────────────────────────────
instance.interceptors.response.use(
  // 成功：直接返回 response，由调用方取 .data
  (response: AxiosResponse) => response,

  // 失败：统一转换为 APIError
  async (error: AxiosError<BackendError>) => {
    const status = error.response?.status;
    const body = error.response?.data;
    const code = body?.error ?? "unknown_error";
    const detail = body?.detail;

    // 429 自动重试（最多 1 次）
    if (status === 429) {
      const retryAfter = body?.retry_after ?? 2;
      const config = error.config;

      if (
        config &&
        !(config as AxiosRequestConfig & { _retried?: boolean })._retried
      ) {
        (config as AxiosRequestConfig & { _retried?: boolean })._retried = true;
        await new Promise((resolve) => setTimeout(resolve, retryAfter * 1000));
        return instance(config);
      }

      throw new APIError(429, code, detail, retryAfter);
    }

    // 网络错误（无 response）
    if (!error.response) {
      throw new APIError(0, "network_error", "Connection failed");
    }

    throw new APIError(status ?? 0, code, detail);
  },
);

export default instance;
```

### 7.3 API 方法封装（`lib/api.ts`）

业务接口全部集中在 `lib/api.ts`，统一使用 `request` 实例，不在组件或 hook 内直接调用 axios。

**文件：** `src/lib/api.ts`

```ts
import request from "./request";
import type { ConversationStateDTO, CollectedData } from "@/types/conversation";
import type { ChatResponse, SummaryResponse } from "@/types/api";
import type { EUserIntent } from "@/types/routing";

// ─── P0 接口 ─────────────────────────────────────────────────

/**
 * POST /chat
 * 发送消息，后端完整处理后返回 AI 回复 + updated_state。
 * ⚠️ P0 为同步 JSON 响应（约 5–10s），P1 改为 SSE。
 */
export async function postChat(
  message: string,
  state: ConversationStateDTO,
): Promise<ChatResponse> {
  const { data } = await request.post<ChatResponse>("/chat", {
    message,
    state,
  });
  return data;
}

/**
 * POST /chat/summary
 * 4 个模块全部完成后调用，生成自然语言摘要 + UserNeeds 结构。
 */
export async function postChatSummary(
  collectedData: CollectedData,
  sessionId: string,
  initialIntent: EUserIntent = "open_ended_query",
): Promise<SummaryResponse> {
  const { data } = await request.post<SummaryResponse>("/chat/summary", {
    collected_data: collectedData,
    session_id: sessionId,
    initial_intent: initialIntent,
  });
  return data;
}

/**
 * GET /health
 * 健康检查，应用启动时调用确认后端可达。
 */
export async function getHealth(): Promise<{ status: string }> {
  const { data } = await request.get<{ status: string }>("/health");
  return data;
}

// ─── P1 接口（占位，后端 P1 就绪后实现） ───────────────────────

/**
 * GET /chat/{sessionId}
 * P1：从 Redis 恢复会话状态，替代 P0 的 sessionStorage 方案。
 * @todo 后端 P1 实现后取消注释
 */
// export async function getSession(sessionId: string) {
//   const { data } = await request.get(`/chat/${sessionId}`)
//   return data
// }

/**
 * DELETE /chat/{sessionId}
 * P1：清除 Redis 会话（"重新开始"功能）。
 * @todo 后端 P1 实现后取消注释
 */
// export async function deleteSession(sessionId: string): Promise<void> {
//   await request.delete(`/chat/${sessionId}`)
// }
```

### 7.4 P1 SSE 专用封装（`lib/sse.ts`）

P1 的 `POST /chat` 改为 SSE 流式响应，axios 不原生支持 SSE，单独用 `fetch` 封装，**不走** `lib/request.ts`。

**文件：** `src/lib/sse.ts`（P1 阶段创建）

```ts
// P1 占位文件，P0 阶段不实现
// SSE 不经过 axios 实例，直接用原生 fetch

export interface SSETokenEvent {
  text: string;
}
export interface SSEDoneEvent {
  extracted: Record<string, unknown>;
  routing: unknown;
}

/**
 * P1: POST /chat（SSE 版本）
 * event: token → 实时文字块
 * event: done  → extracted + routing
 */
export async function postChatSSE(
  sessionId: string,
  message: string,
  onToken: (chunk: string) => void,
  onDone: (data: SSEDoneEvent) => void,
): Promise<void> {
  const res = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify({ session_id: sessionId, message }),
  });

  if (!res.ok || !res.body) throw new Error(`SSE failed: ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    let currentEvent = "";
    for (const line of lines) {
      if (line.startsWith("event: ")) currentEvent = line.slice(7).trim();
      else if (line.startsWith("data: ")) {
        const payload = JSON.parse(line.slice(6));
        if (currentEvent === "token") onToken(payload.text);
        if (currentEvent === "done") onDone(payload);
        currentEvent = "";
      }
    }
  }
}
```

### 7.5 在 Hook 中使用

```ts
// hooks/useChat.ts — P0 版本（使用 lib/api.ts）
import { postChat, postChatSummary } from "@/lib/api";
import { APIError } from "@/lib/request";
import { useConversationStore } from "@/stores/conversationStore";

export function useChat() {
  const { state, setLoading, addUserMessage, setUpdatedState, setRouting } =
    useConversationStore();

  async function sendMessage(content: string) {
    if (!state || !content.trim()) return;

    setLoading(true);
    addUserMessage(content); // 乐观 UI

    try {
      const response = await postChat(content, state);

      // ⚠️ 完整替换，不 merge
      setUpdatedState(response.updated_state);
      addAssistantMessage(response.reply);

      if (response.routing) setRouting(response.routing);
    } catch (err) {
      if (err instanceof APIError) {
        if (err.status === 503) showToast("AI temporarily unavailable");
        if (err.status === 0) showToast("Connection failed");
      }
    } finally {
      setLoading(false);
    }
  }

  return { sendMessage };
}
```

### 7.6 P0 接口列表

| 方法   | 路径            | 封装函数            | 用途                                                                                |
| ------ | --------------- | ------------------- | ----------------------------------------------------------------------------------- |
| `POST` | `/chat`         | `postChat()`        | 发送消息，获取 AI 回复 + updated_state                                              |
| `POST` | `/chat/summary` | `postChatSummary()` | 生成需求摘要（4 模块完成后调用）                                                    |
| `GET`  | `/health`       | `getHealth()`       | 健康检查                                                                            |
| `GET`  | `/chats`        | `getChats()`        | 获取当前匿名用户的历史会话列表（按 updatedAt 倒序，返回全部，前端截取前 10 条）    |

**⚠️ `/chats` 依赖 `propertyai_anon_id` HttpOnly cookie**；`withCredentials: true` 已在 axios 实例中配置，cookie 自动随请求发送。cookie 缺失或无效时后端返回 400，前端静默显示空列表。

**⚠️ P0 无认证接口（Bearer token）**，P1 加入。

### 7.7 P0 响应类型（`types/api.ts`）

```ts
// src/types/api.ts
import type { ConversationStateDTO } from "./conversation";
import type { RoutingPayload, UserNeeds } from "./routing";

export interface ChatResponse {
  reply: string;
  extracted: Record<string, unknown>; // 本轮提取到的字段
  updated_state: ConversationStateDTO; // ⚠️ 必须完整替换，不能 merge
  routing: RoutingPayload | null;
}

export interface SummaryResponse {
  summary_text: string;
  structured: UserNeeds; // 注意：不是 CollectedData，是完整 UserNeeds
}
```

### 7.8 错误处理规则

| HTTP 状态   | code 字段         | 处理方式                                       |
| ----------- | ----------------- | ---------------------------------------------- |
| `422`       | —                 | 表单层拦截（空消息），不应到达后端             |
| `429`       | `rate_limited`    | 拦截器自动等待 `retry_after` 秒后重试一次      |
| `503`       | `llm_unavailable` | Toast："AI temporarily unavailable" + 重试按钮 |
| `0`（网络） | `network_error`   | Toast："Connection failed" + 重试              |

### 7.9 金额格式化（`lib/utils.ts`）

```ts
// 后端金额为 AUD 整数，前端负责格式化显示
export function formatAUD(amount: number): string {
  return new Intl.NumberFormat("en-AU", {
    style: "currency",
    currency: "AUD",
    maximumFractionDigits: 0,
  }).format(amount);
}
// formatAUD(1200000) → "$1,200,000"
```

### 7.10 P1 接口变更预告（代码不提前写）

P1 后端上线后，`POST /chat` 发生**破坏性变更**，需同步修改：

| 项目           | P0                          | P1                                     |
| -------------- | --------------------------- | -------------------------------------- |
| 请求体         | `{ message, state }`        | `{ session_id, message, browser_fp? }` |
| 响应           | JSON，含 `updated_state`    | SSE stream，无 `updated_state`         |
| 封装位置       | `lib/api.ts` → `postChat()` | `lib/sse.ts` → `postChatSSE()`         |
| 前端状态持久化 | sessionStorage              | 后端 Redis，不需要                     |

P1 迁移改动范围：`lib/api.ts`（删除 P0 postChat）、`lib/sse.ts`（启用）、`conversationStore.ts`（移除 state 字段）、`hooks/useChat.ts`（切换调用）。

---

## 8. 非功能要求

| 类别       | 要求                                      | 实现方式                                                           |
| ---------- | ----------------------------------------- | ------------------------------------------------------------------ |
| 性能       | FCP < 2s                                  | Next.js SSR + CloudFront CDN                                       |
| 性能       | P0 对话响应：页面不卡死，loading 状态明确 | ChatInput disabled + TypingIndicator，等待最长 15s                 |
| 响应式     | 桌面优先，移动端可用                      | Tailwind `md:` 断点，最小 375px                                    |
| 无障碍     | WCAG 2.1 AA                               | 所有交互元素有 `aria-label`，颜色对比度 ≥ 4.5:1                    |
| 类型安全   | 严格 TypeScript                           | `tsconfig.json` strict 模式，与后端 Pydantic 模型严格对齐          |
| 代码规范   | ESLint + Prettier                         | CI 强制检查                                                        |
| 安全       | XSS 防护                                  | React 默认转义，不使用 `dangerouslySetInnerHTML`                   |
| 合规       | 借款能力免责声明                          | `BorrowingCapacityCard` 的 `disclaimer` 字段**必须**展示，不可省略 |
| 合规       | AI 免责声明                               | ChatPage 底部固定展示 `"Homi AI can make mistakes..."`             |
| 动画       | 60fps                                     | 优先 `transform` / `opacity`，避免触发 layout                      |
| 会话持久化 | 刷新不丢失对话                            | sessionStorage，key: `conversation_state_{sessionId}`              |

---

---

## 9. Story 清单与执行顺序

每个 Story 对应一个独立的实现单元，格式与后端 PRD 保持一致：**Objective → Files → Specification → Acceptance Criteria → Unit Tests**。

**Story 依赖总览：**

| Story                            | Title                                     | 依赖               |
| -------------------------------- | ----------------------------------------- | ------------------ |
| [S-A](#s-a-project-scaffold)     | Project Scaffold                          | —                  |
| [S-B](#s-b-design-system)        | Design System (Tailwind v4 + globals.css) | S-A                |
| [S-C](#s-c-type-definitions)     | Type Definitions                          | S-A                |
| [S-D](#s-d-axios-request-layer)  | Axios Request Layer                       | S-A, S-C           |
| [S-E](#s-e-api-functions)        | API Functions                             | S-D                |
| [S-F](#s-f-utility-functions)    | Utility Functions                         | S-C                |
| [S-G](#s-g-conversation-store)   | Conversation Store (Zustand)              | S-C, S-F           |
| [S-H](#s-h-ui-store)             | UI Store (Zustand)                        | S-A                |
| [S-I](#s-i-shared-ui-components) | Shared UI Components                      | S-B                |
| [S-J](#s-j-chat-components)      | Chat Components                           | S-B, S-C, S-I      |
| [S-K](#s-k-layout-components)    | Layout Components                         | S-B, S-H, S-I      |
| [S-L](#s-l-homepage)             | HomePage                                  | S-G, S-J, S-K      |
| [S-M](#s-m-chatpage)             | ChatPage                                  | S-G, S-E, S-J, S-K |
| [S-N](#s-n-test-infrastructure)  | Test Infrastructure (MSW + fixtures)      | S-C, S-E, S-F      |
| [S-O](#s-o-unit-tests)           | Unit Tests (≥ 80% coverage)               | S-N + all stories  |
| [S-P](#s-p-chat-history-sidebar) | Chat History Sidebar                      | S-F, S-K, S-N      |

**并行机会：**

```
S-A (Scaffold)
  ├─ S-B (Design System)       ← 可与 S-C 同时进行
  ├─ S-C (Types)               ← 可与 S-B 同时进行
  │    ├─ S-D (Request Layer)
  │    │    └─ S-E (API Functions)
  │    ├─ S-F (Utils)
  │    │    ├─ S-G (Conversation Store)  ← 可与 S-H 同时进行
  │    │    └─ S-H (UI Store)            ← 可与 S-G 同时进行
  │    └─ S-N (Test Infra)    ← D/F 完成后即可开始，无需等组件
  └─ S-B + S-I (Shared UI)
       ├─ S-J (Chat Components)   ← 可与 S-K 同时进行
       └─ S-K (Layout)            ← 可与 S-J 同时进行
            ├─ S-L (HomePage)
            ├─ S-M (ChatPage)
            └─ S-P (Chat History Sidebar)  ← S-K + S-N + S-F 完成后开始
S-O (Unit Tests)  ← 各 Story 完成后滚动补充，不阻塞主线
```

---

---

## S-A: Project Scaffold

### Objective

初始化 Next.js 14 项目，配置 TypeScript、ESLint、Prettier、PostCSS，建立完整目录结构，使项目可启动并通过构建。

### Files

```
package.json
tsconfig.json
.eslintrc.json
.prettierrc
postcss.config.mjs
next.config.ts
src/app/layout.tsx
src/app/(main)/layout.tsx
src/styles/globals.css          (空文件，S-B 填充)
```

### Specification

**package.json 核心依赖：**

```json
{
  "dependencies": {
    "next": "14.x",
    "react": "18.x",
    "react-dom": "18.x",
    "axios": "1.x",
    "zustand": "4.x",
    "@tanstack/react-query": "5.x",
    "zod": "3.x",
    "uuid": "9.x"
  },
  "devDependencies": {
    "typescript": "5.x",
    "tailwindcss": "4.x",
    "@tailwindcss/postcss": "4.x",
    "vitest": "2.x",
    "@vitejs/plugin-react": "4.x",
    "@testing-library/react": "16.x",
    "@testing-library/user-event": "14.x",
    "@testing-library/jest-dom": "6.x",
    "msw": "2.x",
    "@types/uuid": "9.x"
  }
}
```

**postcss.config.mjs：**

```js
export default {
  plugins: { "@tailwindcss/postcss": {} },
};
```

**tsconfig.json 关键配置：**

- `strict: true`
- `paths: { "@/*": ["./src/*"] }`
- `moduleResolution: "bundler"`

**目录结构（全部建立，文件内容可为空占位）：**

```
src/
├── app/
│   ├── layout.tsx               # Root Layout — 引入 globals.css、Plus Jakarta Sans 字体
│   └── (main)/
│       ├── layout.tsx           # Main Layout — 含 SideNavBar
│       └── page.tsx             # HomePage 占位
├── components/
│   ├── layout/
│   ├── chat/
│   ├── ui/
│   └── icons/
├── hooks/
├── lib/
├── stores/
├── types/
└── styles/
    └── globals.css
__tests__/
├── mocks/
└── components/
    ├── chat/
    └── ui/
vitest.config.ts
vitest.setup.ts
```

**Root Layout (`src/app/layout.tsx`)：**

- 引入 Google Fonts：Plus Jakarta Sans（weights: 400, 500, 600, 700）
- `<html>` 加 `className="dark"`（始终深色模式）
- 引入 `globals.css`
- 引入 Material Symbols Outlined 字体

### Acceptance Criteria

| ID   | Criterion                                                  |
| ---- | ---------------------------------------------------------- |
| SA-1 | `npm run dev` 启动成功，浏览器访问 `localhost:3000` 无报错 |
| SA-2 | `npm run build` 构建成功，无 TypeScript 错误               |
| SA-3 | `npm run lint` 通过，无 ESLint 错误                        |
| SA-4 | `tsconfig.json` 中 `strict: true` 且 `@` alias 可用        |
| SA-5 | Plus Jakarta Sans 字体已加载（Network 面板可见字体请求）   |
| SA-6 | `<html>` 元素含 `class="dark"`                             |
| SA-7 | 所有目录已建立，无缺失                                     |

### Unit Tests

```
无（脚手架无业务逻辑，SA-1 至 SA-7 为手动验收标准）
```

---

## S-B: Design System

### Objective

在 `globals.css` 中使用 Tailwind CSS v4 `@theme` 语法定义全部设计 token，使所有颜色、字体、间距、圆角、阴影工具类可用，删除 `tailwind.config.ts` 中任何 token 定义（P0 无插件需求，config 文件可不存在）。

### Files

```
src/styles/globals.css
```

### Specification

**文件结构（固定顺序）：**

```
1. @import "tailwindcss"
2. @theme { ... }          — 所有 design token
3. :root { ... }           — 非工具类用途的 CSS 变量（glass effect）
4. @layer base { ... }     — 全局基础样式、字体排版补充、滚动条
5. @layer utilities { ... } — .glass-panel、.glass-ai
```

**`@theme` 必须包含的命名空间：**

| 命名空间前缀            | 生成工具类             | Token 数量                                |
| ----------------------- | ---------------------- | ----------------------------------------- |
| `--font-*`              | `font-*`               | 1（`--font-sans`）                        |
| `--text-*`              | `text-*`               | 11 个字阶                                 |
| `--spacing-*`           | `p-*` `m-*` `gap-*` 等 | 8 个（xs/base/sm/md/lg/xl/gutter/margin） |
| `--radius-*`            | `rounded-*`            | 6 个（sm/DEFAULT/md/lg/xl/full）          |
| `--shadow-*`            | `shadow-*`             | 2 个（ai-glow/card）                      |
| `--backdrop-blur-*`     | `backdrop-blur-*`      | 1 个（glass）                             |
| `--color-surface*`      | 颜色工具类             | 9 个                                      |
| `--color-on-surface*`   | 颜色工具类             | 4 个                                      |
| `--color-outline*`      | 颜色工具类             | 2 个                                      |
| `--color-primary*`      | 颜色工具类             | 9 个                                      |
| `--color-secondary*`    | 颜色工具类             | 8 个                                      |
| `--color-tertiary*`     | 颜色工具类             | 8 个                                      |
| `--color-error*`        | 颜色工具类             | 4 个                                      |
| `--color-background*`   | 颜色工具类             | 2 个                                      |
| `--color-success-match` | 颜色工具类             | 1 个                                      |
| `--color-warning-cut`   | 颜色工具类             | 1 个                                      |

**`:root` 必须包含（不生成工具类，只供 CSS 变量引用）：**

```css
--glass-bg: rgb(30 41 59 / 0.4);
--glass-border: rgb(66 71 84 / 0.3);
--glass-blur: 12px;
--ai-glow: 0 0 20px rgb(173 198 255 / 0.15);
```

**`@layer base` 必须包含：**

- `html { color-scheme: dark; }`
- `body` 的 background、color、font-family、antialiased
- 11 个字阶的 `line-height`、`letter-spacing`、`font-weight` 补充（`@theme` 的 `--text-*` 只设大小）
- 滚动条样式：`width: 6px`，thumb `#32353c`，track transparent
- `.material-symbols-outlined` font-variation-settings

**`@layer utilities` 必须包含：**

- `.glass-panel`：background + backdrop-filter + border（引用 `:root` 变量）
- `.glass-ai`：glass-panel 基础上加 primary-tinted border + ai-glow shadow

### Acceptance Criteria

| ID    | Criterion                                                          |
| ----- | ------------------------------------------------------------------ |
| SB-1  | `className="bg-surface"` 在页面渲染出 `#10131a` 背景色             |
| SB-2  | `className="text-primary"` 渲染出 `#d8e2ff` 字色                   |
| SB-3  | `className="text-headline-md"` 渲染出 24px 字体                    |
| SB-4  | `className="p-md"` 渲染出 24px padding                             |
| SB-5  | `className="rounded-md"` 渲染出 0.75rem 圆角                       |
| SB-6  | `className="shadow-ai-glow"` 渲染出对应 box-shadow                 |
| SB-7  | `className="backdrop-blur-glass"` 渲染出 12px blur                 |
| SB-8  | `className="glass-panel"` 元素有半透明背景和 1px 边框              |
| SB-9  | `className="glass-ai"` 元素有 primary-tinted border 和 glow shadow |
| SB-10 | 浏览器 DevTools 确认 `body` 背景色为 `#121317`                     |
| SB-11 | Plus Jakarta Sans 字体已在 body 上生效                             |
| SB-12 | 自定义滚动条可见（`overflow-y: auto` 容器中测试）                  |

### Unit Tests

```
无（纯 CSS，用 SB-1 至 SB-12 手动验收）
```

---

## S-C: Type Definitions

### Objective

建立前端所有 TypeScript 类型定义，严格与后端 `models/schemas.py` 的 Pydantic 模型对应，作为全项目类型的单一来源（Single Source of Truth）。

### Files

```
src/types/conversation.ts     — ConversationStateDTO 及全部子类型
src/types/routing.ts          — RoutingPayload、UserNeeds、枚举
src/types/api.ts              — ChatResponse、SummaryResponse
```

### Specification

**`src/types/conversation.ts` 必须导出：**

```ts
// 枚举
type ModuleID       // 'M1_PROPERTY_NEEDS' | 'M2_LIFESTYLE' | 'M3_SUBURB_PREFERENCE' | 'M4_BUDGET' | 'COMPLETE'
type SessionStatus  // 'IN_PROGRESS' | 'REQUIREMENTS_COMPLETE'

// 数据模型（与后端 M1PropertyNeeds / M2Lifestyle / M3SuburbPreference / M4Budget 严格对应）
interface M1PropertyNeeds
interface M2Lifestyle
interface M3SuburbPreference
interface M4Budget              // 含 loan_term_years（S-G 新增字段）
interface CollectedData         // { m1, m2, m3, m4 }

// 计算结果（后端 §17.6 新增到 DTO）
interface BorrowingCapacityResult   // 含 disclaimer: string（合规字段）
interface BudgetGapResult           // 含 suggested_actions: string[]

// 核心 DTO
interface ConversationStateDTO
```

**`src/types/routing.ts` 必须导出：**

```ts
type EUserIntent      // 5 个值（与后端 S-E 一致）
type EExecutionMode   // 'code_driven' | 'agentic_loop'
type ETriggerSource   // 'auto_complete' | 'keyword' | 'manual'

interface UserNeeds        // Part 1 → Part 2 接口契约（后端 §12）
interface RoutingPayload   // 后端 §16.3 完整版本
```

**`src/types/api.ts` 必须导出：**

```ts
interface ChatResponse      // { reply, extracted, updated_state, routing }
interface SummaryResponse   // { summary_text, structured: UserNeeds }
```

**字段约束规则：**

- 所有金额字段类型为 `number`（AUD 整数，非澳分）
- 所有可选字段类型为 `T | null`（不用 `T | undefined`，与后端 Pydantic 行为一致）
- `ConversationStateDTO.conversationHistory` 类型为 `Array<{ role: 'user' | 'assistant'; content: string }>`

### Acceptance Criteria

| ID   | Criterion                                                                                                                                  |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| SC-1 | `import type { ConversationStateDTO } from '@/types/conversation'` 无报错                                                                  |
| SC-2 | `M4Budget` 含 `loan_term_years: number \| null` 字段                                                                                       |
| SC-3 | `BorrowingCapacityResult` 含 `disclaimer: string`（非 optional）                                                                           |
| SC-4 | `BudgetGapResult.suggested_actions` 类型为 `string[]`                                                                                      |
| SC-5 | `RoutingPayload` 含 `execution_mode`、`agents_hint`、`trigger_source` 字段                                                                 |
| SC-6 | `ChatResponse.updated_state` 类型为 `ConversationStateDTO`                                                                                 |
| SC-7 | `SummaryResponse.structured` 类型为 `UserNeeds`（不是 `CollectedData`）                                                                    |
| SC-8 | `EUserIntent` 包含且仅包含 5 个值：`recommend_suburbs` / `list_properties` / `property_detail` / `compare_properties` / `open_ended_query` |
| SC-9 | `npm run build` 无 TypeScript 类型错误                                                                                                     |

### Unit Tests

```
无（纯类型定义，SC-9 的构建检查即为类型测试）
```

---

## S-D: Axios Request Layer

### Objective

创建全局 axios 实例，实现请求拦截器（P1 token 注入占位）和响应拦截器（统一错误转换、429 自动重试），定义 `APIError` 类。全项目所有 HTTP 请求通过此实例发出。

### Files

```
src/lib/request.ts
```

### Specification

**`APIError` 类：**

```ts
class APIError extends Error {
  name: "APIError";
  status: number; // HTTP 状态码，网络错误为 0
  code: string; // 后端 error 字段，网络错误为 'network_error'
  detail?: string; // 后端 detail 字段
  retryAfter?: number; // 仅 429，后端 retry_after 字段
}
```

**axios 实例配置：**

```
baseURL: process.env.NEXT_PUBLIC_API_BASE_URL
timeout: 30_000  （30 秒，覆盖 P0 双轮 LLM 的约 10s 响应时间）
headers: Content-Type: application/json, Accept: application/json
```

**请求拦截器职责：**

- P0：透传，不注入任何 header
- 预留 P1 token 注入位置（注释说明）

**响应拦截器分支（必须全部实现）：**

| 场景             | 判断条件                                       | 行为                                                     |
| ---------------- | ---------------------------------------------- | -------------------------------------------------------- |
| 成功             | `response.status` 2xx                          | 直接返回 response                                        |
| 429 首次         | `status === 429` 且 `!config._retried`         | 等待 `retry_after`（默认 2）秒后重试一次                 |
| 429 重试后仍 429 | `status === 429` 且 `config._retried === true` | 抛出 `APIError(429, code, detail, retryAfter)`           |
| 其他 HTTP 错误   | `status` 非 2xx 非 429                         | 抛出 `APIError(status, code, detail)`                    |
| 网络错误         | `!error.response`                              | 抛出 `APIError(0, 'network_error', 'Connection failed')` |

**导出：**

- `export default instance`（axios 实例）
- `export { APIError }`

### Acceptance Criteria

| ID   | Criterion                                                                          |
| ---- | ---------------------------------------------------------------------------------- |
| SD-1 | `baseURL` 等于 `process.env.NEXT_PUBLIC_API_BASE_URL`                              |
| SD-2 | `timeout` 为 30000 毫秒                                                            |
| SD-3 | 200 响应正常返回，无抛出                                                           |
| SD-4 | 429 首次时，等待 `retry_after` 秒后发起第二次请求                                  |
| SD-5 | 429 重试后仍失败，抛出 `APIError`，`status` 为 429                                 |
| SD-6 | 503 响应抛出 `APIError`，`code` 为后端返回的 `error` 字段值                        |
| SD-7 | 网络断联（无 response）抛出 `APIError`，`status` 为 0，`code` 为 `'network_error'` |
| SD-8 | `APIError` 是 `Error` 的子类（`instanceof Error === true`）                        |
| SD-9 | 同一请求不会无限重试（`_retried` 标记防止循环）                                    |

### Unit Tests

```
__tests__/lib/request.test.ts

test_200_returns_response_data
test_429_retries_once_and_succeeds
test_429_retry_also_fails_throws_api_error
test_429_api_error_has_correct_status_and_retry_after
test_503_throws_api_error_with_backend_code
test_network_error_throws_api_error_status_0
test_network_error_code_is_network_error
test_api_error_is_instance_of_error
test_request_not_retried_more_than_once
```

---

## S-E: API Functions

### Objective

将 P0 的三个后端接口封装为具名函数，统一使用 S-D 的 axios 实例，组件和 hook 不直接调用 axios。P1 接口以注释形式占位。

### Files

```
src/lib/api.ts
```

### Specification

**必须导出的函数：**

```ts
postChat(message: string, state: ConversationStateDTO): Promise<ChatResponse>
postChatSummary(collectedData: CollectedData, sessionId: string, initialIntent?: EUserIntent): Promise<SummaryResponse>
getHealth(): Promise<{ status: string }>
```

**`postChat` 请求体格式（严格按后端 S-D ChatRequest）：**

```json
{ "message": "...", "state": { ConversationStateDTO } }
```

**`postChatSummary` 请求体格式（严格按后端 §17.3 SummaryRequest）：**

```json
{
  "collected_data": { CollectedData },
  "session_id":     "uuid",
  "initial_intent": "open_ended_query"
}
```

注意 key 命名：`collected_data`（snake_case），与后端 Pydantic 字段名一致。

**P1 占位注释格式：**

```ts
// @todo P1: getSession(sessionId: string)
// @todo P1: deleteSession(sessionId: string)
```

### Acceptance Criteria

| ID   | Criterion                                                            |
| ---- | -------------------------------------------------------------------- |
| SE-1 | `postChat` 发送的请求体包含 `message` 和 `state` 字段                |
| SE-2 | `postChatSummary` 发送的请求体 key 为 `collected_data`（snake_case） |
| SE-3 | `postChatSummary` 的 `initial_intent` 默认值为 `'open_ended_query'`  |
| SE-4 | 所有函数返回 `response.data`（不是整个 response 对象）               |
| SE-5 | 所有函数在后端返回错误时向上抛出 `APIError`（不吞异常）              |
| SE-6 | `getHealth` 路径为 `/health`                                         |
| SE-7 | 没有任何组件或 hook 直接 `import axios`                              |

### Unit Tests

```
__tests__/lib/api.test.ts

test_post_chat_sends_message_and_state
test_post_chat_request_body_has_correct_keys
test_post_chat_returns_chat_response
test_post_chat_throws_on_503
test_post_chat_summary_sends_snake_case_collected_data
test_post_chat_summary_default_initial_intent_is_open_ended_query
test_post_chat_summary_returns_summary_response
test_get_health_returns_status_healthy
```

---

## S-F: Utility Functions

### Objective

实现全项目共用的纯函数工具，包括金额格式化和会话初始状态工厂函数。

### Files

```
src/lib/utils.ts
```

### Specification

**必须导出的函数：**

**`formatAUD(amount: number): string`**

- 使用 `Intl.NumberFormat('en-AU', { style: 'currency', currency: 'AUD', maximumFractionDigits: 0 })`
- 输入 `1200000` → 输出 `'$1,200,000'`
- 输入 `0` → 输出 `'$0'`

**`createInitialState(sessionId: string): ConversationStateDTO`**

- 返回严格符合 `ConversationStateDTO` 类型的初始对象
- 所有 `collectedData` 字段为 `null`（M1 / M2 / M3 / M4 全部字段）
- `status: 'IN_PROGRESS'`
- `currentModule: 'M1_PROPERTY_NEEDS'`
- `completionStatus: { M1: false, M2: false, M3: false, M4: false }`
- `conversationHistory: []`
- `finalNeeds: null`
- `borrowing_capacity: null`
- `budget_gap: null`

### Acceptance Criteria

| ID    | Criterion                                                                        |
| ----- | -------------------------------------------------------------------------------- |
| SF-1  | `formatAUD(1200000)` 返回 `'$1,200,000'`                                         |
| SF-2  | `formatAUD(0)` 返回 `'$0'`                                                       |
| SF-3  | `formatAUD(850000)` 不含小数点                                                   |
| SF-4  | `createInitialState('x').sessionId` 等于 `'x'`                                   |
| SF-5  | `createInitialState('x').status` 等于 `'IN_PROGRESS'`                            |
| SF-6  | `createInitialState('x').currentModule` 等于 `'M1_PROPERTY_NEEDS'`               |
| SF-7  | `createInitialState('x').collectedData.m1` 所有值为 `null`                       |
| SF-8  | `createInitialState('x').collectedData.m4` 所有值为 `null`，含 `loan_term_years` |
| SF-9  | `createInitialState('x').borrowing_capacity` 为 `null`                           |
| SF-10 | `createInitialState('x').budget_gap` 为 `null`                                   |
| SF-11 | `createInitialState('x').conversationHistory` 长度为 0                           |
| SF-12 | 函数为纯函数，两次调用同一 id 返回结构相同的独立对象（引用不同）                 |

### Unit Tests

```
__tests__/lib/utils.test.ts

test_format_aud_typical_price
test_format_aud_zero
test_format_aud_no_decimal_places
test_format_aud_small_amount
test_create_initial_state_uses_provided_session_id
test_create_initial_state_status_is_in_progress
test_create_initial_state_current_module_is_m1
test_create_initial_state_all_completion_flags_are_false
test_create_initial_state_m1_all_null
test_create_initial_state_m2_all_null
test_create_initial_state_m3_all_null
test_create_initial_state_m4_all_null_including_loan_term
test_create_initial_state_borrowing_capacity_null
test_create_initial_state_budget_gap_null
test_create_initial_state_conversation_history_empty
test_create_initial_state_returns_independent_objects
```

---

## S-G: Conversation Store (Zustand)

### Objective

实现 P0 的核心客户端状态容器。前端在 P0 阶段持有完整 `ConversationStateDTO`，每次 `POST /chat` 返回后用 `updated_state` 完整替换（不 merge），并同步持久化到 `sessionStorage` 防止刷新丢失。

### Files

```
src/stores/conversationStore.ts
```

### Specification

**Store 结构：**

```ts
interface ConversationStore {
  // 状态
  sessionId: string | null;
  state: ConversationStateDTO | null; // 后端 ConversationStateDTO，完整对象
  messages: UIMessage[]; // UI 专用，含 isLoading 等前端字段
  routing: RoutingPayload | null;
  isLoading: boolean; // POST /chat 进行中

  // Actions
  initSession(sessionId: string): void; // 生成初始 state，写 sessionStorage
  setUpdatedState(state: ConversationStateDTO): void; // 完整替换，写 sessionStorage
  addUserMessage(content: string): void; // 乐观 UI
  addAssistantMessage(content: string): void;
  setAssistantLoading(loading: boolean): void; // 最后一条 assistant 消息的 loading 状态
  setLoading(loading: boolean): void;
  setRouting(routing: RoutingPayload): void;
  restoreFromStorage(sessionId: string): boolean; // 从 sessionStorage 恢复，返回是否成功
  clearSession(): void; // 清空状态和 sessionStorage
}
```

**`UIMessage` 类型（前端专用，不传后端）：**

```ts
interface UIMessage {
  id: string; // 前端生成 uuid
  role: "user" | "assistant";
  content: string;
  isLoading: boolean; // true 时显示 TypingIndicator
  timestamp: Date;
  // 可选附件卡片（assistant 消息专用）
  borrowingCapacity?: BorrowingCapacityResult;
  budgetGap?: BudgetGapResult;
}
```

**关键行为规则：**

1. **`setUpdatedState` 必须完整替换**：`this.state = updated_state`，禁止 `Object.assign` 或 spread merge
2. **`BorrowingCapacityCard` 触发规则**：当 `updated_state.borrowing_capacity` 首次从 `null` 变为非 `null` 时，在 messages 中 append 一条含 `borrowingCapacity` 的 assistant 消息
3. **`BudgetGapCard` 触发规则**：当 `updated_state.budget_gap?.has_gap === true` 时，append 一条含 `budgetGap` 的 assistant 消息
4. **sessionStorage key 格式**：`conversation_state_{sessionId}`，值为 `JSON.stringify(state)`
5. **`restoreFromStorage`**：读取 sessionStorage，parse 后写入 `this.state` 和 `this.messages`（messages 从 `conversationHistory` 重建），返回 `true`；key 不存在返回 `false`

### Acceptance Criteria

| ID    | Criterion                                                                          |
| ----- | ---------------------------------------------------------------------------------- |
| SG-1  | `initSession('abc')` 后 `store.state.sessionId === 'abc'`                          |
| SG-2  | `initSession` 后 `store.state.status === 'IN_PROGRESS'`                            |
| SG-3  | `setUpdatedState` 完整替换 state（前后 state 引用不同）                            |
| SG-4  | `setUpdatedState` 不保留旧 state 的任何字段（完整替换验证）                        |
| SG-5  | `setUpdatedState` 后 sessionStorage 中对应 key 已更新                              |
| SG-6  | `borrowing_capacity` 首次非 null 时 messages 中出现含 `borrowingCapacity` 的条目   |
| SG-7  | `budget_gap.has_gap === true` 时 messages 中出现含 `budgetGap` 的条目              |
| SG-8  | `budget_gap.has_gap === false` 时不追加 BudgetGapCard 消息                         |
| SG-9  | `routing` 初始为 `null`，`setRouting` 后正确赋值                                   |
| SG-10 | `isLoading` 初始为 `false`，`setLoading(true/false)` 正确切换                      |
| SG-11 | `restoreFromStorage` 在 key 存在时返回 `true` 并恢复 state                         |
| SG-12 | `restoreFromStorage` 在 key 不存在时返回 `false`，state 不变                       |
| SG-13 | `clearSession` 后 state、messages、routing 全部为初始值，sessionStorage key 被删除 |

### Unit Tests

```
__tests__/stores/conversationStore.test.ts

test_init_session_sets_session_id
test_init_session_status_is_in_progress
test_init_session_writes_to_session_storage
test_set_updated_state_replaces_completely
test_set_updated_state_not_merge
test_set_updated_state_writes_session_storage
test_borrowing_capacity_appends_card_message_when_first_non_null
test_borrowing_capacity_does_not_append_when_already_present
test_budget_gap_appends_card_message_when_has_gap_true
test_budget_gap_no_append_when_has_gap_false
test_set_routing_stores_payload
test_routing_null_initially
test_set_loading_toggles_is_loading
test_restore_from_storage_returns_true_and_restores_state
test_restore_from_storage_returns_false_when_no_key
test_clear_session_resets_all_state
test_clear_session_removes_session_storage_key
```

---

## S-H: UI Store (Zustand)

### Objective

实现 UI 全局状态：sidebar 折叠状态和 modal 管理。

### Files

```
src/stores/uiStore.ts
```

### Specification

**Store 结构：**

```ts
interface UIStore {
  sidebarCollapsed: boolean;
  activeModal: string | null;

  toggleSidebar(): void;
  setSidebarCollapsed(v: boolean): void;
  openModal(id: string): void;
  closeModal(): void;
}
```

**初始值：** `sidebarCollapsed: false`，`activeModal: null`

### Acceptance Criteria

| ID   | Criterion                                             |
| ---- | ----------------------------------------------------- |
| SH-1 | `sidebarCollapsed` 初始为 `false`                     |
| SH-2 | `toggleSidebar` 将 `false → true → false`             |
| SH-3 | `setSidebarCollapsed(true)` 直接设置为 `true`         |
| SH-4 | `openModal('confirm')` 后 `activeModal === 'confirm'` |
| SH-5 | `closeModal` 后 `activeModal === null`                |

### Unit Tests

```
__tests__/stores/uiStore.test.ts

test_sidebar_collapsed_initial_false
test_toggle_sidebar_false_to_true
test_toggle_sidebar_true_to_false
test_set_sidebar_collapsed_directly
test_open_modal_sets_active_modal
test_close_modal_sets_null
```

---

## S-I: Shared UI Components

### Objective

实现原子级 UI 组件（`Button`、`Chip`、`AIBadge`、`Skeleton`），这些组件无业务逻辑，仅负责视觉呈现。

### Files

```
src/components/ui/Button.tsx
src/components/ui/Chip.tsx
src/components/ui/AIBadge.tsx
src/components/ui/Skeleton.tsx
src/components/icons/MaterialSymbol.tsx
```

### Specification

**`Button`：**

- Props: `variant: 'primary' | 'secondary' | 'ghost' | 'danger'`（默认 `'secondary'`）、`size: 'sm' | 'md' | 'lg'`（默认 `'md'`）、`loading: boolean`、`icon?: string`（Material Symbol 名）、继承 `React.ButtonHTMLAttributes<HTMLButtonElement>`
- `loading` 或 `disabled` 时：`disabled` 属性为 true，onClick 不触发
- `loading` 时显示旋转 spinner，隐藏文字（或文字变灰）

**`Chip`：**

- Props: `label: string`、`color: 'primary' | 'tertiary' | 'error' | 'neutral'`（默认 `'neutral'`）、`icon?: string`、`onRemove?: () => void`
- 始终 `rounded-full`
- 有 `onRemove` 时显示 ✕ 按钮

**`AIBadge`：**

- Props: `label?: string`（默认 `'AI'`）、`size: 'sm' | 'md'`（默认 `'sm'`）
- 使用 `.glass-ai` class
- 包含 `auto_awesome` Material Symbol（`FILL: 1`，tertiary 色）

**`Skeleton`：**

- 导出 `SkeletonText`（单行，宽度可配置）、`SkeletonMessage`（消息气泡形状）
- 使用 `animate-pulse bg-surface-container-high rounded`

**`MaterialSymbol`：**

- Props: `name: string`（图标名）、`filled?: boolean`（默认 false）、`size?: number`（px）、`className?: string`
- 封装 `<span className="material-symbols-outlined">` 并处理 font-variation-settings

### Acceptance Criteria

| ID   | Criterion                                                       |
| ---- | --------------------------------------------------------------- |
| SI-1 | `<Button variant="primary">` 渲染出 `bg-primary-container` 样式 |
| SI-2 | `<Button loading>` 时 button 元素的 `disabled` 属性为 true      |
| SI-3 | `<Button loading>` 时 onClick 不触发                            |
| SI-4 | `<Button disabled>` 时 onClick 不触发                           |
| SI-5 | `<Chip onRemove={fn}>` 渲染出 ✕ 按钮，点击调用 fn               |
| SI-6 | `<Chip>` 无 `onRemove` 时不渲染 ✕ 按钮                          |
| SI-7 | `<AIBadge>` 包含 `auto_awesome` 图标文本                        |
| SI-8 | `<SkeletonText>` 含 `animate-pulse` class                       |
| SI-9 | `<MaterialSymbol name="home" filled>` 渲染出含 `FILL` 1 的 span |

### Unit Tests

```
__tests__/components/ui/Button.test.tsx

test_primary_variant_renders
test_secondary_variant_renders
test_ghost_variant_renders
test_danger_variant_renders
test_loading_disables_button
test_loading_does_not_trigger_onclick
test_disabled_does_not_trigger_onclick
test_renders_icon_when_provided
test_sm_md_lg_sizes_render

__tests__/components/ui/Chip.test.tsx

test_renders_label
test_shows_remove_button_when_on_remove_provided
test_no_remove_button_without_on_remove
test_calls_on_remove_when_x_clicked
test_rounded_full_class_present

__tests__/components/ui/AIBadge.test.tsx

test_renders_auto_awesome_icon
test_default_label_is_ai
test_custom_label_renders

__tests__/components/ui/Skeleton.test.tsx

test_skeleton_text_has_animate_pulse
test_skeleton_message_has_animate_pulse
```

---

## S-J: Chat Components

### Objective

实现对话界面的所有专用组件：消息气泡、输入框、进度指示器、借款能力卡片、预算缺口卡片、等待动画。

### Files

```
src/components/chat/ChatInput.tsx
src/components/chat/ChatMessage.tsx
src/components/chat/ModuleProgress.tsx
src/components/chat/BorrowingCapacityCard.tsx
src/components/chat/BudgetGapCard.tsx
src/components/chat/TypingIndicator.tsx
```

### Specification

**`ChatInput`：**

- Props: `onSend(message: string): void`、`isLoading: boolean`、`disabled?: boolean`、`placeholder?: string`
- `textarea` 自动扩展高度（min 56px，max 160px，`overflow-y: auto`）
- `Enter` → `onSend(trimmed)`，`Shift+Enter` → 换行
- 空消息（trim 后为空）不触发 `onSend`
- 发送后清空 textarea
- `isLoading` 时：textarea 和 send button 均 `disabled`
- 容器使用 `.glass-ai` class，`focus-within` 时无额外处理（glass-ai 已有 glow）

**`ChatMessage`：**

- Props: `role: 'user' | 'assistant'`、`content: string`、`isLoading?: boolean`、`timestamp?: Date`、`borrowingCapacity?: BorrowingCapacityResult`、`budgetGap?: BudgetGapResult`
- user：右对齐，`bg-surface-container-high rounded-2xl rounded-br-md`
- assistant：左对齐，无背景，左侧 `auto_awesome` 图标（tertiary 色，FILL 1）
- `isLoading` 时显示 `TypingIndicator` 替代 content
- `borrowingCapacity` 非 null 时在消息下方渲染 `BorrowingCapacityCard`
- `budgetGap` 非 null 时在消息下方渲染 `BudgetGapCard`

**`ModuleProgress`：**

- Props: `completionStatus: { M1: boolean; M2: boolean; M3: boolean; M4: boolean }`、`currentModule: ModuleID`
- 4 个节点横向排列：M1(Property) / M2(Lifestyle) / M3(Location) / M4(Budget)
- 完成态：primary-container 填充圆 + checkmark
- 当前态：primary-container 边框空心圆 + `animate-pulse`
- 待完成：outline-variant 空心圆

**`BorrowingCapacityCard`：**

- Props: `data: BorrowingCapacityResult`
- 必须渲染：`estimated_capacity`（`formatAUD`）、`annual_rate`、`loan_term_years`、`disclaimer`
- `disclaimer` 必须可见（`toBeVisible()` 断言通过），不可用 `hidden`、`sr-only`、`opacity-0` 隐藏

**`BudgetGapCard`：**

- Props: `data: BudgetGapResult`
- `has_gap === false` 时返回 `null`（不渲染任何元素）
- `has_gap === true` 时渲染：`gap_percentage`、`reference_suburb`、`suggested_actions`（Chip 列表）

**`TypingIndicator`：**

- 三个圆点 `●●●`，交错 CSS `animation`（`opacity` 淡入淡出）
- tertiary 色，无 Props

### Acceptance Criteria

| ID    | Criterion                                                      |
| ----- | -------------------------------------------------------------- |
| SJ-1  | `ChatInput` Enter 发送后 textarea 内容清空                     |
| SJ-2  | `ChatInput` Shift+Enter 不触发 onSend                          |
| SJ-3  | `ChatInput` 空消息不触发 onSend                                |
| SJ-4  | `ChatInput` isLoading 时 textarea disabled                     |
| SJ-5  | `ChatInput` isLoading 时 send button disabled                  |
| SJ-6  | `ChatMessage role="user"` 元素右对齐                           |
| SJ-7  | `ChatMessage role="assistant"` 含 `auto_awesome` 文本          |
| SJ-8  | `ChatMessage isLoading` 时渲染 TypingIndicator，不渲染 content |
| SJ-9  | `ModuleProgress` M1 完成时对应节点含 checkmark                 |
| SJ-10 | `ModuleProgress` currentModule 对应节点含 `animate-pulse`      |
| SJ-11 | `BorrowingCapacityCard` 渲染 `$560,000`（formatAUD 结果）      |
| SJ-12 | `BorrowingCapacityCard` disclaimer 文字可见（`toBeVisible()`） |
| SJ-13 | `BudgetGapCard has_gap=false` 返回空（container 为空 DOM）     |
| SJ-14 | `BudgetGapCard has_gap=true` 渲染 suggested_actions chips      |

### Unit Tests

```
__tests__/components/chat/ChatInput.test.tsx

test_enter_calls_on_send
test_enter_sends_trimmed_message
test_shift_enter_does_not_send
test_empty_message_does_not_send
test_clears_textarea_after_send
test_loading_disables_textarea
test_loading_disables_send_button
test_not_loading_enables_textarea
test_default_placeholder_present
test_custom_placeholder_rendered

__tests__/components/chat/ChatMessage.test.tsx

test_user_message_has_correct_alignment_class
test_assistant_message_contains_auto_awesome
test_loading_shows_typing_indicator
test_loading_hides_content
test_borrowing_capacity_card_rendered_when_provided
test_budget_gap_card_rendered_when_provided

__tests__/components/chat/ModuleProgress.test.tsx

test_completed_module_shows_checkmark
test_current_module_has_animate_pulse
test_pending_module_has_no_checkmark

__tests__/components/chat/BorrowingCapacityCard.test.tsx

test_renders_formatted_capacity
test_renders_annual_rate
test_renders_loan_term
test_compliance_disclaimer_in_document          # ⚠️ 合规
test_compliance_disclaimer_visible              # ⚠️ 合规 toBeVisible()
test_compliance_disclaimer_contains_rate_source # ⚠️ 合规

__tests__/components/chat/BudgetGapCard.test.tsx

test_returns_null_when_has_gap_false
test_renders_gap_percentage_when_has_gap_true
test_renders_reference_suburb
test_renders_all_suggested_actions
```

---

## S-K: Layout Components

### Objective

实现导航布局组件：桌面端侧边栏、移动端顶部栏和底部栏。

### Files

```
src/components/layout/SideNavBar.tsx
src/components/layout/TopNavBar.tsx
src/components/layout/BottomNavBar.tsx
src/app/(main)/layout.tsx
```

### Specification

**`SideNavBar`：**

- Props: `collapsed: boolean`、`onToggleCollapse(): void`、`activePath: string`
- 展开：`w-[260px]`，显示文字 + 图标
- 折叠：`w-[72px]`，仅图标，hover 显示 Tooltip
- `md:flex hidden`（移动端隐藏）
- 顶部：Logo "Homi AI" + collapse 按钮（`left_panel_close` icon）
- New Chat 按钮：点击调用 `conversationStore.clearSession()`，`router.push('/')`
- 会话历史：调用 `useChatHistory()` hook 获取（`GET /api/v1/chats`），最多显示 10 条，每项显示 intent 标签 + 相对时间（S-P 实现）
- 导航项：Home（可用）、Search（disabled，灰色，tooltip "Coming in next release"）
- 底部：Settings 图标（disabled，P2）

**`TopNavBar`（移动端）：**

- `md:hidden flex`
- 左：Logo + `auto_awesome` 图标
- 右：notifications 图标、用户头像占位

**`BottomNavBar`（移动端）：**

- `md:hidden fixed bottom-0`
- 4 个 tab：Home / Search / Saved / Profile
- 当前 tab 用 primary 色高亮

**`(main)/layout.tsx`：**

- 读取 `uiStore.sidebarCollapsed`
- 桌面端：`<SideNavBar>` + `<main>` 左偏移（260px 或 72px）
- 移动端：`<TopNavBar>` + `<main>` + `<BottomNavBar>`

### Acceptance Criteria

| ID   | Criterion                                                         |
| ---- | ----------------------------------------------------------------- |
| SK-1 | `SideNavBar collapsed=false` 宽度为 260px                         |
| SK-2 | `SideNavBar collapsed=true` 宽度为 72px                           |
| SK-3 | `SideNavBar` 在 `md` 断点以下不显示                               |
| SK-4 | New Chat 按钮点击后路由跳转至 `/`                                 |
| SK-5 | Search 导航项有 disabled 样式（cursor-not-allowed 或 opacity-50） |
| SK-6 | `TopNavBar` 在 `md` 断点以上不显示                                |
| SK-7 | `BottomNavBar` 固定在底部（`fixed bottom-0`）                     |

### Unit Tests

```
__tests__/components/layout/SideNavBar.test.tsx

test_expanded_has_260px_width_class
test_collapsed_has_72px_width_class
test_new_chat_button_present
test_search_item_is_disabled
```

---

## S-L: HomePage

### Objective

实现 `/` 路由页面：新建会话入口，用户发送第一条消息后跳转至 ChatPage。

### Files

```
src/app/(main)/page.tsx
```

### Specification

**页面布局：**

- 全屏居中（`flex items-center justify-center h-screen`）
- 主内容最大宽度 `max-w-3xl`，垂直居中排列

**必须包含的元素：**

1. `auto_awesome` 图标（tertiary 色，`FILL 1`，64px，`animate-pulse`）
2. 问候标题：`text-display-md`，P0 固定文字 `"How can I help you today?"`
3. `ChatInput` 组件（`onSend` 绑定 `handleFirstMessage`）
4. 底部免责声明：`text-caption text-outline`，文字：`"Homi AI can make mistakes. Verify important property or financial information."`

**`handleFirstMessage(message: string)` 流程：**

1. 生成新 `sessionId`（`uuid()`）
2. 调用 `conversationStore.initSession(sessionId)`
3. 立即 `router.push('/chat/${sessionId}')`（乐观导航，不等后端）
4. ChatPage 加载后接管发送

**不在此页面调用 `POST /chat`。**

### Acceptance Criteria

| ID   | Criterion                                        |
| ---- | ------------------------------------------------ |
| SL-1 | 页面含 `auto_awesome` 图标                       |
| SL-2 | 标题文字为 `"How can I help you today?"`         |
| SL-3 | `ChatInput` 可见且可交互                         |
| SL-4 | 发送消息后，`conversationStore.sessionId` 已设置 |
| SL-5 | 发送消息后，路由跳转至 `/chat/{sessionId}`       |
| SL-6 | 底部免责声明文字可见                             |
| SL-7 | 页面在移动端（375px 宽）无横向滚动条             |

### Unit Tests

```
无（页面逻辑依赖路由跳转，属于集成层；路由逻辑在 SL-4/SL-5 由手动验收覆盖）
```

---

## S-M: ChatPage

### Objective

实现 `/chat/[sessionId]` 路由页面：完整的对话界面，调用 `POST /chat` 驱动 M1→M4 引导流程，处理 `updated_state` 替换、借款能力卡片、预算缺口卡片和路由完成 CTA。

### Files

```
src/app/(main)/chat/[sessionId]/page.tsx
src/hooks/useChat.ts
src/hooks/useSession.ts
```

### Specification

**`useSession(sessionId: string)`：**

- 组件挂载时调用 `conversationStore.restoreFromStorage(sessionId)`
- 若恢复失败（返回 false），调用 `conversationStore.initSession(sessionId)`
- 返回 `{ isRestored: boolean }`

**`useChat()`：**

- 从 `conversationStore` 取 `state`、`isLoading`、store actions
- `sendMessage(content: string)` 流程（固定顺序）：
  1. `content.trim()` 为空时 return
  2. `store.setLoading(true)`
  3. `store.addUserMessage(content)`（乐观 UI）
  4. `store.addAssistantMessage('')` + `store.setAssistantLoading(true)`（loading 气泡）
  5. `await postChat(content, store.state)`
  6. `store.setAssistantLoading(false)`，用 `response.reply` 更新最后一条 assistant 消息
  7. `store.setUpdatedState(response.updated_state)`（完整替换）
  8. 若 `response.routing` 非 null：`store.setRouting(response.routing)`
  9. catch `APIError`：`store.setAssistantLoading(false)` + 移除 loading 气泡 + Toast 错误提示
  10. finally：`store.setLoading(false)`
- 返回 `{ sendMessage, isLoading }`

**ChatPage 布局（固定结构）：**

```
<div className="flex flex-col h-screen">
  <ModuleProgress .../>               {/* sticky top-0 */}

  <div className="flex-1 overflow-y-auto pb-32">  {/* 消息列表 */}
    {messages.map(msg => <ChatMessage key={msg.id} {...msg} />)}

    {routing && (                      {/* 路由完成 CTA */}
      <div className="glass-ai rounded-xl p-md m-md">
        <p>Ready to find properties...</p>
        <Button variant="primary" onClick={handleViewProperties}>
          View Matching Properties
        </Button>
      </div>
    )}
  </div>

  <div className="fixed bottom-0 ... bg-surface/80 backdrop-blur-glass">
    <ChatInput onSend={sendMessage} isLoading={isLoading} />
    <p className="text-caption text-outline text-center mt-2">
      Homi AI can make mistakes. Verify important property or financial information.
    </p>
  </div>
</div>
```

**路由 CTA 行为：**

- `handleViewProperties`：将 `routing` 存入 sessionStorage（key: `routing_payload_{sessionId}`），`router.push('/properties')`
- `/properties` 在 P2 上线前：显示 toast "Coming soon" 替代跳转

**会话恢复（页面刷新）：**

```
1. URL 取 sessionId
2. useSession(sessionId) → restoreFromStorage
3. 成功 → 渲染历史消息，继续对话
4. 失败 → 空对话，等待用户输入
```

### Acceptance Criteria

| ID    | Criterion                                                       |
| ----- | --------------------------------------------------------------- |
| SM-1  | 页面加载时尝试从 sessionStorage 恢复会话                        |
| SM-2  | 发送消息后，用户消息立即出现在列表（乐观 UI）                   |
| SM-3  | AI 回复未到达时，显示 loading 气泡（TypingIndicator）           |
| SM-4  | AI 回复到达后，loading 气泡替换为 reply 文字                    |
| SM-5  | `updated_state` 完整替换 store（非 merge）                      |
| SM-6  | `routing` 非 null 时，CTA 卡片出现在消息列表底部                |
| SM-7  | `borrowing_capacity` 首次非 null 时，BorrowingCapacityCard 出现 |
| SM-8  | `budget_gap.has_gap === true` 时，BudgetGapCard 出现            |
| SM-9  | 503 错误时 loading 气泡消失，Toast 提示可见                     |
| SM-10 | `ModuleProgress` 随 `completionStatus` 实时更新                 |
| SM-11 | 底部固定区域含免责声明文字                                      |
| SM-12 | 发送中 `ChatInput` 处于 disabled 状态                           |

### Unit Tests

```
__tests__/hooks/useChat.test.ts

test_send_message_calls_post_chat_with_state
test_send_empty_message_does_nothing
test_adds_user_message_optimistically
test_shows_assistant_loading_before_response
test_replaces_loading_with_reply_on_success
test_calls_set_updated_state_with_response_state
test_sets_routing_when_response_has_routing
test_clears_loading_on_503_error
test_shows_toast_on_network_error
test_set_loading_false_in_finally

__tests__/hooks/useSession.test.ts

test_restores_from_storage_on_mount
test_inits_session_when_storage_not_found
test_returns_is_restored_true_when_found
test_returns_is_restored_false_when_not_found
```

---

## S-N: Test Infrastructure

### Objective

搭建测试基础设施：Vitest 配置、MSW 服务、完整 fixture 数据，为 S-O 的全量测试提供支撑。

### Files

```
vitest.config.ts
vitest.setup.ts
__tests__/mocks/server.ts
__tests__/mocks/handlers.ts
__tests__/mocks/fixtures.ts
```

### Specification

**`vitest.config.ts` 关键配置：**

- `environment: 'jsdom'`
- `globals: true`（无需每个文件 import describe/it/expect）
- `setupFiles: ['./vitest.setup.ts']`
- `coverage.thresholds`：branches / functions / lines / statements 全部 **≥ 80%**
- `coverage.exclude`：`src/types/**`、`src/app/**`、`src/styles/**`
- `resolve.alias`：`@` → `./src`

**MSW handlers 必须覆盖：**

| 方法 | 路径            | 默认响应                            |
| ---- | --------------- | ----------------------------------- |
| POST | `/chat`         | `mockChatResponse`（routing: null） |
| POST | `/chat/summary` | `mockSummaryResponse`               |
| GET  | `/health`       | `{ status: 'healthy' }`             |
| GET  | `/chats`        | `mockChatSessions`（2 条 session）  |

**fixtures 必须包含：**

- `mockBorrowingCapacity: BorrowingCapacityResult`（`estimated_capacity: 560000`，含完整 `disclaimer`）
- `mockBudgetGap: BudgetGapResult`（`has_gap: true`，`reference_suburb: 'Brunswick'`）
- `mockChatResponse: ChatResponse`（`routing: null`，`updated_state` 含 m1.property_type: 'house'）
- `mockChatResponseWithRouting: ChatResponse`（`routing.intent: 'list_properties'`）
- `mockSummaryResponse: SummaryResponse`
- `mockChatSessions: ChatSessionDTO[]`（2 条，一条 `initialIntent: 'list_properties'`，一条 `initialIntent: null`）

**`vitest.setup.ts`：**

- `import '@testing-library/jest-dom'`
- `beforeAll / afterEach / afterAll` 管理 MSW server 生命周期

### Acceptance Criteria

| ID   | Criterion                                                                  |
| ---- | -------------------------------------------------------------------------- |
| SN-1 | `npm run test` 执行成功，无配置错误                                        |
| SN-2 | `npm run test:coverage` 输出覆盖率报告                                     |
| SN-3 | MSW 拦截 `POST /chat` 并返回 `mockChatResponse`                            |
| SN-4 | `mockBorrowingCapacity.disclaimer` 为非空字符串，含利率数值                |
| SN-5 | `mockChatResponseWithRouting.routing.intent` 为 `'list_properties'`        |
| SN-6 | `@` alias 在测试文件中可用（`import from '@/lib/utils'` 无报错）           |
| SN-7 | `screen.getByText` 等 jest-dom 断言在所有测试文件中可用（无需显式 import） |

### Unit Tests

```
无（基础设施本身不测试，SN-1 至 SN-7 为验收标准）
```

---

## S-O: Unit Tests

### Objective

基于 S-N 的测试基础设施，为所有业务文件编写单元测试，确保 branches / functions / lines / statements **全部 ≥ 80%**，`BorrowingCapacityCard` 合规测试达到 100%。

### Files

```
__tests__/lib/utils.test.ts             (SF 对应)
__tests__/lib/request.test.ts           (SD 对应)
__tests__/lib/api.test.ts               (SE 对应)
__tests__/stores/conversationStore.test.ts  (SG 对应)
__tests__/stores/uiStore.test.ts        (SH 对应)
__tests__/components/ui/Button.test.tsx     (SI 对应)
__tests__/components/ui/Chip.test.tsx       (SI 对应)
__tests__/components/ui/AIBadge.test.tsx    (SI 对应)
__tests__/components/ui/Skeleton.test.tsx   (SI 对应)
__tests__/components/chat/ChatInput.test.tsx            (SJ 对应)
__tests__/components/chat/ChatMessage.test.tsx          (SJ 对应)
__tests__/components/chat/ModuleProgress.test.tsx       (SJ 对应)
__tests__/components/chat/BorrowingCapacityCard.test.tsx (SJ 对应)
__tests__/components/chat/BudgetGapCard.test.tsx        (SJ 对应)
__tests__/components/layout/SideNavBar.test.tsx         (SK 对应)
__tests__/hooks/useChat.test.ts         (SM 对应)
__tests__/hooks/useSession.test.ts      (SM 对应)
__tests__/hooks/useChatHistory.test.ts  (SP 对应)
__tests__/components/layout/ChatHistoryList.test.tsx    (SP 对应，若抽出子组件)
```

### Specification

所有测试函数名已在对应 Story（S-D 至 S-M）的 **Unit Tests** 小节中列出，此处不重复。

**覆盖率规则：**

| 文件                                        | 最低覆盖率 | 说明                                                            |
| ------------------------------------------- | ---------- | --------------------------------------------------------------- |
| `lib/utils.ts`                              | 100%       | 纯函数，全分支必须覆盖                                          |
| `lib/request.ts`                            | 100%       | 拦截器所有分支（成功、429重试、429失败、503、网络错误）必须覆盖 |
| `lib/api.ts`                                | 100%       | 所有函数正常 + 异常路径                                         |
| `stores/conversationStore.ts`               | ≥ 90%      | 所有 action + 边界条件                                          |
| `stores/uiStore.ts`                         | 100%       | 逻辑简单                                                        |
| `components/chat/BorrowingCapacityCard.tsx` | **100%**   | 合规要求，disclaimer 可见性必须测试                             |
| `hooks/useChatHistory.ts`                   | ≥ 80%      | fetch、截取、错误静默三条主路径                                 |
| 其余文件                                    | ≥ 80%      | 项目统一阈值                                                    |

**合规测试（`BorrowingCapacityCard`）——CI 失败门禁：**

```
test_compliance_disclaimer_in_document    → toBeInTheDocument()
test_compliance_disclaimer_visible        → toBeVisible()（验证无 CSS 隐藏）
test_compliance_disclaimer_contains_rate_source → /RBA F5/
```

以上三个测试任意一个失败，CI 阻断，PR 不可合并。

### Acceptance Criteria

| ID   | Criterion                                                          |
| ---- | ------------------------------------------------------------------ |
| SO-1 | `npm run test` 全部通过，0 failures                                |
| SO-2 | `npm run test:coverage` 的 branches ≥ 80%                          |
| SO-3 | `npm run test:coverage` 的 functions ≥ 80%                         |
| SO-4 | `npm run test:coverage` 的 lines ≥ 80%                             |
| SO-5 | `npm run test:coverage` 的 statements ≥ 80%                        |
| SO-6 | `BorrowingCapacityCard` 的三个合规测试全部通过                     |
| SO-7 | CI workflow 在覆盖率低于 80% 时自动失败                            |
| SO-8 | 无测试使用 `it.skip` 或 `describe.skip` 跳过（除非有文档说明原因） |

### Unit Tests

见各对应 Story 的 Unit Tests 小节（S-D 至 S-M）。

---

---

## S-P: Chat History Sidebar

### Objective

在 SideNavBar 中渲染会话历史列表：页面挂载时通过 `useChatHistory()` hook 调用 `GET /api/v1/chats`，将返回的 session 列表（最多 10 条，后端已按 `updatedAt` 倒序）渲染为可点击条目，点击后跳转至 `/chat/[sessionId]`；当前活跃 session 自动高亮；loading 阶段显示骨架屏；列表为空时显示空状态。

> **In-progress session 可见性：** 后端在第一条消息发送时即写入 DB，因此即使用户尚未完成任何模块，该会话也会出现在列表中。此类条目的 `initialIntent` 为 `null`，渲染为 `'New Conversation'`（见下方 Intent 映射表）。

### Files

**新建：**

```
src/hooks/useChatHistory.ts
```

**修改：**

```
src/types/api.d.ts              — 新增 ChatSessionDTO 接口
src/constants/endpoints.ts      — 新增 CHATS 常量
src/services/chat.ts            — 新增 getChats() 函数
src/lib/utils.ts                — 新增 formatRelativeTime() 函数
src/components/layout/SideNavBar.tsx  — 渲染历史列表区域
```

### Specification

#### `src/types/api.d.ts` — 新增 `ChatSessionDTO`

```ts
export interface ChatSessionDTO {
  sessionId: string
  status: string                // 'IN_PROGRESS' | 'REQUIREMENTS_COMPLETE'
  initialIntent: string | null  // 'recommend_suburbs' | 'list_properties' | ...
  createdAt: string             // ISO 8601
  updatedAt: string             // ISO 8601
  completedAt: string | null    // ISO 8601，四个模块全完成后非 null
}
```

> 字段均为 camelCase，因为后端 `ChatSessionDTO` 继承 `PropertyAIBaseModel`（含 camelCase `alias_generator`）。

#### `src/constants/endpoints.ts` — 新增 `CHATS`

```ts
export const ENDPOINTS = {
  CHAT: 'api/v1/chat',
  CHAT_SUMMARY: 'api/v1/chat/summary',
  CHATS: 'api/v1/chats',   // 新增
} as const
```

#### `src/services/chat.ts` — 新增 `getChats()`

```ts
export function getChats(): Promise<APIResponse<ChatSessionDTO[]>> {
  return request.get<ChatSessionDTO[]>(ENDPOINTS.CHATS)
}
```

无需传参；`withCredentials: true` 已在 axios 实例配置，`propertyai_anon_id` cookie 自动随请求发送。

#### `src/lib/utils.ts` — 新增 `formatRelativeTime()`

```ts
/** 将 ISO 8601 时间字符串格式化为相对时间，如 "2 hours ago"、"Yesterday"、"3 days ago"。
 *  使用 Intl.RelativeTimeFormat('en', { numeric: 'auto' })。 */
export function formatRelativeTime(iso: string): string
```

**实现规则：**

| 差值            | 显示单位    | 示例                       |
| --------------- | ----------- | -------------------------- |
| < 60 秒         | `seconds`   | `"just now"`               |
| 60 秒 – 59 分   | `minutes`   | `"5 minutes ago"`          |
| 1 小时 – 23 小时 | `hours`     | `"2 hours ago"`            |
| 1 天 – 6 天     | `days`      | `"Yesterday"` / `"3 days ago"` |
| ≥ 7 天          | `weeks`     | `"2 weeks ago"`            |

#### `src/hooks/useChatHistory.ts`

```ts
interface UseChatHistoryReturn {
  sessions: ChatSessionDTO[]
  isLoading: boolean
}

export function useChatHistory(): UseChatHistoryReturn
```

**行为规则：**

1. 组件 mount 时触发一次 `getChats()`，不自动 refetch。
2. `response.ok === true` 时：`setSessions(response.data.slice(0, 10))`（前端截取前 10 条）。
3. `response.ok === false`（含 400 cookie 缺失、网络错误）时：静默处理，`sessions` 保持空数组，不对外暴露 error 状态。
4. 请求完成后（成功或失败）设 `isLoading = false`。

#### `src/components/layout/SideNavBar.tsx` — 会话历史区域

**Intent 显示标签映射（模块内常量，不导出）：**

```ts
const INTENT_LABELS: Record<string, string> = {
  recommend_suburbs: 'Suburb Recommendations',
  list_properties: 'Property Search',
  property_detail: 'Property Detail',
  compare_properties: 'Compare Properties',
  open_ended_query: 'Property Chat',
}
```

`initialIntent` 为 `null` 或映射中不存在时，显示 `'New Conversation'`。

**渲染规则：**

```
collapsed === true  → 整个历史区域不渲染（保持图标列布局）

collapsed === false →
  isLoading 时：
    3 条 SkeletonText 占位（高度与条目一致）

  sessions.length === 0 时：
    <p className="text-caption text-outline px-sm">No conversations yet</p>

  sessions.length > 0 时：
    <button> 列表（每条 session 一个），结构：
      主文字：INTENT_LABELS[session.initialIntent] ?? 'New Conversation'
      副文字：formatRelativeTime(session.updatedAt)
      高亮条件：activePath === `/chat/${session.sessionId}`
        → 高亮样式：bg-surface-container 或 variant="primary"（与现有 Home 高亮逻辑一致）
      点击：router.push(`/chat/${session.sessionId}`)
      ARIA：aria-label="Open conversation from {date}"
            aria-current="page"（当前活跃 session）
```

**条目样式参考（与 Navigation 区域保持一致）：**

```
div.flex.flex-col.overflow-hidden（主文字行）
  span.text-label-lg.text-on-surface（截断，1 行）
div.text-caption.text-outline（副文字行：相对时间）
```

### Acceptance Criteria

| ID    | Criterion                                                                     |
| ----- | ----------------------------------------------------------------------------- |
| SP-1  | 页面挂载时发出 `GET /api/v1/chats` 请求（MSW 可拦截验证）                     |
| SP-2  | 后端返回 12 条时，SideNavBar 只渲染 10 条条目                                 |
| SP-3  | `initialIntent: 'list_properties'` 的条目显示文字 `'Property Search'`         |
| SP-4  | `initialIntent: null` 的条目显示文字 `'New Conversation'`                     |
| SP-5  | 每条条目显示基于 `updatedAt` 的格式化相对时间                                 |
| SP-6  | 点击条目触发 `router.push('/chat/[sessionId]')`                               |
| SP-7  | `activePath === '/chat/[sessionId]'` 时对应条目有高亮样式                     |
| SP-8  | 加载中（`isLoading: true`）显示 3 条 SkeletonText                             |
| SP-9  | `sessions` 为空时显示 `'No conversations yet'`                                |
| SP-10 | API 返回 400 时静默显示空状态（不渲染错误文字）                               |
| SP-11 | `collapsed === true` 时历史列表区域不渲染任何条目或骨架                       |
| SP-12 | `formatRelativeTime` 对 2 小时前的时间返回含 `'hours'` 的字符串               |
| SP-13 | `formatRelativeTime` 对 1 天前的时间返回 `'Yesterday'`                        |
| SP-14 | 活跃条目含 `aria-current="page"` 属性                                         |

### Unit Tests

```
__tests__/hooks/useChatHistory.test.ts

test_fetches_chats_on_mount
test_truncates_to_10_sessions_when_more_returned
test_returns_empty_array_on_api_error_400
test_returns_empty_array_on_network_error
test_sets_is_loading_false_after_successful_fetch
test_sets_is_loading_false_after_failed_fetch

__tests__/lib/utils.test.ts（新增用例，追加至现有文件）

test_format_relative_time_returns_just_now_for_seconds_ago
test_format_relative_time_returns_minutes_ago
test_format_relative_time_returns_hours_ago
test_format_relative_time_returns_yesterday
test_format_relative_time_returns_days_ago
test_format_relative_time_returns_weeks_ago

__tests__/components/layout/SideNavBar.test.tsx（新增用例，追加至现有文件）

test_renders_intent_label_for_known_intent
test_renders_new_conversation_for_null_intent
test_renders_relative_time_for_each_session
test_active_session_has_aria_current_page
test_active_session_has_highlight_class
test_shows_skeleton_while_loading
test_shows_empty_state_when_no_sessions
test_navigates_to_chat_session_on_click
test_history_list_not_rendered_when_collapsed
test_silent_empty_state_on_400_error
```

---

_本文档配套后端 Part 1 Technical PRD v1.2。Part 2 接口就绪后将扩展 §3.3 P2+ 页面规范及对应 Stories。_
