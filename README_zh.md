[ENGLISH](README.md)

# Gemini Poise：Gemini API 代理与管理工具

Gemini Poise 是一个全栈应用，旨在帮助您更方便地代理和管理 Gemini API 请求。它具备 API Key 轮换、请求转发、用户认证和配置管理等核心功能，让您的 AI 应用开发和部署过程更加顺畅。

## 技术栈概览

### 后端
- **FastAPI**: 基于 Python 的高性能 Web 框架，用于构建我们的 API 服务。
- **SQLAlchemy**: Python 数据库 ORM 工具，让数据库操作变得简单。
- **Alembic**: 数据库迁移工具，帮助我们管理数据库结构的变化。
- **Redis**: 高速缓存和会话管理工具。
- **Pydantic**: 用于数据验证和设置管理，确保数据格式正确。
- **Passlib**: 处理密码哈希加密，保障用户账户安全。

### 前端
- **React**: 用于构建用户界面的 JavaScript 库。
- **Vite**: 极速的前端构建工具，提供出色的开发体验。
- **Ant Design**: 一套企业级 UI 组件库，提供丰富的开箱即用组件。
- **Tailwind CSS**: 一个实用至上的 CSS 框架，方便快速构建自定义样式。
- **React Router**: 用于管理前端路由，实现页面间的导航。
- **Axios**: 基于 Promise 的 HTTP 客户端，用于前后端数据交互。

## 核心功能一览

- **用户认证与授权**: 确保只有合法用户才能访问系统。
- **API Key 管理**: 轻松添加、编辑、删除、启用或禁用 API Key。
- **密钥存活统计**: 监控和跟踪 API 密钥状态变化，提供详细的统计数据。
- **配置管理**: 灵活设置目标 API URL 及其他系统参数。
- **API 请求代理与转发**: 无缝地代理和转发 Gemini API 请求。
- **API Key 自动轮换**: 自动管理和轮换 API Key，提升 API 的可用性。
- **令牌桶算法**: 先进的速率限制，具备智能负载均衡、采样优化和自动回退机制。
- **请求日志与监控**: 记录和监控 API 请求，便于问题排查和性能分析。

## 项目结构

```
gemini-poise/
├── alembic/                  # 数据库迁移脚本
├── app/                      # 后端应用代码
│   ├── api/                  # API 路由定义
│   ├── core/                 # 核心配置、数据库连接和安全设置
│   ├── crud/                 # 数据库操作（创建、读取、更新、删除）
│   ├── models/               # 数据库模型定义
│   ├── schemas/              # Pydantic 数据模型
│   └── tasks/                # 后台任务（如 Key 验证）
├── gemini-poise-frontend/    # React 前端应用
│   ├── public/               # 静态资源
│   ├── src/                  # 前端源代码
│   │   ├── api/              # 前端 API 请求封装
│   │   ├── assets/           # 静态资源（图片、图标等）
│   │   ├── components/       # 可复用 React 组件
│   │   ├── contexts/         # React 上下文管理
│   │   ├── hooks/            # 自定义 React Hooks
│   │   ├── i18n/             # 国际化配置
│   │   └── pages/            # 页面组件
│   └── index.html            # 前端 HTML 入口文件
├── docker-compose.yml        # Docker Compose 配置文件
├── .env.example              # 环境变量示例文件
├── main.py                   # FastAPI 应用入口
├── requirements.txt          # Python 依赖列表
└── ...                       # 其他配置文件和目录
```

## 快速开始

### 使用 Docker Compose 部署 (推荐)

请确保您的系统已安装 Docker 和 Docker Compose。

1.  **准备环境变量文件**:
    复制 `.env.example` 文件并将其重命名为 `.env`。
    ```bash
    cp .env.example .env
    ```
    根据您的实际需求编辑 `.env` 文件，配置必要的环境变量。

2.  **创建 Docker Compose 配置文件**:
    在项目根目录创建一个名为 `docker-compose.yaml` 的文件，并粘贴以下内容：
    ```yaml
    services:
      backend:
        image: alterem/gemini-poise
        volumes:
          - ./.env:/app/.env
          - ./data/:/data
        environment:
          - TZ=Asia/Shanghai
        depends_on:
          - redis
        restart: always
        healthcheck:
          test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
          interval: 30s
          timeout: 10s
          retries: 3
          start_period: 60s

      frontend:
        image: alterem/gemini-poise-frontend
        ports:
          - "8100:80"
        environment:
          - TZ=Asia/Shanghai
        #volumes:
        #  - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
        depends_on:
          - backend
        restart: always
        healthcheck:
          test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost/"]
          interval: 30s
          timeout: 10s
          retries: 3
          start_period: 30s

      redis:
        image: redis:7-alpine
        volumes:
          - redis_data:/data
        environment:
          - TZ=Asia/Shanghai
        restart: always
        healthcheck:
          test: ["CMD", "redis-cli", "ping"]
          interval: 30s
          timeout: 10s
          retries: 3
        command: redis-server --appendonly yes --maxmemory 128mb --maxmemory-policy allkeys-lru

      postgres:
        image: postgres:15
        profiles:
          - postgresql
        volumes:
          - postgres_data:/var/lib/postgresql/data
        environment:
          - POSTGRES_PASSWORD=${DB_PASSWORD:-postgres}
          - POSTGRES_USER=postgres
          - POSTGRES_DB=gemini_poise
          - TZ=Asia/Shanghai
        ports:
          - "5432:5432"
        restart: always

      mysql:
        image: mysql:8.0
        profiles:
          - mysql
        volumes:
          - mysql_data:/var/lib/mysql
        environment:
          - MYSQL_ROOT_PASSWORD=${DB_PASSWORD:-mysql}
          - MYSQL_DATABASE=gemini_poise
          - TZ=Asia/Shanghai
        ports:
          - "3306:3306"
        restart: always

    volumes:
      redis_data:
      postgres_data:
      mysql_data:

    ```

