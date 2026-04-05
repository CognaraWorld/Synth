'use client'

import { type ReactNode } from 'react'
import { motion } from 'framer-motion'

interface MeetingWindowProps {
  title?: string
  recording?: boolean
  children: ReactNode
  className?: string
  status?: string
}

export function MeetingWindow({
  title = 'Team Standup',
  recording = true,
  children,
  className = '',
  status,
}: MeetingWindowProps) {
  return (
    <div
      className={`w-full rounded-2xl border border-[#EAE8E4] bg-white shadow-xl shadow-[rgba(26,21,15,0.08)] overflow-hidden ${className}`}
    >
      {/* Title bar */}
      <div className="flex items-center justify-between px-5 md:px-6 py-3.5 border-b border-[#EAE8E4] bg-[#FAF9F6]">
        <div className="flex items-center gap-3">
          <div className="flex gap-[7px]">
            <div className="w-3 h-3 rounded-full bg-[#ff5f57]" />
            <div className="w-3 h-3 rounded-full bg-[#febc2e]" />
            <div className="w-3 h-3 rounded-full bg-[#28c840]" />
          </div>
          <span className="text-base text-[#6E6E73] font-medium">{title}</span>
        </div>
        {recording && (
          <div className="flex items-center gap-1.5">
            <motion.div
              className="w-2 h-2 rounded-full bg-red-500"
              animate={{ opacity: [1, 0.3, 1] }}
              transition={{ duration: 1.5, repeat: Infinity }}
            />
            <span className="text-sm text-red-500/80 font-medium">REC</span>
          </div>
        )}
      </div>

      {/* Content */}
      <div className="p-6 md:p-8 bg-white">{children}</div>

      {/* Status bar */}
      {status && (
        <div className="px-5 md:px-6 py-3.5 border-t border-[#EAE8E4] bg-[#FAF9F6]">
          <div className="flex items-center gap-2">
            <motion.div
              className="w-2 h-2 rounded-full bg-warm-amber"
              animate={{ opacity: [1, 0.4, 1] }}
              transition={{ duration: 1, repeat: Infinity }}
            />
            <span className="text-sm text-[#6E6E73] font-medium">{status}</span>
          </div>
        </div>
      )}
    </div>
  )
}

/* ── Participant Avatar ── */

interface ParticipantProps {
  name: string
  initials: string
  color: string
  speaking?: boolean
  ai?: boolean
  status?: string
}

export function Participant({
  name,
  initials,
  color,
  speaking = false,
  ai = false,
  status,
}: ParticipantProps) {
  return (
    <div className="flex flex-col items-center gap-2.5 min-w-[80px]">
      <div className="relative">
        <motion.div
          className="w-16 h-16 md:w-20 md:h-20 rounded-full flex items-center justify-center text-lg md:text-xl font-bold"
          style={{
            backgroundColor: color + '18',
            color: color,
            boxShadow: speaking ? `0 0 24px ${color}40` : 'none',
          }}
          animate={speaking ? { scale: [1, 1.05, 1] } : {}}
          transition={speaking ? { duration: 1.5, repeat: Infinity } : {}}
        >
          {ai ? (
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 8V4H8" /><rect width="16" height="12" x="4" y="8" rx="2" /><path d="m2 14 6-6" /><path d="m22 14-6-6" />
            </svg>
          ) : (
            initials
          )}
        </motion.div>
        {speaking && (
          <motion.div
            className="absolute -bottom-0.5 -right-0.5 w-4 h-4 rounded-full border-2 border-white"
            style={{ backgroundColor: color }}
            animate={{ scale: [1, 1.2, 1] }}
            transition={{ duration: 0.8, repeat: Infinity }}
          />
        )}
      </div>
      <span className="text-sm text-[#6E6E73] font-medium">{name}</span>
      {status && (
        <span className="text-xs text-[#86868B]">{status}</span>
      )}
    </div>
  )
}

/* ── Chat Bubble ── */

interface ChatBubbleProps {
  name: string
  color: string
  message: string
  ai?: boolean
}

export function ChatBubble({ name, color, message, ai = false }: ChatBubbleProps) {
  return (
    <div className="flex gap-3 items-start">
      <div
        className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5"
        style={{ backgroundColor: color + '12', color }}
      >
        {ai ? 'C' : name[0]}
      </div>
      <div>
        <span className="text-sm font-semibold" style={{ color }}>
          {name}
        </span>
        <p className="text-base leading-relaxed mt-0.5 text-[#424245]">
          {message}
        </p>
      </div>
    </div>
  )
}
