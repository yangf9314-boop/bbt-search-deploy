// 搜索框：输入框 + 中/英/双语切换 + 防抖 300ms
import { useState, useEffect, useRef } from 'react'
import type { LangMode } from '../lib/search'

interface Props {
  onSearch: (keyword: string, lang: LangMode) => void
  lang: LangMode
  onLangChange: (lang: LangMode) => void
  compact?: boolean  // Hero 内用紧凑样式
}

const DEBOUNCE_MS = 300

export default function SearchBar({ onSearch, lang, onLangChange, compact }: Props) {
  const [input, setInput] = useState('')
  const timerRef = useRef<number | null>(null)

  useEffect(() => {
    return () => {
      if (timerRef.current) window.clearTimeout(timerRef.current)
    }
  }, [])

  const trigger = (value: string) => {
    if (timerRef.current) window.clearTimeout(timerRef.current)
    if (!value.trim()) return
    timerRef.current = window.setTimeout(() => {
      onSearch(value.trim(), lang)
    }, DEBOUNCE_MS)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      if (timerRef.current) window.clearTimeout(timerRef.current)
      if (input.trim()) onSearch(input.trim(), lang)
    }
  }

  const handleLangClick = (l: LangMode) => {
    onLangChange(l)
    if (input.trim()) {
      if (timerRef.current) window.clearTimeout(timerRef.current)
      onSearch(input.trim(), l)
    }
  }

  const langs: { key: LangMode; label: string }[] = [
    { key: 'both', label: '双语' },
    { key: 'zh', label: '中文' },
    { key: 'en', label: '英文' },
  ]

  return (
    <div className={`search-bar ${compact ? 'compact' : ''}`}>
      <div className="search-input-row">
        <input
          type="text"
          className="search-input"
          placeholder="搜一句台词，试试 love / Sheldon / 牛排"
          value={input}
          onChange={(e) => {
            setInput(e.target.value)
            trigger(e.target.value)
          }}
          onKeyDown={handleKeyDown}
          autoFocus
        />
        <button
          className="search-btn"
          onClick={() => input.trim() && onSearch(input.trim(), lang)}
        >
          搜索
        </button>
      </div>

      <div className="lang-switch">
        {langs.map(({ key, label }) => (
          <button
            key={key}
            className={`lang-btn ${lang === key ? 'active' : ''}`}
            onClick={() => handleLangClick(key)}
          >
            {label}
          </button>
        ))}
      </div>
    </div>
  )
}
