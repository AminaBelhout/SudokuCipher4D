#!/usr/bin/env python3
"""
SudokuCipher4D
==============
A novel, portfolio-grade encryption prototype built on a time-evolving
16x16 sudoku grid.

Four dimensions:
    X = row          Y = column
    Z = message position (which character is being encrypted)
    T = time / grid generation (how many evolution steps have occurred)

For every character of the message, the grid is advanced one step by the
evolution function Phi(S, k, T):
    1. Permute rows *within* each 4-row band using a key+T derived sequence
    2. Permute columns *within* each 4-column stack using a different
       key+T derived sequence
    3. Rotate the order of the boxes (bands and stacks) by T mod 4

Every one of these operations is a classic sudoku symmetry: it can only
ever produce another fully valid 16x16 sudoku grid (every row, column and
4x4 box still contains each of the 16 symbols exactly once). Validity is
therefore preserved at every single step, the same way a legal chess move
can never leave your own king in check.

Substitution works by pairing the grid's 16 boxes with the high nibble of
a character's code point (0-255) and the grid's 16 symbol values with the
low nibble. Because every sudoku box contains each value exactly once,
there is exactly one cell that matches a given (box, value) pair -- this
gives a perfect, reversible mapping between the 256-character keyboard
alphabet and the grid's 256 cells. Since the grid is a different valid
sudoku at every character, that mapping is completely different every
time, even for repeated letters.

This is a PROTOTYPE / PORTFOLIO DEMO. It is not peer-reviewed, has not
been cryptanalyzed, and must never be used to protect real secrets.

Run with:  python sudoku4d.py
"""

from __future__ import annotations

import hashlib
import random
import sys
import time
from dataclasses import dataclass
from typing import List, Tuple

try:
    import numpy as np
    from rich.align import Align
    from rich.console import Console, Group
    from rich.live import Live
    from rich.panel import Panel
    from rich.prompt import Prompt
    from rich.rule import Rule
    from rich.table import Table
    from rich.text import Text
    from rich import box as rbox
except ImportError as exc:  # pragma: no cover
    sys.stderr.write(
        "Missing dependency: {}\n"
        "Install requirements with:\n"
        "    pip install rich numpy\n".format(exc)
    )
    sys.exit(1)


# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

N = 16              # grid dimension / symbol count
BOX = 4              # box dimension (4x4 boxes)
VALUE_CHARS = "0123456789ABCDEF"

VALUE_COLORS = [
    "bright_red", "bright_green", "bright_yellow", "bright_blue",
    "bright_magenta", "bright_cyan", "red3", "chartreuse3",
    "gold3", "dodger_blue1", "orchid", "turquoise2",
    "orange3", "spring_green2", "deep_pink3", "medium_purple1",
]

console = Console()


# --------------------------------------------------------------------------
# Deterministic, key-derived randomness
# --------------------------------------------------------------------------

def seeded_rng(*parts: str) -> random.Random:
    """A random.Random seeded deterministically from the given strings."""
    digest = hashlib.sha256("::".join(parts).encode("utf-8")).digest()
    return random.Random(digest)


