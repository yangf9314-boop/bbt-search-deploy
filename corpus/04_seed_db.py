#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
脚本 4：把台词数据批量写入 Supabase

━━━ 输入 ━━━
  data/parsed/*.jsonl         （脚本 1 产出的台词 JSONL）
  data/clips/clips_index.json （脚本 2 产出的 line_id → clip_key 映射）
  环境变量：
    SUPABASE_URL              形如 https://xxx.supabase.co
    SUPABASE_SERVICE_ROLE_KEY  Supabase 的 service_role key（只放本地，绝对不要放前端！）

━━━ 产出 ━━━
  Supabase episodes / lines 表里有数据

━━━ 验收 ━━━
  1) Supabase 控制台 → Table Editor → episodes 能看到 2–3 行（每集一行）
  2) lines 能看到几百行台词，中英文字段、start_ms、clip_key 都有值
  3) 用前端 anon key 做一条测试查询：supabase.from('lines').select('*').limit(1)
     能返回一条记录就算通过
"""

import json
import sys
from pathlib import Path

try:
    from supabase import create_client
except ImportError:
    print("❌ 缺少依赖，请先安装：pip install supabase")
    sys.exit(1)

from config import PARSED_DIR, SUPABASE_URL, SUPABASE_SECRET_KEY, merge_adjacent

BATCH_SIZE = 100  # 每批插入 100 条


def check_credentials():
    if not SUPABASE_URL:
        print("❌ 缺少 SUPABASE_URL 环境变量")
        sys.exit(1)
    if not SUPABASE_SECRET_KEY:
        print("❌ 缺少 SUPABASE_SECRET_KEY 环境变量")
        print("   新版名称：Supabase 控制台 → Settings → API → Secret keys → default")
        print("   旧版名称：service_role key（SDK 两种名都兼容）")
        sys.exit(1)


def load_all_lines() -> list[dict]:
    """
    读所有集的 JSONL，按 merge_adjacent 合并后，关联 clip_key
    ⚠️ 必须和 02_slice_video.py 用完全相同的合并逻辑 —— 否则切片和 DB 对不上
    """
    # 先关联 clips_index（02_slice_video.py 产出，合并后的 line_id → clip_key 映射）
    index_path = Path(__file__).resolve().parent.parent / "data" / "clips" / "clips_index.json"
    clip_index = {}
    if index_path.exists():
        with open(index_path, encoding="utf-8") as f:
            clip_index = json.load(f)
    else:
        print(f"⚠️  没找到 clips_index.json（{index_path}），clip_key 会用 start_ms 推断")

    all_lines = []
    jsonl_files = sorted(PARSED_DIR.glob("*.jsonl"))
    if not jsonl_files:
        print(f"❌ 在 {PARSED_DIR} 里没找到 .jsonl")
        print("   请先跑 01_parse_srt.py")
        sys.exit(1)

    for jf in jsonl_files:
        # 读原始台词
        raw_lines = []
        with open(jf, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    raw_lines.append(json.loads(line))

        # 和 02_slice_video.py 完全相同的合并逻辑
        merged_lines = merge_adjacent(raw_lines)

        # 关联 clip_key
        for ln in merged_lines:
            ln["clip_key"] = clip_index.get(ln["id"], "")
            if not ln["clip_key"]:
                ln["clip_key"] = f"{ln['episode_id']}_{ln['start_ms']}.mp4"

        all_lines.extend(merged_lines)

    return all_lines


def parse_season_episode(eid: str) -> tuple[int, int]:
    """从任意 episode_id 里提取季/集，支持 'S01E01'、'SHDBZ S01E01' 等格式"""
    import re
    m = re.search(r'(\d{2})[Ee](\d{2})', eid)
    if m:
        return int(m.group(1)), int(m.group(2))
    return 0, 0  # 解析失败兜底

def extract_episodes(lines: list[dict]) -> list[dict]:
    """从台词里提取剧集列表（去重）"""
    episodes = {}
    for ln in lines:
        eid = ln["episode_id"]
        if eid not in episodes:
            season, episode = parse_season_episode(eid)
            episodes[eid] = {
                "id": eid,
                "season": season,
                "episode": episode,
                "title_en": None,
                "title_zh": None,
            }
    return list(episodes.values())


def insert_batch(supabase, table, records: list[dict]) -> int:
    """批量插入，失败就打印前几个错误"""
    if not records:
        return 0
    try:
        result = supabase.table(table).insert(records).execute()
        if hasattr(result, "error") and result.error:
            print(f"   ⚠️  插入 {table} 失败：{result.error}")
            return 0
        return len(result.data) if hasattr(result, "data") and result.data else len(records)
    except Exception as e:
        print(f"   ⚠️  插入 {table} 异常：{e}")
        return 0


def main():
    check_credentials()

    # 连接 Supabase（用 Secret key 跳过 RLS 直接写库）
    supabase = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)

    lines = load_all_lines()
    episodes = extract_episodes(lines)

    print(f"📊 准备插入：{len(episodes)} 集，{len(lines)} 条台词")

    # 先清一下旧数据（避免重复）—— 如果权限不够就跳过
    try:
        print("🗑️  清掉旧数据...")
        supabase.table("lines").delete().neq("id", 0).execute()
        supabase.table("episodes").delete().neq("id", "").execute()
    except Exception as e:
        print(f"   ⚠️  清理失败（可能权限不够），跳过继续插入：{e}")

    # 插入 episodes
    ok = insert_batch(supabase, "episodes", episodes)
    print(f"   episodes 插入 {ok} 条")

    # 分批插入 lines（去掉 JSONL 的 "id" 字段，让数据库自增生成）
    total_lines = 0
    for i in range(0, len(lines), BATCH_SIZE):
        batch = lines[i:i + BATCH_SIZE]
        # 清理掉不需要的字段：id（数据库自增）、clip_duration_ms 计算留空也行
        batch = [{k: v for k, v in item.items() if k != "id"} for item in batch]
        ok = insert_batch(supabase, "lines", batch)
        total_lines += ok
        if (i + BATCH_SIZE) % 500 == 0 or i + BATCH_SIZE >= len(lines):
            print(f"   lines 已插入 {total_lines} / {len(lines)}")

    print(f"\n🎉 全部完成：episodes {len(episodes)}，lines {total_lines}")
    print("   验证：Supabase 控制台 → Table Editor → lines 表，应该能看到数据")


if __name__ == "__main__":
    main()
