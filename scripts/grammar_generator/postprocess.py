import sys
import re

def privatize_anonymous_items(text: str) -> str:
    text = re.sub(r'^(\s+)(item_\d+)\s*:\s*(.*)$',
                  r'\1_\2: InitVar[\3]', text, re.M)
    text = text.replace('from dataclasses import dataclass',
                        'from dataclasses import dataclass, InitVar')
    return text

if __name__ == '__main__':
    for line in sys.stdin:
        print(privatize_anonymous_items(line), end='')
