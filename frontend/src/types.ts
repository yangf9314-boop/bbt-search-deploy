// ============================================
//  全局类型定义
//  数据来源：supabase/migrations/0001_init.sql
//  所有模块的字段都以这里为准
// ============================================

/** 剧集：一集一条（比如 S01E01） */
export interface Episode {
  id: string;              // 编号，形如 "S01E01"
  season: number;          // 第几季
  episode: number;         // 第几集
  title_en: string | null; // 英文剧名（可选）
  title_zh: string | null; // 中文剧名（可选）
  created_at: string;      // 创建时间（ISO 8601）
}

/** 台词：项目核心单元，可搜索、可播放、可分享 */
export interface Line {
  id: number;                        // 自增编号（分享链接 ?id=xxx 用这个）
  episode_id: string;                // 属于哪集，如 "S01E01"
  seq: number;                       // 在剧集中的顺序号
  start_ms: number;                   // 片段起点（毫秒）
  end_ms: number;                     // 片段终点（毫秒）
  speaker: string | null;             // 说话人，如 "Sheldon"（可能为空）
  text_en: string;                    // 英文字幕（可被搜）
  text_zh: string;                    // 中文字幕（可被搜）
  clip_key: string;                   // R2 上的文件名，如 "S01E01_124000.mp4"
  clip_duration_ms: number | null;    // 片段总时长（毫秒，播放器显示用）
}
