import { createTV } from 'tailwind-variants'

/**
 * Custom tv() instance that teaches tailwind-merge about our @theme text-size tokens.
 * Without this, tailwind-merge classifies custom text-* utilities (text-label-lg,
 * text-body-lg, etc.) as color classes and wrongly drops them or drops text-primary.
 */
export const tv = createTV({
  twMergeConfig: {
    extend: {
      classGroups: {
        'font-size': [
          {
            text: [
              'display-lg', 'display-md',
              'headline-lg', 'headline-md',
              'title-lg', 'title-md',
              'body-lg', 'body-md',
              'label-lg', 'label-md',
              'caption',
            ],
          },
        ],
      },
    },
  },
})
