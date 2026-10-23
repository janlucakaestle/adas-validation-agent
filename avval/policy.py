"""The system under test: a small learned ACC policy (a demonstrator, not a production stack).

A 32x32 MLP is behaviour-cloned from a synthetic expert controller (the Intelligent Driver
Model) on synthetic 'nominal driving' states: ordinary highway following. It takes four
ground-truth scalars (gap, speed, relative speed, set speed) and outputs an acceleration.
It has no perception, sensor noise, temporal memory, uncertainty estimate, lateral
behaviour or runtime out-of-distribution handling, so results obtained with it do not
transfer directly to production learned ADAS stacks. It is a testbed for the validation
method: like any learned model it is only as good as its training distribution, and harsh
closing speeds and very short gaps are rare in its training data.

Reproducibility: simulation results depend only on the serialised weights
(`results/policy.json`, hashed into the release ID). Re-training (`train_policy`) is
deterministic for a given seed and library versions, but bit-identical weights across
scikit-learn / NumPy versions or platforms are not guaranteed; `results/policy_meta.json`
records the training recipe and versions used.

Inference is a plain-numpy forward pass so a simulation step costs microseconds.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np
from sklearn.neural_network import MLPRegressor

from . import ROOT

# Expert/training clip only. The runtime actuator authority is release configuration
# (config/sim.yaml `ego`), applied by the simulator.
TRAIN_ACCEL_MIN, TRAIN_ACCEL_MAX = -3.5, 2.0
# The policy is a release input, so it never moves with AVVAL_RESULTS_DIR.
POLICY_PATH = ROOT / "results" / "policy.json"
POLICY_META_PATH = ROOT / "results" / "policy_meta.json"


def idm_expert(gap, v, rel_v, v_set, a=1.5, b=2.0, time_gap=1.5, s0=2.0,
               accel_min=TRAIN_ACCEL_MIN, accel_max=TRAIN_ACCEL_MAX):
    """Intelligent Driver Model; rel_v = v_lead - v_ego (negative when closing)."""
    gap = np.maximum(gap, 0.1)
    s_star = s0 + np.maximum(0.0, v * time_gap - v * rel_v / (2 * np.sqrt(a * b)))
    acc = a * (1 - (v / np.maximum(v_set, 1.0)) ** 4 - (s_star / gap) ** 2)
    return np.clip(acc, accel_min, accel_max)


def nominal_driving_states(n: int, rng: np.random.Generator) -> np.ndarray:
    """Training distribution: everyday following, few harsh situations."""
    v = rng.uniform(8, 36, n)
    v_set = np.minimum(v + rng.uniform(0, 5, n), 38)
    gap = rng.gamma(shape=4.0, scale=v * 0.45 + 2)  # mostly 1-2.5 s headway
    rel_v = np.clip(rng.normal(0.0, 1.8, n), -6.0, 4.0)
    return np.column_stack([gap, v, rel_v, v_set])


@dataclass
class LearnedACC:
    weights: list[np.ndarray]
    biases: list[np.ndarray]
    x_mean: np.ndarray
    x_std: np.ndarray

    def act(self, gap: float, v: float, rel_v: float, v_set: float,
            accel_min: float = TRAIN_ACCEL_MIN, accel_max: float = TRAIN_ACCEL_MAX) -> float:
        """Commanded acceleration, clipped to the actuator authority [accel_min, accel_max].
        Outputs below the training clip are extrapolation: the expert never produced them."""
        h = (np.array([gap, v, rel_v, v_set]) - self.x_mean) / self.x_std
        for i, (w, b) in enumerate(zip(self.weights, self.biases)):
            h = h @ w + b
            if i < len(self.weights) - 1:
                h = np.maximum(h, 0.0)
        return float(min(max(h[0], accel_min), accel_max))

    def to_json(self) -> str:
        """Canonical serialisation: the exact contents of `policy.json` (and what gets hashed)."""
        return json.dumps({
            "weights": [w.tolist() for w in self.weights],
            "biases": [b.tolist() for b in self.biases],
            "x_mean": self.x_mean.tolist(),
            "x_std": self.x_std.tolist(),
        })

    def save(self, path=POLICY_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.to_json().encode())

    @classmethod
    def load(cls, path=POLICY_PATH) -> "LearnedACC":
        if not path.exists():
            raise FileNotFoundError(f"{path} not found - run `python -m avval.cli train` first")
        blob = json.loads(path.read_text())
        return cls(
            [np.array(w) for w in blob["weights"]],
            [np.array(b) for b in blob["biases"]],
            np.array(blob["x_mean"]),
            np.array(blob["x_std"]),
        )


def train_policy(n_samples: int = 40_000, seed: int = 0,
                 accel_min: float = TRAIN_ACCEL_MIN) -> tuple[LearnedACC, dict]:
    """Behaviour-clone the IDM expert. `accel_min` sets the expert's braking clip, so a
    policy can be trained for a different actuator authority (sensitivity analysis)."""
    rng = np.random.default_rng(seed)
    X = nominal_driving_states(n_samples, rng)
    y = idm_expert(*X.T, accel_min=accel_min)
    x_mean, x_std = X.mean(0), X.std(0)
    Xn = (X - x_mean) / x_std
    mlp = MLPRegressor(hidden_layer_sizes=(32, 32), max_iter=200, early_stopping=True,
                       random_state=seed)
    mlp.fit(Xn, y)
    # Held-out error on the nominal distribution vs. a harsher, out-of-distribution one.
    X_test = nominal_driving_states(5_000, rng)
    mae_nominal = float(np.mean(np.abs(mlp.predict((X_test - x_mean) / x_std)
                                       - idm_expert(*X_test.T, accel_min=accel_min))))
    X_ood = X_test.copy()
    X_ood[:, 0] = rng.uniform(5, 30, len(X_ood))
    X_ood[:, 2] = rng.uniform(-12, -6, len(X_ood))
    mae_ood = float(np.mean(np.abs(mlp.predict((X_ood - x_mean) / x_std)
                                   - idm_expert(*X_ood.T, accel_min=accel_min))))
    policy = LearnedACC([w.copy() for w in mlp.coefs_], [b.copy() for b in mlp.intercepts_],
                        x_mean, x_std)
    from .provenance import runtime_fingerprint
    meta = {"recipe": {"n_samples": n_samples, "seed": seed, "accel_min": accel_min,
                       "hidden_layer_sizes": [32, 32], "max_iter": 200,
                       "early_stopping": True, "expert": "IDM(a=1.5, b=2.0, T=1.5, s0=2.0)"},
            "runtime": runtime_fingerprint(),
            "mae_nominal": mae_nominal, "mae_out_of_distribution": mae_ood}
    return policy, meta
