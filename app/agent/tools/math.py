"""数学工具。"""

from __future__ import annotations

from langchain_core.tools import tool


@tool
def multiply(first_number: int, second_number: int) -> int:
    """将两个整数相乘。"""

    return first_number * second_number


@tool
def add(first_number: int, second_number: int) -> int:
    """将两个整数相加。"""

    return first_number + second_number
