// 播放器弹层：短切片 + 字幕随播放位置动态切换
import { useEffect, useRef, useState } from 'react'
import type { Line } from '../types'
import { supabase } from '../lib/supabase'

interface Props {
  line: Line
  onClose: () => void
}

function buildVideoSrc(clipKey: string): string {
  const r2Base = import.meta.env.VITE_R2_PUBLIC_BASE as string | undefined
  if (r2Base) return `${r2Base.replace(/\/$/, '')}/${clipKey}`
  return `/clips/${clipKey}`
}

function buildThumbSrc(clipKey: string): string {
  const r2Base = import.meta.env.VITE_R2_PUBLIC_BASE as string | undefined
  const jpg = clipKey.replace(/\.mp4$/, '.jpg')
  if (r2Base) return `${r2Base.replace(/\/$/, '')}/thumbs/${jpg}`
  return `/thumbs/${jpg}`
}

export default function ClipPlayer({ line, onClose }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [subLang, setSubLang] = useState<'zh' | 'en'>('zh')
  const [overlay, setOverlay] = useState(true)
  const [episodeLines, setEpisodeLines] = useState<Line[] | null>(null)
  const [activeSub, setActiveSub] = useState<Line>(line)
  const activeSubRef = useRef<Line>(line)  // ← 用 ref 避免重挂 listener

  // clip 在全集里的绝对起点（毫秒）— 和 02_slice_video.py 一致
  const CLIP_PRE_MS = 1000
  const clipAbsStartMs = line.start_ms - CLIP_PRE_MS

  // activeSub 变化时同步到 ref
  useEffect(() => { activeSubRef.current = activeSub }, [activeSub])

  // 1. 加载同集全部台词
  useEffect(() => {
    let cancelled = false
    const loadLines = async () => {
      console.log('[ClipPlayer] fetching episode lines for:', line.episode_id)
      const { data, error } = await supabase
        .from('lines')
        .select('*')
        .eq('episode_id', line.episode_id)
        .order('seq', { ascending: true })
      if (!cancelled) {
        if (error) {
          console.error('[ClipPlayer] fetch error:', error)
        } else {
          const linesArr = (data as Line[]) || []
          console.log('[ClipPlayer] loaded', linesArr.length, 'lines')
          setEpisodeLines(linesArr)
          // 加载完立即用当前视频位置同步一次
          requestAnimationFrame(() => {
            const v = videoRef.current
            if (!v || linesArr.length === 0) return
            const absMs = v.currentTime * 1000 + clipAbsStartMs
            const match = linesArr.find(
              (l) => absMs >= l.start_ms - 300 && absMs <= l.end_ms + 300
            )
            console.log('[ClipPlayer] 初始同步: video.t=', v.currentTime.toFixed(2), '→ match seq=', match?.seq ?? 'NONE')
            if (match) setActiveSub(match)
          })
        }
      }
    }
    loadLines()
    return () => { cancelled = true }
  }, [line.episode_id, clipAbsStartMs])

  // 2. timeupdate → 持续更新 activeSub（用 ref 拿最新 activeSub，不进依赖！）
  useEffect(() => {
    const v = videoRef.current
    if (!v) return

    const handleTime = () => {
      const lines = episodeLines
      if (!lines || lines.length === 0) return
      const absMs = v.currentTime * 1000 + clipAbsStartMs
      const match = lines.find(
        (l) => absMs >= l.start_ms - 300 && absMs <= l.end_ms + 300
      )
      if (match && match.id !== activeSubRef.current.id) {
        console.log('[timeupdate] → seq=', match.seq, match.text_en?.substring(0, 60))
        setActiveSub(match)
      }
    }

    // 挂载时立即触发一次（不等浏览器 timeupdate）
    handleTime()
    v.addEventListener('timeupdate', handleTime)
    return () => v.removeEventListener('timeupdate', handleTime)
  }, [episodeLines, clipAbsStartMs])  // ← activeSub.id 不再是依赖！

  // 3. ESC + body 锁定
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handleKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', handleKey)
      document.body.style.overflow = prev
    }
  }, [onClose])

  // 4. 前后对话链（下方模式展示）
  const contextLines = (() => {
    if (!episodeLines) return [line]
    const idx = episodeLines.findIndex((l) => l.id === line.id)
    if (idx < 0) return [line]
    return episodeLines.slice(Math.max(0, idx - 2), Math.min(episodeLines.length, idx + 3))
  })()

  const renderSub = (l: Line) =>
    l[subLang === 'zh' ? 'text_zh' : 'text_en'] ||
    (subLang === 'zh' ? l.text_en : l.text_zh)

  const src = buildVideoSrc(line.clip_key)
  const thumbSrc = buildThumbSrc(line.clip_key)

  return (
    <div className="player-overlay" onClick={onClose}>
      <div className="player-modal" onClick={(e) => e.stopPropagation()}>
        <button className="player-close" onClick={onClose}>✕</button>

        <div className="player-video-wrap">
          <video
            ref={videoRef}
            className="player-video"
            src={src}
            poster={thumbSrc}
            autoPlay
            controls
            playsInline
            onClick={(e) => e.stopPropagation()}
          />
          {overlay && (
            <div className="player-sub-overlay">
              <div className="player-sub-overlay-text">{renderSub(activeSub)}</div>
            </div>
          )}
        </div>

        <div className="player-controls">
          <div className="player-subtitle-toggle">
            <button className={`toggle-btn ${subLang === 'zh' ? 'active' : ''}`} onClick={() => setSubLang('zh')}>中</button>
            <button className={`toggle-btn ${subLang === 'en' ? 'active' : ''}`} onClick={() => setSubLang('en')}>EN</button>
            <button className={`toggle-btn ${overlay ? 'active' : ''}`} onClick={() => setOverlay((o) => !o)}>
              {overlay ? '画面内' : '下方'}
            </button>
          </div>

          {!overlay && (
            <div className="player-context">
              {contextLines.map((ctx) => {
                const isCurrent = activeSub.id === ctx.id
                return (
                  <div key={ctx.id} className={`player-ctx-line ${isCurrent ? 'current' : ''}`}>
                    <span className="player-ctx-speaker">{ctx.speaker || '未知'}</span>
                    <span className="player-ctx-text">{renderSub(ctx)}</span>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
