export const MESSAGE_ROLE = {
  USER:      'user',
  ASSISTANT: 'assistant',
} as const

export const MODULE_ID = {
  M1:       'M1_PROPERTY_NEEDS',
  M2:       'M2_LIFESTYLE',
  M3:       'M3_SUBURB_PREFERENCE',
  M4:       'M4_BUDGET',
  COMPLETE: 'COMPLETE',
} as const

export const SESSION_STATUS = {
  IN_PROGRESS:           'IN_PROGRESS',
  REQUIREMENTS_COMPLETE: 'REQUIREMENTS_COMPLETE',
} as const

export const SUBMODEL_KEY = {
  M1: 'm1',
  M2: 'm2',
  M3: 'm3',
  M4: 'm4',
} as const
