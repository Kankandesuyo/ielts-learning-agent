# IELTS Learning Agent MVP

这是一个面向雅思备考学生的全栈本地 MVP。它不是官方雅思考官，而是一个学习陪练系统：根据用户画像生成并保存学习计划，支持每日打卡，并提供写作批改、口语陪练、阅读训练、听力文本训练、资料出题、词汇任务和错题本。

## 1. 项目整体设计说明

产品经理视角看，这个系统解决三个问题：

1. 学生不知道每天该练什么。
2. 学生写作、口语、阅读、听力错了以后，不知道为什么错。
3. 学生的错误没有沉淀，下一次训练不能针对薄弱点。

当前 MVP 已包含 FastAPI 后端和内置学生前端。核心闭环是：

用户画像 -> 保存学习计划 -> 每日打卡 -> 单项训练 -> 保存错题 -> 下次训练参考历史错误

阅读模拟考试采用问题在左、原文在右的桌面双栏。用鼠标左键拖选题干或选项中的英文词汇，松开后会自动标亮并解释；手机端自动变为问题在前、原文在后的单栏。

升级后的 Agent 架构是：

```text
SupervisorAgent 主 Agent
  -> ListeningCoachAgent 听力专项 Agent
  -> SpeakingCoachAgent 口语专项 Agent
  -> ReadingCoachAgent 阅读专项 Agent
  -> WritingCoachAgent 写作专项 Agent
```

产品经理视角看，主 Agent 不是替代四个专项 Agent，而是像学习主管：读取学生画像、查看弱项和错题本、判断今天优先练哪个模块、调用对应专项 Agent，并给学生一个明确下一步。

当前版本默认使用规则型 Agent，所以没有 API Key 也能运行。后续可以把 Agent 内部替换成真实 LLM 调用。

## 2. 完整目录结构

```text
ielts-agent/
  app/
    main.py
    config.py
    database.py
    models/
      tables.py
    schemas/
      profile.py
      requests.py
    agents/
      base.py
      study_plan_agent.py
      writing_coach_agent.py
      speaking_coach_agent.py
      reading_coach_agent.py
      listening_coach_agent.py
      vocabulary_agent.py
    services/
      profile_service.py
      error_notebook_service.py
      vocabulary_service.py
      rag_service.py
    routers/
      health.py
      profile.py
      study_plan.py
      writing.py
      speaking.py
      reading.py
      listening.py
      vocabulary.py
      errors.py
    prompts/
      study_plan_prompts.py
      writing_prompts.py
      speaking_prompts.py
  data/
    ielts_docs/
      writing_rubric.md
      speaking_rubric.md
      reading_tips.md
      listening_tips.md
  tests/
    test_api.py
.env.example
requirements.txt
README.md
```

## LLM API 接入

项目通过 OpenAI-compatible Chat Completions 格式调用 DeepSeek。配置在 `.env`：

```text
USE_LLM=true
OPENAI_API_KEY="your-api-key"
OPENAI_BASE_URL="https://api.deepseek.com"
OPENAI_MODEL="deepseek-v4-flash"
```

当前使用 DeepSeek 官方兼容接口。密钥只放在本地 `.env`，不要写进前端、聊天截图或提交到公开仓库。历史型号 `deepseek-chat` 将于 2026-07-24 停用，因此项目使用其当前替代型号 `deepseek-v4-flash`。

## 3. 每个模块职责

- `routers/`: API 入口，只处理请求、响应和错误码。
- `agents/`: 智能体核心逻辑，比如生成计划、批改作文、生成口语题。
- `services/`: 业务服务和数据库操作，比如创建用户、保存错题、保存词汇。
- `models/`: SQLAlchemy 数据表模型。
- `schemas/`: Pydantic 请求体校验，防止非法输入进入系统。
- `prompts/`: 后续接入 LLM 时使用的 Prompt 模板。
- `data/ielts_docs/`: RAG 知识库的本地 Markdown 文件。
- `tests/`: 最小 API 自动化测试。

## 4. 数据库表设计

`user_profiles`

- `id`: 用户 ID。
- `current_band`: 当前分数。
- `target_band`: 目标分数。
- `prep_days`: 备考天数。
- `daily_minutes`: 每天学习分钟数。
- `weak_skills`: 弱项，逗号分隔。
- `focus_areas`: 重点提升项，逗号分隔。
- `created_at`: 创建时间。

`error_entries`

- `id`: 错题记录 ID。
- `user_id`: 用户 ID。
- `source`: 来源，比如 writing、speaking、reading、listening。
- `category`: 错误类型。
- `original_text`: 原始回答或原句。
- `feedback`: 问题解释。
- `suggestion`: 修改建议。
- `created_at`: 创建时间。

