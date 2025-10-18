"""
Web utilities for cleaning UI artifacts from tool outputs.
Scalable: Edit UI_PATTERNS list to handle new patterns.
"""

import re

UI_PATTERNS = [
    r'(?ism)^\s*📖\s*FULL PAGE CONTENT.*?(?=---|$)',
    r'^\s*💭\s*Show reasoning.*',
    r'^\s*🔍\s*Show search details.*',
    r'📚\s*(Hide|Show)\s+sources.*',
    r'^🔥|⭐\s*',  # Relevance badges
    r'^\s*\*\s*\[Showing \d+%.*\]\s*\*\s*$',  # Truncation notes
    r'^\s*---\s*$',  # Separators
]

def clean_ui_artifacts(text: str) -> str:
    """
    Remove common UI artifacts from web tool outputs.
    
    Args:
        text: Raw text from tools (search/read results)
    
    Returns:
        Cleaned text, preserving key content.
    """
    for pattern in UI_PATTERNS:
        text = re.sub(pattern, '', text)
    
    # Normalize whitespace: multiple newlines → double newline
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()