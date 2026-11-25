# 《生活大爆炸》台词检索 — MVP 开发手册

> 这份文档是写给 **非技术人员也能看懂** 的。所有技术词第一次出现都会配人话解释。
> 目标：一个能跑通 **搜索 → 播放 → 分享** 的最小可用版本，可以部署上线。
> 用法：每次只给 Trae 一个阶段的任务，做完验收再进下一步。

---

## 0. 先定死：MVP 做什么、不做什么

| ✅ 做（就这 6 件事） | ❌ 不做（第一版一律砍） |
|---|---|
| 输入一个关键词，搜中英文台词 | 多选打包分享、图片卡导出 |
| 结果列表：台词文本 + 角色 + 集数 | 播放器微调裁剪 |
| 点播放 → 看预切好的视频片段 | 角色/季数筛选下拉 |
| 点分享 → 复制单条链接 | 多关键词 AND 搜索 |
| 朋友打开分享链接 → 看到相同内容 | 自定义排序（完全匹配>前缀>子串） |
| 2–3 集样本数据先跑通 | 12 季全集、登录注册、收藏、评论 |

**整条数据流只有一条线，全程照这条检查有没有跑偏：**

```
用户输入关键词 → 数据库模糊匹配 → 返回台词行 → 点播放 → 加载预切好的视频片段
                                                    → 点分享 → 复制 ?id=xxx 链接
                                                                          ↓
                                                              朋友打开 → 按 id 查库 → 渲染
```

---

## 1. 技术栈（一句话讲清楚每个工具干嘛的）

| 层 | 用什么 | 人话解释 | 月费 |
|---|---|---|---|
| 前端 | Vite + React + TypeScript | 做网页的三件套，拖 Trae 生成最快 | ¥0 |
| 数据库 | Supabase | 免费的在线数据库，自带网页查询接口，前端直接调，不用写后端 | ¥0 |
| 视频存储 | Cloudflare R2 | 免费存小视频，全球 CDN 加速播放，流量费为零 | ¥0 |
| 前端托管 | Cloudflare Pages | 免费把网页放上去，和 R2 同一家公司好配 | ¥0 |
| 数据处理 | Python 脚本 + ffmpeg | 本地跑一次，把字幕和视频处理成可用格式 | ¥0 |

**合计月费：¥0** — 所有服务的免费额度都够用。

---

## 2. 项目目录结构

Trae 会按这棵树创建文件。目录分成四块：前端、数据处理脚本、数据库建表 SQL、原始素材。

```text
tbbt-quotes/
├── .env.example              # 环境变量样例（告诉 Trae 需要哪些配置）
├── .gitignore                # 告诉 Git 哪些文件不要上传（视频、密钥等）
│
├── frontend/                 # 【前端层】纯网页，最后部署到 Cloudflare Pages
│   ├── src/
│   │   ├── main.tsx          # 入口：启动网页
│   │   ├── App.tsx           # 路由：搜索页 / 分享页
│   │   ├── types.ts          # 类型定义（所有模块的字段都以这里为准）
│   │   ├── lib/
│   │   │   ├── supabase.ts   # 数据库客户端（读 .env 里的地址和密钥）
│   │   │   └── search.ts     # 搜索：关键词 → 数据库查询 → 结果列表
│   │   ├── components/
│   │   │   ├── SearchBar.tsx     # 搜索框（含中英切换）
│   │   │   ├── ResultCard.tsx    # 单条结果卡（文本 + 播放 + 分享按钮）
│   │   │   └── ClipPlayer.tsx    # 播放器弹层
│   │   ├── pages/
│   │   │   ├── SearchPage.tsx    # 主页面：搜索框 + 结果列表
│   │   │   └── SharedPage.tsx    # 分享落地页
│   │   └── styles/
│   │       └── global.css        # 全局样式（先简单写，后面设计稿来了再细化）
│   └── index.html            # HTML 外壳
│
├── corpus/                   # 【数据处理层】本地一次性运行的 Python 脚本
│   ├── 01_parse_srt.py       # 解析字幕文件
│   ├── 02_slice_video.py     # 切视频片段
│   ├── 03_upload_r2.py       # 上传到 R2
│   ├── 04_seed_db.py         # 写入数据库
│   └── requirements.txt      # Python 依赖列表
│
├── supabase/
│   └── migrations/
│       └── 0001_init.sql     # 建表 SQL（数据库结构的唯一来源）
│
└── data/                     # 【原始素材】本地临时目录，不上传到 Git
    ├── raw_video/            # 你自备的合法 mp4（S01E01.mp4 ...）
    └── raw_srt/              # 字幕文件（S01E01.srt ...）
```

