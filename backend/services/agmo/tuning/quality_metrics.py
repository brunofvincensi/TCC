"""
Métricas de Qualidade para Avaliação de Fronteiras de Pareto

Este módulo implementa métricas para avaliar a qualidade das soluções
obtidas por algoritmos multiobjetivo, essenciais para determinar a
convergência e comparar diferentes configurações de hiperparâmetros.

Métricas Implementadas:
- Hypervolume (HV): Volume coberto pela fronteira de Pareto
- Spread: Distribuição/diversidade das soluções
- Spacing: Uniformidade da distribuição
- Number of Pareto Solutions: Quantidade de soluções não-dominadas
"""

import numpy as np
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class QualityMetrics:
    """
    Classe para cálculo de métricas de qualidade de fronteiras de Pareto.
    """

    def __init__(self, reference_point: Optional[np.ndarray] = None):
        """
        Inicializa o calculador de métricas.

        Args:
            reference_point: Ponto de referência para cálculo de Hypervolume.
                           Se None, será calculado automaticamente.
        """
        self.reference_point = reference_point

    def calculate_hypervolume(self, pareto_front: np.ndarray,
                              ideal_point: Optional[np.ndarray] = None) -> float:
        """
        Calcula o Hypervolume da fronteira de Pareto.

        O Hypervolume mede o volume do espaço de objetivos dominado pela
        fronteira de Pareto. Valores maiores indicam melhor qualidade.

        COMPORTAMENTO CORRETO PARA MINIMIZAÇÃO:
        - Quanto MENORES os valores das soluções, MAIOR o hypervolume
        - HV deve CRESCER ao longo das gerações conforme o algoritmo melhora
        - Ponto de referência fixo representa o pior caso possível

        Args:
            pareto_front: Array (n_solutions, n_objectives) com objetivos

        Returns:
            Valor do hypervolume (maior = melhor qualidade)
        """
        if len(pareto_front) == 0:
            return 0.0

        # Verifica valores inválidos
        if np.any(np.isnan(pareto_front)) or np.any(np.isinf(pareto_front)):
            logger.warning("Fronteira de Pareto contém valores NaN ou Inf. Hypervolume = 0.")
            return 0.0

        # Se não há ponto de referência, usa o pior valor em cada objetivo + margem
        if self.reference_point is None:
            # Usa max + 10% de margem, mas garante um valor mínimo
            max_values = np.max(pareto_front, axis=0)
            ref_point = np.maximum(max_values * 1.1, max_values + 0.1)

            logger.debug(f"Ponto de referência calculado: {ref_point}")
        else:
            ref_point = self.reference_point

        # Para 3 objetivos, usa método de Monte Carlo simplificado
        if pareto_front.shape[1] == 3:
            return self._hypervolume_monte_carlo(pareto_front, ref_point, ideal_point)
        else:
            # Para outros casos, usa aproximação por dominância
            return self._hypervolume_dominated_space(pareto_front, ref_point, ideal_point)

    def _hypervolume_monte_carlo(self, pareto_front: np.ndarray,
                                  ref_point: np.ndarray,
                                  ideal_point: Optional[np.ndarray] = None,
                                  n_samples: int = 10000) -> float:
        """
        Calcula Hypervolume usando Monte Carlo sampling.

        Para minimização: HV mede o volume ENTRE as soluções e o ponto de referência (pior).
        Quanto MENORES os valores das soluções, MAIOR o hypervolume.

        Args:
            pareto_front: Fronteira de Pareto
            ref_point: Ponto de referência (pior caso - valores altos)
            ideal_point: Ponto ideal (melhor caso - valores baixos). Se None, usa min da fronteira.
            n_samples: Número de amostras para Monte Carlo

        Returns:
            Estimativa do hypervolume
        """
        # Usa ideal_point passado, ou min da fronteira atual como fallback
        if ideal_point is None:
            ideal_point = np.min(pareto_front, axis=0)
            logger.debug(f"Ideal point não fornecido, usando min da fronteira: {ideal_point}")
        else:
            logger.debug(f"Usando ideal point GLOBAL fornecido: {ideal_point}")

        # Verifica se o ponto de referência é válido
        dimensions = ref_point - ideal_point
        if np.any(dimensions <= 0):
            logger.warning(f"Dimensões inválidas para hypervolume: {dimensions}")
            logger.warning(f"Ideal point: {ideal_point}, Ref point: {ref_point}")
            return 0.0

        # Volume total da caixa de referência (FIXA - não muda com as soluções)
        box_volume = np.prod(dimensions)
        logger.debug(f"Box volume (FIXO): {box_volume:.6e}, Dimensions: {dimensions}")

        # Gera pontos aleatórios na caixa FIXA
        random_points = np.random.uniform(
            low=ideal_point,    # Ponto ideal (0,0,0) - FIXO
            high=ref_point,     # Ponto de referência (pior caso) - FIXO
            size=(n_samples, pareto_front.shape[1])
        )

        # Conta quantos pontos são dominados por alguma solução da fronteira
        # Quanto MELHORES as soluções (valores menores), MAIS pontos elas dominam
        dominated_count = 0
        for point in random_points:
            # Um ponto é dominado se existe alguma solução que é melhor em todos os objetivos
            if self._is_dominated_by_front(point, pareto_front):
                dominated_count += 1

        # Hypervolume é a fração de pontos dominados vezes o volume total
        # Soluções melhores (menores) → dominam mais pontos → HV maior ✅
        hypervolume = (dominated_count / n_samples) * box_volume

        logger.debug(f"Dominated points: {dominated_count}/{n_samples} ({100*dominated_count/n_samples:.1f}%)")
        logger.debug(f"HV = {hypervolume:.6e} (quanto maior, melhor a fronteira)")

        return hypervolume

    def _is_dominated_by_front(self, point: np.ndarray, front: np.ndarray) -> bool:
        """
        Verifica se um ponto é dominado por alguma solução da fronteira.

        Args:
            point: Ponto a verificar
            front: Fronteira de Pareto

        Returns:
            True se o ponto é dominado
        """
        # Para minimização: uma solução domina se é menor ou igual em todos objetivos
        # e estritamente menor em pelo menos um
        for solution in front:
            if np.all(solution <= point) and np.any(solution < point):
                return True
        return False

    def _hypervolume_dominated_space(self, pareto_front: np.ndarray,
                                     ref_point: np.ndarray,
                                     ideal_point: Optional[np.ndarray] = None) -> float:
        """
        Aproximação simplificada do hypervolume baseada em espaço dominado.

        Para minimização: calcula o volume entre cada solução e o ponto de referência.
        Quanto menores as soluções, maior o hypervolume.

        Args:
            pareto_front: Fronteira de Pareto
            ref_point: Ponto de referência (pior caso)
            ideal_point: Não usado neste método (mantido para consistência de API)

        Returns:
            Aproximação do hypervolume
        """
        # Soma dos volumes individuais (superestimativa devido a sobreposições)
        # Cada solução contribui com o volume entre ela e o ponto de referência
        total_volume = 0.0
        for solution in pareto_front:
            # Volume da caixa entre a solução e o ponto de referência
            # Quanto menor a solução, maior o volume → HV maior ✅
            dimensions = ref_point - solution
            if np.all(dimensions > 0):
                volume = np.prod(dimensions)
                total_volume += volume
            else:
                # Solução está fora do espaço de referência (pior que ref_point)
                logger.warning(f"Solução fora do espaço: {solution} (ref: {ref_point})")

        # Normaliza pelo número de soluções para evitar viés
        avg_volume = total_volume / len(pareto_front) if len(pareto_front) > 0 else 0.0

        logger.debug(f"HV aproximado = {avg_volume:.6e} (média de {len(pareto_front)} soluções)")

        return avg_volume

    def calculate_spread(self, pareto_front: np.ndarray) -> float:
        """
        Calcula o Spread (diversidade) da fronteira de Pareto.

        O Spread mede a extensão da fronteira e a distribuição das soluções.
        Valores menores indicam melhor distribuição.

        Baseado na métrica proposta por Deb et al. (2002) para NSGA-II.

        Args:
            pareto_front: Array (n_solutions, n_objectives)

        Returns:
            Valor do spread (0 = perfeito, maior = pior distribuição)
        """
        if len(pareto_front) < 2:
            return float('inf')

        n_objectives = pareto_front.shape[1]

        # Normaliza os objetivos para [0, 1]
        normalized_front = self._normalize_front(pareto_front)

        # Encontra soluções extremas (melhores em cada objetivo)
        extreme_solutions = []
        for obj_idx in range(n_objectives):
            extreme_idx = np.argmin(normalized_front[:, obj_idx])
            extreme_solutions.append(normalized_front[extreme_idx])

        # Calcula distâncias entre soluções consecutivas
        # Ordena pela primeira dimensão para ter uma sequência
        sorted_indices = np.argsort(normalized_front[:, 0])
        sorted_front = normalized_front[sorted_indices]

        distances = []
        for i in range(len(sorted_front) - 1):
            dist = np.linalg.norm(sorted_front[i+1] - sorted_front[i])
            distances.append(dist)

        if len(distances) == 0:
            return 0.0

        # Distância média
        d_mean = np.mean(distances)

        # Distâncias extremas (do primeiro/último ao ponto extremo ideal)
        d_first = np.linalg.norm(sorted_front[0] - extreme_solutions[0])
        d_last = np.linalg.norm(sorted_front[-1] - extreme_solutions[-1])

        # Spread metric
        numerator = d_first + d_last + np.sum(np.abs(np.array(distances) - d_mean))
        denominator = d_first + d_last + (len(distances) * d_mean)

        spread = numerator / denominator if denominator > 0 else 0.0

        return spread

    def calculate_spacing(self, pareto_front: np.ndarray) -> float:
        """
        Calcula o Spacing (uniformidade) da fronteira de Pareto.

        O Spacing mede a uniformidade da distribuição das soluções.
        Valores menores indicam distribuição mais uniforme.

        Args:
            pareto_front: Array (n_solutions, n_objectives)

        Returns:
            Valor do spacing (0 = perfeitamente uniforme)
        """
        if len(pareto_front) < 2:
            return 0.0

        # Para cada solução, encontra a distância ao vizinho mais próximo
        min_distances = []
        for i, solution in enumerate(pareto_front):
            distances_to_others = []
            for j, other_solution in enumerate(pareto_front):
                if i != j:
                    dist = np.linalg.norm(solution - other_solution)
                    distances_to_others.append(dist)

            if distances_to_others:
                min_distances.append(min(distances_to_others))

        # Spacing é o desvio padrão das distâncias mínimas
        spacing = np.std(min_distances) if min_distances else 0.0

        return spacing

    def calculate_pareto_size(self, pareto_front: np.ndarray) -> int:
        """
        Retorna o número de soluções na fronteira de Pareto.

        Args:
            pareto_front: Array (n_solutions, n_objectives)

        Returns:
            Número de soluções
        """
        return len(pareto_front)

    def calculate_all_metrics(self, pareto_front: np.ndarray,
                              ideal_point: Optional[np.ndarray] = None) -> dict:
        """
        Calcula todas as métricas de qualidade.

        Args:
            pareto_front: Array (n_solutions, n_objectives)
            ideal_point: Ponto ideal para cálculo de hypervolume

        Returns:
            Dicionário com todas as métricas
        """
        metrics = {
            'hypervolume': self.calculate_hypervolume(pareto_front, ideal_point),
            'spread': self.calculate_spread(pareto_front),
            'spacing': self.calculate_spacing(pareto_front),
            'pareto_size': self.calculate_pareto_size(pareto_front),
        }

        return metrics

    def _normalize_front(self, pareto_front: np.ndarray) -> np.ndarray:
        """
        Normaliza a fronteira de Pareto para [0, 1] em cada objetivo.

        Args:
            pareto_front: Fronteira original

        Returns:
            Fronteira normalizada
        """
        min_vals = np.min(pareto_front, axis=0)
        max_vals = np.max(pareto_front, axis=0)

        # Evita divisão por zero
        ranges = max_vals - min_vals
        ranges[ranges == 0] = 1.0

        normalized = (pareto_front - min_vals) / ranges

        return normalized


