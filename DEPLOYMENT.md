# Production Deployment Guide

目标域名：`https://kaiqiang.ai`

## 1. 部署范围

Vercel 用于部署 `apps/web` 的 Next.js 前端。

当前 FastAPI 后端不适合直接部署到 Vercel，因为它依赖长期运行的 Uvicorn 服务、文件上传、Supabase service role key、可选 CosyVoice 本地服务。生产环境建议把 FastAPI 部署到 Render、Railway、Fly.io、云服务器或 Docker 主机，然后把后端公网地址填入 Vercel 环境变量：

```env
NEXT_PUBLIC_API_URL=https://your-fastapi-api.example.com
SERVER_API_URL=https://your-fastapi-api.example.com
```

## 2. Vercel 项目设置

在 Vercel 新建项目时：

- Framework Preset: `Next.js`
- Root Directory: `apps/web`
- Install Command: `npm install`
- Build Command: `npm run build`
- Output Directory: 留空，Vercel 自动识别 `.next`

## 3. Vercel 环境变量

在 Vercel Project Settings -> Environment Variables 中添加：

| Name | Environment | Example | Required |
| --- | --- | --- | --- |
| `NEXT_PUBLIC_API_URL` | Production/Preview/Development | `https://api.kaiqiang.ai` | Yes |
| `SERVER_API_URL` | Production/Preview/Development | `https://api.kaiqiang.ai` | Yes |
| `NEXT_PUBLIC_SUPABASE_URL` | Production/Preview/Development | `https://xxx.supabase.co` | Yes |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Production/Preview/Development | `eyJ...` | Yes |
| `SERVER_ADMIN_API_KEY` | Production/Preview/Development | same as FastAPI `ADMIN_API_KEY` | Yes |

不要在 Vercel 前端项目里配置 `SUPABASE_SERVICE_ROLE_KEY`。

`SERVER_ADMIN_API_KEY` 必须只填写密钥值本身，不能填写成 `ADMIN_API_KEY=xxxx`。Web 服务端会优先读取 `SERVER_ADMIN_API_KEY`，并兼容旧的 `ADMIN_API_KEY`。不要配置 `NEXT_PUBLIC_ADMIN_API_KEY`。可访问后端 `/debug/config` 查看 `admin_api_key_fingerprint`，用它和本地/部署平台中同一密钥的 SHA-256 前 12 位对齐排查，不要公开原始密钥。

## 4. FastAPI 生产环境变量

部署 FastAPI 的平台需要配置：

| Name | Example | Required |
| --- | --- | --- |
| `SUPABASE_URL` | `https://xxx.supabase.co` | Yes |
| `SUPABASE_SERVICE_ROLE_KEY` | `eyJ...service_role...` | Yes |
| `SUPABASE_IMAGE_BUCKET` | `images` | Yes |
| `SUPABASE_VOICE_BUCKET` | `voices` | Yes |
| `SUPABASE_CLONED_BUCKET` | `cloned` | Yes |
| `SUPABASE_VIDEO_BUCKET` | `videos` | Yes |
| `SUPABASE_SUBTITLE_BUCKET` | `subtitles` | Yes |
| `ADMIN_API_KEY` | same as Vercel | Yes |
| `WEB_ORIGIN` | `https://kaiqiang.ai` | Yes |
| `CORS_ORIGINS` | `https://kaiqiang.ai,https://www.kaiqiang.ai,https://kaiqiang-58mkzjhmo-kaiqiang-ai-s-projects.vercel.app,https://kaiqiang-pltbb4kum-kaiqiang-ai-s-projects.vercel.app` | Yes |
| `MINIMAX_API_KEY` | MiniMax key | Optional for current semi-auto flow |
| `MINIMAX_GROUP_ID` | MiniMax group id | Optional for current semi-auto flow |
| `COSYVOICE_URL` | `http://localhost:50000` | Optional |
| `MUSE_TALK_DEFAULT_TEMPLATE_VIDEO_URL` | `https://.../template.mp4` | Required for `/api/avatar/dynamic-video` |

## 5. Supabase 上线检查

在 Supabase SQL Editor 执行：

```text
supabase/schema.sql
supabase/heygen_workflow_migration.sql
supabase/commerce_mvp_migration.sql
```

确认 public buckets 存在：

- `images`
- `voices`
- `videos`
- `subtitles`
- `cloned`

## 6. 绑定 `kaiqiang.ai`

在 Vercel：

1. 打开 Project Settings -> Domains。
2. 添加 `kaiqiang.ai`。
3. 再添加 `www.kaiqiang.ai`。
4. 选择把 `www` redirect 到 apex，或把 apex redirect 到 `www`。建议主站使用 apex：`kaiqiang.ai`。

## 7. Spaceship DNS 配置

在 Spaceship 域名 DNS 管理里添加或修改：

| Host/Name | Type | Value | TTL | Purpose |
| --- | --- | --- | --- | --- |
| `@` | `A` | `76.76.21.21` | Auto/300 | Vercel apex domain |
| `www` | `CNAME` | `cname.vercel-dns-0.com` | Auto/300 | Vercel www domain |

如果已有冲突记录：

- 删除 `@` 上旧的 A/AAAA 记录。
- 删除 `www` 上旧的 CNAME/A 记录。
- 不要删除邮箱相关 MX/TXT 记录，除非你确认不用邮箱。

DNS 生效后，Vercel 会自动签发 SSL 证书，访问：

```text
https://kaiqiang.ai
```

## 8. 发布前命令

```powershell
npm install
npm --workspace apps/web run lint
npm --workspace apps/web run build
```

如果本机 Git 已安装：

```powershell
git init
git add .
git commit -m "Deploy AI video agent MVP"
```
