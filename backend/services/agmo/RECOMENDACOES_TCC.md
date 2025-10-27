# Recomendações Práticas para Determinação de Hiperparâmetros - TCC

## 🎯 Resposta Direta à Sua Pergunta

**"Qual seria a melhor forma de medir quantas gerações e a quantidade da população ideal para o meu AGMO?"**

### Resposta em 3 Passos:

1. **PASSO 1: Análise de Convergência** (1-2 horas)
   - Execute `exemplo_tuning.py` → Opção 1
   - Isso vai mostrar em quantas gerações o algoritmo converge
   - Use essa informação como baseline

2. **PASSO 2: Grid Search Básico** (2-4 horas)
   - Execute `exemplo_tuning.py` → Opção 2
   - Teste diferentes populações com o número de gerações do Passo 1
   - Encontre o melhor trade-off qualidade vs tempo

3. **PASSO 3: Validação Final** (opcional, mas recomendado para TCC)
   - Execute `exemplo_tuning.py` → Opção 3
   - Faz análise estatística robusta (10 execuções)
   - Gera todos os gráficos e tabelas para o TCC

---

## 📋 Protocolo Recomendado para o seu TCC

### Fase 1: Exploração Inicial (Rápida)

```bash
cd backend/services/agmo
python exemplo_tuning.py
# Escolha opção 5 (Teste Rápido)
```

**Objetivo**: Validar que tudo funciona
**Tempo**: ~10 minutos
**Resultado**: Confiança de que o sistema está operacional

### Fase 2: Análise de Convergência (Essencial)

```bash
python exemplo_tuning.py
# Escolha opção 1 (Análise de Convergência)
```

**O que você vai descobrir**:
- Número médio de gerações até convergência
- Variabilidade entre execuções
- Se seu algoritmo está convergindo de forma estável

**Exemplo de resultado**:
```
Convergência média: 87 gerações
Desvio padrão: 12 gerações
Recomendação: Use 100 gerações
```

**Para o TCC**: Este resultado justifica cientificamente o número de gerações escolhido.

### Fase 3: Grid Search (Fundamental)

```bash
python exemplo_tuning.py
# Escolha opção 2 (Grid Search Básico)
```

**O que você vai descobrir**:
- Qual tamanho de população é mais eficiente
- Trade-off entre qualidade e tempo computacional
- Configuração ótima para seu problema

**Exemplo de resultado**:
```
🏆 Melhor Configuração:
   - População: 150
   - Gerações: 100
   - Hypervolume: 0.8234 (±0.0156)
   - Tempo: 45.3s (±3.2s)
```

**Para o TCC**: Tabela e gráficos comparativos entre configurações.

### Fase 4: Análise Completa (Para TCC Nota 10)

```bash
python exemplo_tuning.py
# Escolha opção 3 (Grid Search Completo)
```

⚠️ **ATENÇÃO**: Isso pode levar várias horas!

**Recomendações**:
- Execute durante a noite ou fim de semana
- Use um servidor se possível
- Salve os resultados em backup

**O que você vai obter**:
- Análise estatística robusta (10 execuções por configuração)
- Todos os gráficos profissionais para o TCC
- Tabelas completas para apêndice
- Dados para análise de sensibilidade

---

## 📊 O que Incluir no TCC

### Capítulo de Metodologia

#### Seção: "Determinação de Hiperparâmetros"