class ConvergenceTracker:
    """
    Rastreia a convergência do algoritmo ao longo das gerações.
    """

    def __init__(self, reference_point: Optional[np.ndarray] = None):
        """
        Inicializa o rastreador.

        Args:
            reference_point: Ponto de referência fixo para cálculo de hypervolume.
                           Se None, será determinado na primeira geração.
        """
        self.history = {
            'generation': [],
            'hypervolume': [],
            'spread': [],
            'spacing': [],
            'pareto_size': [],
            'best_fitness': [],
        }
        self.reference_point = reference_point
        self.reference_point_set = reference_point is not None
        self.ideal_point = None  # Melhores valores já vistos (global)
        self.ideal_point_set = False
        self.metrics_calculator = QualityMetrics(reference_point=reference_point)

    def update(self, generation: int, pareto_front: np.ndarray,
               population_fitness: np.ndarray):
        """
        Atualiza as métricas para a geração atual.

        Args:
            generation: Número da geração
            pareto_front: Fronteira de Pareto atual
            population_fitness: Fitness de toda a população
        """
        # Define ponto de referência fixo na primeira geração (PIOR CASO)
        if not self.reference_point_set and len(pareto_front) > 0:
            max_values = np.max(pareto_front, axis=0)
            self.reference_point = np.maximum(max_values * 1.5, max_values + 1.0)
            self.metrics_calculator.reference_point = self.reference_point
            self.reference_point_set = True

            logger.info(f"📍 Ponto de referência FIXO (nadir/pior caso): {self.reference_point}")
            logger.info(f"   Baseado em max da geração 0: {max_values}")

        # Atualiza ponto ideal GLOBAL (MELHOR CASO acumulado de todas as gerações)
        if len(pareto_front) > 0:
            min_values = np.min(pareto_front, axis=0)

            if not self.ideal_point_set:
                # Primeira geração: inicializa ideal point
                self.ideal_point = min_values.copy()
                self.ideal_point_set = True
                logger.info(f"🎯 Ponto ideal INICIAL (melhor caso gen 0): {self.ideal_point}")
            else:
                # Atualiza ideal point com os MELHORES valores já vistos
                # Em minimização: min é melhor
                old_ideal = self.ideal_point.copy()
                self.ideal_point = np.minimum(self.ideal_point, min_values)

                if not np.array_equal(old_ideal, self.ideal_point):
                    logger.info(f"🎯 Ponto ideal ATUALIZADO: {self.ideal_point}")
                    logger.info(f"   Melhoria: {old_ideal - self.ideal_point}")

            logger.info(f"   ✅ Box HV: entre ideal {self.ideal_point} e ref {self.reference_point}")
            logger.info(f"   ✅ HV vai CRESCER conforme ideal_point melhora (diminui)")

        # Debug: Log estatísticas da fronteira de Pareto
        if len(pareto_front) > 0:
            logger.debug(f"\n=== Geração {generation} ===")
            logger.debug(f"Tamanho da fronteira: {len(pareto_front)}")
            logger.debug(f"Objetivos - Min: {np.min(pareto_front, axis=0)}")
            logger.debug(f"Objetivos - Max: {np.max(pareto_front, axis=0)}")
            logger.debug(f"Objetivos - Média: {np.mean(pareto_front, axis=0)}")

            # Verifica valores inválidos
            if np.any(np.isnan(pareto_front)) or np.any(np.isinf(pareto_front)):
                logger.error(f"⚠️ Valores inválidos detectados na fronteira de Pareto!")
                logger.error(f"NaN: {np.sum(np.isnan(pareto_front))}, Inf: {np.sum(np.isinf(pareto_front))}")

        # Calcula métricas usando o ideal_point GLOBAL
        metrics = self.metrics_calculator.calculate_all_metrics(pareto_front, self.ideal_point)

        # Debug: Log métricas calculadas
        logger.debug(f"Hypervolume: {metrics['hypervolume']:.6e}")
        logger.debug(f"Spread: {metrics['spread']:.4f}")
        logger.debug(f"Spacing: {metrics['spacing']:.6e}")

        # Melhor fitness individual (menor valor no primeiro objetivo)
        best_fitness = np.min(population_fitness[:, 0]) if len(population_fitness) > 0 else 0

        self.history['generation'].append(generation)
        self.history['hypervolume'].append(metrics['hypervolume'])
        self.history['spread'].append(metrics['spread'])
        self.history['spacing'].append(metrics['spacing'])
        self.history['pareto_size'].append(metrics['pareto_size'])
        self.history['best_fitness'].append(best_fitness)

    def get_history(self) -> dict:
        """
        Retorna o histórico completo de métricas.

        Returns:
            Dicionário com histórico de todas as métricas
        """
        return self.history

    def has_converged(self, window: int = 10, threshold: float = 0.01) -> bool:
        """
        Verifica se o algoritmo convergiu baseado no hypervolume.

        Args:
            window: Janela de gerações para análise
            threshold: Threshold de melhoria para considerar convergência

        Returns:
            True se convergiu
        """
        if len(self.history['hypervolume']) < window + 1:
            return False

        recent_hv = self.history['hypervolume'][-window:]
        improvement = (max(recent_hv) - min(recent_hv)) / (min(recent_hv) + 1e-10)

        return improvement < threshold

    def get_convergence_generation(self, window: int = 10,
                                   threshold: float = 0.01) -> Optional[int]:
        """
        Retorna a geração em que o algoritmo convergiu.

        Args:
            window: Janela de gerações para análise
            threshold: Threshold de melhoria

        Returns:
            Número da geração de convergência ou None se não convergiu
        """
        for i in range(window, len(self.history['hypervolume'])):
            window_hv = self.history['hypervolume'][i-window:i]
            improvement = (max(window_hv) - min(window_hv)) / (min(window_hv) + 1e-10)

            if improvement < threshold:
                return self.history['generation'][i]

        return None
