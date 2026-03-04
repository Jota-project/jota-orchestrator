# ---------------------------------------------------------------------------
# Tool call protocol tags
# Must match what get_system_prompt_addition() instructs the model to emit.
# ---------------------------------------------------------------------------
TOOL_CALL_OPEN = "<tool_call>"
TOOL_CALL_CLOSE = "</tool_call>"

# ---------------------------------------------------------------------------
# Response / context text markers
# ---------------------------------------------------------------------------
INTERRUPTED_MARKER = " [INTERRUPTED]"
TOOL_OUTPUT_TRUNCATED_MARKER = "\n...[OUTPUT TRUNCATED]"
CONTEXT_TRUNCATED_MARKER = "\n...[TRUNCATED TO PREVENT CONTEXT SATURATION]"
