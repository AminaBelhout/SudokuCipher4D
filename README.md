# SudokuCipher4D

Experimental Python prototype of a 4-dimensional time-evolving Sudoku substitution cipher.

## Overview

SudokuCipher4D is an educational cryptography project exploring how a valid 16×16 Sudoku grid can act as a substitution table that evolves after every encrypted character. It combines deterministic Sudoku transformations with a reversible byte mapping to create a dynamic substitution cipher.

## Inspiration

While revising classical cryptography for Security+, I wondered whether a Sudoku grid could be used as a substitution table for all 256 byte values. After researching existing Sudoku ciphers, I noticed most relied on a static grid. That led to a simple question: what if the grid itself evolved after every encrypted character while always remaining valid?

## Four Dimensions

| Dimension | Meaning |
|-----------|---------|
| X | Row position |
| Y | Column position |
| Z | Character position in message |
| T | Grid evolution step (time) |

## Features

✔ 16×16 Sudoku grid — 256-byte mapping  
✔ Deterministic key-derived evolution  
✔ Reversible encryption  
✔ Animated terminal visualization  
✔ Challenge mode  

## Screenshots

![Genesis Grid](screenshots/1x.png)
![Encryption](screenshots/1xx.png)

## Run

pip install -r requirements.txt
python sudoku4d.py

## Challenge

The algorithm is public. The ciphertext is public. The key is hidden.

Can you recover the plaintext without the key?

> **Disclaimer: This is an educational prototype. It has not been peer reviewed or cryptanalyzed and must never be used to protect real-world secrets.**

---
Concept by Amina Belhout | Prototype
