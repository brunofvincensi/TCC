# Sistema de Tuning de Hiperparâmetros - AGMO

Sistema completo para otimização e validação de hiperparâmetros do algoritmo genético multiobjetivo (NSGA-II) para otimização de portfólios.

## 📋 Índice

- [Visão Geral](#visão-geral)
- [Arquivos do Sistema](#arquivos-do-sistema)
- [Instalação](#instalação)
- [Como Usar](#como-usar)
- [Métricas Implementadas](#métricas-implementadas)
- [Exemplos Práticos](#exemplos-práticos)
- [Interpretação dos Resultados](#interpretação-dos-resultados)
- [Recomendações para o TCC](#recomendações-para-o-tcc)

## 🎯 Visão Geral

Este sistema permite determinar cientificamente os melhores hiperparâmetros para o AGMO através de:

1. **Análise de Convergência**: Determina quantas gerações são necessárias
2. **Grid Search**: Testa combinações de população × gerações
3. **Validação Estatística**: Múltiplas execuções com análise de variância
4. **Visualizações**: Gráficos profissionais para o TCC

### Por que fazer tuning de hiperparâmetros?

- ✅ Fundamentação científica para escolha de parâmetros
- ✅ Evita desperdício computacional (gerações excessivas)
- ✅ Garante qualidade das soluções (gerações insuficientes)
- ✅ Material robusto para metodologia do TCC
- ✅ Permite comparações objetivas

## 📁 Arquivos do Sistema

```
backend/services/agmo/
├── quality_metrics.py                   # Métricas de qualidade (Hypervolume, Spread, etc)
├── hyperparameter_tuning_service.py     # Serviço principal de tuning
├── exemplo_tuning.py                    # Exemplos de uso
├── agmo_service.py                      # (modificado) Suporte a callbacks
└── README_TUNING.md                     # Esta documentação
```

## 🔧 Instalação

### 1. Instalar Dependências

```bash
cd backend
pip install -r requirements.txt
```

As novas dependências incluem:
- `pandas==2.1.3` - Análise de dados
- `matplotlib==3.8.2` - Geração de gráficos
- `seaborn==0.13.0` - Visualizações estatísticas

### 2. Verificar Instalação

```bash
python -c "import matplotlib; import seaborn; print('OK')"
```

## 🚀 Como Usar

### Forma Mais Simples: Menu Interativo

```bash
cd backend/services/agmo
python exemplo_tuning.py
```

O menu oferece 5 opções:
1. Análise de Convergência (recomendado para começar)
2. Grid Search Básico
3. Grid Search Completo (para TCC)
4. Análise por Perfil de Risco
5. Teste Rápido (validação)

### Uso Programático

```python
from app import create_app
from services.agmo.tuning.hyperparameter_tuning_service import HyperparameterTuningService

app = create_app()
tuning_service = HyperparameterTuningService(app)

# Análise de convergência
resultados = tuning_service.convergence_analysis(
    ids_ativos=[1, 2, 3, 4, 5],
    nivel_risco='moderado',
    max_generations=200,
    population_size=100,
    n_runs=5
)

print(f"Convergência média: {resultados['convergence_mean']:.1f} gerações")

# Grid search
summary = tuning_service.grid_search(
    ids_ativos=[1, 2, 3, 4, 5],
    nivel_risco='moderado',
    population_sizes=[50, 100, 200],
    generation_counts=[25, 50, 100],
    n_runs=3
)

# Melhor configuração
best_config = tuning_service.get_best_configuration()
print(f"Melhor config: {best_config}")
```

## 📊 Métricas Implementadas

### 1. Hypervolume (HV)
- **O que é**: Volume do espaço de objetivos dominado pela fronteira de Pareto
- **Interpretação**: Maior = melhor qualidade das soluções
- **Uso**: Métrica principal para comparar configurações

### 2. Spread
- **O que é**: Diversidade e extensão da fronteira de Pareto
- **Interpretação**: Menor = melhor distribuição das soluções
- **Uso**: Garante que temos soluções variadas

### 3. Spacing
- **O que é**: Uniformidade da distribuição das soluções
- **Interpretação**: Menor = distribuição mais uniforme
- **Uso**: Complementa a análise de diversidade

### 4. Pareto Size
- **O que é**: Número de soluções não-dominadas
- **Interpretação**: Mais soluções = mais opções para o usuário
- **Uso**: Deve ser balanceado (nem muito pequeno, nem excessivo)

## 💡 Exemplos Práticos

### Exemplo 1: Determinar Número Mínimo de Gerações

**Objetivo**: Evitar executar mais gerações que o necessário.

```python
resultados = tuning_service.convergence_analysis(
    ids_ativos=lista_ativos,
    nivel_risco='moderado',
    max_generations=200,  # Testa até 200
    population_size=100,
    n_runs=5  # 5 execuções para média
)

# Resultado: "Convergência média em 87 gerações"
# Recomendação: Use 100 gerações (margem de segurança)
```

**Saída**: Gráfico mostrando evolução das métricas ao longo das gerações.

### Exemplo 2: Encontrar Melhor População

**Objetivo**: Balancear qualidade vs tempo computacional.

```python
summary = tuning_service.grid_search(
    ids_ativos=lista_ativos,
    nivel_risco='moderado',
    population_sizes=[50, 100, 150, 200, 300],
    generation_counts=[100],  # Fixa gerações
    n_runs=5
)

# Resultado: População 150 tem melhor custo-benefício
```

**Saída**:
- Tabela comparativa
- Gráfico de trade-off qualidade vs tempo
- Heatmap de hypervolume

### Exemplo 3: Comparar Perfis de Risco

**Objetivo**: Verificar se perfis diferentes precisam de parâmetros diferentes.

```python
for perfil in ['conservador', 'moderado', 'arrojado']:
    resultado = tuning_service.convergence_analysis(
        ids_ativos=lista_ativos,
        nivel_risco=perfil,
        max_generations=150,
        population_size=100,
        n_runs=5
    )
    print(f"{perfil}: {resultado['convergence_mean']:.1f} gerações")

# Resultado típico:
# conservador: 92 gerações
# moderado: 87 gerações
# arrojado: 85 gerações
# Conclusão: Diferença pequena, pode usar mesma config
```

## 📈 Interpretação dos Resultados

### O que procurar nos gráficos:

1. **Gráfico de Convergência (Hypervolume vs Gerações)**
   - Procure onde a curva "estabiliza"
   - Ponto de estabilização = convergência
   - Use esse valor + margem de 10-20%

2. **Heatmap de Configurações**
   - Cores mais quentes = melhor hypervolume
   - Identifique "região ótima"
   - Evite cantos (muito pequeno ou muito grande)

3. **Trade-off Qualidade vs Tempo**
   - Procure o "joelho" da curva
   - Ponto onde tempo aumenta muito mas qualidade pouco
   - Esse é o sweet spot

### Exemplo de Conclusão para TCC:

> "Através de análise sistemática com 5 execuções independentes,
> observou-se convergência média em 87±12 gerações (média ± desvio padrão).
> O grid search testou 30 configurações (5 populações × 6 gerações × 3 runs),
> identificando população=150 e gerações=100 como configuração ótima,
> apresentando hypervolume médio de 0.8234±0.0156 com tempo de execução
> de 45.3±3.2 segundos. Esta configuração representa o melhor trade-off
> entre qualidade da solução e custo computacional, sendo adotada para
> todas as otimizações subsequentes."

## 🎓 Recomendações para o TCC

### 1. Metodologia

Inclua na seção de metodologia:
- Justificativa para tuning de hiperparâmetros
- Descrição das métricas usadas (HV, Spread, Spacing)
- Protocolo experimental (n_runs, configurações testadas)
- Critérios de convergência

### 2. Resultados

Apresente:
- Gráficos de convergência para cada perfil
- Tabela comparativa de configurações
- Análise estatística (média ± desvio padrão)
- Justificativa da escolha final

### 3. Discussão

Discuta:
- Por que a configuração escolhida é ótima
- Sensibilidade dos resultados aos parâmetros
- Limitações (tempo computacional, dados disponíveis)
- Comparação com literatura (valores típicos: pop=100-300, gen=50-200)

### 4. Material Visual Sugerido

**Figuras essenciais para o TCC:**
1. Gráfico de convergência (4 painéis: HV, Spread, Spacing, Pareto Size)
2. Histograma de gerações de convergência
3. Heatmap de configurações
4. Trade-off qualidade vs tempo
5. Comparação entre perfis de risco

**Tabelas essenciais:**
1. Resumo de configurações testadas
2. Estatísticas descritivas (média, std, min, max)
3. Configuração final escolhida com justificativa

## 🔬 Valores de Referência

Com base na literatura de NSGA-II e otimização de portfólio:

### Regra de Bolso
- **População**: 10 × n_objectives × √n_variables
  - Para 3 objetivos e 10 ativos: `10 × 3 × √10 ≈ 95`
  - **Faixa razoável: 50-300**

- **Gerações**: Depende da convergência observada
  - **Faixa típica: 50-200**
  - Problemas simples: 50-100
  - Problemas complexos: 100-200

### Sinais de Problema

❌ **População muito pequena (< 50)**:
- Baixa diversidade
- Convergência prematura
- Fronteira de Pareto incompleta

❌ **População muito grande (> 500)**:
- Desperdício computacional
- Tempo excessivo
- Ganho marginal de qualidade

❌ **Gerações insuficientes**:
- Hypervolume ainda crescendo
- Alta variância entre execuções
- Soluções subótimas

❌ **Gerações excessivas**:
- Hypervolume estável há muitas gerações
- Tempo desperdiçado
- Risco de overfitting

## 🐛 Troubleshooting

### Problema: "Sem dados históricos disponíveis"
**Solução**: Verifique se há dados no banco para os ativos selecionados.

### Problema: Tempo muito longo
**Solução**:
1. Comece com teste rápido (Exemplo 5)
2. Use menos ativos inicialmente
3. Reduza n_runs para 3
4. Use time_limit no grid_search

### Problema: Resultados inconsistentes (alta variância)
**Solução**:
1. Aumente n_runs (mínimo 5, ideal 10)
2. Verifique qualidade dos dados históricos
3. Aumente população (mais diversidade)

### Problema: Gráficos não aparecem
**Solução**:
```bash
# Linux
export MPLBACKEND=Agg

# Windows
set MPLBACKEND=Agg
```

## 📚 Referências

1. Deb, K., et al. (2002). "A fast and elitist multiobjective genetic algorithm: NSGA-II"
2. Blank, J., & Deb, K. (2020). "pymoo: Multi-Objective Optimization in Python"
3. Zitzler, E., et al. (2003). "Performance assessment of multiobjective optimizers"

## 📞 Suporte

Para dúvidas ou problemas:
1. Verifique esta documentação
2. Execute o Exemplo 5 (Teste Rápido) para validar instalação
3. Consulte os logs em `tuning_results/`

---

**Última atualização**: Outubro 2025
**Autor**: Sistema de Otimização de Portfólio - TCC
