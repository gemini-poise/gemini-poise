# Gemini Poise 服务

一个用于代理和管理 Gemini API 请求的全栈应用，支持 API Key 轮换和请求转发。

## 技术栈

### 后端
- **FastAPI**: 高性能的 Python Web 框架
- **SQLAlchemy**: ORM 工具，用于数据库交互
- **Alembic**: 数据库迁移工具
- **Redis**: 用于缓存和会话管理
- **Pydantic**: 数据验证和设置管理
- **Passlib**: 处理密码哈希加密

### 前端
- **React**: UI 构建库
- **Vite**: 前端构建工具
- **Ant Design**: UI 组件库
- **Tailwind CSS**: 实用优先的 CSS 框架
- **React Router**: 前端路由管理
- **Axios**: HTTP 客户端

## 核心功能

- 用户认证与授权
- API Key 管理（添加、编辑、删除、启用/禁用）
- 配置管理（目标 API URL 设置）
- API 请求代理与转发
- API Key 自动轮换
- 请求日志与监控

## 项目结构

```
gemini-proxy/
├── alembic/       # 数据库迁移
├── app/           # 应用代码
│   ├── api/       # API 路由
│   ├── core/      # 核心配置
│   ├── db/        # 数据库模型和会话
│   ├── schemas/   # Pydantic 模型
│   └── services/  # 业务逻辑
└── main.py        # 应用入口
├── gemini-poise-frontend/          # React 前端
│   ├── public/        # 静态资源
│   ├── src/           # 源代码
│   │   ├── components/# React 组件
│   │   ├── contexts/  # React 上下文
│   │   └── pages/     # 页面组件
│   └── index.html     # HTML 入口
└── docker-compose.yml # Docker 配置
```

## 快速开始

### 后端设置

1. 克隆仓库并进入后端目录
   ```bash
   git clone https://github.com/alterem/gemini-poise.git
   cd gemini-poise
   ```

2. 创建并激活虚拟环境
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # 或
   venv\Scripts\activate     # Windows
   ```

3. 安装依赖
   ```bash
   pip install -r requirements.txt
   ```

4. 配置环境变量
   ```bash
   cp .env.example .env
   # 编辑 .env 文件设置必要的环境变量
   ```

5. 初始化数据库
   ```bash
   alembic upgrade head
   ```

6. 启动服务
   ```bash
   uvicorn main:app --reload
   ```

### 前端设置

1. 进入前端目录
   ```bash
   cd ../frontend
   ```

2. 安装依赖
   ```bash
   npm install
   ```

3. 配置环境变量
   ```bash
   cp .env.example .env.local
   # 编辑 .env.local 文件设置 API 地址
   ```

4. 启动开发服务器
   ```bash
   npm run dev
   ```

5. 访问 http://localhost:3000 访问到登陆页面，输入 账号：`admin`，密码：`password123`


6. 客户端配置：配置设置页面的所需要配置后，设置 gemini（openai） 的代理路径为：`http://localhost:8000`, 密钥为：配置页面配置的 `API Token`

## 📸 截图

![img1](https://raw.githubusercontent.com/alterem/picFB/master/uPic/2025/05/24/ssOF8r.png)

![img2](https://raw.githubusercontent.com/alterem/picFB/master/uPic/2025/05/24/4MRLd4.png)

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

### 第三阶段：后端核心功能
- [x] 实现随机获取可用 API Key 的逻辑
- [x] 实现 API 请求转发逻辑
- [x] 实现 Key 使用状态更新逻辑

### 第四阶段：前端基础
- [x] 前端项目初始化与依赖安装
- [x] 配置 Tailwind CSS
- [x] 集成 Ant Design
- [x] 设置路由 (React Router)

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