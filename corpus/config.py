# -*- coding: utf-8 -*-
"""
集中配置：路径、ffmpeg 参数、R2 连接信息
运行每个脚本前，环境变量从 .env 文件自动加载（python-dotenv）
"""
from pathlib import Path
import os
from dotenv import load_dotenv

# 项目根目录（corpus/ 的上两级）
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 自动加载 .env / .env.local（优先级：.env.local > .env）
load_dotenv(PROJECT_ROOT / "corpus" / ".env.local")
load_dotenv(PROJECT_ROOT / "corpus" / ".env")

# 数据路径（相对项目根）
RAW_VIDEO_DIR = PROJECT_ROOT / "data" / "raw_video"
RAW_SRT_DIR = PROJECT_ROOT / "data" / "raw_srt"
PARSED_DIR    = PROJECT_ROOT / "data" / "parsed"
CLIPS_DIR     = PROJECT_ROOT / "data" / "clips"

# 确保目录存在
for d in [RAW_VIDEO_DIR, RAW_SRT_DIR, PARSED_DIR, CLIPS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ffmpeg 切片参数
SLICE_PRE_SECONDS  = 1   # 台词起点前留 1 秒
SLICE_POST_SECONDS = 2   # 台词终点后留 2 秒
FFMPEG_CRF    = 26       # 压缩率（数字越大体积越小、画质越低）
FFMPEG_PRESET = "veryfast"
FFMPEG_VIDEO_CODEC = "libx264"
FFMPEG_AUDIO_CODEC = "aac"
FFMPEG_AUDIO_BITRATE = "96k"

# 双语字幕合并阈值（毫秒）：相邻字幕时间差小于此值且说话人相同 → 合并
MERGE_GAP_MS = 500


# ─────────────────────────────────────────────
# 跨脚本共享的数据处理函数
# ─────────────────────────────────────────────

def merge_adjacent(lines: list[dict], gap_ms: int | None = None) -> list[dict]:
    """
    合并相邻台词：如果前一条的 end_ms 和后一条的 start_ms 时间差 < MERGE_GAP_MS
    且说话人相同 → 合并成一条（延长 end_ms、拼接文本、保留第一条的 id/seq/start_ms）

    02_slice_video.py 切片前调用，04_seed_db.py 入库前也必须调用 —— 两处必须用同样逻辑
    否则数据库里会出现 clip_key 不存在的孤立台词。
    """
    if gap_ms is None:
        gap_ms = MERGE_GAP_MS
    if len(lines) <= 1:
        return list(lines)

    merged = [dict(lines[0])]  # 浅拷贝，避免修改输入
    for curr in lines[1:]:
        prev = merged[-1]
        gap = curr["start_ms"] - prev["end_ms"]
        same_speaker = (prev.get("speaker") == curr.get("speaker"))

        if gap < gap_ms and same_speaker:
            prev["end_ms"] = curr["end_ms"]
            prev["text_en"] += " " + curr.get("text_en", "")
            prev["text_zh"] += " " + curr.get("text_zh", "")
        else:
            merged.append(dict(curr))

    return merged

# Supabase（新版：Secret key 只用于本地脚本写入，绝对不要放进前端代码！）
# 从环境变量读：SUPABASE_URL / SUPABASE_SECRET_KEY
# 注：旧版 service_role key = 新版 Secret key，Supabase SDK 两种名都能读
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SECRET_KEY = os.environ.get("SUPABASE_SECRET_KEY", "") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

# Cloudflare R2（用 boto3 S3 协议连接）
# 从环境变量读：R2_ENDPOINT / R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY
R2_BUCKET = "tbbt-clips"
R2_ENDPOINT = os.environ.get("R2_ENDPOINT", "")  # 形如 https://xxx.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", "")
