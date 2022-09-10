from __future__ import annotations
from typing import Literal, Annotated, Union, Optional
from dataclasses import dataclass, InitVar
from parsival import Commit
from parsival.helper_rules import *

class CustomIndent(Indent):

    @classmethod
    def indent(cls) -> parsival.Rule:
        return SpaceOrTabIndent.indent()

@dataclass
class RegexLiteral:
    _item_1: InitVar[Literal['r']]
    _item_2: InitVar[NO_SPACE]
    pattern: STRING

@dataclass
class Grouped:
    _item_1: InitVar[Literal['(']]
    _item_2: InitVar[Commit]
    alts: Alts
    _item_4: InitVar[Literal[')']]

Plain = Union[Grouped, RegexLiteral, NAME, STRING]

@dataclass
class SeparatedQuantifier:
    sep: Plain
    _item_2: InitVar[Literal['.']]
    node: Plain
    _item_4: InitVar[Literal['+']]

@dataclass
class Quantifier:
    node: Plain
    quantifier: Union[Literal['?'], Literal['*'], Literal['+']]

@dataclass
class BracketOpt:
    _item_1: InitVar[Literal['[']]
    _item_2: InitVar[Commit]
    alts: Alts
    _item_4: InitVar[Literal[']']]

Item = Union[BracketOpt, Quantifier, SeparatedQuantifier, Plain]

@dataclass
class LookaheadOrCut_1:
    type: Literal['&']
    _item_2: InitVar[Commit]
    atom: Plain

@dataclass
class LookaheadOrCut_2:
    type: Literal['!']
    _item_2: InitVar[Commit]
    atom: Plain

@dataclass
class LookaheadOrCut_3:
    type: Literal['~']

LookaheadOrCut = Union[LookaheadOrCut_1, LookaheadOrCut_2, LookaheadOrCut_3]

@dataclass
class NamedItem_1:
    name: NAME
    _item_2: InitVar[Literal['=']]
    _item_3: InitVar[Commit]
    item: Item

@dataclass
class NamedItem_2:
    item: Item

@dataclass
class NamedItem_3:
    item: LookaheadOrCut

NamedItem = Union[NamedItem_1, NamedItem_2, NamedItem_3]

@dataclass
class Alt:
    items: Annotated[list[NamedItem], "+", NO_LF_SPACE]
    ending: Optional[Literal['$']]

@dataclass
class MoreAlts:
    _item_1: InitVar[Literal['|']]
    alts: Alts
    _item_3: InitVar[NEWLINE]
    more_alts: Optional[MoreAlts]

@dataclass
class Alts:
    alts: Annotated[list[Alt], "+", Literal['|']]

@dataclass
class Type:
    _item_1: InitVar[Literal['[']]
    type: NAME
    pointer: Optional[Literal['*']]
    _item_4: InitVar[Literal[']']]

@dataclass
class RuleName:
    name: NAME
    type: Optional[Type]

@dataclass
class Rule_1:
    rulename: RuleName
    _item_2: InitVar[Literal[':']]
    alts: Alts
    _item_4: InitVar[NEWLINE]
    _item_5: InitVar[INDENT]
    more_alts: MoreAlts
    _item_7: InitVar[DEDENT]

@dataclass
class Rule_2:
    rulename: RuleName
    _item_2: InitVar[Literal[':']]
    alts: None
    _item_4: InitVar[NEWLINE]
    _item_5: InitVar[INDENT]
    more_alts: MoreAlts
    _item_7: InitVar[DEDENT]

@dataclass
class Rule_3:
    rulename: RuleName
    _item_2: InitVar[Literal[':']]
    alts: Alts
    _item_4: InitVar[NEWLINE]
    more_alts: None

Rule = Union[Rule_1, Rule_2, Rule_3]

@dataclass
class MetaTuple:
    _item_1: InitVar[Literal['@']]
    meta_name: NAME
    meta_value: Union[NAME, STRING, None]
    _item_4: InitVar[NEWLINE]

@dataclass
class Grammar:
    metas: list[MetaTuple]
    rules: Annotated[list[Rule], "+"]

@dataclass
class Start:
    grammar: Grammar
    _item_2: InitVar[ENDMARKER]

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
        pprint(parsival.parse(text, Start, indent=CustomIndent))
    except (SyntaxError, parsival.Failed) as exc:
        print('Failed:', str(exc)[:50], file=sys.stderr)
