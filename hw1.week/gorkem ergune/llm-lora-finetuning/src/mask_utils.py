"""Token-level completion-only masking for Gemma 4's turn/tool format.

Supervise ONLY model-generated tokens: reasoning (<|channel>thought..), tool_calls
(<|tool_call>..), final content, and the model's turn-close (learn to stop).
Mask: system/user turns, the '<|turn>model\\n' role header, and tool_response spans
(<|tool_response>..<tool_response|>) since those are provided by the harness, not
generated. Operates on token ids only -> robust to BPE boundaries (unlike v1's
string-marker masking that silently dropped 93% of data).
"""
TURN_OPEN, TURN_CLOSE = 105, 106
TOOL_RESP_OPEN, TOOL_RESP_CLOSE = 50, 51
ROLE_MODEL, NL = 4368, 107

def build_labels(ids):
    n = len(ids)
    labels = [-100] * n
    in_model = False
    in_tool_resp = False
    i = 0
    while i < n:
        t = ids[i]
        if t == TURN_OPEN:                      # '<|turn>' + role + '\n' = scaffold (mask)
            role = ids[i + 1] if i + 1 < n else None
            in_model = (role == ROLE_MODEL)
            in_tool_resp = False
            j = i + 1
            if j < n and ids[j] in (ROLE_MODEL, 2364, 9731):
                j += 1
            if j < n and ids[j] == NL:
                j += 1
            i = j
            continue
        if t == TURN_CLOSE:                      # supervise the model's own turn-close
            if in_model:
                labels[i] = t
            in_model = False
            in_tool_resp = False
            i += 1
            continue
        if t == TOOL_RESP_OPEN:                  # harness-provided tool output -> mask
            in_tool_resp = True
            i += 1
            continue
        if t == TOOL_RESP_CLOSE:
            in_tool_resp = False
            i += 1
            continue
        if in_model and not in_tool_resp:
            labels[i] = t
        i += 1
    return labels
