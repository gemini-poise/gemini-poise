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
- **配置管理**: 灵活设置目标 API URL 及其他系统参数。
- **API 请求代理与转发**: 无缝地代理和转发 Gemini API 请求。
- **API Key 自动轮换**: 自动管理和轮换 API Key，提升 API 的可用性。
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
        ports:
          - "8100:8000"
        volumes:
          - ./.env:/app/.env
          - ./data/:/data
        environment:
          - TZ=Asia/Shanghai
        depends_on:
          - redis
        restart: always

      frontend:
        image: alterem/gemini-poise-frontend
        ports:
          - "8101:80"
        environment:
          - TZ=Asia/Shanghai
        restart: always

      redis:
        image: redis:latest
        volumes:
          - redis_data:/data
        environment:
          - TZ=Asia/Shanghai
        restart: always

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
    *   **后端**: 访问 `http://localhost:8100`。如果看到页面输出 `{"message":"Welcome to Gemini Poise AI Proxy Tool"}`，则表示后端服务已成功启动。
    *   **前端**: 访问 `http://localhost:8101`。您将进入前端登录页面。
        *   默认登录账号：`admin`
        *   默认登录密码：`password123`
    *   **API 使用提示**: 登录前端后，请务必前往设置页面 (`http://localhost:8101/config`) 配置 `API Token` 字段，此字段不能为空。

### 手动设置 (适用于开发环境)

#### 后端设置

1.  **克隆项目仓库**:
    ```bash
    git clone https://github.com/alterem/gemini-poise.git
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
    登录前端后，请在设置页面配置您的 Gemini (或 OpenAI) 代理路径为 `http://localhost:8000`，并将密钥设置为您在配置页面中生成的 `API Token`。

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
- [x] 实现 token bucket

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