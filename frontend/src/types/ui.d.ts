import { COMPONENT_SIZE, COMPONENT_VARIANT, COMPONENT_COLOR } from '../constants/ui'

export type ComponentSize    = typeof COMPONENT_SIZE[keyof typeof COMPONENT_SIZE]
export type ComponentVariant = typeof COMPONENT_VARIANT[keyof typeof COMPONENT_VARIANT]
export type ComponentColor   = typeof COMPONENT_COLOR[keyof typeof COMPONENT_COLOR]
