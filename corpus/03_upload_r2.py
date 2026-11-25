#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
脚本 3：批量上传视频片段到 Cloudflare R2

━━━ 输入 ━━━
  data/clips/*.mp4           （脚本 2 切好的视频片段）
  data/clips/clips_index.json （脚本 2 产出的映射索引）
  环境变量：
    R2_ENDPOINT            形如 https://xxx.r2.cloudflarestorage.com
    R2_ACCESS_KEY_ID       R2 的 Access Key ID
    R2_SECRET_ACCESS_KEY   R2 的 Secret Access Key

━━━ 产出 ━━━
  终端打印上传成功数量

━━━ 验收 ━━━
  1) 终端打印 "uploaded N clips"，N 和 data/clips/ 里的 mp4 数量一致
  2) R2 控制台 → tbbt-clips 桶里能看到对应的 mp4 文件
  3) 浏览器打开 R2 公有域名 + "/" + 某个 clip_key，能播放
"""

import os
import sys
from pathlib import Path

try:
    import boto3
    from botocore.config import Config
except ImportError:
    print("❌ 缺少依赖，请先安装：pip install boto3")
    sys.exit(1)

from config import CLIPS_DIR, R2_BUCKET, R2_ENDPOINT, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY


def check_credentials():
    """检查必要的环境变量"""
    missing = []
    if not R2_ENDPOINT:
        missing.append("R2_ENDPOINT")
    if not R2_ACCESS_KEY_ID:
        missing.append("R2_ACCESS_KEY_ID")
    if not R2_SECRET_ACCESS_KEY:
        missing.append("R2_SECRET_ACCESS_KEY")

    if missing:
        print(f"❌ 缺少环境变量：{', '.join(missing)}")
        print("   请在 R2 控制台 → Settings → API Tokens 创建，然后在终端：")
        print("   export R2_ENDPOINT='https://xxx.r2.cloudflarestorage.com'")
        print("   export R2_ACCESS_KEY_ID='your-key-id'")
        print("   export R2_SECRET_ACCESS_KEY='your-secret'")
        sys.exit(1)


def upload_all():
    clips = sorted(CLIPS_DIR.glob("*.mp4"))
    if not clips:
        print(f"❌ 在 {CLIPS_DIR} 里没找到 .mp4 文件")
        print("   请先跑 02_slice_video.py")
        return

    # 创建 R2 客户端（S3 协议）
    s3 = boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
    )

    ok = 0
    fail = 0

    for clip_path in clips:
        clip_key = clip_path.name  # S01E01_124000.mp4
        try:
            s3.upload_file(str(clip_path), R2_BUCKET, clip_key)
            ok += 1
            if ok % 50 == 0:
                print(f"   已上传 {ok} / {len(clips)} ...")
        except Exception as e:
            fail += 1
            print(f"   ⚠️  上传失败 {clip_key}: {e}")

    print(f"\n🎉 uploaded {ok} clips（失败 {fail}）")
    print(f"   桶名：{R2_BUCKET}")


if __name__ == "__main__":
    check_credentials()
    upload_all()
