import { ChatSession } from '@/components'

interface ChatSessionPageProps {
  params: { sessionId: string }
  searchParams: { q?: string }
}

export default function ChatSessionPage({ params, searchParams }: ChatSessionPageProps) {
  return <ChatSession sessionId={params.sessionId} initialMessage={searchParams.q ?? null} />
}
