# Módulo de Análise de Convergência - R-NSGA2

Este módulo fornece ferramentas para calcular e visualizar o **R-Hypervolume** (R-HV) durante a otimização de portfólios usando o algoritmo R-NSGA2.

## 📊 Funcionalidades

### 1. Cálculo de Métricas de Qualidade

- **R-Hypervolume (R-HV)**: Métrica apropriada para R-NSGA2 baseada no R2 indicator
- **Hypervolume (HV)**: Métrica tradicional de volume dominado
- **Spread**: Medida de diversidade da fronteira de Pareto
- **Spacing**: Medida de uniformidade da distribuição
- **Pareto Size**: Número de soluções não-dominadas

### 2. Tracking de Convergência

O `ConvergenceTracker` monitora a evolução das métricas ao longo das gerações durante a otimização.

### 3. Visualização

Gera gráficos profissionais mostrando:
- Evolução do R-Hypervolume
- Tamanho da fronteira de Pareto
- Spread e Spacing
- Comparação entre múltiplas execuções

## 🚀 Uso Rápido

### Exemplo Básico

```python
from app import create_app
from services.agmo.agmo_service import (
    Nsga2OtimizacaoService,
    REFERENCE_POINTS_CONFIG,
    WEIGHTS_CONFIG
)
from services.agmo.tuning import (
    ConvergenceTracker,
    plot_convergence_evolution,
    plot_hypervolume_only,
    print_convergence_summary
)

# Criar aplicação
app = create_app()

# Configurar serviço de otimização
service = Nsga2OtimizacaoService(
    app=app,
    restricted_asset_ids=[],
    risk_level='moderado',
    years_period=10
)

# Criar tracker com configuração apropriada para R-NSGA2
tracker = ConvergenceTracker(
    reference_points_rnsga2=REFERENCE_POINTS_CONFIG['moderado'],
    weights=WEIGHTS_CONFIG['moderado'],
    use_r_hv=True  # Usa R-HV ao invés de HV tradicional
)

# Executar otimização COM tracking
result = service.optimize(
    population_size=100,
    generations=150,
    convergence_tracker=tracker,  # Passa o tracker
    max_assets=10
)

# Obter histórico de métricas
history = tracker.get_history()

# Imprimir resumo estatístico
print_convergence_summary(history)

# Gerar gráficos
plot_convergence_evolution(
    history=history,
    title="Evolução da Convergência - R-NSGA2",
    save_path='convergence_full.png'
)

plot_hypervolume_only(
    history=history,
    title="Evolução do R-Hypervolume",
    save_path='r_hypervolume.png'
)
```

## 📖 Exemplos Detalhados

Execute os exemplos incluídos no módulo:

```bash
# Exemplo simples
python3 exemplo_convergence_tracking.py --exemplo simples

# Comparação de múltiplas configurações
python3 exemplo_convergence_tracking.py --exemplo comparacao

# Análise de perfis de risco
python3 exemplo_convergence_tracking.py --exemplo perfis
```

## 📚 Referências Teóricas

### R-Hypervolume (R2 Indicator)

O R-Hypervolume é baseado no **R2 indicator**, que usa a **Achievement Scalarizing Function (ASF)**:

```
R2 = 1/|Z| * Σ_{z∈Z} min_{a∈A} ASF(a, z, w)
```

Onde:
- `ASF(a, z, w) = max_i {(a_i - z_i) / w_i}`
- `a`: solução (normalizada)
- `z`: ponto de referência (aspiração)
- `w`: vetor de pesos

**Por que R-HV para R-NSGA2?**

O R-HV é mais apropriado que o HV tradicional para algoritmos baseados em pontos de referência porque:

1. **Alinhamento com os objetivos**: Mede qualidade em relação aos pontos de referência que guiam a busca
2. **Considera preferências do usuário**: Incorpora os pesos definidos por perfil de risco
3. **Mais sensível a melhorias**: Detecta melhor quando soluções se aproximam das aspirações do usuário

### Interpretação dos Valores

- **R-HV**: Quanto **MAIOR**, melhor a qualidade (retornamos `1/R2`)
  - Valores crescentes indicam que a fronteira está se aproximando dos pontos de referência
  - Estabilização indica convergência

- **Spread**: Quanto **MENOR**, melhor a distribuição
  - Valores próximos de 0 indicam distribuição uniforme

- **Spacing**: Quanto **MENOR**, mais uniforme a distribuição
  - Valores baixos indicam soluções bem espaçadas

## 🎯 Estrutura do Módulo

```
tuning/
├── __init__.py                          # Exports do módulo
├── quality_metrics.py                   # QualityMetrics e ConvergenceTracker
├── convergence_visualization.py        # Funções de visualização
├── exemplo_convergence_tracking.py      # Exemplos de uso
├── test_quick.py                        # Teste rápido
└── README.md                            # Esta documentação
```

## 🔧 API Reference

### ConvergenceTracker

