"""Task instruction strings for extraction and question-generation prompts."""

EXTRACTION_INSTRUCTION = (
    "Extract only the property requirement fields explicitly stated in the user's message. "
    "Do not infer or guess missing values. Populate only fields that are clearly mentioned."
)

QUESTION_TASK_INSTRUCTION = (
    "Task: Generate exactly ONE short, natural, conversational question targeting the most "
    "important missing required field for the current module. "
    "Do not re-ask fields already collected."
)
SESSION_RESTORE_INSTRUCTION = (
    "Task: The user is returning to a previous conversation. "
    "Write a warm, concise welcome-back message in no more than 3 sentences. "
    "Sentence 1: Naturally acknowledge the user is returning — do NOT use the words 'database', 'cache', 'session', or any technical terms. "
    "Sentence 2: Briefly recap the key requirements already collected in plain language; do not list every field verbatim. "
    "Sentence 3: If the conversation status is IN_PROGRESS, ask the single most natural next question for the current module. "
    "If the conversation status is REQUIREMENTS_COMPLETE, acknowledge completion and offer to review the summary or proceed to property search."
)