```markdown
### 4.3 Determinação de Hiperparâmetros

A determinação dos hiperparâmetros do NSGA-II (tamanho da população
e número de gerações) foi realizada através de análise sistemática
com as seguintes métricas de qualidade:

1. **Hypervolume (HV)**: Volume do espaço de objetivos dominado pela
   fronteira de Pareto. Valores maiores indicam melhor qualidade das
   soluções [Zitzler et al., 2003].

2. **Spread**: Diversidade e extensão da fronteira de Pareto [Deb et al., 2002].

3. **Spacing**: Uniformidade da distribuição das soluções ao longo da
   fronteira de Pareto.

#### 4.3.1 Protocolo Experimental

Foram realizadas duas análises principais:

**Análise de Convergência**: Para determinar o número mínimo de gerações,
o algoritmo foi executado por 200 gerações com população de 100 indivíduos.
Foram realizadas 5 execuções independentes para cada configuração,
permitindo análise estatística dos resultados.

**Grid Search de Hiperparâmetros**: Testou-se sistematicamente combinações
de tamanho de população (50, 100, 150, 200, 300) e número de gerações
(25, 50, 75, 100, 150, 200), totalizando 30 configurações distintas.
Cada configuração foi executada 10 vezes para garantir robustez estatística.

#### 4.3.2 Resultados

[INCLUIR AQUI OS SEUS RESULTADOS REAIS]

A análise de convergência identificou estabilização do Hypervolume
em 87±12 gerações (média ± desvio padrão), conforme apresentado na
Figura X. Baseando-se neste resultado, estabeleceu-se 100 gerações
como número mínimo para garantir convergência.

O grid search identificou a configuração ótima de população=150 e
gerações=100, apresentando Hypervolume médio de 0.8234±0.0156 com
tempo de execução de 45.3±3.2 segundos (Tabela Y). Esta configuração
representa o melhor trade-off entre qualidade da solução e custo
computacional, sendo adotada para todas as otimizações subsequentes.
```

### Figuras Essenciais

**Figura 1: Análise de Convergência**
- Local: `tuning_results/convergence_analysis_YYYYMMDD_HHMMSS.png`
- Legenda: "Evolução das métricas de qualidade ao longo das gerações.
  (a) Hypervolume, (b) Spread, (c) Spacing, (d) Tamanho da Fronteira.
  Linhas representam média de 5 execuções, área sombreada representa
  desvio padrão."

**Figura 2: Distribuição das Gerações de Convergência**
- Local: `tuning_results/convergence_histogram_YYYYMMDD_HHMMSS.png`
- Legenda: "Histograma das gerações de convergência em 5 execuções
  independentes. Linha vermelha indica média."

**Figura 3: Heatmap de Configurações**
- Local: `tuning_results/grid_search_heatmap_YYYYMMDD_HHMMSS.png`
- Legenda: "Hypervolume médio para diferentes combinações de população
  e gerações. Cores mais quentes indicam melhor desempenho."

**Figura 4: Trade-off Qualidade vs Tempo**
- Local: `tuning_results/quality_vs_time_YYYYMMDD_HHMMSS.png`
- Legenda: "Relação entre tempo de execução e qualidade da solução
  (Hypervolume) para diferentes tamanhos de população."

### Tabelas Essenciais

**Tabela 1: Resumo das Configurações Testadas**
- Local: `tuning_results/grid_search_summary_YYYYMMDD_HHMMSS.csv`
- Incluir no TCC as top 10 configurações

**Tabela 2: Estatísticas da Configuração Ótima**
```
| Métrica           | Valor         | Unidade |
|-------------------|---------------|---------|
| População         | 150           | -       |
| Gerações          | 100           | -       |
| Hypervolume       | 0.8234±0.0156 | -       |
| Spread            | 0.3421±0.0234 | -       |
| Spacing           | 0.0123±0.0045 | -       |
| Tamanho Pareto    | 23.4±2.1      | soluções|
| Tempo Execução    | 45.3±3.2      | segundos|
```

---

## 🔬 Valores Esperados para Seu Problema

Com base na estrutura da sua aplicação:

### Características do Seu Problema
- **Objetivos**: 3 (Retorno, Variância, CVaR)
- **Variáveis**: ~10-20 ativos (típico)
- **Restrições**: Soma = 1, limites individuais
- **Complexidade**: Média

### Expectativas Realistas

**População:**
- **Mínimo aceitável**: 50
- **Recomendado**: 100-150
- **Máximo útil**: 300
- **Seu sweet spot provável**: 100-200

**Gerações:**
- **Mínimo aceitável**: 50
- **Recomendado**: 75-150
- **Máximo útil**: 200
- **Sua convergência esperada**: 70-100 gerações

**Tempo de Execução (estimativa):**
- População 100, Gerações 100: ~30-60 segundos
- População 200, Gerações 100: ~60-120 segundos
- População 100, Gerações 200: ~60-120 segundos

Se seus resultados divergirem muito disso:
- Muito mais rápido: Problema pode ser simples (ok!)
- Muito mais lento: Verificar implementação ou dados

---

## 💡 Dicas Práticas

