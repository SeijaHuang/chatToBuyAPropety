import type { CollectedData } from './conversation'
import type { EUserIntent } from './routing'

export interface UserNeeds {
  sessionId:     string
  generatedAt:   string
  schemaVersion: string
  collected:     CollectedData
  initialIntent: EUserIntent
}
