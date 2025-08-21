[中文](README_zh.md)

# Gemini Poise: Gemini API Proxy and Management Tool

Gemini Poise is a full-stack application designed to help you easily proxy and manage Gemini API requests. It features API Key rotation, request forwarding, user authentication, and configuration management, making your AI application development and deployment smoother.

## Technology Stack Overview

### Backend
- **FastAPI**: A high-performance Python web framework for building our API services.
- **SQLAlchemy**: A powerful Python ORM tool that simplifies database operations.
- **Alembic**: A database migration tool that helps us manage changes to the database schema.
- **Redis**: A high-performance key-value store used for caching and session management.
- **Pydantic**: Used for data validation and settings management, ensuring correct data structures.
- **Passlib**: A secure password hashing library to protect user authentication.

### Frontend
- **React**: A popular JavaScript library for building user interfaces.
- **Vite**: An extremely fast frontend build tool, providing an excellent development experience.
- **Ant Design**: An enterprise-level UI component library, offering a rich set of out-of-the-box components.
- **Tailwind CSS**: A utility-first CSS framework for quickly building custom designs.
- **React Router**: A declarative routing library for managing frontend page navigation.
- **Axios**: A Promise-based HTTP client for interacting with backend services.

## Core Features at a Glance

- **User Authentication and Authorization**: Ensures that only authorized users can access the system.
- **API Key Management**: Easily add, edit, delete, enable, or disable API Keys.
- **Key Survival Statistics**: Monitor and track API key status changes over time with detailed statistics.
- **Configuration Management**: Flexible settings for target API URLs and other system parameters.
- **API Request Proxy and Forwarding**: Seamlessly proxies and forwards Gemini API requests.
- **API Key Automatic Rotation**: Automatically manages and rotates API Keys to improve API availability.
- **Request Logging and Monitoring**: Logs and monitors API requests for troubleshooting and performance analysis.

## Project Structure

```
gemini-poise/
├── alembic/                  # Database migration scripts
├── app/                      # Backend application code
│   ├── api/                  # API route definitions
│   ├── core/                 # Core configurations, database connections, and security settings
│   ├── crud/                 # Database operations (Create, Read, Update, Delete)
│   ├── models/               # Database model definitions
│   ├── schemas/              # Pydantic data models
│   └── tasks/                # Background tasks (e.g., Key validation)
├── gemini-poise-frontend/    # React frontend application
│   ├── public/               # Static assets
│   ├── src/                  # Frontend source code
│   │   ├── api/              # Frontend API request encapsulation
│   │   ├── assets/           # Static assets (images, icons, etc.)
│   │   ├── components/       # Reusable React components
│   │   ├── contexts/         # React context management
│   │   ├── hooks/            # Custom React Hooks
│   │   ├── i18n/             # Internationalization configuration
│   │   └── pages/            # Page components
│   └── index.html            # Frontend HTML entry file
├── docker-compose.yml        # Docker Compose configuration file
├── .env.example              # Example environment variables file
├── main.py                   # FastAPI application entry point
├── requirements.txt          # Python dependency list
└── ...                       # Other configuration files and directories
```

## Quick Start

### Deploy with Docker Compose (Recommended)

Please ensure you have Docker and Docker Compose installed on your system.

1.  **Prepare the environment variables file**:
    Copy the `.env.example` file and rename it to `.env`.
    ```bash
    cp .env.example .env
    ```
    Edit the `.env` file to configure the necessary environment variables according to your needs.

2.  **Create the Docker Compose configuration file**:
    In the project root directory, create a file named `docker-compose.yaml` and paste the following content:
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
          - "8100:80"  # Single unified port
        environment:
          - TZ=Asia/Shanghai
        #volumes:
        #  - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
        depends_on:
          - backendvolumes:
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

3.  **Start the services**:
    Execute the following command in the directory where the `docker-compose.yaml` file is located to start all services (choose one of the three):

    sqlite database
    ```bash
    docker compose up -d
    ```

    PostgreSQL database
    ```bash
    docker compose --profile postgresql up -d
    ```

    Start MySQL database
    ```bash
    docker compose --profile mysql up -d
    ```

4.  **Verify service startup**:
    All services are now accessible through a single port for better user experience:
    
    *   **🎨 Frontend Interface**: Access `http://localhost:8100` to reach the web interface
        *   Default login account: `admin`
        *   Default login password: `password123`
    *   **🤖 OpenAI Compatible API**: `http://localhost:8100/v1/chat/completions`
    *   **🧠 Gemini Pure API**: `http://localhost:8100/v1beta/models`
    *   **⚙️ Management API**: `http://localhost:8100/api/`
    *   **📚 API Documentation**: `http://localhost:8100/docs`
    *   **🏥 Health Check**: `http://localhost:8100/health`
    
    *   **API Usage Tip**: After logging into the frontend, please make sure to configure the `API Token` field on the settings page (`http://localhost:8100/config`). This field cannot be empty.

