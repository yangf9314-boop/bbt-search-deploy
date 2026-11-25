#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
脚本 2：按台词切视频片段

━━━ 输入 ━━━
  data/raw_video/*.mp4  （S01E01.mp4 ...）
  data/parsed/*.jsonl   （脚本 1 产出的台词 JSONL）

━━━ 产出 ━━━
  data/clips/*.mp4  （每个文件名形如 S01E01_124000.mp4）
  data/clips_index.json  （台词 ID → clip_key 的映射，供脚本 3、4 用）

━━━ 验收 ━━━
  1) 浏览器直接打开 data/clips/ 里任意一个 .mp4，能正常播放
  2) 抽查 3 个片段，起点确实是对话开始处（台词起点 - 1 秒余量）
  3) clips_index.json 里的映射数量和切出来的 mp4 数量一致
"""

import json
import subprocess
import sys
from pathlib import Path

from config import (
    RAW_VIDEO_DIR, PARSED_DIR, CLIPS_DIR,
    SLICE_PRE_SECONDS, SLICE_POST_SECONDS,
    FFMPEG_CRF, FFMPEG_PRESET, FFMPEG_VIDEO_CODEC,
    FFMPEG_AUDIO_CODEC, FFMPEG_AUDIO_BITRATE,
    merge_adjacent,
)


# ─────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────

def load_lines(jsonl_path: Path) -> list[dict]:
    """读一个集的 JSONL，返回台词列表"""
    lines = []
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                lines.append(json.loads(line))
    return lines

def slice_one(video_path: Path, line: dict, out_dir: Path) -> str | None:
    """
    用 ffmpeg 切一个片段
    返回生成的 clip_key（文件名），失败返回 None
    """
    episode_id = line["episode_id"]
    start_ms   = line["start_ms"]
    end_ms     = line["end_ms"]

    # 切片参数：起点 -1 秒，终点 +2 秒
    pre_ms  = int(SLICE_PRE_SECONDS * 1000)
    post_ms = int(SLICE_POST_SECONDS * 1000)

    slice_start_ms = max(0, start_ms - pre_ms)
    slice_end_ms   = end_ms + post_ms
    duration_ms    = slice_end_ms - slice_start_ms

    start_sec = slice_start_ms / 1000.0
    duration_sec = duration_ms / 1000.0

    clip_key = f"{episode_id}_{start_ms}.mp4"
    out_path = out_dir / clip_key

    # ffmpeg 命令：-ss 在 -i 前 + 重编码 → 快且精确（accurate_seek 默认开启）
    cmd = [
        "ffmpeg",
        "-ss", str(start_sec),          # 定位（关键帧 seek + 重编码精确到帧）
        "-i", str(video_path),           # 输入视频
        "-t", str(duration_sec),         # 切片时长
        "-c:v", FFMPEG_VIDEO_CODEC,
        "-crf", str(FFMPEG_CRF),
        "-preset", FFMPEG_PRESET,
        "-c:a", FFMPEG_AUDIO_CODEC,
        "-b:a", FFMPEG_AUDIO_BITRATE,
        "-movflags", "+faststart",
        "-y",                             # 覆盖已存在
        str(out_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"   ⚠️  ffmpeg 失败：{episode_id} seq={line['seq']}")
        print(f"      {result.stderr[-200:]}")
        return None

    return clip_key


# ─────────────────────────────────────────────
# 单个集处理
# ─────────────────────────────────────────────

def process_episode(jsonl_path: Path, video_path: Path, index: dict):
    lines = load_lines(jsonl_path)
    lines = merge_adjacent(lines)  # 先合并相邻同说话人

    episode_id = jsonl_path.stem
    success = 0
    fail = 0

    for line in lines:
        clip_key = slice_one(video_path, line, CLIPS_DIR)
        if clip_key:
            line["clip_key"] = clip_key
            line["clip_duration_ms"] = int(line["end_ms"] - line["start_ms"] + (SLICE_PRE_SECONDS + SLICE_POST_SECONDS) * 1000)
            index[line["id"]] = clip_key
            success += 1
        else:
            fail += 1

    print(f"   ✅ {episode_id}: 成功 {success}，失败 {fail}")
    return success, fail


# ─────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────

def main():
    # 找所有集：jsonl 和对应的 mp4
    jsonl_files = sorted(PARSED_DIR.glob("*.jsonl"))
    if not jsonl_files:
        print(f"❌ 在 {PARSED_DIR} 里没找到 .jsonl 文件")
        print("   请先跑 01_parse_srt.py")
        return

    # 检查 ffmpeg
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except FileNotFoundError:
        print("❌ 没检测到 ffmpeg，请先安装：brew install ffmpeg")
        sys.exit(1)

    total_ok = 0
    total_fail = 0
    index = {}  # line_id → clip_key

    for jsonl_path in jsonl_files:
        episode_id = jsonl_path.stem
        # 优先找 .mp4，其次 .mkv，最后 .mov（ffmpeg 都能直接解码）
        video_path = None
        for ext in ("mp4", "mkv", "mov"):
            candidate = RAW_VIDEO_DIR / f"{episode_id}.{ext}"
            if candidate.exists():
                video_path = candidate
                break

        if video_path is None:
            print(f"⚠️  跳过 {episode_id}：没找到对应视频（支持 .mp4 / .mkv / .mov）")
            continue

        ok, fail = process_episode(jsonl_path, video_path, index)
        total_ok += ok
        total_fail += fail

    # 保存映射索引
    index_path = CLIPS_DIR / "clips_index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

    print(f"\n🎉 全部完成：成功 {total_ok}，失败 {total_fail}")
    print(f"   切片产出：{CLIPS_DIR}")
    print(f"   映射索引：{index_path}")


if __name__ == "__main__":
    main()
