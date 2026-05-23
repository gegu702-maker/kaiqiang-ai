# AI 带货视频生成器 MVP

一个半自动 AI 带货视频生成器 MVP。用户上传商品信息、商品图、参考语音和个人形象素材后，系统生成商品卖点分析、黄金 3 秒开头、抖音带货口播脚本、分镜脚本、标题和管理员执行清单。前端使用 Next.js 15 App Router、TypeScript、Tailwind CSS 和 Server Actions；后端使用 FastAPI；文件和任务数据存储在 Supabase。

## 功能

- 用户提交带货视频任务：商品名称、商品图片、产品卖点、目标人群、视频风格、是否使用数字人、参考语音、个人形象素材
- 系统自动生成：`selling_points`、`hook`、`script`、`shot_list`、`title_options`、`caption`、`admin_workflow`
- 商业增长模块：AI 封面文案、封面生成 prompt、抖音标签、评论区引导、成交收口
- 首页升级为 AI Studio 三栏结构：左侧导航、中间提交工作区、右侧动态短视频预览和生成进度
- 支持视频风格：硬核带货、情绪种草、测评解说、剧情短片
- Supabase Storage 上传产品图片、声音素材和最终视频并返回公开 URL
- 用户通过邮箱查看任务状态和下载最终视频
- 用户任务详情页：查看状态、生成进度、播放最终视频、下载 MP4
- 管理员任务详情页：查看商品图、用户素材、AI 卖点分析、AI 脚本、AI 分镜、HeyGen / 即梦 / 可灵执行清单
- AI 视频生成工作台：`/admin/studio/{task_id}`，集中处理 HeyGen、即梦、可灵、剪映、CapCut 半自动生产流程
- 管理员可复制脚本、分镜 JSON、视频生成提示词和执行清单
- 后端预留 `workflow_engine.py`，用于未来接入队列、渲染状态和完整视频生成 pipeline
- 自动字幕系统：管理员上传最终 MP4 后，系统用 `script` 自动生成 WebVTT 字幕并挂到播放器
- 管理后台显示当前 TTS language 和 MiniMax voice
- CosyVoice 本地语音克隆：管理员在 Studio 上传参考声音，生成 clone voice，自动上传 Supabase Storage
- 管理员快捷操作：复制文案、下载 voice、打开产品图
- 管理员修改状态、上传最终 MP4，系统自动写入 `result_video_url`
- 任务列表和详情页每 10 秒自动刷新状态
- Supabase Storage 存储最终视频
- 前后端分离，API 模块化，环境变量管理密钥
- 上传限制：图片 10MB，音频 20MB，视频 200MB
- 格式限制：图片 jpg/png/webp，音频 mp3/wav/m4a，视频 mp4
- 任务状态：pending / scripting / producing / completed / failed

## 目录结构

```text
.
├── apps
│   ├── api
│   │   ├── app
│   │   │   ├── api
│   │   │   │   ├── admin.py
│   │   │   │   ├── cosyvoice.py
│   │   │   │   ├── health.py
│   │   │   │   └── tasks.py
│   │   │   ├── core
│   │   │   │   ├── config.py
│   │   │   │   └── supabase.py
│   │   │   ├── models
│   │   │   │   └── video_task.py
│   │   │   ├── services
│   │   │   │   ├── cosyvoice.py
│   │   │   │   ├── storage.py
│   │   │   │   └── tasks.py
│   │   │   └── main.py
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── .env.example
│   └── web
│       ├── app
│       │   ├── actions
│       │   │   ├── admin.ts
│       │   │   └── tasks.ts
│       │   ├── admin
│       │   │   ├── studio
│       │   │   │   └── [task_id]
│       │   │   │       └── page.tsx
│       │   │   ├── tasks
│       │   │   │   └── [id]
│       │   │   │       └── page.tsx
│       │   │   └── page.tsx
│       │   ├── tasks
│       │   │   ├── [id]
│       │   │   │   └── page.tsx
│       │   │   └── page.tsx
│       │   ├── globals.css
│       │   ├── layout.tsx
│       │   └── page.tsx
│       ├── components
│       ├── lib
│       ├── Dockerfile
│       ├── next.config.ts
│       ├── package.json
│       └── .env.example
├── supabase
│   └── schema.sql
├── services
│   └── cosyvoice
│       └── Dockerfile
├── scripts
│   └── start_cosyvoice.ps1
├── docker-compose.yml
├── docker-compose.gpu.yml
└── package.json
```

## Supabase 设置

1. 创建 Supabase 项目。
2. 在 SQL Editor 执行 `supabase/schema.sql`。
   如果是从旧版数字人口播 MVP 升级，请额外执行：

```text
supabase/commerce_mvp_migration.sql
```

该迁移会新增带货视频字段，并刷新 PostgREST schema cache。

3. 创建三个公开 Storage bucket：
   - `images`
   - `voices`
   - `cloned`
   - `videos`
   - `subtitles`
4. 复制环境变量：

```bash
cp apps/web/.env.example apps/web/.env.local
cp apps/api/.env.example apps/api/.env
```

5. 填入 Supabase URL、anon key、service role key 和管理员密钥。

## 本地运行

前端：

```bash
cd apps/web
npm install
npm run dev
```

后端：

