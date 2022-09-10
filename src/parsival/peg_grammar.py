from __future__ import annotations
from typing import Literal, Annotated, Union, Optional
from dataclasses import dataclass
from parsival import Commit
from parsival.helper_rules import *

@dataclass
class Start:
    item_1: Grammar
    item_2: ENDMARKER

@dataclass
class Grammar:
    metas: list[MetaTuple]
    rules: Annotated[list[Rule], "+"]

@dataclass
class MetaTuple:
    item_1: Literal['@']
    meta_name: NAME
    meta_value: Union[NAME, STRING, None]
    item_4: NEWLINE

@dataclass
class Rule_1:
    rulename: RuleName
    item_2: Literal[':']
    alts: Alts
    item_4: NEWLINE
    item_5: INDENT
    more_alts: MoreAlts
    item_7: DEDENT

@dataclass
class Rule_2:
    rulename: RuleName
    item_2: Literal[':']
    alts: None
    item_4: NEWLINE
    item_5: INDENT
    more_alts: MoreAlts
    item_7: DEDENT

@dataclass
class Rule_3:
    rulename: RuleName
    item_2: Literal[':']
    alts: Alts
    item_4: NEWLINE
    more_alts: None

Rule = Union[Rule_1, Rule_2, Rule_3]

@dataclass
class Type:
    item_1: Literal['[']
    type: NAME
    pointer: Optional[Literal['*']]
    item_4: Literal[']']

@dataclass
class RuleName:
    name: NAME
    type: Optional[Type]

@dataclass
class Alts:
    alts: Annotated[list[Alt], "+", Literal['|']]

@dataclass
class MoreAlts:
    item_1: Literal['|']
    alts: Alts
    item_3: NEWLINE
    more_alts: Optional[MoreAlts]

@dataclass
class Alt:
    items: Annotated[list[NamedItem], "+", NO_LF_SPACE]
    ending: Optional[Literal['$']]

@dataclass
class NamedItem_1:
    name: NAME
    item_2: Literal['=']
    item_3: Commit
    item: Item

@dataclass
class NamedItem_2:
    item: Item

@dataclass
class NamedItem_3:
    item: LookaheadOrCut

NamedItem = Union[NamedItem_1, NamedItem_2, NamedItem_3]

@dataclass
class LookaheadOrCut_1:
    type: Literal['&']
    item_2: Commit
    atom: Plain

@dataclass
class LookaheadOrCut_2:
    type: Literal['!']
    item_2: Commit
    atom: Plain

@dataclass
class LookaheadOrCut_3:
    type: Literal['~']

LookaheadOrCut = Union[LookaheadOrCut_1, LookaheadOrCut_2, LookaheadOrCut_3]

@dataclass
class Item_1:
    node: BracketOpt

@dataclass
class Item_2:
    node: Quantifier

@dataclass
class Item_3:
    node: SeparatedQuantifier

@dataclass
class Item_4:
    node: Plain

Item = Union[Item_1, Item_2, Item_3, Item_4]

@dataclass
class BracketOpt:
    item_1: Literal['[']
    item_2: Commit
    alts: Alts
    item_4: Literal[']']

@dataclass
class Quantifier:
    node: Plain
    quantifier: Union[Literal['?'], Literal['*'], Literal['+']]

@dataclass
class SeparatedQuantifier:
    sep: Plain
    item_2: Literal['.']
    node: Plain
    item_4: Literal['+']

@dataclass
class Plain_1:
    atom: Grouped

@dataclass
class Plain_2:
    atom: RegexLiteral

@dataclass
class Plain_3:
    atom: NAME

@dataclass
class Plain_4:
    atom: STRING

Plain = Union[Plain_1, Plain_2, Plain_3, Plain_4]

@dataclass
class Grouped:
    item_1: Literal['(']
    item_2: Commit
    alts: Alts
    item_4: Literal[')']

@dataclass
class RegexLiteral:
    item_1: Literal['r']
    item_2: NO_SPACE
    pattern: STRING

if __name__ == '__main__':
    import sys
    import parsival

    text = sys.stdin.read()

    try:
        from prettyprinter import pprint, install_extras
    except ImportError:
        from pprint import pprint
    else:
        install_extras(include=frozenset({'dataclasses'}))

    try:
        parsival.DEBUG = '--debug' in sys.argv
        pprint(parsival.parse(text, Start))
    except (SyntaxError, parsival.Failed) as exc:
        print('Failed:', str(exc)[:50], file=sys.stderr)
