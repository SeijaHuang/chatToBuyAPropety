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
