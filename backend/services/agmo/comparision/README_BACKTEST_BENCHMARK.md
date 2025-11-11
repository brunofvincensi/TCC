# Backtest e Comparação com Benchmark

Este documento descreve as novas funcionalidades adicionadas ao sistema AGMO para backtest de carteiras e comparação com benchmarks de mercado.

## 📋 Índice

1. [Visão Geral](#visão-geral)
2. [Funcionalidades](#funcionalidades)
3. [Como Usar](#como-usar)
4. [Exemplos Práticos](#exemplos-práticos)
5. [Métricas Calculadas](#métricas-calculadas)
6. [Gráficos Gerados](#gráficos-gerados)

## 🎯 Visão Geral

O sistema agora oferece duas novas funcionalidades principais:

1. **Gráficos de Backtest**: Visualização do retorno acumulado e volatilidade da carteira ao longo do tempo
2. **Comparação com Benchmark**: Análise comparativa da carteira otimizada versus índices de mercado (ex: Ibovespa)

> **🌐 Novidade:** Os dados dos benchmarks são obtidos **automaticamente do Yahoo Finance** via biblioteca `yfinance`. Não é necessário cadastrar os índices no banco de dados!

## 🚀 Funcionalidades

### 1. Geração de Gráficos de Backtest

**Arquivo**: `agmo_service.py`
**Função**: `salvar_grafico_backtest()`

Gera e salva um gráfico com:
- Retorno acumulado da carteira ao longo do tempo
- Volatilidade rolling (janela configurável)
- Métricas de desempenho

**Parâmetros:**
```python
salvar_grafico_backtest(
    carteira,           # Lista com composição da carteira
    data_inicio,        # Data inicial do backtest
    data_fim,           # Data final do backtest
    app,                # Instância da aplicação Flask
    nome_arquivo=None,  # Nome do arquivo (opcional)
    janela_volatilidade=6  # Janela para volatilidade rolling (meses)
)
```

**Retorna:** Caminho completo do arquivo PNG salvo

### 2. Comparação com Benchmark

**Arquivo**: `benchmark_comparison.py`
**Classe**: `BenchmarkComparison`

Compara a carteira otimizada com índices de mercado, calculando:
- Alpha (retorno acima do benchmark)
- Beta (sensibilidade ao mercado)
- Tracking Error
- Information Ratio
- Correlação
- E outras métricas importantes

**Uso básico:**

```python
from services.agmo.comparision.benchmark_comparison import BenchmarkComparison

comparador = BenchmarkComparison(app)
metricas = comparador.gerar_relatorio_completo(
    carteira=carteira_otimizada,
    ticker_benchmark='^BVSP',  # Ibovespa
    data_inicio=date(2020, 1, 1),
    data_fim=date(2024, 12, 31),
    salvar_grafico=True
)
```

## 📖 Como Usar

### Passo 1: Otimizar Carteira em Modo Backtest

```python
from datetime import date
from app import create_app
from services.agmo.agmo_service import Nsga2OtimizacaoService

app = create_app()

# Data de referência para otimização
data_referencia = date(2020, 1, 1)

# Criar serviço com data de referência (modo backtest)
service = Nsga2OtimizacaoService(
    app=app,
    ids_ativos_restringidos=[],
    nivel_risco='moderado',
    prazo_anos=5,
    data_referencia=data_referencia  # ✅ Ativa modo backtest
)

# Otimizar
resultado = service.otimizar(max_ativos=10)
carteira = resultado['composicao']
```

### Passo 2: Gerar Gráfico de Backtest

```python
from services.agmo.agmo_service import salvar_grafico_backtest

data_fim = date(2024, 12, 31)

caminho_grafico = salvar_grafico_backtest(
    carteira=carteira,
    data_inicio=data_referencia,
    data_fim=data_fim,
    app=app,
    nome_arquivo='meu_backtest.png'
)

print(f"Gráfico salvo em: {caminho_grafico}")
```

### Passo 3: Comparar com Benchmark

```python
from services.agmo.comparision.benchmark_comparison import BenchmarkComparison

comparador = BenchmarkComparison(app)

metricas = comparador.gerar_relatorio_completo(
    carteira=carteira,
    ticker_benchmark='^BVSP',  # Ibovespa
    data_inicio=data_referencia,
    data_fim=data_fim,
    salvar_grafico=True
)

# Acessar métricas
print(f"Alpha: {metricas['comparativas']['alpha']}")
print(f"Beta: {metricas['comparativas']['beta']}")
print(f"Information Ratio: {metricas['comparativas']['information_ratio']}")
```

## 💡 Exemplos Práticos

### Exemplo Completo

Execute o arquivo de exemplo:

```bash
cd backend/services/agmo
python exemplo_backtest_comparacao.py
```

Este exemplo demonstra:
1. Otimização de carteira em modo backtest
2. Geração de gráfico de retorno e volatilidade
3. Comparação com Ibovespa
4. Análise completa de métricas

### Exemplo Simples - Apenas Backtest

```python
from datetime import date
from app import create_app
from services.agmo.agmo_service import Nsga2OtimizacaoService, salvar_grafico_backtest

app = create_app()

# Otimizar
service = Nsga2OtimizacaoService(
    app, [], 'moderado', 5,
    data_referencia=date(2020, 1, 1)
)
resultado = service.otimizar(max_ativos=10)

# Gerar gráfico
salvar_grafico_backtest(
    resultado['composicao'],
    date(2020, 1, 1),
    date(2024, 12, 31),
    app
)
```

### Exemplo Simples - Apenas Comparação

```python
from datetime import date
from app import create_app
from services.agmo.comparision.benchmark_comparison import BenchmarkComparison

app = create_app()
comparador = BenchmarkComparison(app)

# Sua carteira
carteira = [
    {'id_ativo': 1, 'ticker': 'PETR4', 'peso': 0.5},
    {'id_ativo': 2, 'ticker': 'VALE3', 'peso': 0.5}
]

# Comparar
metricas = comparador.gerar_relatorio_completo(
    carteira, '^BVSP',
    date(2020, 1, 1), date(2024, 12, 31)
)
```

## 📊 Métricas Calculadas

### Métricas da Carteira

- **Retorno Total**: Retorno acumulado no período
- **Retorno Anualizado**: Retorno médio anualizado
- **Volatilidade Anualizada**: Desvio padrão dos retornos (anualizado)
- **Sharpe Ratio**: Retorno / Volatilidade
- **Max Drawdown**: Maior queda do pico ao vale

### Métricas do Benchmark

As mesmas métricas calculadas para o índice de referência.

### Métricas Comparativas

- **Alpha**: Retorno da carteira acima do benchmark (anualizado)
  - α > 0: Carteira supera o benchmark
  - α < 0: Benchmark supera a carteira

- **Beta**: Sensibilidade da carteira aos movimentos do mercado
  - β > 1: Carteira mais volátil que o mercado
  - β < 1: Carteira menos volátil que o mercado
  - β ≈ 1: Volatilidade similar ao mercado

- **Tracking Error**: Volatilidade do excess return (carteira - benchmark)
  - Mede o quanto a carteira se desvia do benchmark

- **Information Ratio**: Alpha / Tracking Error
  - Mede o retorno adicional por unidade de risco ativo
  - IR > 0.5: Excelente
  - IR > 0: Bom
  - IR < 0: Ruim

- **Correlação**: Correlação entre retornos da carteira e benchmark
  - Valores próximos a 1: Alta correlação
  - Valores próximos a 0: Baixa correlação

## 📈 Gráficos Gerados

### 1. Gráfico de Backtest (`salvar_grafico_backtest`)

**Arquivo gerado**: `backtest_carteira_YYYYMMDD_HHMMSS.png`

**Conteúdo**:
- **Subplot 1**: Retorno acumulado ao longo do tempo
  - Linha com retorno acumulado
  - Área preenchida
  - Anotação com retorno total

- **Subplot 2**: Volatilidade rolling
  - Linha com volatilidade calculada em janela móvel
  - Linha tracejada com média
  - Área preenchida

### 2. Gráfico de Comparação (`gerar_grafico_comparacao`)

**Arquivo gerado**: `comparacao_benchmark_YYYYMMDD_HHMMSS.png`

**Conteúdo**:
- **Subplot 1**: Retorno acumulado comparado
  - Carteira vs Benchmark
  - Anotações com retornos finais

- **Subplot 2**: Retornos mensais comparados
  - Barras lado a lado
  - Carteira vs Benchmark

- **Subplot 3**: Excess Returns
  - Diferença entre retornos (carteira - benchmark)
  - Verde: Carteira superou
  - Vermelho: Benchmark superou
  - Linha de média

## ⚠️ Requisitos

### Dados de Benchmark

Os dados dos benchmarks são **obtidos automaticamente do Yahoo Finance** usando a biblioteca `yfinance`.

**Não é necessário** cadastrar o benchmark no banco de dados ou popular seu histórico de preços!

### Requisitos técnicos:

1. **Conexão com a internet** - Para buscar dados do Yahoo Finance
2. **Biblioteca yfinance** - Já incluída nas dependências do projeto
3. **Ticker válido** - Use tickers disponíveis no Yahoo Finance

### Tickers comuns de benchmarks:

**Brasil:**
- `^BVSP` - Ibovespa (Índice Bovespa)
- `^BVMF` - Índice BM&F Bovespa

**Estados Unidos:**
- `^GSPC` - S&P 500
- `^DJI` - Dow Jones Industrial Average
- `^IXIC` - NASDAQ Composite
- `^RUT` - Russell 2000

**Internacional:**
- `^FTSE` - FTSE 100 (Reino Unido)
- `^N225` - Nikkei 225 (Japão)
- `^GDAXI` - DAX (Alemanha)

> **Dica:** Para encontrar outros tickers, acesse [Yahoo Finance](https://finance.yahoo.com/) e pesquise pelo índice desejado.

## 🔧 Configurações

### Janela de Volatilidade

Ajuste a janela para cálculo da volatilidade rolling:

```python
salvar_grafico_backtest(
    ...,
    janela_volatilidade=12  # 12 meses em vez do padrão (6)
)
```

### Nome dos Arquivos

Customize o nome dos arquivos gerados:

```python
# Gráfico de backtest
salvar_grafico_backtest(
    ...,
    nome_arquivo='resultados/backtest_2024.png'
)

# Gráfico de comparação
comparador.gerar_grafico_comparacao(
    nome_arquivo='resultados/comparacao_ibov.png'
)
```

## 📝 Interpretação dos Resultados

### Alpha Positivo
- A carteira está gerando retorno acima do benchmark
- Estratégia de otimização está funcionando

### Alpha Negativo
- O benchmark está superando a carteira
- Considere revisar a estratégia ou parâmetros

### Beta Alto (> 1.2)
- Carteira mais arriscada que o mercado
- Pode ser apropriado para perfil arrojado

### Beta Baixo (< 0.8)
- Carteira mais conservadora
- Pode ser apropriado para perfil conservador

### Information Ratio Alto (> 0.5)
- Excelente geração de alpha ajustada ao risco
- Tracking error compensado pelo retorno adicional

### Information Ratio Negativo
- Risco adicional não está sendo compensado
- Considere revisar a estratégia

## 🎓 Referências

### Métricas Calculadas

- **Sharpe Ratio**: Sharpe, W. F. (1966). "Mutual fund performance"
- **Information Ratio**: Goodwin, T. H. (1998). "The information ratio"
- **Tracking Error**: Roll, R. (1992). "A mean/variance analysis of tracking error"
- **Alpha & Beta**: Jensen, M. C. (1968). "The performance of mutual funds"

### Implementação

- Biblioteca matplotlib para gráficos
- Pandas para manipulação de dados
- NumPy para cálculos estatísticos

## 🐛 Troubleshooting

### Erro: "Não foi possível obter dados do Yahoo Finance"
**Causas possíveis:**
- Ticker incorreto ou inexistente
- Sem conexão com a internet
- Serviços do Yahoo Finance temporariamente indisponíveis

**Solução:**
- Verifique a conexão com a internet
- Confirme que o ticker está correto (ex: `^BVSP` para Ibovespa)
- Consulte a lista de tickers comuns na seção de Requisitos
- Tente novamente após alguns minutos

### Erro: "Sem datas em comum"
**Causas possíveis:**
- Períodos da carteira e benchmark não se sobrepõem
- Dados do benchmark não disponíveis para o período solicitado

**Solução:**
- Verifique se o período solicitado tem dados disponíveis no Yahoo Finance
- Ajuste as datas de início e fim para um período mais recente
- Alguns índices podem não ter histórico muito antigo

### Erro: "Sem dados do benchmark após processamento"
**Causas possíveis:**
- Período muito curto ou sem dados mensais completos
- Datas fora do range disponível no Yahoo Finance

**Solução:**
- Use períodos de pelo menos 2-3 meses
- Verifique se as datas estão no formato correto (date)
- Confirme que o período tem dados disponíveis

### Gráfico não é salvo
**Causas possíveis:**
- Sem permissões no diretório
- Caminho inválido

**Solução:**
- Verifique permissões do diretório
- Use caminhos relativos ou absolutos válidos
- O sistema criará diretórios automaticamente se necessário

### Erro: "ModuleNotFoundError: No module named 'yfinance'"
**Causa:**
- Biblioteca yfinance não instalada

**Solução:**
```bash
pip install yfinance
```

## 📞 Suporte

Para dúvidas ou problemas:
1. Verifique os exemplos em `exemplo_backtest_comparacao.py`
2. Consulte a documentação dos módulos
3. Revise este README

## 🎉 Conclusão

Estas ferramentas permitem:
- ✅ Avaliar desempenho histórico de carteiras otimizadas
- ✅ Comparar com benchmarks de mercado
- ✅ Tomar decisões informadas sobre estratégias de investimento
- ✅ Visualizar resultados de forma clara e profissional

---

**Última atualização**: 2025-11-09
**Versão**: 1.0
