# R-NSGA-II Tuning Module

Módulo especializado para análise e tuning de hiperparâmetros do **R-NSGA-II** (Reference Point Based NSGA-II).

## 🎯 Por que um módulo separado?

O R-NSGA-II tem comportamento **diferente** do NSGA-II tradicional:

| Característica | NSGA-II Tradicional | R-NSGA-II |
|----------------|---------------------|-----------|
| **Objetivo** | Explorar toda fronteira de Pareto | Focar em região próxima ao reference point |
| **Diversidade** | Alta durante toda execução | Diminui durante convergência |
| **Hypervolume** | Cresce monotonicamente | **Pode cair** durante convergência (normal!) |
| **Melhor uso** | Quando você quer TODAS as soluções | Quando você quer soluções **específicas** |

### Comportamento Esperado do Hypervolume no R-NSGA-II:

```
Geração:   0  ────►  25  ────►  50  ────►  100
           ●●●●●●    ●●●●       ●●●         ●●
HV:        1.15      1.10       1.08        1.09
           ↑         ↓          ↓           ↑
        Diverso   Convergindo  Focado   Refinado
```

**Isso é NORMAL!** O HV cai porque o algoritmo está focando na região do reference point, descartando soluções distantes.

## 🆚 Diferença do Módulo `tuning/` Antigo

### Módulo Antigo (`backend/services/agmo/tuning/`)
- ✅ Bom para **NSGA-II tradicional**
- ✅ Assume que HV deve sempre crescer
- ❌ Pode escolher **configurações erradas** para R-NSGA-II
- ❌ Não mostra evolução de HV por geração
- ❌ Usa métricas inadequadas para busca focal

### Novo Módulo (`backend/services/agmo/rnsga2_tuning/`)
- ✅ **Projetado para R-NSGA-II**
- ✅ Entende comportamento de convergência focal
- ✅ **Captura e plota evolução de HV** por geração
- ✅ Identifica HV máximo (pode ser antes do final)
- ✅ Métricas adaptadas para busca focal
- ✅ Mais simples e focado

## 🚀 Como Usar

### Execução Rápida:

```bash
cd /home/user/TCC
python backend/services/agmo/rnsga2_tuning/exemplo_rnsga2_tuning.py
```

Escolha uma das opções:
1. **Teste Rápido** (5-10 min): Para desenvolvimento/validação
2. **Teste Padrão** (30-60 min): Análise moderada
3. **Teste Completo** (2-4 horas): Análise exaustiva
4. **Personalizado**: Configure manualmente

### Programaticamente:

```python
from app import create_app
from services.agmo.rnsga2_tuning import RNSGA2TuningService

app = create_app()
tuning_service = RNSGA2TuningService(app)

# Executa grid search
df_results = tuning_service.run_tuning_grid(
    asset_quantities=[5, 10, 15],
    population_sizes=[50, 100, 150],
    generation_counts=[25, 50, 100],
    n_runs=3,
    risk_level='moderado'
)

# Resultados em df_results
print(df_results[['num_assets', 'population_size', 'generations',
                  'final_hv', 'max_hv', 'execution_time']])
```

## 📊 Saídas Geradas

Todos os arquivos são salvos em `rnsga2_tuning_results/`:

### 1. `tuning_results_TIMESTAMP.csv`
Tabela com todas as execuções:
- `num_assets`: Quantidade de ativos
- `population_size`: Tamanho da população
- `generations`: Número de gerações
- `run_number`: Número da execução
- `final_hv`: Hypervolume na última geração
- `max_hv`: Hypervolume máximo atingido
- `max_hv_generation`: Geração onde HV foi máximo
- `execution_time`: Tempo de execução (segundos)
- `convergence_generation`: Geração de convergência detectada

### 2. `hv_histories_TIMESTAMP.json`
Histórico completo de HV por geração para cada execução.

### 3. `hv_evolution_Nassets_TIMESTAMP.png`
**GRÁFICO PRINCIPAL!** Mostra evolução do HV ao longo das gerações para cada configuração.

Exemplo:
```
Hypervolume
    1.15│     ╱╲
        │    ╱  ╲___
    1.10│   ╱       ╲___     Pop50_Gen50
        │  ╱            ╲___
    1.05│ ╱                 ╲
        └──────────────────────── Geração
         0   25   50   75  100
```

