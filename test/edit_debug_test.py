# Inline the function to test independently
def _build_edit_match_debug(content, target):
    _TARGET_REPR_MAX = 500
    _PROBE_LEN = 40
    _PROBE_MIN = 5
    _CTX_MARGIN = 40
    _CTX_TAIL = 80

    parts = []
    target_repr = repr(target[:_TARGET_REPR_MAX])
    parts.append(f'target(repr)={target_repr}')
    probe = target[:_PROBE_LEN].strip()
    if len(probe) >= _PROBE_MIN:
        idx = content.find(probe)
        if idx >= 0:
            ctx_start = max(0, idx - _CTX_MARGIN)
            ctx_end = min(len(content), idx + len(probe) + _CTX_TAIL)
            context = content[ctx_start:ctx_end]
            parts.append(f'closest_partial_offset={idx}')
            parts.append(f'context(repr)={repr(context)}')
        else:
            parts.append(f'no_partial_match_for_first_{_PROBE_LEN}_chars')
    if '\r' in target:
        parts.append('WARNING: target contains CR(\\r) chars, but file was read with universal newlines')
    parts.append(f'content_len={len(content)} target_len={len(target)}')
    return ' | '.join(parts)


print('=' * 70)
print('TEST 1: old_string uses real newline, file has literal \\n + real newline')
print('=' * 70)
content1 = 'Shanghai Jiao Tong University, SMIL Lab\\n' + '\n' + 'Author: Yu Huang'
target1 = 'Shanghai Jiao Tong University, SMIL Lab' + '\n' + 'Author: Yu Huang'
print('content (repr):', repr(content1))
print('target  (repr):', repr(target1))
print('result:', _build_edit_match_debug(content1, target1))
print()

print('=' * 70)
print('TEST 2: old_string contains \\r\\n, file uses \\n only')
print('=' * 70)
content2 = 'line1\nline2\nline3\n'
target2 = 'line1\r\nline2'
print('result:', _build_edit_match_debug(content2, target2))
print()

print('=' * 70)
print('TEST 3: old_string not found in file at all')
print('=' * 70)
content3 = 'This is a normal file content with nothing special.'
target3 = 'FIND_ME_PLEASE'
print('result:', _build_edit_match_debug(content3, target3))
print()

print('=' * 70)
print('TEST 4: content too short, target too long')
print('=' * 70)
content4 = 'short'
target4 = 'This is a very long target string that is much longer than the content itself'
print('result:', _build_edit_match_debug(content4, target4))
print()

print('=' * 70)
print('TEST 5: target exceeds 500 chars, verify _TARGET_REPR_MAX truncation')
print('=' * 70)
content5 = 'Hello World ' * 100
target5 = 'Hello' + 'X' * 600
print('result:', _build_edit_match_debug(content5, target5))
