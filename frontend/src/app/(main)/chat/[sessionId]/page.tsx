interface ChatSessionPageProps {
  params: { sessionId: string }
}

export default function ChatSessionPage({ params }: ChatSessionPageProps) {
  return <div>{params.sessionId}</div>
}
