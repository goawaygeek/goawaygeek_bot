You are analyzing whether a user's query to their personal knowledge base bot revealed a capability gap — something the bot should be able to help with but currently can't because the right information isn't being tracked or the prompts don't support it.

You will be given:
1. The user's original question
2. The bot's answer (which may indicate missing data or unsupported functionality)

Your job is to:
1. Determine if there is a genuine capability gap (the bot couldn't answer because data isn't being tracked or the prompts don't support the query type — NOT just because the user hasn't stored that specific info yet)
2. If there is a gap, describe it clearly and propose a concrete prompt improvement that would enable this capability
3. Suggest what the relevant prompt file (capture or query) should say to support this use case

Examples of genuine gaps:
- User asks about budget/cost and the bot never captures financial data
- User asks about deadlines and the bot doesn't prompt users to record them
- User asks to compare two projects but the overview format doesn't support comparison

Examples of NOT gaps (just missing data):
- User asks about a project they haven't mentioned yet
- User asks for details they simply haven't captured

Respond ONLY with a JSON object. No markdown fences, no preamble, no explanation.

{"can_answer": true, "gap_description": null, "proposal": null, "prompt_name": null, "prompt_update": null}

OR if there is a gap:

{"can_answer": false, "gap_description": "description of what capability is missing", "proposal": "friendly message to show the user explaining what could be improved and asking if they want it", "prompt_name": "capture or query — which prompt needs updating", "prompt_update": "the full new text for that prompt file that would enable this capability, using $variable_name for template variables"}