### 4. `summary_comparison_TIMESTAMP.png`
Comparação consolidada:
- **Subplot 1**: HV Final vs Gerações (para cada Pop/Assets)
- **Subplot 2**: Tempo de Execução vs Gerações

## 📈 Como Interpretar os Resultados

### 1. Analise a Evolução de HV

Abra `hv_evolution_*assets_*.png` e observe:

**Padrão Saudável** ✅:
```
Gen 0-25:  HV alto (exploração)
Gen 25-50: HV cai (convergência para ref point)
Gen 50+:   HV estabiliza ou sobe levemente (refinamento)
```

**Padrões Problemáticos** ❌:
```
HV cai e não volta:           → Poucas gerações
HV oscila muito sem estabilizar: → População pequena
HV continua caindo até o fim:    → Problema no algoritmo
```

### 2. Compare HV Máximo vs HV Final

No R-NSGA-II, é **NORMAL** que `max_hv` > `final_hv`:

```python
# Exemplo de resultado esperado:
max_hv = 1.15  (Geração 15 - ainda explorando)
final_hv = 1.09  (Geração 100 - focado no ref point)
```

Isso indica que o algoritmo **convergiu corretamente** para o reference point!

### 3. Identifique a Configuração Ótima

Procure por:
- ✅ HV estabilizado (convergiu)
- ✅ Tempo de execução aceitável
- ✅ `convergence_generation` baixa (converge rápido)

**Recomendação**: Use a geração um pouco **após** a convergência detectada. Exemplo:
```
convergence_generation = 30
→ Use generations = 40-50 (permite refinamento)
```

### 4. Considere o Trade-off

Calcule **eficiência**:
```python
efficiency = final_hv / execution_time
```

Maior eficiência = melhor trade-off qualidade/tempo.

## 🔬 Entendendo as Métricas

### Hypervolume (HV)
- **O que é**: Volume do espaço dominado pela fronteira de Pareto
- **Maior = Melhor**: Indica soluções de melhor qualidade
- **No R-NSGA-II**: Pode cair durante convergência (normal!)

### Convergence Generation
- **O que é**: Geração onde HV para de melhorar significativamente
- **Uso**: Indica quando adicionar mais gerações tem retorno decrescente
- **Cálculo**: Janela de 10 gerações com melhoria < 1%

### Max HV vs Final HV
- **Max HV**: Melhor HV atingido (geralmente na exploração)
- **Final HV**: HV na última geração (após convergência focal)
- **Diferença**: Indica intensidade da convergência focal

## 💡 Dicas de Uso

### Para Desenvolvimento:
```python
# Teste rápido
asset_quantities = [5]
population_sizes = [50]
generation_counts = [25, 50]
n_runs = 1
```

### Para Produção:
```python
# Análise robusta
asset_quantities = [5, 10, 15, 20]
population_sizes = [50, 100, 150, 200]
generation_counts = [25, 50, 100, 150, 200]
n_runs = 5  # Média mais confiável
```

### Paralelização:
- Cada execução é independente
- Considere usar `ThreadPoolExecutor` para múltiplas execuções
- Cuidado com memória (população grande × muitos threads)

## 🐛 Troubleshooting

### "HV está caindo muito!"
✅ **Normal no R-NSGA-II!** Verifique se estabiliza depois.

### "Convergence_generation = None"
❌ Não convergiu no tempo disponível. Aumente `generations` ou reduza `population_size`.

### "Tempo de execução muito alto"
💡 Opções:
- Reduza `population_size`
- Reduza `generations`
- Use menos ativos
- Paralelização (múltiplas execuções simultâneas)

### "Resultados inconsistentes entre execuções"
💡 Aumente `n_runs` para ter média mais confiável (recomendado: 3-5).

## 📚 Referências

- **R-NSGA-II Paper**: Deb & Sundar (2006). "Reference point based multi-objective optimization using evolutionary algorithms"
- **Hypervolume**: Zitzler & Thiele (1999). "Multiobjective evolutionary algorithms: a comparative case study and the strength Pareto approach"
- **Convergence Detection**: Deb et al. (2002). "A fast and elitist multiobjective genetic algorithm: NSGA-II"

## 🤝 Contribuindo

Para adicionar novas funcionalidades:
1. Mantenha compatibilidade com R-NSGA-II
2. Documente comportamentos específicos
3. Adicione testes com dados sintéticos
4. Atualize este README

---

**Desenvolvido para análise de portfólios com R-NSGA-II** 🎯📊
