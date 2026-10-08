"""Command-line adapter for the published MCount single-image algorithm.

Algorithm source:
  https://github.com/hyu-kim/mcount
  Codes/Codes for single image.ipynb, commit
  04dd394523f2528d914295c5b266b4abfaf424ee

The upstream project is MIT licensed. This file preserves the upstream
algorithm and only turns the notebook cell into a non-interactive CLI.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import cv2
import numpy as np
from scipy import optimize
from scipy.ndimage import maximum_filter
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import lil_matrix


def find_maxima(img: np.ndarray):
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    sub_opening = cv2.morphologyEx(img, cv2.MORPH_OPEN, kernel, iterations=2)
    dist = cv2.distanceTransform(sub_opening, cv2.DIST_L2, 3)
    maxima = (dist > 0) * (dist == maximum_filter(dist, 3, mode="constant", cval=math.inf))
    res = np.where(1 == maxima)
    centroids = list(map(list, zip(list(res[1]), list(res[0]), list(dist[res]))))
    return len(centroids), maxima, centroids, dist


def distance(cnt_i, cnt_j, cnt_k):
    x1, y1 = cnt_i[0][0], cnt_i[0][1]
    line_start_x, line_start_y = cnt_j[0][0], cnt_j[0][1]
    x2, y2 = cnt_k[0][0], cnt_k[0][1]
    array_longi = np.array([x2 - x1, y2 - y1])
    denominator = array_longi.dot(array_longi)
    if denominator == 0:
        return 0.0
    array_trans = np.array([x2 - line_start_x, y2 - line_start_y])
    array_temp = float(array_trans.dot(array_longi)) / denominator
    array_temp = array_longi.dot(array_temp)
    return np.sqrt((array_trans - array_temp).dot(array_trans - array_temp))


def clockwise_angle(v1, v2):
    x1, y1 = v1
    x2, y2 = v2
    return np.arctan2(x1 * y2 - x2 * y1, x1 * x2 + y1 * y2)


def calc_r(x, y, xc, yc):
    return np.sqrt((x - xc) ** 2 + (y - yc) ** 2)


def circle_residual(c, x, y):
    radii = calc_r(x, y, *c)
    return radii - radii.mean()


def leastsq_circle(x, y):
    center_estimate = np.mean(x), np.mean(y)
    center, _ = optimize.leastsq(circle_residual, center_estimate, args=(x, y))
    xc, yc = center
    radii = calc_r(x, y, *center)
    radius = radii.mean()
    residual = np.sum((radii - radius) ** 2)
    return int(xc), int(yc), radius, residual


def seg_counting(labels, label_id, d_threshold, lam):
    img_component = np.uint8(255 * (labels == label_id))
    count, maxima, centroids, dist = find_maxima(img_component)
    contours, _ = cv2.findContours(img_component, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)
    contours_split = []
    for contour in contours:
        if len(contour) < 2:
            continue
        turning_points = [contour[0]]
        i, k = 0, 2
        while k < len(contour):
            distance_max, index = 0, 0
            for j in range(i + 1, k):
                candidate_distance = distance(contour[i], contour[j], contour[k])
                if candidate_distance > distance_max:
                    distance_max, index = candidate_distance, j
            if distance_max > d_threshold:
                turning_points = np.append(turning_points, [contour[index]], axis=0)
                i, k = index, index + 2
            else:
                k += 1

        concave_points = [turning_points[0]]
        for index in range(len(turning_points) - 2):
            angle = clockwise_angle(
                [
                    turning_points[index + 1][0][0] - turning_points[index][0][0],
                    turning_points[index + 1][0][1] - turning_points[index][0][1],
                ],
                [
                    turning_points[index + 2][0][0] - turning_points[index + 1][0][0],
                    turning_points[index + 2][0][1] - turning_points[index + 1][0][1],
                ],
            ) / math.pi * 180
            if angle > 0:
                concave_points = np.append(concave_points, [turning_points[index + 1]], axis=0)

        contour_indexes = []
        point_index = 0
        for index in range(len(contour)):
            x, y = concave_points[point_index][0][0], concave_points[point_index][0][1]
            x_now, y_now = contour[index][0][0], contour[index][0][1]
            if x == x_now and y == y_now:
                contour_indexes.append(index)
                point_index += 1
            if point_index == len(concave_points):
                break
        if not contour_indexes:
            continue
        contours_split.extend([[contour[contour_indexes[x]:contour_indexes[x + 1]]] for x in range(len(contour_indexes) - 1)])
        contours_split.append([contour[contour_indexes[-1]:]])

    for split in contours_split:
        x = [point[0][0] for point in split[0]]
        y = [point[0][1] for point in split[0]]
        if len(x) <= 3:
            continue
        xc, yc, _, _ = leastsq_circle(x, y)
        y_max, x_max = maxima.shape
        if 0 <= yc < y_max and 0 <= xc < x_max and img_component[yc][xc] > 0 and dist[yc][xc] > 0:
            count += 1 - int(maxima[yc][xc])
            maxima[yc][xc] = 1
            centroids.append((xc, yc, dist[yc][xc]))

    if count == 0 or not contours_split:
        return 0, "Not Solved"

    distances = np.zeros((len(contours_split), count))
    for i, split in enumerate(contours_split):
        for j in range(count):
            for point in split[0]:
                distances[i][j] += abs(
                    math.dist([point[0][0], point[0][1]], [centroids[j][0], centroids[j][1]]) - centroids[j][2]
                )

    result = solve_assignment(distances, lam)
    return int(np.rint(result.x[distances.size:]).sum()), "Optimal"


def solve_assignment(distances, lam):
    # Same binary optimization model as the upstream PuLP/COIN_CMD notebook,
    # solved by SciPy's bundled HiGHS backend so it works on ARM64 without a
    # system-wide solver installation.
    contour_count, count = distances.shape
    x_count = contour_count * count
    variable_count = x_count + count
    objective = np.append(distances.flatten(), np.full(count, lam))
    constraint_count = contour_count + count + x_count
    matrix = lil_matrix((constraint_count, variable_count), dtype=float)
    lower = np.full(constraint_count, -np.inf)
    upper = np.full(constraint_count, np.inf)
    for i in range(contour_count):
        matrix[i, i * count:(i + 1) * count] = 1
        lower[i] = upper[i] = 1
    for j in range(count):
        first_row = contour_count + j
        for i in range(contour_count):
            matrix[first_row, i * count + j] = 1
            # x_ij <= y_j is equivalent for integer centre choices, but
            # gives a tighter relaxation than sum(x_ij) <= M*y_j.
            second_row = contour_count + count + i * count + j
            matrix[second_row, i * count + j] = 1
            matrix[second_row, x_count + j] = -1
            upper[second_row] = 0
        matrix[first_row, x_count + j] = -1
        lower[first_row] = 0
    result = milp(
        c=objective,
        # For fixed binary centre choices, the assignment constraints form a
        # transportation polytope with integral bounds. Continuous assignments
        # therefore have an integral optimum; only centre choices need MILP.
        integrality=np.concatenate((np.zeros(x_count), np.ones(count))),
        bounds=Bounds(np.zeros(variable_count), np.ones(variable_count)),
        constraints=LinearConstraint(matrix.tocsr(), lower, upper),
        options={"disp": False},
    )
    if not result.success or result.x is None:
        raise RuntimeError(f"MCount solver did not reach an optimal result: {result.message}")
    return result


def count_image(path: Path, d_threshold: float, lam: float):
    image = cv2.imread(str(path))
    if image is None:
        raise ValueError(f"Unable to read image: {path}")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    otsu_threshold, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_OTSU)
    num_labels, labels, _, _ = cv2.connectedComponentsWithStats(binary)
    total = 0
    solver_statuses = []
    for label_id in range(1, num_labels):
        component_count, solver_status = seg_counting(labels, label_id, d_threshold, lam)
        total += component_count
        solver_statuses.append(solver_status)
    return total, otsu_threshold, num_labels - 1, solver_statuses


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the published MCount single-image algorithm")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--lambda", dest="lam", type=float, default=30.0)
    parser.add_argument("--d", dest="d_threshold", type=float, default=0.5)
    args = parser.parse_args()
    started = time.monotonic()
    count, otsu_threshold, components, solver_statuses = count_image(args.input, args.d_threshold, args.lam)
    print(json.dumps({
        "backend": "mcount",
        "status": "ok",
        "count": count,
        "duration_seconds": round(time.monotonic() - started, 3),
        "lambda": args.lam,
        "d": args.d_threshold,
        "otsu_threshold": otsu_threshold,
        "connected_components": components,
        "solver_statuses": solver_statuses,
        "source_commit": "04dd394523f2528d914295c5b266b4abfaf424ee",
    }, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
