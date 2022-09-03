"""Leaf classes for PEP 617 grammar minus grammar actions."""
from __future__ import annotations
from dataclasses import InitVar, dataclass
from enum import Enum
from typing import Annotated, Literal, Optional, Union

from parsival import Commit, Failed, Here, parse
from parsival.helper_rules import NEWLINE, NO_LF_SPACE, Regex

NAME = Regex[str, r'[a-zA-Z_][a-zA-Z_0-9]*']
@dataclass
class STRING:
    string: Regex[str, r"'(?:[^'\\]|\\(?:\\\\)*.)*'"
                  + r'|"(?:[^"\\]|\\(?:\\\\)*.)*"']

@dataclass
class Grouped:
    _paren1: InitVar[Literal['(']]
    _: InitVar[Commit]
    alts: Alts
    _paren2: InitVar[Literal[')']]

Atom = Union[Grouped, NAME, STRING]

@dataclass
class Gather:
    sep: Atom
    _dot: InitVar[Literal['.']]
    node: Atom
    _plus: InitVar[Literal['+']]

class QuantifierType(Enum):
    OPTIONAL = '?'
    REPEAT_0 = '*'
    REPEAT_1 = '+'

@dataclass
class Quantifier:
    atom: Atom
    quantifier: QuantifierType

@dataclass
class BracketOpt:
    _bracket1: InitVar[Literal['[']]
    _: InitVar[Commit]
    alts: Alts
    _bracket2: InitVar[Literal[']']]

Item = Union[BracketOpt, Quantifier, Gather, Atom]

class Cut(Enum):
    CUT = '~'

class LookaheadType(Enum):
    POSITIVE = '&'
    NEGATIVE = '!'

@dataclass
class PNLookahead:
    type: LookaheadType
    _: InitVar[Commit]
    atom: Atom

Lookahead = Union[PNLookahead, Cut]

@dataclass
class NamedItem:
    name: NAME
    _equals: InitVar[Literal['=']]
    _: InitVar[Commit]
    item: Item

@dataclass
class Alt:
    items: Annotated[list[Union[NamedItem, Item, Lookahead]], '+', NO_LF_SPACE]

@dataclass
class _Alts:
    alt: Alt
    _pipe: InitVar[Literal['|']]
    alts: Alts

Alts = Union[_Alts, Alt]

@dataclass
class _MoreAlts:
    _pipe: InitVar[Literal['|']]
    alts: Alts
    _newline: InitVar[NEWLINE]
    more_alts: MoreAlts

MoreAlts = Union[_MoreAlts, Annotated[Alts, tuple[Literal['|'], Here, NEWLINE]]]

@dataclass
class RuleType:
    _bracket1: InitVar[Literal['[']]
    type: NAME
    pointer: Optional[Literal['*']]
    _bracket2: InitVar[Literal[']']]

@dataclass
class RuleName:
    name: NAME
    type: Optional[RuleType]

@dataclass
class _Rule:
    rulename: RuleName
    _colon: InitVar[Literal[':']]

@dataclass
class _Rule1(_Rule):
    alts: Alts
    _newline: InitVar[NEWLINE]
    more_alts: MoreAlts

@dataclass
class _Rule2(_Rule):
    _newline: InitVar[NEWLINE]
    more_alts: MoreAlts
    alts = None

@dataclass
class _Rule3(_Rule):
    alts: Alts
    _newline: InitVar[NEWLINE]
    more_alts = None

Rule = Union[_Rule1, _Rule2, _Rule3]

@dataclass
class RuleList:
    rules: list[Rule]

@dataclass
class Meta:
    _at: InitVar[Literal['@']]
    name_a: NAME

@dataclass
class MetaName(Meta):
    name_b: NAME

@dataclass
class MetaString(Meta):
    string: Optional[STRING]

@dataclass
class MetaList:
    metas: list[Union[Meta, MetaName, MetaString]]

@dataclass
class Grammar:
    metas: Optional[MetaList]
    rules: RuleList

Start = Grammar

if __name__ == '__main__':
    try:
        from prettyprinter import pprint, install_extras
    except ImportError:
        from pprint import pprint
    else:
        install_extras(include=frozenset({'dataclasses'}))
    with open('parsival/python.gram') as f:
        text = f.read()
    try:
        pprint(parse(text, Start))
    except (SyntaxError, Failed):
        print('Failed')
