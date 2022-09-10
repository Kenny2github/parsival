import sys
import re
from typing import TextIO

def privatize_anonymous_items(text: str) -> str:
    text = re.sub(r'^(\s+)(item_\d+)\s*:\s*(.*)$',
                  r'\1_\2: InitVar[\3]', text, re.M)
    text = text.replace('from dataclasses import dataclass',
                        'from dataclasses import dataclass, InitVar')
    return text

def main(file: TextIO) -> str:
    lines: list[str] = []
    for line in file:
        lines.append(privatize_anonymous_items(line))
    return ''.join(lines)

if __name__ == '__main__':
    print(main(sys.stdin))
