import numpy as np


def compute_asf(solution: np.ndarray,
                ref_point: np.ndarray,
                weights: np.ndarray) -> float:
    """
    Calcula a Achievement Scalarizing Function (ASF).
    ASF(a, z, w) = max_i (a_i - z_i) / w_i
    Quanto menor o ASF, mais próxima a solução do ponto de referência.

    Usa fallback para pesos muito pequenos.
    """
    solution = np.asarray(solution)
    ref_point = np.asarray(ref_point)
    weights = np.asarray(weights)

    # evita w = 0
    safe_weights = np.where(weights > 1e-9, weights, 1e-9)

    asf_components = (solution - ref_point) / safe_weights
    return np.max(asf_components)