3.  **启动服务**:

    在 `docker-compose.yaml` 文件所在的目录执行以下命令，启动所有服务（三选一）：

    sqlite 数据库 
    ```bash
    docker compose up -d
    ```

    PostgreSQL 数据库
    ```bash
    docker compose --profile postgresql up -d
    ```

    启动 MySQL 数据库
    ```bash
    docker compose --profile mysql up -d
    ```

4.  **验证服务是否成功启动**:
    现在所有服务都通过单一端口访问，提供更好的用户体验：
    
    *   **🎨 前端界面**: 访问 `http://localhost:8100` 进入 Web 管理界面
        *   默认登录账号：`admin`
        *   默认登录密码：`password123`
    *   **🤖 OpenAI 兼容 API**: `http://localhost:8100/v1/chat/completions`
    *   **🧠 Gemini 纯净 API**: `http://localhost:8100/v1beta/models`
    *   **⚙️ 管理 API**: `http://localhost:8100/api/`
    *   **📚 API 文档**: `http://localhost:8100/docs`
    *   **🏥 健康检查**: `http://localhost:8100/health`
    
    *   **API 使用提示**: 登录前端后，请务必前往设置页面 (`http://localhost:8100/config`) 配置 `API Token` 字段，此字段不能为空。

### 手动设置 (适用于开发环境)

#### 后端设置

1.  **克隆项目仓库**:
    ```bash
    git clone https://github.com/gemini-poise/gemini-poise.git
    cd gemini-poise
    ```

2.  **创建并激活 Python 虚拟环境**:
    ```bash
    python -m venv venv
    source venv/bin/activate  # 适用于 Linux/macOS
    # 或者
    venv\Scripts\activate     # 适用于 Windows
    ```

3.  **安装后端依赖**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **配置环境变量**:
    复制 `.env.example` 文件并重命名为 `.env`。
    ```bash
    cp .env.example .env
    ```
    编辑 `.env` 文件，根据您的需求设置必要的环境变量（例如数据库连接信息）。

5.  **初始化数据库**:
    ```bash
    alembic upgrade head
    ```

6.  **启动后端服务**:
    ```bash
    # uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
    uvicorn main:app --reload
    ```
    后端服务将在 `http://localhost:8000` 启动。

#### 前端设置

1.  **进入前端项目目录**:
    ```bash
    cd gemini-poise-frontend
    ```

2.  **安装前端依赖**:
    ```bash
    pnpm install
    ```

3.  **配置环境变量**:
    复制 `.env.example` 文件并重命名为 `.env.local`。
    ```bash
    cp .env.example .env.local
    ```
    编辑 `.env.local` 文件，设置后端 API 地址。例如：`VITE_API_BASE_URL=http://localhost:8000`。

4.  **启动前端开发服务器**:
    ```bash
    pnpm run dev
    ```
    前端开发服务器将在 `http://localhost:3000` 启动。

5.  **访问前端页面**:
    在浏览器中打开 `http://localhost:3000`，您将看到登录页面。
    *   默认登录账号：`admin`
    *   默认登录密码：`password123`

6.  **客户端配置提示**:
    登录前端后，请配置您的 AI 客户端使用统一端点：
    *   **OpenAI 兼容客户端**: 设置 base URL 为 `http://localhost:8100/v1`
    *   **Gemini 纯净 API 客户端**: 设置 base URL 为 `http://localhost:8100/v1beta`
    *   **API 密钥**: 使用配置页面 (`http://localhost:8100/config`) 中生成的 `API Token`

## 📸 截图

