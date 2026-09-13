#!/usr/bin/env python3
"""Deterministic gap detection: check all URLs from source exist in target (with normalization)."""
import sys
import re
from urllib.parse import unquote


def normalize_url(url):
    """Normalize URL for comparison: strip tracking params, decode encoding, strip trailing punct."""
    # Strip trailing punctuation that's not part of URLs
    url = url.rstrip('/)>].,;:!?\'"')

    # Recursive percent-decoding (handles %25xx double/triple encoding)
    prev = None
    while prev != url:
        prev = url
        url = unquote(url)

    # Strip common tracking parameters
    tracking_params = {'si', 'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content'}
    if '?' in url:
        base, query = url.split('?', 1)
        params = query.split('&')
        filtered = [p for p in params if p.split('=')[0] not in tracking_params]
        url = base + ('?' + '&'.join(filtered) if filtered else '')

    # Strip trailing slash
    url = url.rstrip('/')

    return url


def extract_urls(filepath):
    with open(filepath, encoding='utf-8') as f:
        text = f.read()
    raw = set(re.findall(r'https?://[^\s\)>\]]+', text))
    return {normalize_url(u) for u in raw}


def extract_urls_raw(filepath):
    """Extract raw URLs for reporting."""
    with open(filepath, encoding='utf-8') as f:
        text = f.read()
    return set(re.findall(r'https?://[^\s\)>\]]+', text))


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <source> <target>")
        sys.exit(2)
    src_urls = extract_urls(sys.argv[1])
    dst_urls = extract_urls(sys.argv[2])
    missing = src_urls - dst_urls
    if not missing:
        print(f"✅ All {len(src_urls)} URLs present in target")
        sys.exit(0)
    else:
        print(f"❌ URLS missing from target ({len(missing)}):")
        for url in sorted(missing):
            print(f"  - {url[:150]}")
        sys.exit(1)


if __name__ == "__main__":
    main()
