# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Test fixture: Large class with multiple large methods.

Used to test semantic chunker's ability to chunk individual methods
when the entire class exceeds token limits.
"""


class LargeClass:
    """A class with multiple large methods."""

    def method_one(self):
        """Large method one."""
        result = 0
        for i in range(1000):
            result += i * 2
            result -= i // 2
            result *= i % 3 + 1
            result += i ** 2
            result -= i // 3
            result *= i % 5 + 1
            result += i * 3
            result -= i // 4
            result *= i % 7 + 1
            result += i * 4
            result -= i // 5
            result *= i % 11 + 1
            result += i * 5
            result -= i // 6
            result *= i % 13 + 1
        return result

    def method_two(self):
        """Large method two."""
        data = []
        for i in range(1000):
            data.append({
                "id": i,
                "value": i * 2,
                "computed": i ** 2,
                "nested": {
                    "inner_id": i * 3,
                    "inner_value": i ** 3,
                    "deep": {
                        "level": i,
                        "data": [j for j in range(i, i + 10)]
                    }
                },
                "list_data": [k * i for k in range(20)],
                "more_data": {
                    "x": i * 4,
                    "y": i * 5,
                    "z": i * 6
                }
            })
        return data

    def method_three(self):
        """Large method three."""
        mapping = {}
        for i in range(1000):
            mapping[f"key_{i}"] = {
                "data": [j for j in range(i, i + 10)],
                "meta": {"index": i, "active": True},
                "computed": [
                    {"val": j * 2, "squared": j ** 2}
                    for j in range(i, i + 5)
                ],
                "nested_map": {
                    f"inner_{k}": {"value": k * i, "doubled": k * i * 2}
                    for k in range(10)
                },
                "list_of_lists": [
                    [m * n for m in range(5)]
                    for n in range(i, i + 3)
                ]
            }
        return mapping

    def method_four(self):
        """Large method four."""
        results = []
        for i in range(1000):
            temp = i
            temp = temp * 2 + 1
            temp = temp ** 2 - temp
            temp = temp // 3 + temp % 7
            temp = temp * temp - i
            temp = temp + i ** 2
            temp = temp // (i + 1)
            temp = temp * 3 + i
            temp = temp - i ** 2 // 2
            temp = temp % 1000
            results.append({
                "index": i,
                "result": temp,
                "intermediate": [
                    temp * j for j in range(1, 11)
                ],
                "transformed": {
                    "doubled": temp * 2,
                    "tripled": temp * 3,
                    "squared": temp ** 2
                }
            })
        return results

    def method_five(self):
        """Large method five."""
        matrix = []
        for i in range(100):
            row = []
            for j in range(100):
                cell_value = i * j
                cell_data = {
                    "row": i,
                    "col": j,
                    "value": cell_value,
                    "neighbors": [
                        (i - 1, j), (i + 1, j),
                        (i, j - 1), (i, j + 1)
                    ],
                    "diagonals": [
                        (i - 1, j - 1), (i - 1, j + 1),
                        (i + 1, j - 1), (i + 1, j + 1)
                    ],
                    "computed": {
                        "sum": i + j,
                        "product": i * j,
                        "difference": abs(i - j),
                        "power": (i + 1) ** (j % 3 + 1)
                    }
                }
                row.append(cell_data)
            matrix.append(row)
        return matrix
