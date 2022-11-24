import sys
import re
from typing import TextIO, Match

def privatize_anonymous_items(text: str) -> str:
    text = re.sub(r'^(\s+)(item_\d+)\s*:\s*(.*)$',
                  r'\1_\2: InitVar[\3]', text, re.M)
    text = text.replace('from dataclasses import dataclass',
                        'from dataclasses import dataclass, InitVar')
    return text

def union_of_literals_to_literal(match: Match) -> str:
    # Union[Literal, ...] -> Literal[...]
    text = match.group(0)
    text = re.sub(r"Literal\s*\[([^\]]+)\]", r"\1", text)
    text = text.replace('Union', 'Literal', 1)
    return text

def unions_of_literals_to_literals(text: str) -> str:
    # note: the [^\]]+ should work because
    # subscription is illegal in Literals
    text = re.sub(r"Union\s*\[\s*(?:Literal\s*\[[^\]]+\]\s*,\s*)+"
                  r"Literal\s*\[[^\]]+\]\s*\]",
                  union_of_literals_to_literal, text)
    return text

def main(file: TextIO) -> str:
    lines: list[str] = []
    for line in file:
        line = unions_of_literals_to_literals(line)
        line = privatize_anonymous_items(line)
        lines.append(line)
    return ''.join(lines)

if __name__ == '__main__':
    print(main(sys.stdin))