---

## 3. 数据库结构（只有两张表，砍掉 shares 表和 context 字段）

把下面的 SQL 存为 `supabase/migrations/0001_init.sql`，然后在 Supabase 控制台的 SQL Editor 里粘贴执行。

> SQL 里的人话注释：每一行 `--` 后面的话是给 Trae 读的，帮它理解这行 SQL 干嘛的。

```sql
-- ① 开启中文/英文的模糊搜索索引（让"搜片段"能快起来）
create extension if not exists pg_trgm;

-- ② 剧集表：一集一条（比如 S01E01、S01E02...）
create table if not exists episodes (
  id text primary key,              -- 编号，形如 S01E01
  season int not null,              -- 第几季
  episode int not null,             -- 第几集
  title_en text,                    -- 英文剧名（可选）
  title_zh text,                    -- 中文剧名（可选）
  created_at timestamptz default now()
);

-- ③ 台词表：项目的核心，每条台词 = 一个可搜索、可播放、可分享的单元
create table if not exists lines (
  id bigint generated always as identity primary key,  -- 自增编号（分享链接用这个）
  episode_id text not null references episodes(id) on delete cascade,  -- 属于哪集
  seq int not null,                 -- 在剧集中的顺序号
  start_ms int not null,            -- 片段起点（毫秒）
  end_ms int not null,              -- 片段终点（毫秒）
  speaker text,                     -- 说话人（Sheldon / Penny ...）
  text_en text not null,            -- 英文字幕（可被搜）
  text_zh text not null,            -- 中文字幕（可被搜）
  clip_key text not null,           -- R2 上的文件名（如 S01E01_124000.mp4）
  clip_duration_ms int,             -- 片段总时长（播放器显示用）
  unique(episode_id, start_ms)      -- 防止重复导入
);

-- ④ 给搜索字段加索引（让模糊搜索更快）
create index if not exists lines_text_en_trgm on lines using gin (text_en gin_trgm_ops);
create index if not exists lines_text_zh_trgm on lines using gin (text_zh gin_trgm_ops);
create index if not exists lines_episode_idx on lines(episode_id);

-- ⑤ 安全策略：所有人只能读，不能改（匿名 key 公开使用）
alter table episodes enable row level security;
alter table lines enable row level security;

create policy "public read episodes" on episodes for select using (true);
create policy "public read lines"    on lines    for select using (true);
-- 注意：没有开放 insert/update/delete，所以前端 anon key 无法篡改数据
-- 导入数据要用 service_role key（只放在本地脚本里，绝不写进前端）
```

---

## 4. 数据处理流水线（4 个脚本，逐个跑）

### 4.1 素材准备（你自己做，Trae 帮不了）

- **视频 MP4**：你合法持有的《生活大爆炸》2–3 集，命名 `S01E01.mp4`、`S01E02.mp4`... 放进 `data/raw_video/`
- **字幕 SRT**：优先下载**双语字幕**（一个文件里同一时间点上下两行中文+英文），命名 `S01E01.srt`... 放进 `data/raw_srt/`
  - 推荐来源：OpenSubtitles、SubDL（无需注册）
  - 如果拿到的字幕格式乱，**人工看一眼分中英**就行，2–3 集很快

### 4.2 四个脚本的职责（Trae 生成，你逐个跑）

#### 脚本 1：`01_parse_srt.py` — 解析字幕

- **输入**：`data/raw_srt/S01E01.srt`
- **动作**：读 srt 文件，拆成每条字幕记录（时间 + 英文 + 中文），输出 JSONL
- **双语字幕识别规则**：一个时间块内有两行，第一行英文第二行中文（或反过来），脚本自动判断
- **产出**：`data/parsed/S01E01.jsonl`
- **验收**：随便打开一个 .jsonl，能看到 `"start_ms": 1234500`、`"text_en": "..."`、`"text_zh": "..."`

