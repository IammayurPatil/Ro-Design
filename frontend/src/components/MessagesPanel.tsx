import clsx from 'clsx'
import type { Message } from '../types'
import { Card } from './ui'

export function MessagesPanel({ messages, title = 'Messages', showPage = false }: { messages: Message[]; title?: string; showPage?: boolean }) {
  return (
    <Card title={title}>
      {messages.length === 0 ? (
        <p className="text-sm text-muted">No messages.</p>
      ) : (
        <ul className="space-y-1.5 text-sm" aria-live="polite">
          {messages.map((m, i) => (
            <li
              key={i}
              className={clsx('flex gap-2', m.level === 'info' ? 'text-muted' : 'font-medium text-danger')}
            >
              <span aria-hidden>{m.level === 'info' ? 'ℹ' : '⚠'}</span>
              <span>
                {showPage && m.page && <span className="mr-1 text-muted">[{m.page}]</span>}
                {m.text}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
