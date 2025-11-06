# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Test fixture: Large class with multiple large methods.

Used to test semantic chunker's ability to chunk individual methods
when the entire class exceeds token limits. Each method is designed
to be around 1000+ tokens to ensure the class is oversized.
"""


class LargeClass:
    """A class with multiple large methods that together exceed token limits."""

    def method_one(self):
        """Large method one - data processing pipeline."""
        result = 0
        intermediate_data = []
        processed_results = {}

        # First processing stage
        for i in range(500):
            temp_value = i * 2
            temp_value += i**2
            temp_value -= i // 3
            temp_value *= i % 7 + 1
            temp_value += i * 3
            temp_value -= i // 5
            temp_value *= i % 11 + 1
            temp_value += i * 4
            temp_value -= i // 7
            temp_value *= i % 13 + 1
            result += temp_value

            intermediate_data.append({
                "index": i,
                "value": temp_value,
                "squared": temp_value**2,
                "cubed": temp_value**3,
                "metadata": {"iteration": i, "stage": "first", "computed_at": i * 1000},
            })

        # Second processing stage
        for i in range(500):
            if i in processed_results:
                processed_results[i] *= 2
            else:
                processed_results[i] = i * 3

            processed_results[f"key_{i}"] = {
                "primary": i * 10,
                "secondary": i * 20,
                "tertiary": i * 30,
                "nested": {
                    "level1": i,
                    "level2": i**2,
                    "level3": i**3,
                    "level4": {"deep_value": i * 100, "deep_list": list(range(i, i + 20))},
                },
            }

        # Third processing stage
        final_results = []
        for i in range(500):
            combined = intermediate_data[i]["value"] + processed_results.get(i, 0)
            transformed = combined * 2 + combined**2 - combined // 3
            final_results.append({
                "index": i,
                "combined": combined,
                "transformed": transformed,
                "ratios": [transformed / (j + 1) for j in range(20)],
                "products": [transformed * j for j in range(20)],
            })

        return {
            "result": result,
            "intermediate": intermediate_data,
            "processed": processed_results,
            "final": final_results,
        }

    def method_two(self):
        """Large method two - matrix operations."""
        matrix_data = []
        row_sums = []
        col_sums = [0] * 100

        # Build matrix
        for i in range(100):
            row = []
            row_sum = 0
            for j in range(100):
                cell_value = (i * j) + (i**2) + (j**2)
                row.append({
                    "value": cell_value,
                    "row": i,
                    "col": j,
                    "neighbors": {
                        "north": (i - 1, j) if i > 0 else None,
                        "south": (i + 1, j) if i < 99 else None,
                        "east": (i, j + 1) if j < 99 else None,
                        "west": (i, j - 1) if j > 0 else None,
                    },
                    "diagonals": {
                        "nw": (i - 1, j - 1) if i > 0 and j > 0 else None,
                        "ne": (i - 1, j + 1) if i > 0 and j < 99 else None,
                        "sw": (i + 1, j - 1) if i < 99 and j > 0 else None,
                        "se": (i + 1, j + 1) if i < 99 and j < 99 else None,
                    },
                    "computed": {
                        "sum": i + j,
                        "product": i * j,
                        "difference": abs(i - j),
                        "power": (i + 1) ** (j % 3 + 1),
                        "mod": i % (j + 1),
                    },
                })
                row_sum += cell_value
                col_sums[j] += cell_value

            row_sums.append(row_sum)
            matrix_data.append(row)

        # Transform matrix
        transformed_matrix = []
        for i in range(100):
            transformed_row = []
            for j in range(100):
                original_value = matrix_data[i][j]["value"]
                transformed_value = (
                    (original_value * 2) + (row_sums[i] // 100) + (col_sums[j] // 100)
                )
                transformed_row.append({
                    "original": original_value,
                    "transformed": transformed_value,
                    "row_context": row_sums[i],
                    "col_context": col_sums[j],
                    "local_average": (
                        original_value + matrix_data[i - 1][j]["value"]
                        if i > 0
                        else 0 + matrix_data[i + 1][j]["value"]
                        if i < 99
                        else 0 + matrix_data[i][j - 1]["value"]
                        if j > 0
                        else 0 + matrix_data[i][j + 1]["value"]
                        if j < 99
                        else 0
                    )
                    / 5,
                })
            transformed_matrix.append(transformed_row)

        return {
            "matrix": matrix_data,
            "row_sums": row_sums,
            "col_sums": col_sums,
            "transformed": transformed_matrix,
        }

    def method_three(self):
        """Large method three - graph operations."""
        nodes = {}
        edges = []
        graph_metrics = {}

        # Build nodes
        for i in range(300):
            nodes[i] = {
                "id": i,
                "value": i * 10,
                "metadata": {
                    "created_at": i * 1000,
                    "category": "type_" + str(i % 10),
                    "priority": i % 5,
                    "attributes": {
                        "weight": i * 2,
                        "cost": i * 3,
                        "benefit": i * 4,
                        "tags": [f"tag_{j}" for j in range(i % 20)],
                    },
                },
                "neighbors": [],
                "paths": {},
            }

        # Build edges
        for i in range(300):
            for j in range(i + 1, min(i + 20, 300)):
                edge_weight = abs(nodes[i]["value"] - nodes[j]["value"])
                edges.append({
                    "from": i,
                    "to": j,
                    "weight": edge_weight,
                    "metadata": {
                        "type": "directed" if i < j else "undirected",
                        "capacity": edge_weight * 2,
                        "flow": edge_weight // 2,
                        "attributes": {"cost": edge_weight * 3, "benefit": edge_weight * 4},
                    },
                })
                nodes[i]["neighbors"].append(j)
                nodes[j]["neighbors"].append(i)

        # Compute graph metrics
        for i in range(300):
            node_degree = len(nodes[i]["neighbors"])
            node_edges = [e for e in edges if e["from"] == i or e["to"] == i]
            total_edge_weight = sum(e["weight"] for e in node_edges)

            graph_metrics[i] = {
                "degree": node_degree,
                "total_edge_weight": total_edge_weight,
                "average_edge_weight": total_edge_weight / node_degree if node_degree > 0 else 0,
                "centrality": node_degree / 299.0,  # Simple degree centrality
                "connected_categories": list({
                    nodes[neighbor]["metadata"]["category"] for neighbor in nodes[i]["neighbors"]
                }),
            }

        return {
            "nodes": nodes,
            "edges": edges,
            "metrics": graph_metrics,
            "summary": {
                "node_count": len(nodes),
                "edge_count": len(edges),
                "avg_degree": sum(len(n["neighbors"]) for n in nodes.values()) / len(nodes),
            },
        }

    def method_four(self):
        """Large method four - time series analysis."""
        time_series = []
        moving_averages = []
        trends = []

        # Generate time series data
        for i in range(500):
            base_value = 100
            trend = i * 0.5
            seasonal = 20 * (1 if i % 12 < 6 else -1)
            noise = (i * 17) % 30 - 15
            value = base_value + trend + seasonal + noise

            time_series.append({
                "timestamp": i * 1000,
                "value": value,
                "components": {
                    "base": base_value,
                    "trend": trend,
                    "seasonal": seasonal,
                    "noise": noise,
                },
                "metadata": {"period": i // 12, "phase": i % 12, "quarter": (i % 12) // 3},
            })

        # Calculate moving averages
        window_size = 20
        for i in range(len(time_series)):
            if i < window_size:
                window = time_series[0 : i + 1]
            else:
                window = time_series[i - window_size + 1 : i + 1]

            avg_value = sum(point["value"] for point in window) / len(window)
            moving_averages.append({
                "timestamp": time_series[i]["timestamp"],
                "value": avg_value,
                "window_size": len(window),
                "std_dev": (
                    sum((point["value"] - avg_value) ** 2 for point in window) / len(window)
                )
                ** 0.5,
            })

        # Detect trends
        for i in range(20, len(time_series) - 20):
            prev_avg = sum(point["value"] for point in time_series[i - 20 : i]) / 20
            next_avg = sum(point["value"] for point in time_series[i : i + 20]) / 20

            trend_direction = (
                "up"
                if next_avg > prev_avg * 1.05
                else "down"
                if next_avg < prev_avg * 0.95
                else "flat"
            )
            trend_strength = abs(next_avg - prev_avg) / prev_avg if prev_avg != 0 else 0

            trends.append({
                "timestamp": time_series[i]["timestamp"],
                "direction": trend_direction,
                "strength": trend_strength,
                "prev_avg": prev_avg,
                "next_avg": next_avg,
                "change": next_avg - prev_avg,
            })

        return {
            "time_series": time_series,
            "moving_averages": moving_averages,
            "trends": trends,
            "summary": {
                "count": len(time_series),
                "min": min(point["value"] for point in time_series),
                "max": max(point["value"] for point in time_series),
                "avg": sum(point["value"] for point in time_series) / len(time_series),
            },
        }

    def method_five(self):
        """Large method five - text processing pipeline."""
        documents = []
        word_freq = {}
        bigram_freq = {}

        # Generate documents
        words_pool = [f"word{i}" for i in range(100)]
        for i in range(200):
            doc_length = 50 + (i % 50)
            doc_words = [words_pool[(i * 7 + j * 13) % 100] for j in range(doc_length)]

            documents.append({
                "id": i,
                "words": doc_words,
                "length": doc_length,
                "metadata": {
                    "created_at": i * 1000,
                    "category": f"category_{i % 10}",
                    "author": f"author_{i % 20}",
                    "tags": [f"tag_{j}" for j in range(i % 10)],
                },
                "statistics": {
                    "unique_words": len(set(doc_words)),
                    "avg_word_length": sum(len(w) for w in doc_words) / len(doc_words),
                    "longest_word": max(doc_words, key=len),
                },
            })

            # Update word frequencies
            for word in doc_words:
                if word in word_freq:
                    word_freq[word]["count"] += 1
                    word_freq[word]["documents"].add(i)
                else:
                    word_freq[word] = {"count": 1, "documents": {i}}

            # Update bigram frequencies
            for j in range(len(doc_words) - 1):
                bigram = (doc_words[j], doc_words[j + 1])
                if bigram in bigram_freq:
                    bigram_freq[bigram] += 1
                else:
                    bigram_freq[bigram] = 1

        # Calculate TF-IDF scores
        num_docs = len(documents)
        tfidf_scores = {}
        for word, freq_data in word_freq.items():
            df = len(freq_data["documents"])
            idf = (num_docs / df) if df > 0 else 0
            tfidf_scores[word] = {
                "tf": freq_data["count"],
                "df": df,
                "idf": idf,
                "tfidf": freq_data["count"] * idf,
            }

        return {
            "documents": documents,
            "word_freq": {
                k: {"count": v["count"], "doc_count": len(v["documents"])}
                for k, v in word_freq.items()
            },
            "bigram_freq": bigram_freq,
            "tfidf": tfidf_scores,
            "summary": {
                "doc_count": len(documents),
                "unique_words": len(word_freq),
                "unique_bigrams": len(bigram_freq),
                "avg_doc_length": sum(doc["length"] for doc in documents) / len(documents),
            },
        }
