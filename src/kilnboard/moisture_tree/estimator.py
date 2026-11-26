from dataclasses import dataclass
import numpy as np

from .contracts import LearningRow, Probe


@dataclass(frozen=True)
class Split:
    average: float
    support: int
    coordinate: int = -1
    boundary: float = 0.0
    left: 'Split | None' = None
    right: 'Split | None' = None

    def trace(self, data: tuple[float, ...]) -> float:
        branch = self
        while branch.left is not None and branch.right is not None:
            branch = branch.left if data[branch.coordinate] <= branch.boundary else branch.right
        return branch.average

    def conditions(self, path=()) -> list:
        if self.left is None or self.right is None:
            return [{'splits': list(path), 'expected_moisture': self.average, 'support': self.support}]
        branch = (self.coordinate,self.boundary)
        return self.left.conditions((*path, (*branch, '<='))) + self.right.conditions((*path, (*branch, '>')))


def gain(y: np.ndarray) -> float:
    return float(np.sum((y-np.mean(y))**2))


def cut(x: np.ndarray, y: np.ndarray, depth: int, max_depth: int) -> Split:
    location = float(np.mean(y))
    if depth >= max_depth or len(y) < 16 or gain(y) < .3:
        return Split(location, len(y))
    choose = None
    best = gain(y) * .955
    for axis, column in enumerate(x.T):
        for boundary in np.unique(np.quantile(column, [.15,.29,.43,.56,.70,.84])):
            left = column <= boundary
            if left.sum() < 7 or (~left).sum() < 7:
                continue
            after = gain(y[left]) + gain(y[~left])
            if after < best:
                best, choose = after, (axis, float(boundary), left)
    if choose is None:
        return Split(location, len(y))
    axis, boundary, left = choose
    return Split(location, len(y), axis, boundary, cut(x[left], y[left], depth+1,max_depth),
                 cut(x[~left], y[~left], depth+1,max_depth))


@dataclass(frozen=True)
class BoardMoisture:
    tree: Split
    depth: int
    floor: float

    def predict(self, probe: Probe) -> float:
        rough = self.tree.trace(probe.standard)
        return max(self.floor, rough)

    def describe(self) -> dict:
        return {'depth': self.depth, 'regimes': self.tree.conditions(), 'moisture_floor': self.floor}


def fit_estimator(rows: tuple[LearningRow, ...]) -> BoardMoisture:
    x = np.asarray([r.probe.standard for r in rows])
    y = np.asarray([r.outcome for r in rows])
    boundary = max(10, int(len(rows)*.77))
    scores = []
    for depth in (2,3,4,5):
        tree = cut(x[:boundary], y[:boundary], 0, depth)
        errors = [abs(measurement-tree.trace(tuple(sample))) for sample,measurement in zip(x[boundary:],y[boundary:])]
        scores.append((float(np.mean(errors)) + depth*.018, depth))
    _, depth = min(scores)
    return BoardMoisture(cut(x, y, 0, depth), depth, max(0,float(np.min(y))*.85))