def make_base_grid() -> np.ndarray:
    """Standard closed-form generator for a *valid* box^2 x box^2 sudoku."""
    grid = np.zeros((N, N), dtype=int)
    for r in range(N):
        for c in range(N):
            grid[r, c] = (BOX * (r % BOX) + r // BOX + c) % N
    return grid


# --------------------------------------------------------------------------
# The evolving sudoku grid
# --------------------------------------------------------------------------

@dataclass
class SudokuGrid:
    arr: np.ndarray

    def copy(self) -> "SudokuGrid":
        return SudokuGrid(self.arr.copy())

    # -- validity-preserving primitive operations -------------------------
    # Each of these only ever reorders whole rows/columns/bands/stacks, so
    # every row, column and 4x4 box keeps exactly the same *set* of values
    # it had before -- sudoku validity can never be broken.

    def _permute_bands(self, order: List[int]) -> None:
        bands = [self.arr[b * BOX:(b + 1) * BOX, :].copy() for b in range(BOX)]
        for new_pos, old_band in enumerate(order):
            self.arr[new_pos * BOX:(new_pos + 1) * BOX, :] = bands[old_band]

    def _permute_stacks(self, order: List[int]) -> None:
        stacks = [self.arr[:, s * BOX:(s + 1) * BOX].copy() for s in range(BOX)]
        for new_pos, old_stack in enumerate(order):
            self.arr[:, new_pos * BOX:(new_pos + 1) * BOX] = stacks[old_stack]

    def _permute_rows_in_band(self, band: int, order: List[int]) -> None:
        base = band * BOX
        rows = [self.arr[base + i, :].copy() for i in range(BOX)]
        for new_pos, old_row in enumerate(order):
            self.arr[base + new_pos, :] = rows[old_row]

    def _permute_cols_in_stack(self, stack: int, order: List[int]) -> None:
        base = stack * BOX
        cols = [self.arr[:, base + i].copy() for i in range(BOX)]
        for new_pos, old_col in enumerate(order):
            self.arr[:, base + new_pos] = cols[old_col]

    def _relabel_values(self, mapping: List[int]) -> None:
        self.arr = np.vectorize(lambda v: mapping[v])(self.arr)

    # -- construction & evolution ------------------------------------------

    @classmethod
    def generate(cls, key: str) -> "SudokuGrid":
        """S0: a key-dependent, fully valid 16x16 sudoku grid."""
        g = cls(make_base_grid())
        rng = seeded_rng(key, "genesis")
        g._permute_bands(rng.sample(range(BOX), BOX))
        g._permute_stacks(rng.sample(range(BOX), BOX))
        for b in range(BOX):
            g._permute_rows_in_band(b, rng.sample(range(BOX), BOX))
        for s in range(BOX):
            g._permute_cols_in_stack(s, rng.sample(range(BOX), BOX))
        g._relabel_values(rng.sample(range(N), N))
        return g

    def evolve(self, key: str, T: int) -> "SudokuGrid":
        """Phi(S, k, T) -- one legal, validity-preserving evolution step."""
        g = self.copy()
        rng = seeded_rng(key, f"T{T}")

        # 1. row permutation, key-derived sequence, scoped per band
        for b in range(BOX):
            g._permute_rows_in_band(b, rng.sample(range(BOX), BOX))

        # 2. column permutation, a *different* key-derived sequence
        for s in range(BOX):
            g._permute_cols_in_stack(s, rng.sample(range(BOX), BOX))

        # 3. box rotation by T mod 4
        rotate = T % BOX
        if rotate:
            band_order = [(i + rotate) % BOX for i in range(BOX)]
            stack_order = [(i + rotate) % BOX for i in range(BOX)]
            g._permute_bands(band_order)
            g._permute_stacks(stack_order)

        return g

    def find_cell(self, box_id: int, value: int) -> Tuple[int, int]:
        """The unique cell in the given box holding `value` (box constraint)."""
        band, stack = divmod(box_id, BOX)
        r0, c0 = band * BOX, stack * BOX
        sub = self.arr[r0:r0 + BOX, c0:c0 + BOX]
        pos = np.argwhere(sub == value)[0]
        return int(r0 + pos[0]), int(c0 + pos[1])


# --------------------------------------------------------------------------
# The cipher itself
# --------------------------------------------------------------------------

class SudokuCipher4D:
    """
    Substitution scheme: a character's code point m (0-255) is split into
    box_id = m // 16  and  value = m % 16. Because every sudoku box holds
    each value exactly once, there is exactly one cell (r, c) matching
    that pair in the *current* grid -- that cell's flat index r*16+c is
    the ciphertext byte. Since the grid evolves every character, the same
    plaintext character maps to a different cell (and different byte)
    almost every time.
    """

    def __init__(self, key: str):
        self.key = key

    @staticmethod
    def _char_to_box_value(ch: str) -> Tuple[int, int]:
        m = ord(ch)
        if m > 255:
            raise ValueError(
                f"Character {ch!r} falls outside the 256-symbol keyboard "
                f"alphabet supported by SudokuCipher4D."
            )
        return divmod(m, N)  # (box_id, value)

    def encrypt(self, message: str) -> List[int]:
        grid = SudokuGrid.generate(self.key)
        cipher_bytes = []
        for t, ch in enumerate(message, start=1):
            grid = grid.evolve(self.key, t)
            box_id, value = self._char_to_box_value(ch)
            r, c = grid.find_cell(box_id, value)
            cipher_bytes.append(r * N + c)
        return cipher_bytes

    def decrypt(self, cipher_bytes: List[int]) -> str:
        grid = SudokuGrid.generate(self.key)
        out = []
        for t, byte in enumerate(cipher_bytes, start=1):
            grid = grid.evolve(self.key, t)
            r, c = divmod(byte, N)
            value = int(grid.arr[r, c])
            box_id = (r // BOX) * BOX + (c // BOX)
            out.append(chr(box_id * N + value))
        return "".join(out)


# --------------------------------------------------------------------------
# Rendering helpers
# --------------------------------------------------------------------------

def render_grid(grid: SudokuGrid, title: str, highlight: Tuple[int, int] = None) -> Panel:
    table = Table(
        title=title,
        box=rbox.HEAVY,
        show_header=True,
        header_style="bold white on grey23",
        padding=0,
        pad_edge=False,
    )
    table.add_column("", justify="center", style="dim", width=2)
    for c in range(N):
        table.add_column(VALUE_CHARS[c], justify="center", width=2)

    for r in range(N):
        cells = [Text(VALUE_CHARS[r], style="dim")]
        for c in range(N):
            v = int(grid.arr[r, c])
            if highlight is not None and highlight == (r, c):
                style = f"bold white on {VALUE_COLORS[v]}"
            else:
                style = VALUE_COLORS[v]
            cells.append(Text(VALUE_CHARS[v], style=style, justify="center"))
        table.add_row(*cells)

    return Panel(table, border_style="cyan")


def render_cipher_matrix(cipher_bytes: List[int]) -> Panel:
    cols = 16
    grid_table = Table(show_header=False, box=rbox.MINIMAL, padding=0)
    for _ in range(cols):
        grid_table.add_column(justify="center", width=3)

    if not cipher_bytes:
        grid_table.add_row(*(["--"] + [""] * (cols - 1)))
    else:
        for i in range(0, len(cipher_bytes), cols):
            chunk = cipher_bytes[i:i + cols]
            cells = [Text(f"{b:02X}", style=VALUE_COLORS[b % N]) for b in chunk]
            while len(cells) < cols:
                cells.append(Text(""))
            grid_table.add_row(*cells)

    return Panel(grid_table, title="Ciphertext Matrix (hex bytes)", border_style="bright_green")


def banner() -> None:
    title = Text("SUDOKU CIPHER 4D", style="bold white on dark_magenta", justify="center")
    width = min(max(console.width - 4, 40), 74)
    console.print(Align.center(Panel(
        Align.center(title),
        subtitle="[italic]4-dimensional time-evolving sudoku substitution cipher[/italic]",
        border_style="bright_magenta",
        padding=(1, 4),
        width=width,
    )))
    console.print()


# --------------------------------------------------------------------------
# Animated evolution demo (first few characters)
# --------------------------------------------------------------------------

def animate_evolution(cipher: SudokuCipher4D, message: str) -> None:
    steps = min(3, len(message))
    if steps == 0:
        return

    console.print(Rule("[bold yellow]4D Evolution — watch the grid transform[/bold yellow]"))
    grid = SudokuGrid.generate(cipher.key)

    with Live(console=console, refresh_per_second=4, transient=False) as live:
        live.update(Align.center(render_grid(grid, "S₀ — Genesis Grid  (T=0)")))
        time.sleep(0.9)

        for t in range(1, steps + 1):
            ch = message[t - 1]
            grid = grid.evolve(cipher.key, t)
            box_id, value = cipher._char_to_box_value(ch)
            r, c = grid.find_cell(box_id, value)
            byte = r * N + c

            info = Table.grid(padding=(0, 2))
            info.add_column(style="bold cyan")
            info.add_column()
            info.add_row("Time step T", str(t))
            info.add_row("Character (Z)", repr(ch))
            info.add_row("Row perm", f"rows shuffled within each band  [dim](seed = key ⊕ T={t})[/dim]")
            info.add_row("Column perm", f"columns shuffled within each stack  [dim](seed = key ⊕ T={t})[/dim]")
            info.add_row("Box rotation", f"T mod 4 = {t % BOX}")
            info.add_row("(box, value) target", f"({box_id}, {value})")
            info.add_row("Matched cell (X, Y)", f"({r}, {c})")
            info.add_row("Cipher byte", f"0x{byte:02X}")

            group = Group(
                render_grid(grid, f"S_{t} — Evolved Grid  (Φ applied)", highlight=(r, c)),
                Panel(info, title=f"Step {t} trace", border_style="green"),
            )
            live.update(Align.center(group))
            time.sleep(1.0)

    console.print()


# --------------------------------------------------------------------------
# Encryption / decryption reveal
# --------------------------------------------------------------------------

def show_encryption(cipher: SudokuCipher4D, message: str) -> List[int]:
    cipher_bytes = cipher.encrypt(message)
    hexstr = " ".join(f"{b:02X}" for b in cipher_bytes)

    summary = Table(box=rbox.ROUNDED, border_style="magenta", show_header=False, padding=(0, 1))
    summary.add_column(style="bold")
    summary.add_column()
    summary.add_row("Original message", Text(message, style="white"))
    summary.add_row("Ciphertext (hex)", Text(hexstr or "(empty)", style="bright_green"))
    console.print(summary)
    console.print(Align.center(render_cipher_matrix(cipher_bytes)))
    return cipher_bytes


def show_decryption(cipher: SudokuCipher4D, cipher_bytes: List[int], original: str) -> None:
    plain = cipher.decrypt(cipher_bytes)
    ok = plain == original
    body = (
        f"Decrypted message : {plain!r}\n"
        f"Matches original  : {'YES ✅' if ok else 'NO ❌'}"
    )
    console.print(Panel(
        body,
        title="Decryption Verification",
        border_style="green" if ok else "red",
    ))


# --------------------------------------------------------------------------
# Challenge mode
# --------------------------------------------------------------------------

_CHALLENGE_BYTES = [
    109, 93, 123, 104, 106, 73, 95, 94, 74, 59,
    120, 75, 77, 10, 107, 125, 91, 72, 75,
]


def challenge_mode() -> None:
    hexstr = " ".join(f"{b:02X}" for b in _CHALLENGE_BYTES)

    console.print(Panel(
        Align.center(Text(hexstr, style="bold bright_red")),
        title="🔐 CHALLENGE MODE — Crack the Cipher!",
        subtitle="[dim]key hidden • 19 characters • the grid re-evolves every character[/dim]",
        border_style="red",
    ))


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main() -> None:
    console.clear()
    banner()

    key = Prompt.ask("[bold cyan]🔑  Enter your private key[/bold cyan]") or "default-key"
    message = Prompt.ask("[bold cyan]✉️   Enter your secret message[/bold cyan]") or "Hello, Sudoku World!"

    invalid = sorted({c for c in message if ord(c) > 255})
    if invalid:
        console.print(
            f"[bold red]Message contains characters outside the 256-symbol "
            f"keyboard alphabet: {invalid}. Please use standard keyboard "
            f"characters.[/bold red]"
        )
        return

    cipher = SudokuCipher4D(key)

    console.print(Rule("[bold]Initial Grid  S₀[/bold]"))
    console.print(Align.center(render_grid(SudokuGrid.generate(key), "S₀ — Genesis Sudoku Grid")))
    console.print()

    animate_evolution(cipher, message)

    console.print(Rule("[bold]Full Encryption[/bold]"))
    cipher_bytes = show_encryption(cipher, message)
    console.print()

    console.print(Rule("[bold]Full Decryption[/bold]"))
    show_decryption(cipher, cipher_bytes, message)
    console.print()

    console.print(Rule("[bold]Challenge Mode[/bold]"))
    challenge_mode()
    console.print()

    console.print(Align.center(Text(
        "SudokuCipher4D — A 4-dimensional time-evolving substitution cipher",
        style="bold bright_cyan",
    )))
    console.print(Align.center(Text(
        "Concept by Amina Belhout | Prototype",
        style="italic grey70",
    )))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted.[/dim]")