```python
tracker = ConvergenceTracker(
    reference_point=None,                    # Para HV tradicional
    reference_points_rnsga2=ref_points,      # Para R-HV (recomendado)
    weights=weights,                         # Pesos para ASF
    use_r_hv=True                           # True para R-HV, False para HV
)

# Atualizar métricas em cada geração (chamado automaticamente pelo callback)
tracker.update(generation, pareto_front, population_fitness)

# Obter histórico completo
history = tracker.get_history()
# Retorna: {'generation': [...], 'r_hypervolume': [...], 'spread': [...], ...}

# Verificar convergência
converged = tracker.has_converged(window=10, threshold=0.01)
conv_gen = tracker.get_convergence_generation(window=10, threshold=0.01)
```

### Funções de Visualização

```python
# Gráfico completo com todas as métricas
plot_convergence_evolution(
    history,
    title="Título do gráfico",
    save_path="caminho/arquivo.png",
    show_plot=True,
    figsize=(16, 10)
)

# Gráfico focado apenas no R-Hypervolume
plot_hypervolume_only(
    history,
    title="Título do gráfico",
    save_path="caminho/arquivo.png",
    show_plot=True,
    figsize=(12, 7)
)

# Comparação de múltiplas execuções
plot_multiple_runs_comparison(
    histories=[history1, history2, ...],
    labels=['Config 1', 'Config 2', ...],
    title="Comparação",
    save_path="comparison.png"
)

# Imprimir resumo estatístico
print_convergence_summary(history)
```

## 📈 Interpretando os Gráficos

### Gráfico de Convergência Completo

Mostra 4 subplots:

1. **R-Hypervolume**: Deve crescer e estabilizar
   - Crescimento rápido inicial indica boa exploração
   - Estabilização indica convergência

2. **Tamanho da Fronteira**: Número de soluções não-dominadas
   - Valores maiores = mais diversidade
   - Estabilização indica fronteira bem estabelecida

3. **Spread**: Diversidade da fronteira
   - Valores baixos = boa distribuição
   - Deve diminuir e estabilizar

4. **Spacing**: Uniformidade da distribuição
   - Valores baixos = distribuição uniforme
   - Deve diminuir e estabilizar

### Indicadores de Boa Convergência

✅ **Sinais positivos:**
- R-HV crescente e estabilizado
- Spread baixo e estável
- Spacing baixo e estável
- Tamanho da fronteira estável

⚠️ **Sinais de atenção:**
- R-HV decrescente (possível regressão)
- Spread muito alto (fronteira não uniforme)
- Oscilações intensas (falta de convergência)

## 🔬 Análise Avançada

### Detectar Convergência Prematura

```python
# Verifica se convergiu muito cedo
conv_gen = tracker.get_convergence_generation(window=10, threshold=0.01)
total_gens = len(tracker.history['generation'])

if conv_gen and conv_gen < total_gens * 0.5:
    print(f"⚠️ Convergência prematura na geração {conv_gen}")
    print("Considere aumentar a diversidade genética")
```

### Comparar Configurações

```python
# Executa múltiplas configurações e compara
configs = [
    {'pop': 50, 'gen': 100},
    {'pop': 100, 'gen': 100},
    {'pop': 100, 'gen': 200}
]

for config in configs:
    # ... executar otimização com tracker ...
    final_rhv = tracker.history['r_hypervolume'][-1]
    print(f"Config {config}: R-HV final = {final_rhv:.6e}")
```

## 🎓 Referências Bibliográficas

1. **Hansen, M. P., & Jaszkiewicz, A. (1998)**. "Evaluating the quality of approximations to the non-dominated set". *IMM Technical Report*.

2. **Deb, K., & Sundar, J. (2006)**. "Reference point based multi-objective optimization using evolutionary algorithms". *GECCO*.

3. **Deb, K., et al. (2002)**. "A fast and elitist multiobjective genetic algorithm: NSGA-II". *IEEE Transactions on Evolutionary Computation*.

4. **Zitzler, E., et al. (2003)**. "Performance assessment of multiobjective optimizers: An analysis and review". *IEEE Transactions on Evolutionary Computation*.

## 📝 Notas Importantes

1. **Use R-HV para R-NSGA2**: O R-Hypervolume é mais apropriado que o HV tradicional para algoritmos baseados em pontos de referência.

2. **Pontos de Referência Fixos**: Os pontos de referência (nadir e ideal) são fixados na primeira geração para garantir comparabilidade.

3. **Normalização**: Todas as métricas são calculadas no espaço normalizado [0, 1] para garantir equidade entre objetivos.

4. **Performance**: O cálculo de R-HV é rápido (O(|A| × |Z|)) e adequado para tracking em tempo real.

## 🆘 Troubleshooting

**Problema**: R-HV muito alto (1e10)
- **Causa**: Soluções muito melhores que pontos de referência
- **Solução**: Normal, indica fronteira excelente

**Problema**: R-HV constante
- **Causa**: Possível convergência prematura
- **Solução**: Aumentar diversidade (mutation_eta, crossover_eta)

**Problema**: Gráfico não gerado
- **Causa**: Matplotlib não configurado
- **Solução**: Verifique instalação de matplotlib

**Problema**: Import Error
- **Causa**: Dependências não instaladas
- **Solução**: `pip install numpy matplotlib pandas`

---

**Desenvolvido para o Trabalho de Conclusão de Curso (TCC)**

*Otimização Multi-Objetivo de Portfólios usando R-NSGA2*