### 1. Comece Pequeno, Escale Gradualmente

```python
# Primeira execução: teste rápido
n_runs = 2
population_sizes = [50, 100]
generation_counts = [25, 50]

# Se funcionar: análise intermediária
n_runs = 3
population_sizes = [50, 100, 150, 200]
generation_counts = [50, 75, 100]

# Para o TCC final: análise completa
n_runs = 10
population_sizes = [50, 100, 150, 200, 300]
generation_counts = [25, 50, 75, 100, 150, 200]
```

### 2. Salve TUDO

Os resultados são salvos automaticamente em:
- `tuning_results/convergence_analysis_*.png`
- `tuning_results/convergence_histogram_*.png`
- `tuning_results/grid_search_heatmap_*.png`
- `tuning_results/quality_vs_time_*.png`
- `tuning_results/grid_search_summary_*.csv`
- `tuning_results/all_results_*.json`

**Faça backup desses arquivos!** Eles são o coração da sua análise.

### 3. Documente Conforme Executa

Crie um arquivo `diario_experimentos.md`:

```markdown
# Diário de Experimentos - Tuning AGMO

## 2025-10-27: Teste Inicial
- Executei exemplo 5 (teste rápido)
- 5 ativos, 2 execuções
- Funcionou OK
- Tempo: 5 minutos

## 2025-10-27: Análise de Convergência
- 10 ativos, 5 execuções, 200 gerações
- Convergência média: 85 gerações
- Decisão: usar 100 gerações nos próximos testes
- Tempo: 2 horas

## 2025-10-28: Grid Search
- Configuração: [50,100,150,200] × [50,75,100]
- 3 execuções cada
- Melhor: pop=150, gen=100
- Hypervolume: 0.8234
- Tempo: 4 horas
```

### 4. Interprete com Cuidado

**Não busque perfeição matemática, busque evidência suficiente:**

✅ **BOM**: "5 execuções mostram convergência consistente em ~90 gerações"
❌ **EXCESSIVO**: "1000 execuções para determinar exatamente 89.43 gerações"

✅ **BOM**: "População 150 é 5% melhor que 100, com 30% mais tempo"
❌ **EXCESSIVO**: "População 147 é ótima, 148 é ruim"

---

## 🎓 Checklist para o TCC

Antes de escrever, certifique-se de ter:

- [ ] Executado análise de convergência (5+ execuções)
- [ ] Executado grid search (3+ execuções por config)
- [ ] Salvado todos os gráficos e tabelas
- [ ] Documentado o protocolo experimental
- [ ] Calculado estatísticas (média ± desvio padrão)
- [ ] Identificado configuração ótima com justificativa
- [ ] Comparado com valores da literatura
- [ ] Analisado sensibilidade dos resultados

---

## 📞 Perguntas Frequentes

### P: Quantas execuções são suficientes?
**R**: Mínimo 3 para média, ideal 5-10 para robustez estatística.

### P: Preciso testar TODAS as combinações?
**R**: Não. Comece com análise de convergência para fixar gerações,
depois varie apenas população. Economiza tempo.

### P: E se os perfis de risco convergirem diferente?
**R**: Use a análise por perfil (exemplo 4). Se diferença < 20%,
pode usar mesma configuração para todos. Se > 20%, ajuste por perfil.

### P: Meus resultados têm muito desvio padrão, é normal?
**R**: Alguma variabilidade é esperada (CV < 10% é bom, CV < 20% é ok).
Se CV > 30%, aumente população ou número de gerações.

### P: Quanto tempo vai levar?
**R**:
- Teste rápido: 10-30 min
- Análise convergência: 1-3 horas
- Grid search básico: 2-6 horas
- Grid search completo: 6-24 horas

---

## 🚀 Próximos Passos

Depois de determinar os hiperparâmetros:

1. **Use-os no backtest**: `backtest_service.py` já usa `agmo_service.py`
2. **Documente no TCC**: Use os gráficos e tabelas gerados
3. **Compare com benchmark**: Portfolio igualmente ponderado
4. **Analise robustez**: Teste em diferentes períodos
5. **Valide em produção**: Integre com a API

---

**Última atualização**: Outubro 2025
**Autor**: Sistema de Otimização de Portfólio - TCC
