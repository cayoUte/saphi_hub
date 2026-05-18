"""
shared/option.py
================
Option[T] — tipo funcional para valores opcionales sin usar None.

Variantes
---------
  Some[T]  — contiene un valor de tipo T.
  Nothing  — ausencia de valor; análogo a None pero tipado y explícito.

Alias público
-------------
  Option[T] = Some[T] | Nothing
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from shared.result import Err, Ok, UnwrapError


@dataclass(frozen=True)
class Some[T]:
    value: T

    def map[U](self, f: Callable[[T], U]) -> Some[U]:
        return Some(f(self.value))

    def bind[U](self, f: Callable[[T], Some[U] | Nothing]) -> Some[U] | Nothing:
        return f(self.value)

    def unwrap(self) -> T:
        return self.value

    def unwrap_or(self, default: T) -> T:  # noqa: ARG002
        return self.value

    def to_result[E](self, error: E) -> Ok[T] | Err[E]:  # noqa: ARG002
        return Ok(self.value)

    def __bool__(self) -> bool:
        return True


@dataclass(frozen=True)
class Nothing:
    def map[T, U](self, f: Callable[[T], U]) -> Nothing:  # noqa: ARG002
        return self

    def bind[T, U](self, f: Callable[[T], Some[U] | Nothing]) -> Nothing:  # noqa: ARG002
        return self

    def unwrap[T](self) -> T:
        raise UnwrapError()

    def unwrap_or[T](self, default: T) -> T:
        return default

    def to_result[T, E](self, error: E) -> Ok[T] | Err[E]:
        return Err(error)

    def __bool__(self) -> bool:
        return False


type Option[T] = Some[T] | Nothing

__all__: list[str] = [
    "Some",
    "Nothing",
    "Option",
]