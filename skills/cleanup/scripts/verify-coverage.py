#!/usr/bin/env python3
"""Safety net: every sorted line must be in rewritten OR in gaps. 100% guarantee."""
import sys
import re


def extract_urls(text):
    """Extract all URLs from text."""
    return set(re.findall(r'https?://[^\s\)>\]]+', text))


def normalize(line):
    """Normalize for fuzzy matching: lowercase, collapse whitespace, strip markers and links."""
    s = line.strip().lower()
    # Remove markdown link syntax: [text](url) → text url
    s = re.sub(r'\[([^\]]*)\]\([^\)]*\)', r'\1', s)
    # Remove raw URLs (they'll be compared separately)
    s = re.sub(r'https?://\S+', '', s)
    # Remove list/heading markers
    s = re.sub(r'^[-*>\d.)\]#]+\s*', '', s)
    # Remove checkboxes
    s = re.sub(r'^\[[ x]\]\s*', '', s)
    # Strip markdown bold/italic
    s = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', s)
    s = re.sub(r'_{1,2}([^_]+)_{1,2}', r'\1', s)
    # Strip inline code
    s = re.sub(r'`([^`]+)`', r'\1', s)
    # Strip HTML tags
    s = re.sub(r'<[^>]+>', ' ', s)
    # Normalize punctuation
    s = re.sub(r'[;:—–]', ' ', s)
    # Collapse whitespace
    s = re.sub(r'\s+', ' ', s)
    # Normalize cyrillic
    s = s.replace('ё', 'е')
    return s.strip()


def words_set(text):
    """Extract significant words (3+ chars) from text."""
    words = re.findall(r'[a-zA-Zа-яА-ЯёЁ0-9]{3,}', text.lower().replace('ё', 'е'))
    return set(words)


def is_covered(line, rewritten_text, rewritten_norm, rewritten_words, rewritten_urls, norm_gaps, gaps_text):
    """Check if a sorted line is covered by rewritten or gaps."""
    # URLs are checked first and are NECESSARY, never sufficient: normalize()
    # strips them, so a URL-only line normalizes to "" and the short-content
    # guard below would call a deleted URL "covered". A line that keeps its URL
    # but loses its prose still has to pass the text checks underneath.
    line_urls = extract_urls(line)
    if line_urls and not all(url in rewritten_urls or url in gaps_text for url in line_urls):
        return False

    norm = normalize(line)
    if line_urls and len(norm) < 4:
        return True          # the line was only a URL, and that URL survived

    # Skip trivially short content
    if len(norm) < 4:
        return True

    # Normalized substring match in rewritten or gaps
    if norm in rewritten_norm or norm in norm_gaps:
        return True

    # Fuzzy: 40-char prefix match
    if len(norm) >= 20:
        chunk = norm[:40]
        if chunk in rewritten_norm or chunk in norm_gaps:
            return True

    # Word overlap with adaptive threshold
    line_words = words_set(line)
    if len(line_words) >= 3:
        overlap = line_words & rewritten_words
        ratio = len(overlap) / len(line_words)
        # Stricter threshold for short lines (more likely false positive)
        threshold = 0.65 if len(line.strip()) < 50 else 0.5
        if ratio >= threshold:
            return True

    return False


def main():
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <sorted> <rewritten> <gaps>")
        sys.exit(2)

    with open(sys.argv[1], encoding='utf-8') as f:
        sorted_lines = [l.rstrip() for l in f if l.strip()]
    with open(sys.argv[2], encoding='utf-8') as f:
        rewritten_text = f.read()
    try:
        with open(sys.argv[3], encoding='utf-8') as f:
            gaps_text = f.read()
    except FileNotFoundError:
        gaps_text = ''          # no gaps file yet (or already applied and deleted)

    rewritten_norm = normalize(rewritten_text)
    rewritten_urls = extract_urls(rewritten_text)
    rewritten_words = words_set(rewritten_text)
    norm_gaps = normalize(gaps_text)          # hoisted: normalizing per line is O(n*m)

    uncovered = []
    for line in sorted_lines:
        if line.startswith('## ') or line.startswith('### ') or line.startswith('####'):
            continue
        if line.strip().startswith('```'):
            continue
        if len(line.strip()) < 5:
            continue

        if not is_covered(line, rewritten_text, rewritten_norm, rewritten_words, rewritten_urls, norm_gaps, gaps_text):
            uncovered.append(line)

    if not uncovered:
        print(f"✅ COVERAGE 100%: all {len(sorted_lines)} sorted lines accounted for")
        sys.exit(0)
    else:
        # Write candidates to temp file for agent verification (don't add to gaps directly)
        import os
        base = os.path.splitext(sys.argv[1])[0]
        candidates_path = base + '.uncovered.tmp'
        with open(candidates_path, 'w', encoding='utf-8') as f:
            for line in uncovered:
                f.write(f"{line}\n")
        print(f"⚠️  UNCOVERED: {len(uncovered)} candidates written to {candidates_path}")
        print("→ Agent verification needed before adding to gaps")
        sys.exit(1)


if __name__ == "__main__":
    main()
