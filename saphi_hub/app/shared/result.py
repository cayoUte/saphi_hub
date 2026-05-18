"""
shared/result.py
================
Result[T, E] — tipo funcional para manejo explícito de errores.

Variantes
---------
  Ok[T]   — operación exitosa; contiene un valor de tipo T.
  Err[E]  — operación fallida; contiene un error de tipo E.

Alias público
-------------
  Result[T, E] = Ok[T] | Err[E]

Railway Oriented Programming (ROP) completo
--------------------------------------------
Cada variante implementa las cuatro operaciones simétricas:

  ┌──────────────┬────────────────────────────────────────────────────────┐
  │ Operación    │ Descripción                                            │
  ├──────────────┼────────────────────────────────────────────────────────┤
  │ map(f)       │ Transforma el valor Ok;   no‑op en Err                 │
  │ bind(f)      │ Encadena Ok → Result;     cortocircuita en Err         │
  │ alt(f)  *    │ Transforma el error Err;  no‑op en Ok                  │
  │ lash(f) *    │ Recupera Err → Result;    no‑op en Ok                  │
  └──────────────┴────────────────────────────────────────────────────────┘
  * Añadidos en esta versión para completar el cuadrado ROP.

Cada operación tiene su gemela asíncrona:
  map_async, bind_async, alt_async, lash_async.

Relación con map_err
--------------------
  alt(f) ≡ map_err(f): ambos transforman el error.
  map_err se mantiene como nombre canónico; alt como alias Railway.

Funciones de módulo
-------------------
  map2(r1, r2, f)        — combina dos Ok con f(a, b); devuelve el primer Err.
  combine(results)       — list[Result] → Result[list[T]]; cortocircuita en Err.
  from_exception(f, t)   — ejecuta f(); captura exc de tipo t y devuelve Err(e).

Notas de diseño
---------------
* Tipos inmutables — @dataclass(frozen=True).
* Genéricos con sintaxis PEP 695 (Python 3.12+).
* match usado en funciones de módulo.
* Sin dependencias externas; solo biblioteca estándar.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


# ---------------------------------------------------------------------------
# Excepción de dominio
# ---------------------------------------------------------------------------

class UnwrapError(Exception):
    """
    Lanzada al llamar .unwrap() sobre un Err o Nothing.

    Attributes
    ----------
    error : Any | None
        El error original encapsulado (solo presente al venir de Err.unwrap).
        Permite inspección programática sin necesidad de parsear el mensaje.

    Examples
    --------
        try:
            Err(404).unwrap()
        except UnwrapError as exc:
            print(exc.error)   # 404
    """

    def __init__(self, error: Any = None, message: str = "") -> None:
        self.error = error
        if message:
            msg = message
        elif error is not None:
            msg = f"unwrap() llamado sobre Err — error: {error!r}"
        else:
            msg = "unwrap() llamado sobre Nothing"
        super().__init__(msg)


# ---------------------------------------------------------------------------
# Variante exitosa
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Ok[T]:
    """
    Envuelve un valor T que representa una operación completada con éxito.

    Diagrama ROP (Ok es la vía feliz):
        valor  ──map──►  Ok(f(valor))
        valor  ──bind──► f(valor)           (puede devolver Ok o Err)
        valor  ──alt──►  Ok(valor)          [no‑op: no hay error que transformar]
        valor  ──lash──► Ok(valor)          [no‑op: no hay error que recuperar]
    """

    value: T

    # ── Vía feliz ────────────────────────────────────────────────────── #

    def map[U](self, f: Callable[[T], U]) -> Ok[U]:
        """
        Transforma el valor con *f* y devuelve Ok con el resultado.

        >>> Ok(2).map(lambda x: x * 3)
        Ok(value=6)
        """
        return Ok(f(self.value))

    def bind[U, E](
        self, f: Callable[[T], Ok[U] | Err[E]]
    ) -> Ok[U] | Err[E]:
        """
        Encadena *f* al valor (flatMap / >>=).

        >>> Ok(4).bind(lambda x: Ok(x + 1) if x > 0 else Err("negativo"))
        Ok(value=5)
        """
        return f(self.value)

    # ── Vía de error (no‑ops en Ok) ───────────────────────────────────── #

    def map_err[F](self, f: Callable[[Any], F]) -> Ok[T]:
        """
        No‑op: Ok no contiene error que transformar.
        Existe para que la interfaz sea simétrica con Err.
        """
        return self

    def alt[F](self, f: Callable[[Any], F]) -> Ok[T]:
        """
        Alias Railway de map_err.
        No‑op: Ok no tiene error, por lo que *f* no se invoca.

        Mnemoregla: alt ↔ «alternativa para el error».
        """
        return self

    def lash[F](self, f: Callable[[Any], Ok[T] | Err[F]]) -> Ok[T]:
        """
        No‑op: Ok ya es exitoso, no hay error que recuperar.
        *f* no se invoca.

        Mnemoregla: lash ↔ «engancharse al error para rescatarlo».
        """
        return self

    # ── Extracción ────────────────────────────────────────────────────── #

    def unwrap(self) -> T:
        """Devuelve el valor. En Ok nunca lanza."""
        return self.value

    def unwrap_or(self, default: T) -> T:  # noqa: ARG002
        """Devuelve el valor; *default* se ignora en Ok."""
        return self.value

    # ── Asíncronas ────────────────────────────────────────────────────── #

    async def map_async[U](
        self, f: Callable[[T], Awaitable[U]]
    ) -> Ok[U]:
        """Aplica la función asíncrona *f* al valor."""
        return Ok(await f(self.value))

    async def bind_async[U, E](
        self, f: Callable[[T], Awaitable[Ok[U] | Err[E]]]
    ) -> Ok[U] | Err[E]:
        """Encadena la función asíncrona *f* al valor."""
        return await f(self.value)

    async def alt_async[F](
        self, f: Callable[[Any], Awaitable[F]]
    ) -> Ok[T]:
        """No‑op asíncrono: Ok no tiene error que transformar."""
        return self

    async def lash_async[F](
        self, f: Callable[[Any], Awaitable[Ok[T] | Err[F]]]
    ) -> Ok[T]:
        """No‑op asíncrono: Ok no necesita recuperación."""
        return self

    # ── Utilidades ────────────────────────────────────────────────────── #

    def __bool__(self) -> bool:
        """Ok es truthy."""
        return True


# ---------------------------------------------------------------------------
# Variante fallida
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Err[E]:
    """
    Envuelve un error E que representa una operación fallida.

    Diagrama ROP (Err es la vía de error):
        error  ──map──►  Err(error)         [no‑op: no hay valor que transformar]
        error  ──bind──► Err(error)         [no‑op: cortocircuita]
        error  ──alt──►  Err(f(error))       transforma el error
        error  ──lash──► f(error)            recupera: puede volver a Ok
    """

    error: E

    # ── Vía feliz (no‑ops en Err) ─────────────────────────────────────── #

    def map[T, U](self, f: Callable[[T], U]) -> Err[E]:  # noqa: ARG002
        """No‑op: Err no tiene valor que transformar."""
        return self

    def bind[T, U](
        self, f: Callable[[T], Ok[U] | Err[E]]  # noqa: ARG002
    ) -> Err[E]:
        """No‑op: Err cortocircuita la cadena sin invocar *f*."""
        return self

    # ── Vía de error ──────────────────────────────────────────────────── #

    def map_err[F](self, f: Callable[[E], F]) -> Err[F]:
        """
        Transforma el error con *f*; útil para normalizar tipos de error.

        >>> Err(404).map_err(str)
        Err(error='404')
        """
        return Err(f(self.error))

    def alt[F](self, f: Callable[[E], F]) -> Err[F]:
        """
        Alias Railway de map_err.
        Transforma el error con *f* devolviendo Err con el nuevo error.

        Útil para adaptar errores de infraestructura a errores de dominio:

            db_result.alt(lambda e: DomainError(f"DB falló: {e}"))

        >>> Err("timeout").alt(lambda e: f"ERROR: {e}")
        Err(error='ERROR: timeout')
        """
        return Err(f(self.error))

    def lash[F](self, f: Callable[[E], Ok[F] | Err[F]]) -> Ok[F] | Err[F]:
        """
        Recuperación desde el error: aplica *f* al error.

        A diferencia de alt/map_err (que siempre produce Err), lash
        permite que *f* devuelva Ok para «rescatar» la vía feliz.

        Casos de uso:
          * Reintentar con un valor por defecto.
          * Convertir un error recuperable en valor.
          * Propagar un error diferente.

        >>> Err("no encontrado").lash(lambda _: Ok(0))
        Ok(value=0)
        >>> Err("crítico").lash(lambda e: Err(f"[FATAL] {e}"))
        Err(error='[FATAL] crítico')
        """
        return f(self.error)

    # ── Extracción ────────────────────────────────────────────────────── #

    def unwrap[T](self) -> T:
        """
        Siempre lanza UnwrapError con el error encapsulado.
        El error original queda en ``exc.error`` para inspección.
        """
        raise UnwrapError(self.error)

    def unwrap_or[T](self, default: T) -> T:
        """Devuelve *default* ya que Err no tiene valor."""
        return default

    # ── Asíncronas ────────────────────────────────────────────────────── #

    async def map_async[T, U](
        self, f: Callable[[T], Awaitable[U]]  # noqa: ARG002
    ) -> Err[E]:
        """No‑op asíncrono: propaga el error sin ejecutar *f*."""
        return self

    async def bind_async[T, U](
        self, f: Callable[[T], Awaitable[Ok[U] | Err[E]]]  # noqa: ARG002
    ) -> Err[E]:
        """No‑op asíncrono: propaga el error sin ejecutar *f*."""
        return self

    async def alt_async[F](
        self, f: Callable[[E], Awaitable[F]]
    ) -> Err[F]:
        """
        Transforma el error de forma asíncrona.

            await Err(exc).alt_async(log_and_classify)
        """
        return Err(await f(self.error))

    async def lash_async[F](
        self, f: Callable[[E], Awaitable[Ok[F] | Err[F]]]
    ) -> Ok[F] | Err[F]:
        """
        Recuperación asíncrona desde el error.

            await Err(exc).lash_async(retry_with_fallback)
        """
        return await f(self.error)

    # ── Utilidades ────────────────────────────────────────────────────── #

    def __bool__(self) -> bool:
        """Err es falsy."""
        return False


# ---------------------------------------------------------------------------
# Alias de tipo público
# ---------------------------------------------------------------------------

type Result[T, E] = Ok[T] | Err[E]
"""
Alias de unión discriminada: Ok[T] | Err[E].