`vocabulary_items`

- `word`: 单词。
- `topic`: 主题。
- `meaning`: 含义。
- `example_sentence`: 例句。
- `collocation`: 搭配。
- `ielts_usage`: 雅思使用建议。
- `mastery_level`: 掌握程度。
- `next_review_day`: 间隔复习日期。

## 5. Prompt 设计

Prompt 的原则：

- 明确声明不是官方雅思考官。
- 分数只能是 estimated band score。
- 每次输出必须包含 `next_step`。
- 写作必须按四个维度反馈，并给出原句问题和改写句。
- 口语的 pronunciation 只能基于文本做有限判断，不能假装听到了音频。
- 阅读和听力重点解释定位词、同义替换和陷阱项。

Prompt 文件在 `app/prompts/`，当前 MVP 先保留模板，后续接 LLM 时直接复用。

## 6. LangGraph Agent 流程设计

当前 `app/agents/base.py` 提供一个最小 LangGraph 包装：

```text
input -> agent_step -> output
```

生产版本可以扩展成：

```text
input -> load_profile -> retrieve_rag -> generate_answer -> save_error -> output
```

为什么这样设计：初学者先跑通最小链路，再逐步理解 LangGraph 的节点和状态传递。

## 7. FastAPI 接口代码

主要接口：

- `GET /health`
- `POST /profile/create`
- `GET /profile/{user_id}`
- `PUT /profile/{user_id}`
- `DELETE /profile/{user_id}`
- `POST /study-plan/generate`
- `GET /study-plan/{user_id}/latest`
- `PATCH /study-plan/{user_id}/{plan_id}/days/{day_number}`
- `POST /writing/review`
- `POST /speaking/practice`
- `POST /reading/practice`
- `POST /listening/practice`
- `POST /vocabulary/generate`
- `GET /errors/{user_id}`
- `POST /supervisor/diagnose`
- `POST /supervisor/coach`
- `GET /knowledge/status`
- `POST /knowledge/index`
- `POST /knowledge/question`
- `POST /knowledge/analyze`
- `GET /knowledge/status`：查看 `database/` 资料是否已索引。
- `POST /knowledge/index`：读取 PDF/TXT/MD 并建立本地索引。
- `POST /knowledge/question`：从资料原文生成阅读、听力文本、词汇或写作题。
- `POST /knowledge/analyze`：按题目 ID 对照原资料分析答案。
- `GET /exam/reading/start`：读取 Cambridge IELTS 16 Academic Reading Test 1 的三篇文章与 40 道题。
- `POST /exam/reading/submit`：整套交卷，返回 Raw Score、估算 Band、分篇表现和 40 题逐题结果。
- `POST /exam/vocabulary/explain`：解释学生在真题题干或选项中选中的英文词汇；后端会重新从 `database` PDF 定位语境和页码，然后优先查询 `database/legal-dictionaries` 中的本机离线词典。

### 标亮后的本地词典查询

真题页面支持拖选或双击英文词汇。浏览器负责标亮，后端负责可信查询：先从 PDF 原文确认该词确实存在，再读取本机词典，不把学生画像或答案发到外部服务。

- FreeDict English-Chinese 2025.11.23：解析 StarDict 的 `idx.gz` 索引并按字节读取 `dict` 词条，提供英中释义。
- GNU GCIDE 0.54：当 FreeDict 没有词条时，按首字母读取 GCIDE 英英释义。
- 支持常见复数、第三人称、过去式和 `-ing` 词形回退，例如 `contradicts` 可尝试查询 `contradict`。
- 只有本地词典未命中时，才继续使用已配置模型或公开词典降级服务。

相关配置：`LOCAL_DICTIONARY_ENABLED=true`、`LOCAL_DICTIONARY_DIR=database/legal-dictionaries`。对外分发词典数据时，需要保留 FreeDict 的 CC BY-SA 3.0 和 GCIDE 的 GPLv3 许可证信息。

启动后访问 Swagger 文档：

```text
http://127.0.0.1:8000/docs
```

启动后访问前端页面：

```text
http://127.0.0.1:8000/
```

