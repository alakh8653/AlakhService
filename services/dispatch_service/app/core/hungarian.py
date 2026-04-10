import math
from typing import Optional


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine formula for distance in km."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))


def hungarian_algorithm(cost_matrix: list[list[float]]) -> list[tuple[int, int]]:
    """
    Hungarian algorithm for optimal assignment. O(n^3).
    Returns list of (row, col) assignments minimizing total cost.
    """
    n = len(cost_matrix)
    if n == 0:
        return []
    m = max(len(row) for row in cost_matrix)
    size = max(n, m)
    INF = float('inf')
    # Dummy rows use 0.0 so column reduction preserves the real row's relative ordering.
    # Dummy cols use INF to prevent real rows from being assigned there.
    C = []
    for i in range(size):
        row = []
        for j in range(size):
            if i < n and j < m:
                row.append(float(cost_matrix[i][j]))
            elif i < n:
                row.append(INF)   # real row, dummy col: forbidden
            else:
                row.append(0.0)   # dummy row: zero cost for any assignment
        C.append(row)

    # Step 1: Row reduction
    for i in range(size):
        finite_vals = [v for v in C[i] if v != INF]
        if not finite_vals:
            continue
        min_val = min(finite_vals)
        C[i] = [v - min_val if v != INF else INF for v in C[i]]

    # Step 2: Column reduction
    for j in range(size):
        min_val = min(C[i][j] for i in range(size))
        if min_val != INF and min_val != 0.0:
            for i in range(size):
                if C[i][j] != INF:
                    C[i][j] -= min_val

    row_to_col = [-1] * size
    col_to_row = [-1] * size

    def try_augment(row: int, visited_cols: set) -> bool:
        for col in range(size):
            if C[row][col] == 0 and col not in visited_cols:
                visited_cols.add(col)
                if col_to_row[col] == -1 or try_augment(col_to_row[col], visited_cols):
                    row_to_col[row] = col
                    col_to_row[col] = row
                    return True
        return False

    while True:
        # Find maximum matching via augmenting paths
        for row in range(size):
            if row_to_col[row] == -1:
                try_augment(row, set())

        if all(row_to_col[i] != -1 for i in range(n)):
            break

        # Minimum line cover via König's theorem:
        # Mark unmatched rows, then propagate alternating paths
        marked_rows: set = set(i for i in range(size) if row_to_col[i] == -1)
        marked_cols: set = set()
        frontier = set(marked_rows)
        while frontier:
            new_cols = set()
            for row in frontier:
                for col in range(size):
                    if C[row][col] == 0 and col not in marked_cols:
                        new_cols.add(col)
            marked_cols |= new_cols
            frontier = set()
            for col in new_cols:
                if col_to_row[col] != -1 and col_to_row[col] not in marked_rows:
                    marked_rows.add(col_to_row[col])
                    frontier.add(col_to_row[col])

        # covered lines = marked cols ∪ unmarked rows
        covered_rows = set(range(size)) - marked_rows
        covered_cols = marked_cols

        min_uncovered = INF
        for i in range(size):
            for j in range(size):
                if i not in covered_rows and j not in covered_cols:
                    if C[i][j] != INF and C[i][j] < min_uncovered:
                        min_uncovered = C[i][j]

        if min_uncovered == INF or min_uncovered == 0:
            break

        for i in range(size):
            for j in range(size):
                if C[i][j] == INF:
                    continue
                if i not in covered_rows and j not in covered_cols:
                    C[i][j] -= min_uncovered
                elif i in covered_rows and j in covered_cols:
                    C[i][j] += min_uncovered

        # Reset matching and retry with updated zeros
        row_to_col = [-1] * size
        col_to_row = [-1] * size

    return [(i, row_to_col[i]) for i in range(n) if row_to_col[i] != -1 and row_to_col[i] < m]
