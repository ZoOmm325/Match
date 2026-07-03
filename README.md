# 岗位 JD → 大学专业匹配系统

[中文](#中文说明) | [English](#english)

## 中文说明

### 项目概述

本项目从招聘岗位描述（JD）中提取技能，标准化技能名称，并结合向量相似度、技能覆盖率和就业方向匹配度，推荐相关大学专业。

系统提供：

- JD 技能抽取与熟练度识别
- 技能别名、分类和规范名称统一
- 1024 维本地 BGE-M3 文本向量
- 技能库与专业知识库向量检索
- 多维评分、排序和推荐理由
- JD、技能、专业及历史匹配 REST API
- 响应式 Next.js 操作界面
- PostgreSQL、pgvector、Alembic 和 Docker 部署支持

推荐结果用于教育和招聘分析参考，不应作为招生、录用或个人发展决策的唯一依据。

### 系统架构

```mermaid
flowchart LR
    U["浏览器 / API 调用方"] --> F["Next.js 前端"]
    F --> A["FastAPI API"]
    A --> J["JD 技能抽取"]
    J --> D["DeepSeek Chat API"]
    J --> N["技能标准化"]
    N --> E["本地 BGE-M3 Embedding"]
    E --> V["pgvector 向量检索"]
    V --> M["技能与专业匹配"]
    M --> R["多维评分与推荐排序"]
    R --> A
    A --> P[("PostgreSQL + pgvector")]
```

请求流程：

1. 前端将 JD 提交到 FastAPI。
2. DeepSeek 提取技能、分类和所需熟练度。
3. `SkillNormalizer` 合并别名并统一分类。
4. 本地 `BAAI/bge-m3` 生成 1024 维向量。
5. pgvector 搜索相似技能和候选专业。
6. 推荐系统综合技能相似度、覆盖率和就业方向得分。
7. 结果与评分详情写入 PostgreSQL，并返回前端。

### 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | Next.js 15、React 19、TypeScript、Tailwind CSS |
| API | FastAPI、Pydantic v2、Uvicorn |
| 数据访问 | SQLAlchemy 2 异步模式、asyncpg、Alembic |
| 数据库 | PostgreSQL 16、pgvector |
| LLM | DeepSeek OpenAI-compatible API |
| Embedding | sentence-transformers、BAAI/bge-m3（本地运行） |
| 测试 | pytest、pytest-asyncio、pytest-cov、Node.js `node:test` |
| CI | GitHub Actions、pgvector service container |

### 快速开始：Docker Compose

#### 环境要求

- Docker Engine 24+ 和 Docker Compose v2
- DeepSeek API Key
- 建议至少 8 GB 内存；首次生成向量时需下载 BGE-M3 模型

#### 1. 配置环境变量

PowerShell：

```powershell
Copy-Item .env.example .env
```

macOS / Linux：

```bash
cp .env.example .env
```

编辑 `.env`，取消 `DEEPSEEK_API_KEY` 的注释并填写真实 Key：

```dotenv
DEEPSEEK_API_KEY=sk-your-deepseek-api-key
```

不要提交 `.env`。仓库只跟踪不含密钥的 `.env.example`。

#### 2. 构建镜像并启动数据库

```bash
docker compose build
docker compose up -d db
```

#### 3. 执行数据库迁移

```bash
docker compose run --rm backend sh -c "cd /app/backend && alembic upgrade head"
```

#### 4. 导入知识库种子数据

```bash
docker compose run --rm backend python -m backend.scripts.seed_skills
docker compose run --rm backend python -m backend.scripts.seed_majors
```

种子命令是幂等的，可以重复执行。首次执行会下载 `BAAI/bge-m3`，耗时取决于网络和硬件。

#### 5. 启动全部服务

```bash
docker compose up -d
docker compose ps
```

服务地址：

- 前端：http://localhost:3000
- API：http://localhost:8000/api
- Swagger UI：http://localhost:8000/docs
- OpenAPI JSON：http://localhost:8000/openapi.json
- 健康检查：http://localhost:8000/api/health

查看日志或停止服务：

```bash
docker compose logs -f backend frontend
docker compose down
```

### 本地开发

#### 环境要求

- Python 3.12
- Node.js 22 和 npm
- PostgreSQL 16，并安装 pgvector 扩展
- DeepSeek API Key

#### 后端

PowerShell：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt

Copy-Item .env.example .env
$env:DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/match"
$env:DEEPSEEK_API_KEY="sk-your-deepseek-api-key"

Set-Location backend
python -m alembic upgrade head
Set-Location ..

python -m backend.scripts.seed_skills
python -m backend.scripts.seed_majors
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

`.env.example` 中的主机名 `db` 用于 Docker 网络。直接在宿主机运行后端时，数据库主机应改为 `localhost`。

#### 前端

另开一个终端：

```powershell
Set-Location frontend
npm ci
$env:NEXT_PUBLIC_API_BASE_URL="http://localhost:8000/api"
npm run dev
```

打开 http://localhost:3000。

### 主要配置

| 变量 | 默认值 / 示例 | 说明 |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@db:5432/match` | 异步 PostgreSQL URL |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | 允许访问 API 的浏览器来源 JSON 数组 |
| `DEEPSEEK_API_KEY` | 无 | DeepSeek API Key；匹配功能需要 |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | DeepSeek API 地址 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 对话模型 |
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | 本地 Embedding 模型 |
| `DEEPSEEK_TIMEOUT_SECONDS` | `60` | LLM 请求超时 |
| `DEEPSEEK_MAX_RETRIES` | `3` | 可恢复错误重试次数 |
| `DEEPSEEK_RATE_LIMIT_PER_MINUTE` | `60` | 进程级每分钟请求上限 |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000/api` | 浏览器访问的 API 地址 |

完整配置见 [`.env.example`](.env.example)。

### API

交互式文档启动后位于 [http://localhost:8000/docs](http://localhost:8000/docs)。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/api/health` | 健康检查 |
| `POST` | `/api/jd/extract` | 提取技能并保存 JD |
| `GET` | `/api/jd` | 分页查询 JD |
| `GET` / `DELETE` | `/api/jd/{jd_id}` | 查询或删除 JD |
| `POST` | `/api/match` | 执行完整匹配 |
| `POST` | `/api/match/by-skills` | 按显式技能匹配 |
| `GET` | `/api/match/{jd_id}` | 查询历史匹配 |
| `GET` | `/api/skills` | 查询技能库 |
| `GET` | `/api/skills/categories` | 查询技能分类 |
| `GET` | `/api/majors` | 查询专业库 |
| `GET` | `/api/majors/search` | 语义搜索专业 |

所有业务响应使用统一结构：

```json
{
  "code": 0,
  "data": {},
  "message": "success"
}
```

### 测试

后端：

```powershell
python -m pytest backend\tests tests -q
python -m pytest backend\tests tests --cov=backend --cov-config=.coveragerc --cov-report=term-missing --cov-fail-under=80
```

真实 pgvector 集成测试：

```powershell
$env:TEST_PGVECTOR_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/match"
python -m pytest backend\tests\test_services\test_vector_service.py -m pgvector -q
```

前端：

```powershell
Set-Location frontend
npm test
npx tsc --noEmit
npm run build
```

### 项目结构

```text
.
├── backend/
│   ├── core/                  # 配置、数据库、DeepSeek 客户端、中间件
│   ├── migrations/            # Alembic 迁移
│   ├── models/                # SQLAlchemy 模型
│   ├── routers/               # FastAPI 路由
│   ├── schemas/               # Pydantic 请求与响应模型
│   ├── scripts/               # 技能与专业种子数据
│   ├── services/              # 提取、标准化、向量匹配和推荐服务
│   └── tests/                 # 后端测试
├── frontend/
│   ├── app/                   # Next.js App Router 页面
│   ├── components/            # 业务与通用 UI 组件
│   ├── lib/                   # API 客户端
│   └── tests/                 # 前端测试
├── tests/                     # 基础设施与 CI 配置测试
├── .github/workflows/         # GitHub Actions
├── docker-compose.yml
├── tasks.json
└── project-spec.md
```

---

## English

### Overview

This application extracts skills from recruitment job descriptions, normalizes skill names, and recommends related university majors using vector similarity, skill coverage, and employment-alignment scoring.

It includes JD extraction, skill normalization, a skill and major knowledge base, local BGE-M3 embeddings, pgvector search, multidimensional recommendation ranking, historical results, and a responsive Next.js interface.

Recommendations are informational and should not be the sole basis for admissions, hiring, or career decisions.

### Architecture

The browser uses the Next.js frontend to call FastAPI. FastAPI sends structured extraction and recommendation-reason requests to DeepSeek. Skill names are normalized before the local `BAAI/bge-m3` model generates 1024-dimensional embeddings. PostgreSQL with pgvector retrieves similar skills and majors. The recommendation layer scores and ranks candidates, persists the result, and returns a uniform API response.

### Technology

- Next.js 15, React 19, TypeScript, and Tailwind CSS
- FastAPI, Pydantic v2, SQLAlchemy 2, asyncpg, and Alembic
- PostgreSQL 16 with pgvector
- DeepSeek Chat API
- sentence-transformers with local `BAAI/bge-m3`
- pytest, pytest-asyncio, pytest-cov, and Node.js `node:test`
- Docker Compose and GitHub Actions

### Quick Start with Docker Compose

Requirements:

- Docker Engine 24+ with Docker Compose v2
- A DeepSeek API key
- At least 8 GB of memory is recommended

Create the local environment file:

```bash
cp .env.example .env
```

On PowerShell, use `Copy-Item .env.example .env`. Set `DEEPSEEK_API_KEY` in `.env`, then run:

```bash
docker compose build
docker compose up -d db
docker compose run --rm backend sh -c "cd /app/backend && alembic upgrade head"
docker compose run --rm backend python -m backend.scripts.seed_skills
docker compose run --rm backend python -m backend.scripts.seed_majors
docker compose up -d
```

The first seed run downloads the local BGE-M3 model. Seed commands are idempotent.

Open:

- Frontend: http://localhost:3000
- API: http://localhost:8000/api
- Swagger UI: http://localhost:8000/docs
- OpenAPI JSON: http://localhost:8000/openapi.json

### Local Development

#### Requirements

- Python 3.12
- Node.js 22 and npm
- PostgreSQL 16 with the pgvector extension
- A DeepSeek API key

Install backend dependencies and configure a local PostgreSQL URL:

```bash
python -m venv .venv
python -m pip install -r backend/requirements.txt
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/match
export DEEPSEEK_API_KEY=sk-your-deepseek-api-key
cd backend
python -m alembic upgrade head
cd ..
python -m backend.scripts.seed_skills
python -m backend.scripts.seed_majors
python -m uvicorn backend.main:app --reload
```

The `db` hostname in `.env.example` is for the Docker network. Use `localhost` when the backend runs directly on the host.
Set `CORS_ORIGINS` to a JSON array of trusted frontend origins in production.

Start the frontend in another terminal:

```bash
cd frontend
npm ci
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api npm run dev
```

### API Documentation

Swagger UI is available at [http://localhost:8000/docs](http://localhost:8000/docs) after the backend starts. The principal routes are `/api/jd`, `/api/match`, `/api/skills`, and `/api/majors`.

### Tests

```bash
python -m pytest backend/tests tests -q
python -m pytest backend/tests tests --cov=backend --cov-config=.coveragerc --cov-fail-under=80

cd frontend
npm test
npx tsc --noEmit
npm run build
```

Set `TEST_PGVECTOR_DATABASE_URL` to an async PostgreSQL URL to enable the real pgvector integration test.

### Repository Layout

- `backend/core`: configuration, database, DeepSeek client, middleware
- `backend/models`: SQLAlchemy models
- `backend/routers`: FastAPI routes
- `backend/services`: extraction, normalization, matching, and recommendation logic
- `backend/scripts`: seed data and import commands
- `backend/tests`: backend unit and integration tests
- `frontend/app`: Next.js pages
- `frontend/components`: domain and shared UI components
- `frontend/tests`: frontend tests
- `tests`: infrastructure and CI configuration tests
- `.github/workflows`: continuous integration

### Common Commands

```bash
make install
make migrate
make seed
make dev
make test
make lint
make build
make clean
```

`make dev` starts PostgreSQL, applies the Alembic migrations, and launches the
backend and frontend development services. Configure `.env` first. `make clean`
only removes the explicit `.coverage` and `coverage.xml` files; directory caches
are intentionally retained.

The underlying Docker Compose commands remain available:

```bash
docker compose ps
docker compose logs -f backend frontend
docker compose down
```

Use `/api/health` to verify the backend and `/docs` to explore and execute API requests.