![img1](https://raw.githubusercontent.com/alterem/picFB/master/uPic/2025/05/24/ssOF8r.png)

![img2](https://raw.githubusercontent.com/alterem/picFB/master/uPic/2025/06/07/sA5rmJ.png)

![img3](https://raw.githubusercontent.com/alterem/picFB/master/uPic/2025/05/24/qR2mVj.png)

![img4](https://raw.githubusercontent.com/alterem/picFB/master/uPic/2025/05/24/HG79g3.png)

![img5](https://raw.githubusercontent.com/alterem/picFB/master/uPic/2025/05/24/Mdd6Ow.png)

## 开发路线图

### 第一阶段：后端基础
- [x] 项目初始化与环境搭建
- [x] 数据库配置与模型定义 (User, ApiKey, Config)
- [x] 数据库迁移 (Alembic)
- [x] 用户认证基础 (密码哈希)
- [x] API Key 管理 API (CRUD)
- [x] 配置管理 API (获取/更新目标 API URL)

### 第二阶段：后端认证与缓存
- [x] 集成 Redis
- [x] 实现用户登录与 Token 生成
- [x] 实现 Token 认证依赖
- [x] 实现用户登出
- [x] 保护 Key 管理和配置 API
- [x] 用户密码修改

### 第三阶段：后端核心功能
- [x] 实现随机获取可用 API Key 的逻辑
- [x] 实现 API 请求转发逻辑
- [x] 实现 Key 使用状态更新逻辑
- [x] 实现令牌桶算法

## 配置管理

Gemini Poise 通过 Web 界面提供灵活的配置管理：

### 基础配置
- **目标 API URL**: 设置 Gemini API 端点地址
- **API Token**: 内部认证令牌，用于API访问
- **密钥验证设置**: 配置API密钥验证间隔和参数

### 重试配置

系统支持可配置的重试机制以提高可靠性：

#### 代理请求重试次数
配置在遇到临时故障时代理请求的最大重试次数：

| 配置值 | 行为 | 总尝试次数 |
|--------|------|-----------|
| **0** | 不重试，只尝试1次 | 1次 |
| **1** | 初始失败后重试1次 | 2次 |
| **2** | 初始失败后重试2次 | 3次 |
| **3** | 初始失败后重试3次（默认） | 4次 |

#### 配置建议
- **0**: 适用于对延迟敏感的场景，失败就立即返回
- **1-2**: 适用于一般场景，轻量重试逻辑
- **3**: 默认值，在重试次数和性能之间取得平衡
- **5+**: 适用于网络不稳定环境，但会增加响应延迟

#### 重试策略
- **指数退避**: 延迟逐步增加（1秒 → 2秒 → 4秒 → 8秒）
- **抖动机制**: 随机延迟变化，防止雷群效应
- **智能错误检测**: 仅对5xx服务器错误、429限流错误和网络错误进行重试
- **不可重试错误**: 4xx客户端错误不会重试，因为它们表示永久性失败

## 令牌桶算法

Gemini Poise 实现了一套先进的令牌桶算法，用于智能API密钥选择和速率限制：

### 核心架构
- **TokenBucket数据结构**: 存储容量、当前令牌数、补充速率、上次补充时间
- **TokenBucketManager**: 基于Redis存储的令牌桶管理器，支持分布式环境
- **OptimizedTokenBucketManager**: 增强版本，支持内存缓存和Lua脚本优化

### 关键特性
- **Redis存储**: 持久化令牌桶状态，支持分布式环境
- **Lua脚本优化**: 原子性令牌消耗操作，减少竞争条件
- **内存缓存**: 5秒TTL本地缓存，减少Redis查询
- **批量操作**: 支持批量检查和获取令牌，使用Redis pipeline优化
- **智能采样**: 渐进式采样(200→1000)，避免全量扫描

### 算法策略
- **加权随机选择**: 根据剩余令牌数进行权重分配
- **自动补充**: 基于时间和配置的补充速率自动补充令牌
- **回退机制**: Token bucket失败时自动回退到随机选择
- **动态TTL**: 根据使用频率设置不同的过期时间
- **LRU淘汰**: 支持最大桶数量限制和LRU策略

### 配置管理
- **优先级配置**: 高/中/低优先级的不同容量和补充速率
- **数据库配置**: 配置持久化到数据库，支持动态调整
- **参数验证**: 完整的配置验证机制

### 性能优化
- **缓存分层**: API key缓存 + 令牌信息缓存
- **SCAN替代KEYS**: 避免Redis阻塞
- **Pipeline批量**: 减少网络往返次数
- **懒删除**: 按需清理过期数据

### 第四阶段：前端基础
- [x] 前端项目初始化与依赖安装
- [x] 配置 Tailwind CSS
- [x] 集成 Ant Design
- [x] 设置路由 (React Router)
- [x] 国际化支持

### 第五阶段：前端认证
- [x] 创建登录页面
- [x] 实现 Auth Context (管理用户状态和 Token)
- [x] 配置 Axios 拦截器 (自动添加 Token)
- [x] 创建 ProtectedRoute 组件

### 第六阶段：前端管理页面
- [x] 创建 Key 管理页面 (展示、添加、编辑、删除)
- [x] 创建配置页面 (修改目标 API URL)

### 第七阶段：联调、优化与部署
- [x] 前后端联调测试
- [x] 密钥存活统计与监控功能
- [x] 项目依赖管理迁移至 pyproject.toml 和 uv
- [x] 使用 uv 优化 Docker 构建
- [ ] 日志记录
- [x] Docker 化部署

## 贡献指南

欢迎贡献代码、报告问题或提出功能建议。请遵循以下步骤:

1. Fork 仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## 许可证

本项目采用 MIT 许可证 - 详情请查看 [LICENSE](LICENSE) 文件

## 联系方式

如有问题，请通过 GitHub Issues 联系我们。