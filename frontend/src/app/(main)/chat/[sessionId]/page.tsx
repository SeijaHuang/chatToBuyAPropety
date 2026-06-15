import { ChatSession } from '@/components'

interface ChatSessionPageProps {
  params: { sessionId: string }
}

export default function ChatSessionPage({ params }: ChatSessionPageProps) {
  return <ChatSession sessionId={params.sessionId} />
}
