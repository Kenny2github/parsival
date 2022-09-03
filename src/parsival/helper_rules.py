"""Helper rules to make annotation-based parsing easier."""
from __future__ import annotations
from enum import Enum
import re
import typing as t
from dataclasses import InitVar, dataclass

if t.TYPE_CHECKING:
    from . import Rule

__all__ = [
    'Regex',
    'Not',
    'Lookahead',
    'SPACE',
    'NO_LF_SPACE',
    'NEWLINE',
    'NO_SPACE',
    'ENDMARKER',
]

class _RuleAnnotation:
    """Helper base class that makes things easier."""
    args: tuple

    def __init__(self, *args) -> None:
        self.args = args

    def __call__(self, *args: t.Any, **kwds: t.Any) -> t.Any:
        pass

    def __repr__(self) -> str:
        return f'{type(self).__qualname__}[' + ', '.join(map(repr, self.args)) + ']'

    def __class_getitem__(cls, arg: tuple):
        return cls(*arg)

class _Regex(_RuleAnnotation):
    """Regex[str, <pattern>] matches <pattern> and returns the matched string.

    Regex[str, <pattern>, <flags>] is the same,
    but compiles <pattern> with <flags>.
    """
    pattern: re.Pattern[str]

    def __init__(self, _: type[str],
                 pattern: str, flags: int = 0) -> None:
        self.pattern = re.compile(pattern, flags)

    def __repr__(self) -> str:
        return f'parsival.Regex[str, r"""{self.pattern.pattern}""", ' \
            f'{self.pattern.flags}]'

if t.TYPE_CHECKING:
    Regex = t.Annotated
else:
    Regex = _Regex

class _Not(_RuleAnnotation):
    """Not[<rule>] is a negative lookahead for <rule>."""
    rule: Rule

    def __init__(self, rule: Rule) -> None:
        super().__init__(rule)
        self.rule = rule

    def __class_getitem__(cls, rule: Rule) -> _Not:
        return cls(rule)

if t.TYPE_CHECKING:
    Not = t.Optional # since successful parse returns None
else:
    Not = _Not

class _Lookahead(_RuleAnnotation):
    """Lookahead[<rule>] is a positive lookahead for <rule>."""
    rule: Rule

    def __init__(self, rule: Rule) -> None:
        super().__init__(rule)
        self.rule = rule

    def __class_getitem__(cls, rule: Rule) -> _Lookahead:
        return cls(rule)

if t.TYPE_CHECKING:
    Lookahead = t.Optional # since successful parse returns the expression
else:
    Lookahead = _Lookahead

# literal rules

@dataclass
class SPACE:
    """A required space."""
    text: Regex[str, r'\s+']

@dataclass
class NO_LF_SPACE:
    """A required space, excluding newlines."""
    text: Regex[str, r'[^\S\n]+']

@dataclass
class NEWLINE:
    """A newline."""
    text: t.Literal['\n']

@dataclass
class NO_SPACE:
    """Assert that there is no space here, between two other rules."""
    text: Not[SPACE]

@dataclass
class ENDMARKER:
    """Assert position at the end of the file."""
    _end: InitVar[Regex[str, r'\Z']]