#### 脚本 2：`02_slice_video.py` — 切视频片段

- **输入**：`data/raw_video/S01E01.mp4` + `data/parsed/S01E01.jsonl`
- **动作**：对每条台词，用 ffmpeg 切成独立片段：从台词起点前 1 秒开始，到台词终点后 2 秒结束（留点前后余量，播放自然）
- **ffmpeg 命令**（脚本内部用）：
  ```bash
  ffmpeg -ss <起点秒数-1> -i S01E01.mp4 -t <时长+3> \
    -c:v libx264 -crf 26 -preset veryfast \
    -c:a aac -b:a 96k -movflags +faststart \
    -y S01E01_124000.mp4
  ```
  参数人话解释：
  - `-crf 26`：压缩视频体积，画质够用
  - `-preset veryfast`：加速编码
  - `+faststart`：让网页能边下边播，不用等全加载完
- **产出**：`data/clips/S01E01_124000.mp4`、`S01E01_...mp4`...
- **验收**：浏览器直接打开一个片段能播放；抽查 3 条，起点确实是对话开始处

#### 脚本 3：`03_upload_r2.py` — 上传到 R2

- **输入**：`data/clips/*.mp4`
- **动作**：批量上传到 Cloudflare R2 的 `tbbt-clips` 桶，上传时记录"本地路径 → R2 对象 key"的映射
- **产出**：上传完成后打印 "uploaded N clips"
- **验收**：浏览器打开 R2 公有域名 + `/S01E01_124000.mp4`，能播放且能拖动进度条

#### 脚本 4：`04_seed_db.py` — 写入 Supabase

- **输入**：脚本 1 解析的字幕数据 + 脚本 2 生成的 clip_key 映射
- **动作**：组装成 lines 表的记录，用 service_role key 批量插入 Supabase（每批 100 条）
- **产出**：数据库里有数据
- **验收**：Supabase 控制台 → Table Editor → lines 表，能看到中英台词、start_ms、clip_key 都有值

---

## 5. 前端交互（MVP 极简版）

### 5.1 页面布局

```
┌──────────────────────────────────────────────┐
│        TBBT Quotes     中 / 英 / 双语        │
├──────────────────────────────────────────────┤
│                                              │
│        ┌────────────────────────────┐        │
│        │  搜台词...        [搜索]   │        │
│        └────────────────────────────┘        │
│   试试：bazinga / 天才 / 室友协议              │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │ 👤 Sheldon   S01E01  00:12:30          │  │  ResultCard
│  │  Bazinga!                              │  │
│  │  逗你玩！                              │  │
│  │       [▶ 播放]        [🔗 分享]        │  │
│  └────────────────────────────────────────┘  │
│  ...（更多结果）                              │
└──────────────────────────────────────────────┘
```

### 5.2 三个组件的职责（砍到最少）

#### SearchBar（搜索框）

- 一个输入框 + 三个切换按钮：中 / 英 / 双语（默认双语）
- 输入 ≥ 1 字符触发搜索（防抖 300ms），也支持回车
- **MVP 只支持单个关键词**，输入框就提示"输入一个关键词"
- 结果高亮：命中的关键词用黄色底标出来
- 空结果：显示"没找到，换个词试试"+ 示例词

#### ResultCard（单条结果卡）

- 显示：角色、集数、时间点、英文台词、中文台词
- 两个按钮：
  - **[▶ 播放]** → 打开 ClipPlayer 弹层
  - **[🔗 分享]** → 复制 `tbbt-quotes.com/shared?id=123` 到剪贴板，弹 toast "已复制链接"

#### ClipPlayer（播放器弹层）

- `<video autoPlay controls>` 加载预切好的片段
- 视频地址拼接：`VITE_R2_PUBLIC_BASE + '/' + clip_key`
- 字幕浮层：显示当前台词的中英文本，可切换
- 关闭按钮：暂停并卸载 video 元素

### 5.3 两个页面

#### SearchPage（主页面）

- 组合 SearchBar + ResultCard 列表
- 搜索结果直接渲染，分页先不做（几百条一次能看完）

#### SharedPage（分享落地页）

