#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
脚本 1：解析双语字幕 SRT → JSONL

━━━ 输入 ━━━
  data/raw_srt/*.srt  （每个文件对应一集，如 S01E01.srt）

━━━ 产出 ━━━
  data/parsed/*.jsonl  （每个 .jsonl 对应一集，每行一条台词）
  每行一个 JSON，格式：
  {
    "id": "S01E01_00001",
    "episode_id": "S01E01",
    "seq": 1,
    "start_ms": 1234500,
    "end_ms": 1236500,
    "speaker": "Sheldon",   // 可能为 null
    "text_en": "...",
    "text_zh": "..."
  }

━━━ 验收 ━━━
  1) 随便打开一个 .jsonl，每行能看到 start_ms / text_en / text_zh 三个字段都有值
  2) 中英时间戳对得上（同一条台词的 start_ms 和 end_ms 只有一对）
  3) 抽查 5 条，中文是中文、英文是英文，没有中英混写
"""

import json
import re
from pathlib import Path
import pysrt

from config import RAW_SRT_DIR, PARSED_DIR


# ─────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────

def strip_ass_tags(text: str) -> str:
    """清理 ASS 格式标签：{\\fs16\\an2\\b0} 这种"""
    return re.sub(r'\{[^}]*\}', '', text)

def is_chinese(text: str) -> bool:
    """判断一段文字主要是中文（含 CJK 字符）"""
    for ch in text:
        if '\u4e00' <= ch <= '\u9fff':
            return True
    return False

def clean_speaker(text: str) -> tuple[str | None, str]:
    """
    从字幕文本里提取说话人前缀（如 "Sheldon: Hello"）
    返回 (speaker, 清理后的文本)
    """
    match = re.match(r'^\s*([A-Za-z\u4e00-\u9fff]+)\s*[:：]\s*(.+)$', text)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return None, text.strip()

def ms(srt_time) -> int:
    """srt 时间 → 毫秒整数"""
    return srt_time.ordinal


# ─────────────────────────────────────────────
# 单个文件处理
# ─────────────────────────────────────────────

def parse_one_srt(srt_path: Path) -> list[dict]:
    """
    解析一个双语字幕文件，返回台词记录列表
    """
    episode_id = srt_path.stem  # S01E01

    # 尝试多种编码
    subs = None
    for enc in ['utf-8', 'utf-8-sig', 'gbk', 'gb18030']:
        try:
            subs = pysrt.open(str(srt_path), encoding=enc)
            break
        except UnicodeDecodeError:
            continue
    if subs is None:
        raise RuntimeError(f"无法识别编码：{srt_path}")

    results = []
    seq = 0

    for item in subs:
        # 先清理 ASS 标签
        raw_text = strip_ass_tags(item.text)
        lines = raw_text.strip().splitlines()
        lines = [l.strip() for l in lines if l.strip()]

        if not lines:
            continue

        speaker = None
        text_en = ""
        text_zh = ""

        if len(lines) >= 2:
            # 双语字幕：判断哪行是中文
            first_is_zh = is_chinese(lines[0])
            zh_line = lines[0] if first_is_zh else lines[1]
            en_line = lines[1] if first_is_zh else lines[0]

            # 提取说话人
            speaker_zh, zh_line = clean_speaker(zh_line)
            speaker_en, en_line = clean_speaker(en_line)
            speaker = speaker_zh or speaker_en  # 哪边有说话人就用哪边

            text_zh = zh_line
            text_en = en_line

        elif len(lines) == 1:
            # 单行字幕，尽力判断
            speaker, text = clean_speaker(lines[0])
            if is_chinese(text):
                text_zh = text
            else:
                text_en = text

        if not text_en and not text_zh:
            continue

        seq += 1
        results.append({
            "id": f"{episode_id}_{seq:05d}",
            "episode_id": episode_id,
            "seq": seq,
            "start_ms": ms(item.start),
            "end_ms": ms(item.end),
            "speaker": speaker,
            "text_en": text_en,
            "text_zh": text_zh,
        })

    return results


# ─────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────

def main():
    srt_files = sorted(RAW_SRT_DIR.glob("*.srt"))
    if not srt_files:
        print(f"❌ 在 {RAW_SRT_DIR} 里没找到任何 .srt 文件")
        print("   请把字幕文件放进去（命名如 S01E01.srt）")
        return

    total = 0
    for srt_path in srt_files:
        records = parse_one_srt(srt_path)
        out_path = PARSED_DIR / f"{srt_path.stem}.jsonl"
        with open(out_path, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"✅ {srt_path.name} → {out_path.name}（{len(records)} 条台词）")
        total += len(records)

    print(f"\n🎉 全部完成：共 {len(srt_files)} 集，{total} 条台词")
    print(f"   产出目录：{PARSED_DIR}")


if __name__ == "__main__":
    main()
