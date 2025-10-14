import numpy as np
from pymoo.core.problem import ElementwiseProblem
from pymoo.algorithms.moo.nsga3 import NSGA3
from pymoo.optimize import minimize
from pymoo.util.ref_dirs import get_reference_directions

# mu, cov, retornos_hist, idx_internacional fornecidos pelo pipeline
class PortfolioProblem(ElementwiseProblem):
    def __init__(self, mu, cov, retornos_hist, idx_internacional, minimo_internacional, horizonte=None, nivel_risco=None):
        self.mu = mu
        self.cov = cov
        self.retornos_hist = retornos_hist   # DataFrame (T x n)
        self.idx_internacional = idx_internacional
        self.minimo_internacional = minimo_internacional
        self.horizonte = horizonte
        self.nivel_risco = nivel_risco
        super().__init__(n_var=len(mu), n_obj=3, n_ieq_constr=1, xl=0.0, xu=1.0)

    def calcular_cvar(self, w, alpha=0.05):
        retornos_p = (self.retornos_hist.values @ w)
        perdas = np.sort(retornos_p)
        k = max(1, int(alpha * len(perdas)))
        return perdas[:k].mean()

    def _evaluate(self, x, out, *args, **kwargs):
        w = np.array(x)
        w = np.maximum(w, 0)
        if w.sum() == 0:
            w = np.ones_like(w) / len(w)
        w = w / w.sum()

        # Ajustes por horizonte (opcional): usar cov ajustada/holding-period
        cov_adj = self.cov.copy()
        if self.horizonte and self.horizonte >= 20:
            cov_adj = cov_adj * 0.5

        # Ajustes por perfil (opcional)
        mu_adj = self.mu.copy()
        if self.nivel_risco == 'baixo':
            mu_adj = mu_adj * 0.9

        retorno = float(np.dot(w, mu_adj))
        variancia = float(w @ cov_adj @ w)
        cvar = float(self.calcular_cvar(w, alpha=0.05))

        f1 = -retorno
        f2 = variancia
        f3 = cvar

        soma_int = float(np.sum(w[self.idx_internacional]))
        g1 = self.minimo_internacional - soma_int  # <=0 ok

        out["F"] = [f1, f2, f3]
        out["G"] = [g1]

# Rodar NSGA-III
ref_dirs = get_reference_directions("das-dennis", 3, n_partitions=12)
algo = NSGA3(pop_size=100, ref_dirs=ref_dirs)
prob = PortfolioProblem(mu, cov, retornos_hist, idx_internacional=[6,7], minimo_internacional=0.10, horizonte=30, nivel_risco='medio')
res = minimize(prob, algo, ('n_gen', 200), seed=42, verbose=True)
# res.F (objetivos), res.X (soluções)
