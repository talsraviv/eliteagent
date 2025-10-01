#!/usr/bin/env python3

def is_prime(n: int) -> bool:
    if n < 2:
        return False
    if n == 2:
        return True
    if n % 2 == 0:
        return False
    i = 3
    while i * i <= n:
        if n % i == 0:
            return False
        i += 2
    return True


def int_to_roman(n: int) -> str:
    """Convert an integer (1..3999) to a Roman numeral.
    For this task, input will be 1..1000 inclusive.
    """
    if not (1 <= n <= 3999):
        raise ValueError("int_to_roman supports values from 1 to 3999")
    numerals = [
        (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
        (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
        (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
    ]
    result = []
    for value, symbol in numerals:
        if n == 0:
            break
        count, n = divmod(n, value)
        if count:
            result.append(symbol * count)
    return "".join(result)


def main() -> None:
    for i in range(1, 1001):
        rn = int_to_roman(i)
        print(f"{rn}{'*' if is_prime(i) else ''}")


if __name__ == "__main__":
    main()