如果 8000 被旧进程占用，可以换端口：

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8001
```

然后访问：

```text
http://127.0.0.1:8001/
```

## 8. Agent 核心代码

已实现：

- `StudyPlanAgent`: 生成每日任务、时间分配、模考计划、弱项计划。
- `WritingCoachAgent`: 判断作文类型、估算分数、四维度反馈、保存典型错误。
- `SpeakingCoachAgent`: 生成题目、追问、文本反馈、自然表达和样例答案。
- `ReadingCoachAgent`: 文本阅读题、定位词、同义替换、陷阱解释。
- `ListeningCoachAgent`: 文本版听力训练，预留真实音频接口说明。
- `VocabularyAgent`: 按主题生成词汇和简单 spaced repetition 信息。

## 9. RAG 基础代码

`app/services/rag_service.py` 已实现：

- 文档加载。
- 文本切分。
- 简单 token 检索。
- 返回可传给 Agent 的上下文。

MVP 用简单检索是为了降低学习成本。后续可以换成：

- Chroma
- FAISS
- PostgreSQL + pgvector
- LangChain retriever

## 10. README 启动说明

安装依赖：

```powershell
cd D:\TeacherEnglish
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

启动服务：

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

测试健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

创建用户画像：

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/profile/create `
  -ContentType "application/json" `
  -Body '{"current_band":5.5,"target_band":6.5,"prep_days":30,"daily_minutes":120,"weak_skills":["Writing","Speaking"],"focus_areas":["grammar","writing logic"]}'
```

生成学习计划，假设上一步返回的用户 ID 是 1：

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/study-plan/generate `
  -ContentType "application/json" `
  -Body '{"user_id":1,"days":7}'
```

让主管 Agent 诊断当前学习系统：

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/supervisor/diagnose `
  -ContentType "application/json" `
  -Body '{"user_id":1}'
```

让主管 Agent 自动安排下一次训练：

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/supervisor/coach `
  -ContentType "application/json" `
  -Body '{"user_id":1,"skill_focus":null,"learner_input":null,"speaking_part":1}'
```

也可以强制主管调度口语 Agent：

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/supervisor/coach `
  -ContentType "application/json" `
  -Body '{"user_id":1,"skill_focus":"speaking","learner_input":"I study software engineering because I want to build useful tools.","speaking_part":1}'
```

安装测试与覆盖率工具：

```powershell
\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

运行完整自动化测试并查看覆盖率：

```powershell
\.venv\Scripts\python.exe -m pytest --cov=app --cov-report=term-missing -q
```

## 11. 后续优化方向

- 接入真实 LLM，把规则型反馈升级成更自然的个性化反馈。
- 写作批改增加逐句 diff 和更完整的高分范文。
- 口语加入音频上传、语音识别和发音评分，但要明确发音评分不是官方结果。
- RAG 使用向量数据库，接入更多评分标准、题库、范文和技巧资料。
- 当前资料出题采用可解释的本地关键词检索和原文挖空；后续可升级为向量检索，但仍应保留书名和页码来源。
- 增加登录系统、用户权限、周/月学习统计仪表盘和提醒功能。
- SQLite 切换 PostgreSQL，支持多用户长期使用。
- 增加安全措施：认证、限流、输入长度限制、日志脱敏、API Key 加密管理。

## 安全措施

- `.env` 管理敏感配置，不把密钥写死进代码。
- `.gitignore` 排除 `.env`、SQLite、上传文件、知识索引、资料原文件和临时输出。
- Pydantic 限制分数、天数、技能枚举和文本长度等输入。
- 数据库操作集中在 service 层，减少路由直接操作数据库的风险。
- 上传文件限制扩展名、大小、分类、备注长度，并检查 PDF/Office/文本文件头。
- 前端动态内容统一 HTML 转义，避免作文、错题、文件名和模型输出触发 XSS。
- 真题词汇解释只接受 80 字符以内的英文词或短语，并验证它确实存在于指定 `database` 题目页，防止把接口当作任意文本代理。
- 模型不可用时可降级到公开英英词典和翻译服务；只发送公开真题中的所选词与短语境，不发送用户画像、答案或密钥。
- 自动化测试使用独立临时数据库和上传目录，不污染正式数据。
- 不声称官方评分，避免误导学生。
- 后续上线前应加入用户认证、请求限流、日志脱敏和 HTTPS。

## 12. 2026-07-17 可运行状态

- 已建立 Git 仓库和安全忽略规则。
- 已实现画像读取、修改、删除。
- 学习计划会持久化到 `study_plans` 和 `study_plan_days`，支持每日完成/撤销打卡和进度百分比。
- 已把本地资料索引、来源页码出题和答案分析纳入前端与 API。
- 当前自动化测试结果：`30 passed`，后端行覆盖率 `90%`；测试同时调用前端 XSS 安全脚本。
- 已真实启动服务验证首页、画像创建、两天计划生成、Day 1 打卡、最近计划读取，进度正确返回 `50%`。
- 当前仍属于本地单用户 MVP；公开部署前必须完成登录鉴权和服务端数据所有权校验。
