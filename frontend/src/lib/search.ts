// 搜索封装：关键词 → Supabase 查询 → 结果列表
import type { Line } from '../types'
import { supabase } from './supabase'

export type LangMode = 'zh' | 'en' | 'both'

/** 从 episode_id 里提取季/集，比如 "SHDBZ S01E01" → { season: 1, episode: 1 } */
function parseEpisodeId(episode_id: string): { season: number; episode: number } {
  const m = episode_id.match(/(\d{2})[Ee](\d{2})/)
  if (m) return { season: parseInt(m[1]), episode: parseInt(m[2]) }
  return { season: 0, episode: 0 }
}

/**
 * 搜索台词
 * @param keyword 关键词（单个词）
 * @param lang 语言模式：只搜中文 / 只搜英文 / 两个都搜
 */
export async function searchLines(
  keyword: string,
  lang: LangMode = 'both'
): Promise<Line[]> {
  const kw = keyword.trim()
  if (!kw) return []

  // 只查 lines 表（不加 join，避免重复 + 简化逻辑）
  let query = supabase.from('lines').select('*')

  // 按语言模式模糊匹配
  const pattern = `%${kw}%`
  if (lang === 'zh') {
    query = query.ilike('text_zh', pattern)
  } else if (lang === 'en') {
    query = query.ilike('text_en', pattern)
  } else {
    // both：用 OR 搜两个字段
    query = query.or(`text_zh.ilike.${pattern},text_en.ilike.${pattern}`)
  }

  query = query.order('id', { ascending: false }).limit(50)

  const { data, error } = await query

  if (error) {
    console.error('搜索失败:', error)
    throw error
  }

  return (data || []).map((row: any) => {
    const { season, episode } = parseEpisodeId(row.episode_id)
    return {
      id: row.id,
      episode_id: row.episode_id,
      seq: row.seq,
      start_ms: row.start_ms,
      end_ms: row.end_ms,
      speaker: row.speaker,
      text_en: row.text_en,
      text_zh: row.text_zh,
      clip_key: row.clip_key,
      clip_duration_ms: row.clip_duration_ms,
      // 直接挂到对象上（不用 _ 前缀了）
      season,
      episode,
    } as Line & { season: number; episode: number }
  })
}
