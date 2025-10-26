# Funcionalidade de Backtest - AGMO Service

## Visão Geral

A funcionalidade de backtest permite que você teste a otimização de carteira usando apenas dados históricos até uma data específica. Isso é útil para:

- Avaliar o desempenho da estratégia de otimização em diferentes períodos históricos
- Comparar carteiras otimizadas em diferentes datas
- Validar a robustez do algoritmo de otimização

## Como Usar

### 1. Otimização Normal (sem backtest)

```python
from datetime import date
from app import create_app
from services.agmo.agmo_service import Nsga2OtimizacaoService

app = create_app()

# Cria o serviço sem data_referencia
service = Nsga2OtimizacaoService(
    app=app,
    ids_ativos_restringidos=[1, 2, 3],  # IDs de ativos a excluir
    nivel_risco="moderado",              # 'conservador', 'moderado' ou 'arrojado'
    prazo_anos=5                         # Prazo do investimento
)

# Executa a otimização
resultado = service.otimizar()

print(f"Composição da carteira: {resultado['composicao']}")
print(f"Período usado: {resultado['periodo_inicio']} até {resultado['periodo_fim']}")
print(f"Número de meses: {resultado['num_meses']}")
```

### 2. Otimização com Backtest

```python
from datetime import date
from app import create_app
from services.agmo.agmo_service import Nsga2OtimizacaoService

app = create_app()

# Define a data de referência para o backtest
data_referencia = date(2023, 12, 31)  # Usar dados até 31/12/2023

# Cria o serviço COM data_referencia
service = Nsga2OtimizacaoService(
    app=app,
    ids_ativos_restringidos=[1, 2, 3],
    nivel_risco="moderado",
    prazo_anos=5,
    data_referencia=data_referencia  # ✅ Parâmetro de backtest
)

# Executa a otimização com dados até a data de referência
resultado = service.otimizar()

print(f"Modo Backtest: {resultado['modo_backtest']}")
print(f"Data de referência: {resultado['data_referencia']}")
print(f"Composição da carteira: {resultado['composicao']}")
print(f"Período usado: {resultado['periodo_inicio']} até {resultado['periodo_fim']}")
print(f"Número de meses: {resultado['num_meses']}")
```

## Estrutura do Resultado

O método `otimizar()` retorna um dicionário com as seguintes chaves:

```python
{
    'composicao': [
        {
            'id_ativo': 123,
            'ticker': 'PETR4',
            'peso': 0.35
        },
        # ... outros ativos
    ],
    'data_referencia': date(2023, 12, 31) ou None,  # None se não for backtest
    'periodo_inicio': Timestamp('2020-01-31'),      # Data inicial dos dados usados
    'periodo_fim': Timestamp('2023-12-31'),         # Data final dos dados usados
    'num_meses': 48,                                # Quantidade de meses de histórico
    'modo_backtest': True ou False                  # Indica se foi usado backtest
}
```

## Validações

- **Dados suficientes**: O serviço requer no mínimo 12 meses de dados históricos. Se a data de referência resultar em menos de 12 meses, um erro será lançado.
- **Filtro automático**: Quando `data_referencia` é fornecida, APENAS dados com `data <= data_referencia` são considerados.

## Exemplo de Comparação de Carteiras

```python
from datetime import date
from app import create_app
from services.agmo.agmo_service import Nsga2OtimizacaoService

app = create_app()

# Carteira otimizada em 2022
resultado_2022 = Nsga2OtimizacaoService(
    app, [1], "moderado", 5,
    data_referencia=date(2022, 12, 31)
).otimizar()

# Carteira otimizada em 2023
resultado_2023 = Nsga2OtimizacaoService(
    app, [1], "moderado", 5,
    data_referencia=date(2023, 12, 31)
).otimizar()

# Carteira otimizada com todos os dados disponíveis
resultado_atual = Nsga2OtimizacaoService(
    app, [1], "moderado", 5
).otimizar()

# Compare as carteiras
print("Comparação de carteiras ao longo do tempo:")
print(f"2022: {resultado_2022['composicao']}")
print(f"2023: {resultado_2023['composicao']}")
print(f"Atual: {resultado_atual['composicao']}")
```

## Notas Importantes

1. A data de referência deve ser do tipo `datetime.date`
2. O filtro é aplicado no nível da query SQL, garantindo eficiência
3. Todos os métodos de otimização (cálculo de retornos, matriz de covariância, CVaR) funcionam normalmente com os dados filtrados
4. O modo backtest é totalmente transparente para a lógica de otimização