- 读 URL 参数 `?id=123`
- 调 Supabase 查 `lines` 表 `id = 123`
- 渲染 ResultCard + 播放器
- 如果 id 无效或查不到：显示"这个台词好像不存在了 :("

---

## 6. 部署步骤（能跑通就能上线）

### 6.1 一次性准备（按顺序做，Trae 帮不了控制台操作）

1. **Supabase**：
   - 注册 → 新建项目（区域选 Singapore 或离你近的）
   - SQL Editor → 粘贴第 3 章的 SQL → Run
   - Settings → API → 复制 `Project URL` 和 `Publishable key`（Supabase 新版名称，原来的 anon public key 已改名）

2. **Cloudflare R2**：
   - 控制台 → R2 → 创建桶 `tbbt-clips`
   - 开启 **R2.dev 子域**（临时公有访问，免费）
   - 记下公有域名（形如 `https://pub-xxx.r2.dev`）

3. **Cloudflare Pages**：
   - 创建项目 → 连接 GitHub 仓库
   - 构建命令：`cd frontend && npm run build`
   - 输出目录：`frontend/dist`

4. **本地环境变量**（`.env.local`，不进 Git）：
   ```
   VITE_SUPABASE_URL=https://xxxx.supabase.co
   VITE_SUPABASE_ANON_KEY=sb_publishable_xxx
   VITE_R2_PUBLIC_BASE=https://pub-xxxx.r2.dev
   ```

### 6.2 部署流程

```
Step 1  本地跑通：`cd frontend && npm install && npm run dev`，确认搜索+播放+分享都能用
Step 2  git push → Pages 自动构建 → 拿到 xxx.pages.dev 链接
Step 3  Pages → Settings → Environment variables → 填入上面 3 个变量
Step 4  重新部署（Retry deployment）→ 打开线上链接验收
```

### 6.3 上线验收（一个都不能跳）

| 检查项 | 怎么验证 | 通过标准 |
|---|---|---|
| 数据库可读 | 线上搜索能返回结果 | 能看到台词列表 |
| 视频能播 | 点任意一个"播放" | 弹层里视频加载并自动播放 |
| Range 请求 | 浏览器 DevTools → Network → 点 mp4 → 看响应头 | 状态 206 Partial Content，能拖动进度 |
| 分享可还原 | 复制分享链接 → 无痕窗口打开 | 看到相同台词 + 能播放 |
| 手机端 | 手机打开网页 | 布局不溢出 |

### 6.4 运维（几乎为零）

- 月费：**¥0**
- 每周：Supabase 免费项目闲置 1 周会自动暂停 → 去 cron-job.org 建个免费定时任务，每周请求一次你的 Supabase REST 地址保活
- 扩数据：重复第 4 章流水线（新片段上传 R2、新台词写数据库），前端不用改
- 备份：Supabase 控制台 → Table Editor → lines 表 → Export CSV，存本地

---

## 7. 分阶段执行清单（Trae 提示词模板）

每次只给 Trae 一个阶段的内容，**不要一次性全丢**。做完验收再进下一步。

### 阶段 0 — 建项目骨架

> 📌 **这一步做完后你会看到什么：**
> - 工作区出现了一棵完整的目录树（和第 2 章画的一模一样），里面每个 .tsx / .py / .sql 文件都是空的占位
> - 终端 `cd frontend && npm run dev`，浏览器会打开一个空白页（标题写着 TBBT Quotes）
> - 还看不到任何搜索框、结果列表、播放器 —— 那些后面阶段才做

**Trae 提示词：**

```
在 [工作区路径] 创建一个 Vite + React + TypeScript 项目，目录结构严格按下面的树来建（只建目录和占位文件，不写业务逻辑）：
[粘贴第 2 章的目录树]
要求：
- 安装 @supabase/supabase-js
- 创建 .env.example 列出 VITE_SUPABASE_URL、VITE_SUPABASE_ANON_KEY、VITE_R2_PUBLIC_BASE 三项
- 写 .gitignore 忽略 node_modules、.env、data/
```

**验收**：`cd frontend && npm run dev` 能起一个空白页（浏览器打开 http://localhost:5173）。

### 阶段 1 — 数据库 + 类型定义