El cuadrado ROP completo:

              Ok[T]                 Err[E]
             ┌──────────────────────────────────────────┐
    map(f)   │  Ok(f(value))        Err(error)   no‑op  │
    bind(f)  │  f(value)            Err(error)   no‑op  │
    alt(f)   │  Ok(value)  no‑op    Err(f(error))       │
    lash(f)  │  Ok(value)  no‑op    f(error)            │
             └──────────────────────────────────────────┘

Ejemplo de uso completo
-----------------------
    def dividir(a: float, b: float) -> Result[float, str]:
        if b == 0:
            return Err("división por cero")
        return Ok(a / b)

    resultado = (
        dividir(10, 0)
        .lash(lambda _: Ok(float("inf")))   # recuperar con infinito
        .map(lambda v: round(v, 2))
    )
    # Ok(value=inf)
"""


# ---------------------------------------------------------------------------
# Funciones de módulo
# ---------------------------------------------------------------------------

def map2[T, U, V, E](
    r1: Ok[T] | Err[E],
    r2: Ok[U] | Err[E],
    f: Callable[[T, U], V],
) -> Ok[V] | Err[E]:
    """
    Combina dos Result exitosos aplicando ``f(a, b)``.
    Devuelve el primer Err encontrado (r1 tiene prioridad).

    >>> map2(Ok(3), Ok(4), lambda a, b: a + b)
    Ok(value=7)
    >>> map2(Err("fallo"), Ok(4), lambda a, b: a + b)
    Err(error='fallo')
    """
    match (r1, r2):
        case (Ok(value=a), Ok(value=b)):
            return Ok(f(a, b))
        case (Err() as e, _):
            return e
        case (_, Err() as e):
            return e
        case _:  # pragma: no cover
            raise TypeError(
                f"map2: tipos inesperados ({type(r1).__name__}, {type(r2).__name__})"
            )


def combine[T, E](
    results: list[Ok[T] | Err[E]],
) -> Ok[list[T]] | Err[E]:
    """
    Convierte una lista de Result en un Result de lista.
    Cortocircuita en el primer Err.

    >>> combine([Ok(1), Ok(2), Ok(3)])
    Ok(value=[1, 2, 3])
    >>> combine([Ok(1), Err("x"), Ok(3)])
    Err(error='x')
    """
    values: list[T] = []
    for r in results:
        match r:
            case Ok(value=v):
                values.append(v)
            case Err() as e:
                return e
    return Ok(values)


def from_exception[T, E: Exception](
    f: Callable[[], T],
    exc_type: type[E],
) -> Ok[T] | Err[E]:
    """
    Ejecuta ``f()`` capturando excepciones del tipo *exc_type*.
    Cualquier otra excepción se propaga sin capturar.

    >>> from_exception(lambda: int("42"), ValueError)
    Ok(value=42)
    >>> from_exception(lambda: int("abc"), ValueError)
    Err(error=ValueError(...))
    """
    try:
        return Ok(f())
    except exc_type as e:
        return Err(e)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Exportaciones públicas
# ---------------------------------------------------------------------------

__all__: list[str] = [
    "Ok",
    "Err",
    "Result",
    "UnwrapError",
    "map2",
    "combine",
    "from_exception",
]