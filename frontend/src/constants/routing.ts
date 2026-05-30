export const USER_INTENT = {
  RECOMMEND_SUBURBS:  'recommend_suburbs',
  LIST_PROPERTIES:    'list_properties',
  PROPERTY_DETAIL:    'property_detail',
  OPEN_ENDED_QUERY:   'open_ended_query',
  COMPARE_PROPERTIES: 'compare_properties',
} as const

export const EXECUTION_MODE = {
  CODE_DRIVEN:  'code_driven',
  AGENTIC_LOOP: 'agentic_loop',
} as const

export const TRIGGER_SOURCE = {
  AUTO_COMPLETE: 'auto_complete',
  KEYWORD:       'keyword',
  MANUAL:        'manual',
} as const