> 📌 **这一步做完后你会看到什么：**
> - Trae 把一段 SQL 存进了 `supabase/migrations/0001_init.sql`（可以打开看内容）
> - 你去 Supabase 控制台 → SQL Editor → 粘贴执行 → Table Editor，会看到 **episodes** 和 **lines** 两张空表（还没有数据）
> - `src/types.ts` 里多了 Line 和 Episode 两个接口，每个字段旁边有中文注释
> - 这一步网页**还是空白的**（类型定义只是告诉代码"数据长什么样"，不产生 UI）

**Trae 提示词：**

```
1) 把这段 SQL 存到 supabase/migrations/0001_init.sql：
[粘贴第 3 章完整 SQL]

2) 根据这张表结构，在 src/types.ts 定义 Line 和 Episode 两个 TypeScript 接口，
   字段名和 SQL 完全一致，每个字段写中文注释。
```

**验收**：SQL 在 Supabase 执行无报错；types.ts 字段和表一一对应。

### 阶段 2 — 数据处理脚本

> 📌 **这一步做完后你会看到什么：**
> - `corpus/` 下有 4 个 .py 文件 + requirements.txt
> - 你把视频和字幕放进 `data/raw_video/` 和 `data/raw_srt/`，然后在终端依次跑这 4 个脚本
> - 跑完 `01_parse_srt.py` → `data/parsed/` 出现 .jsonl 文件（用文本编辑器打开，每行一条台词，能看到中英文字 + 毫秒时间戳）
> - 跑完 `02_slice_video.py` → `data/clips/` 出现一堆 mp4（浏览器直接打开其中一个能播）
> - 跑完 `03_upload_r2.py` → 终端打印 "uploaded N clips"
> - 跑完 `04_seed_db.py` → Supabase 控制台 lines 表里终于有数据了！能看到几百条台词
> - ⚠️ 这一步网页**还是空白的**（脚本和前端是两条独立的线）

**Trae 提示词：**

```
在 corpus/ 下按第 4 章的 4 个步骤生成 Python 脚本，要求：
- 01_parse_srt.py：读 data/raw_srt/*.srt，双语字幕自动分中英文，输出 JSONL
- 02_slice_video.py：按 start_ms/end_ms 切片段，前后各留 1 秒/2 秒余量，ffmpeg 参数用手册里的那条
- 03_upload_r2.py：批量上传到 R2 tbbt-clips 桶
- 04_seed_db.py：组装 lines 记录，用 service_role key 批量写入 Supabase
- 每个脚本开头写清楚：输入路径、产出路径、验收方法
- 给出 requirements.txt：pysrt、boto3、supabase
```

**验收**：用 1 集数据跑通 4 步，抽查 20 条台词，中英对应、时间递增、clip_key 不重复。

### 阶段 3 — 搜索功能 + 结果列表

> 📌 **这一步做完后你会看到什么：**
> - 终端 `cd frontend && npm run dev` → 浏览器打开 → **终于不是空白页了！**
> - 顶部有搜索框，中/英/双语三个切换按钮
> - 输入 "bazinga" → 回车 → 能看到结果列表
> - 命中的关键词有黄色高亮
> - 每条结果卡底部有两个按钮：
>   - **[▶ 播放]** — 点了之后**还不会弹视频**（控制台会打印一行 clip_key，播放器是下一阶段做的）
>   - **[🔗 分享]** — 点了之后浏览器会提示"已复制链接"，粘贴出来长得像 `http://localhost:5173/shared?id=42`

**Trae 提示词：**

```
实现 src/lib/search.ts 和 SearchBar、ResultCard 组件。

search.ts：
- 从 Supabase 查 lines 表
- 语言参数：'zh' 只搜 text_zh，'en' 只搜 text_en，'both' 两个字段都搜（默认 both）
- 单关键词，用 ilike '%xxx%' 模糊匹配
- 用默认相似度排序（不需要自定义排序）

ResultCard：
- 显示 speaker、episode_id、时间点、英文台词、中文台词
- 结果高亮：命中的关键词用黄色底标出来
- 两个按钮：[▶ 播放] 先只打印 clip_key 到控制台，播放器下阶段做；[🔗 分享] 点击后复制当前 URL + ?id={line.id} 到剪贴板

SearchBar：
- 输入框 + 中/英/双语三个按钮
- 防抖 300ms
- 空结果显示友好提示
```

