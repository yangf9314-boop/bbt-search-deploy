// 首页：Hero 大图 + Featured Clips 栅格 + 搜索 + 结果
import { useState, useEffect } from 'react'
import SearchBar from '../components/SearchBar'
import ResultCard from '../components/ResultCard'
import ClipPlayer from '../components/ClipPlayer'
import { searchLines, type LangMode } from '../lib/search'
import type { Line } from '../types'
import { supabase } from '../lib/supabase'

// 精选台词（id 对应 Supabase lines 表，clip_key 决定缩略图）
const FEATURED_IDS = [
  2216, 2222, 2223, 2226, 2213, 2091,
]

// 和 ClipPlayer/ResultCard 保持一致的 R2 公网地址拼接
function buildR2PublicUrl(key: string): string {
  const r2Base = import.meta.env.VITE_R2_PUBLIC_BASE as string | undefined
  if (r2Base) return `${r2Base.replace(/\/$/, '')}/${key}`
  return `/${key}`
}

function buildThumbSrc(clipKey: string): string {
  return buildR2PublicUrl(`thumbs/${clipKey.replace('.mp4', '.jpg')}`)
}

// Hero 背景固定用一张 clip 的缩略图（R2 thumbs/ 里有）
const HERO_CLIP_KEY = 'SHDBZ S01E01_924140.mp4'

export default function SearchPage() {
  const [keyword, setKeyword] = useState('')
  const [lang, setLang] = useState<LangMode>('both')
  const [results, setResults] = useState<Line[]>([])
  const [loading, setLoading] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)
  const [playing, setPlaying] = useState<Line | null>(null)
  const [featured, setFeatured] = useState<Line[]>([])

  // 首屏加载精选台词
  useEffect(() => {
    supabase
      .from('lines')
      .select('*')
      .in('id', FEATURED_IDS)
      .then(({ data }) => setFeatured((data as Line[]) || []))
  }, [])

  const handleSearch = async (kw: string, l: LangMode) => {
    setKeyword(kw)
    setLang(l)
    setLoading(true)
    setHasSearched(true)
    try {
      const list = await searchLines(kw, l)
      setResults(list)
    } catch (e) {
      console.error(e)
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="search-page">
      {/* ===== Hero ===== */}
      <section className="hero" style={{ backgroundImage: `url(${buildThumbSrc(HERO_CLIP_KEY)})` }}>
        <div className="hero-mask" />
        <div className="hero-content">
          <h1 className="hero-title">生活大爆炸 · 台词检索</h1>
          <p className="hero-subtitle">
            搜一句台词，点一下，Sheldon 和 Penny 立刻在你耳边说出来。
          </p>
          <SearchBar onSearch={handleSearch} lang={lang} onLangChange={setLang} compact />
          <div className="hero-suggestions">
            试试：
            <button onClick={() => handleSearch('love', lang)}>love</button>
            <button onClick={() => handleSearch('Sheldon', lang)}>Sheldon</button>
            <button onClick={() => handleSearch('牛排', lang)}>牛排</button>
          </div>
        </div>
      </section>

      {/* ===== 搜索结果 ===== */}
      {hasSearched && (
        <section className="result-section">
          {loading && <div className="loading">搜索中...</div>}
          {!loading && results.length === 0 && (
            <div className="empty">没找到，换个词试试？</div>
          )}
          {!loading && results.length > 0 && (
            <>
              <div className="result-count">找到 {results.length} 条</div>
              <div className="result-list">
                {results.map((line) => (
                  <ResultCard key={line.id} line={line} keyword={keyword} onPlay={setPlaying} />
                ))}
              </div>
            </>
          )}
        </section>
      )}

      {/* ===== Featured Clips ===== */}
      {!hasSearched && featured.length > 0 && (
        <section className="featured-section">
          <div className="section-header">
            <h2>经典片段</h2>
            <span className="section-desc">点任意一张直接开演</span>
          </div>
          <div className="featured-grid">
            {featured.map((line) => (
              <div
                key={line.id}
                className="featured-card"
                onClick={() => setPlaying(line)}
              >
                <img
                  className="featured-img"
                  src={buildThumbSrc(line.clip_key)}
                  alt=""
                  loading="lazy"
                />
                <div className="featured-overlay">
                  <div className="featured-text">{line.text_en}</div>
                  {line.text_zh && (
                    <div className="featured-text-zh">{line.text_zh}</div>
                  )}
                  <div className="featured-play">▶</div>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {playing && <ClipPlayer line={playing} onClose={() => setPlaying(null)} />}
    </div>
  )
}