```bash
cd apps/api
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Windows 本地运行 FastAPI 后端

当前后端需要真实 Python 3.11+。如果 `python --version` 没有输出版本，或者只指向 `C:\Users\Administrator\AppData\Local\Microsoft\WindowsApps\python.exe`，说明当前是 Microsoft Store 占位符，不是真正的 Python。

1. 下载 Python 3.11+：
   https://www.python.org/downloads/

2. 安装时必须勾选：
   `Add Python to PATH`

3. 重新打开 PowerShell，检查：

```powershell
python --version
python -m pip --version
```

4. 复制并填写后端环境变量：

```powershell
copy apps\api\.env.example apps\api\.env
```

至少需要填写：

```env
SUPABASE_URL=你的 Supabase URL
SUPABASE_SERVICE_ROLE_KEY=你的 Supabase service role key
ADMIN_API_KEY=change-me
MINIMAX_API_KEY=你的 MiniMax API key
MINIMAX_GROUP_ID=你的 MiniMax group id
SUPABASE_CLONED_BUCKET=cloned
COSYVOICE_URL=http://localhost:50000
```

5. 一键创建虚拟环境、安装依赖并启动后端：

```powershell
setup_backend.bat
```

或手动运行：

```powershell
cd apps\api
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

如果提示 `uvicorn not recognized`，使用：

```powershell
python -m uvicorn app.main:app --reload --port 8000
```

6. 验证健康检查：

```powershell
curl http://127.0.0.1:8000/health
```

期望返回：

```json
{"status":"ok"}
```

后端 CORS 已允许：

- `http://localhost:3000`
- `http://127.0.0.1:3000`

也可以直接运行：

```powershell
start_backend.bat
```

访问：

- 用户提交页：http://localhost:3000
- 用户任务页：http://localhost:3000/tasks
- 用户任务详情页：http://localhost:3000/tasks/{id}
- 管理后台：http://localhost:3000/admin
- 管理任务详情页：http://localhost:3000/admin/tasks/{id}
- AI 视频生成工作台：http://localhost:3000/admin/studio/{task_id}
- FastAPI 文档：http://localhost:8000/docs

## CosyVoice 本地语音克隆

CosyVoice 作为独立 Docker 服务运行在 `50000` 端口。现有 FastAPI 通过 `/api/cosyvoice/clone` 调用它，再把生成的 WAV 上传到 Supabase `cloned` bucket，并写回：

- `video_tasks.cloned_voice_url`
- `video_tasks.cosyvoice_status`

### 数据库升级

在 Supabase SQL Editor 重新执行：

```text
supabase/cosyvoice_migration.sql
```

确认新增字段：

```sql
cloned_voice_url text
cosyvoice_status text default 'pending'
```

### 启动 CosyVoice

先安装 Docker Desktop：

https://www.docker.com/products/docker-desktop/

Windows 一键启动：

```powershell
start_cosyvoice.bat
```

脚本会自动检测 `nvidia-smi`：

- 有 NVIDIA GPU：使用 `docker-compose.gpu.yml`
- 没有 GPU：fallback CPU 模式

首次启动会 clone `FunAudioLLM/CosyVoice`、安装依赖并下载模型，时间会比较久。默认模型：

```env
COSYVOICE_MODEL_DIR=iic/CosyVoice2-0.5B
```

也可以改用 CosyVoice3：

```powershell
$env:COSYVOICE_MODEL_DIR="FunAudioLLM/Fun-CosyVoice3-0.5B-2512"
start_cosyvoice.bat
```

### Studio 工作流

进入：

```text
http://localhost:3000/admin/studio/{task_id}
```

当前主流程使用半自动 HeyGen 生产模式：

1. 复制用户口播文案
2. 下载用户参考语音
3. 下载个人形象素材
4. 打开 HeyGen 创建 avatar / voice / video
5. 回填 `HeyGen avatar_id`、`HeyGen voice_id`、`HeyGen video_id`、`HeyGen video_url`
6. 上传最终 MP4，系统自动更新最终视频 URL 和任务状态

如果 Supabase 尚未包含 HeyGen 字段，请在 Supabase SQL Editor 执行：

```text
supabase/heygen_workflow_migration.sql
```

### CosyVoice API

```http
POST /api/cosyvoice/clone
Header: x-admin-key: <ADMIN_API_KEY>
FormData:
  text: 要合成的文案
  reference_audio: mp3/wav/m4a
  task_id: 可选，传入后自动更新 video_tasks
  prompt_text: 可选，参考音频对应文本
```

返回：

```json
{
  "audio_url": "https://...",
  "local_path": "tmp/cosyvoice/xxx.wav",
  "task": {}
}
```

## Docker 运行

先准备好 `apps/web/.env.local` 和 `apps/api/.env`，然后：

```bash
docker compose up --build
```

## MVP 说明

这个版本不接真实视频模型 API，不做全自动视频生成、真人数字人训练、自动 lip sync、自动剪辑、ASR、Whisper、实时 streaming、TensorRT 或微调训练。当前主流程先采用半自动生产：用户上传商品和素材，系统生成带货脚本、分镜和提示词；管理员手动粘贴到 HeyGen、即梦、可灵、剪映/CapCut 完成视频，并在 Studio 上传最终 MP4 交付。CosyVoice 本地 voice clone 代码保留为备用能力，但不再作为 Studio 主流程入口。