**验收**：线上/本地能搜出结果，高亮正确，分享按钮能复制链接。

### 阶段 4 — 播放器

> 📌 **这一步做完后你会看到什么：**
> - 在结果列表点 **[▶ 播放]** → 弹出一个视频框，视频自动开始播了！
> - 视频下方有字幕（中/英可切换）
> - 能拖动进度条，能暂停
> - 右上角有关闭按钮，点一下视频消失
> - 如果视频加载慢，检查一下 4.3 验收里的 Range 请求那条（99% 情况 R2 没问题）

**Trae 提示词：**

```
实现 ClipPlayer 组件：
- 接收 clip_key 和台词文本
- src = import.meta.env.VITE_R2_PUBLIC_BASE + '/' + clip_key
- <video autoPlay controls>
- 字幕浮层显示中英台词，可切换
- 关闭时暂停并卸载 video

在 ResultCard 里接上 [▶ 播放] 按钮。
```

**验收**：能弹出播放器、视频加载并自动播放、能拖动进度条。

### 阶段 5 — 分享落地页

> 📌 **这一步做完后你会看到什么：**
> - 在结果列表点 **[🔗 分享]** → 复制链接
> - 新建一个**无痕浏览器窗口** → 粘贴链接 → 回车
> - 能看到和刚才一模一样的那条台词卡 + 点播放能看视频
> - 如果把 URL 里的 id 改成一个不存在的数字（比如 `?id=99999`），页面会显示"这个台词好像不存在了"
> - ✅ 到这一步，**搜索 → 播放 → 分享 → 还原** 整条链在本地跑通了

**Trae 提示词：**

```
实现 SharedPage（pages/SharedPage.tsx）：
- 读 URL 参数 ?id=xxx
- 调 Supabase 查 lines 表 where id = xxx
- 查到了 → 渲染 ResultCard + ClipPlayer（复用已有组件）
- 查不到 → 显示 "这个台词好像不存在了"

在 App.tsx 里加路由：'/shared' → SharedPage，根路径 '/' → SearchPage
```

**验收**：复制分享链接 → 无痕窗口打开 → 能看到相同台词 + 能播放。

### 阶段 6 — 部署上线

> 📌 **这一步做完后你会看到什么：**
> - 项目推到 GitHub → Cloudflare Pages 自动构建完成
> - 拿到一个公网链接，形如 `tbbt-quotes.pages.dev`
> - 任何人（包括你朋友）打开这个链接 → 能搜索、能播放、能分享、能还原
> - 手机打开也能用
> - 月费 ¥0，不需要服务器

**怎么操作（控制台手动步骤，Trae 帮不了）：**

按第 6.1 / 6.2 的步骤手动操作控制台，然后跑 6.3 全部验收检查点。

---

## 8. Trae 使用规范

1. **一次一个阶段。** 不要把整份手册一次性丢给 Trae。
2. **用文件路径引用。** 改某处时写"参考 `src/types.ts` 的 Line 类型"，别让它猜。
3. **每阶段存快照。** 验收通过后 `git add && git commit`，改崩了能退回。
4. **看不懂就让它解释。** 选中代码问"这段干嘛的"。
5. **报错贴全量。** 把完整报错（终端输出 + 截图）贴进 Chat，不要只说"它报错了"。

---

## 9. 风险与待确认

| 风险 | 影响 | 怎么处理 |
|---|---|---|
| 视频版权 | 公开发布有法律风险 | 只用你合法持有的片源，页面声明"个人演示用途"，视频不进 Git |
| 字幕为粉丝翻译 | 同上 | 只用于演示，数据集来源在页脚署名 |
| Supabase 1 周暂停 | 演示时打不开 | 配免费保活任务（cron-job.org） |
| R2 Range 不支持 | 视频不能拖进度 | 验收检查点 3 验证；现在 R2.dev 默认支持 Range，99% 没问题 |
| 双语字幕格式乱 | 中英对不上 | 2–3 集直接人工分，不依赖复杂自动识别 |

---

**等你提供后再补的：**
- 页面设计稿（拿到后告诉我，我会更新 `styles/global.css` 和组件 className，不动数据流）
- 你实际选的片源和集数（决定先切几集）
