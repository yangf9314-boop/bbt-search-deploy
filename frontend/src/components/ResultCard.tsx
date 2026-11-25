// 结果卡：缩略图 + 台词 + 播放/分享按钮
import type { Line } from '../types'

interface Props {
  line: Line
  keyword?: string
  onPlay?: (line: Line) => void
}

/** 把文本里命中的关键词高亮出来（黄色底） */
function highlight(text: string, keyword?: string) {
  if (!keyword || !text) return text
  const regex = new RegExp(
    `(${keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`,
    'gi'
  )
  const parts = text.split(regex)
  return parts.map((part, i) =>
    regex.test(part) ? (
      <mark key={i} className="highlight">
        {part}
      </mark>
    ) : (
      part
    )
  )
}

/** 毫秒 → "00:12:30" 格式 */
function msToClock(ms: number) {
  const totalSec = Math.floor(ms / 1000)
  const h = Math.floor(totalSec / 3600)
  const m = Math.floor((totalSec % 3600) / 60)
  const s = totalSec % 60
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(h)}:${pad(m)}:${pad(s)}`
}

/** 缩略图地址 */
function buildThumbSrc(clipKey: string): string {
  const r2Base = import.meta.env.VITE_R2_PUBLIC_BASE as string | undefined
  const jpg = clipKey.replace(/\.mp4$/, '.jpg')
  if (r2Base) {
    return `${r2Base.replace(/\/$/, '')}/thumbs/${jpg}`
  }
  return `/thumbs/${jpg}`
}

export default function ResultCard({ line, keyword, onPlay }: Props) {
  const anyLine = line as any
  const season = anyLine.season
  const episode = anyLine.episode

  const handlePlay = () => {
    if (onPlay) onPlay(line)
    else console.log('[播放] clip_key =', line.clip_key)
  }

  const handleShare = async () => {
    const url = `${window.location.origin}/?id=${line.id}`
    try {
      await navigator.clipboard.writeText(url)
      alert('已复制链接，粘贴给朋友就能看到这条台词 ✨')
    } catch {
      const ta = document.createElement('textarea')
      ta.value = url
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
      alert(`链接已复制：${url}`)
    }
  }

  const thumbSrc = buildThumbSrc(line.clip_key)

  return (
    <div className="result-card">
      <div className="result-thumb-wrap" onClick={handlePlay}>
        <img
          className="result-thumb"
          src={thumbSrc}
          alt=""
          loading="lazy"
          onError={(e) => {
            // 缩略图不存在时隐藏
            (e.currentTarget as HTMLImageElement).style.display = 'none'
          }}
        />
        <div className="result-thumb-play">▶</div>
      </div>

      <div className="result-body">
        <div className="result-meta">
          <span className="speaker">👤 {line.speaker || '未知'}</span>
          <span className="episode">
            S{season !== undefined ? String(season).padStart(2, '0') : '??'}
            E{episode !== undefined ? String(episode).padStart(2, '0') : '??'}
          </span>
          <span className="time">{msToClock(line.start_ms)}</span>
        </div>

        <div className="result-text text-en">{highlight(line.text_en, keyword)}</div>
        <div className="result-text text-zh">{highlight(line.text_zh, keyword)}</div>

        <div className="result-actions">
          <button className="btn-play" onClick={handlePlay}>▶ 播放</button>
          <button className="btn-share" onClick={handleShare}>🔗 分享</button>
        </div>
      </div>
    </div>
  )
}