### Manual Setup (for Development Environment)

#### Backend Setup

1.  **Clone the project repository**:
    ```bash
    git clone https://github.com/alterem/gemini-poise.git
    cd gemini-poise
    ```

2.  **Create and activate a Python virtual environment**:
    ```bash
    python -m venv venv
    source venv/bin/activate  # For Linux/macOS
    # Or
    venv\Scripts\activate     # For Windows
    ```

3.  **Install backend dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure environment variables**:
    Copy the `.env.example` file and rename it to `.env`.
    ```bash
    cp .env.example .env
    ```
    Edit the `.env` file to set the necessary environment variables (e.g., database connection information) according to your needs.

5.  **Initialize the database**:
    ```bash
    alembic upgrade head
    ```

6.  **Start the backend service**:
    ```bash
    # uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
    uvicorn main:app --reload
    ```
    The backend service will start at `http://localhost:8000`.

#### Frontend Setup

1.  **Navigate to the frontend project directory**:
    ```bash
    cd gemini-poise-frontend
    ```

2.  **Install frontend dependencies**:
    ```bash
    pnpm install
    ```

3.  **Configure environment variables**:
    Copy the `.env.example` file and rename it to `.env.local`.
    ```bash
    cp .env.example .env.local
    ```
    Edit the `.env.local` file to set the backend API address. For example: `VITE_API_BASE_URL=http://localhost:8000`.

4.  **Start the frontend development server**:
    ```bash
    pnpm run dev
    ```
    The frontend development server will start at `http://localhost:3000`.

5.  **Access the frontend page**:
    Open your browser and navigate to `http://localhost:3000`. You will see the login page.
    *   Default login account: `admin`
    *   Default login password: `password123`

6.  **Client Configuration Tip**:
    After logging into the frontend, please configure your AI client to use the unified endpoint:
    *   **OpenAI Compatible Clients**: Set base URL to `http://localhost:8100/v1` 
    *   **Gemini Pure API Clients**: Set base URL to `http://localhost:8100/v1beta`
    *   **API Key**: Use the `API Token` generated on the configuration page (`http://localhost:8100/config`)

## 📸 Screenshots

![img1](https://raw.githubusercontent.com/alterem/picFB/master/uPic/2025/05/24/ssOF8r.png)

![img2](https://raw.githubusercontent.com/alterem/picFB/master/uPic/2025/06/07/sA5rmJ.png)

![img3](https://raw.githubusercontent.com/alterem/picFB/master/uPic/2025/05/24/qR2mVj.png)

![img4](https://raw.githubusercontent.com/alterem/picFB/master/uPic/2025/05/24/HG79g3.png)

![img5](https://raw.githubusercontent.com/alterem/picFB/master/uPic/2025/05/24/Mdd6Ow.png)

## Development Roadmap

### Phase 1: Backend Foundation
- [x] Project initialization and environment setup
- [x] Database configuration and model definition (User, ApiKey, Config)
- [x] Database migrations (Alembic)
- [x] Basic user authentication (password hashing)
- [x] API Key management API (CRUD)
- [x] Configuration management API (get/update target API URL)

### Phase 2: Backend Authentication and Caching
- [x] Redis integration
- [x] User login and Token generation
- [x] Token authentication dependency
- [x] User logout
- [x] Protect Key management and configuration APIs
- [x] User password modification

### Phase 3: Backend Core Functionality
- [x] Logic for randomly fetching available API Keys
- [x] API request forwarding logic
- [x] Logic for updating Key usage status
- [x] Token bucket

### Phase 4: Frontend Foundation
- [x] Frontend project initialization and dependency installation
- [x] Tailwind CSS configuration
- [x] Ant Design integration
- [x] Routing setup (React Router)
- [x] Internationalization support

### Phase 5: Frontend Authentication
- [x] Create login page
- [x] Implement Auth Context (manage user state and Token)
- [x] Configure Axios interceptors (automatically add Token)
- [x] Create ProtectedRoute component

### Phase 6: Frontend Management Pages
- [x] Create Key management page (display, add, edit, delete)
- [x] Create configuration page (modify target API URL)

### Phase 7: Integration, Optimization, and Deployment
- [x] Frontend and backend integration testing
- [x] Key survival statistics and monitoring
- [x] Project dependency management with pyproject.toml and uv
- [x] Docker build optimization with uv
- [ ] Logging
- [x] Dockerization for deployment

## Contribution Guide

Contributions are welcome! Feel free to report issues or suggest features. Please follow these steps:

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contact

For any questions, please reach out via GitHub Issues.