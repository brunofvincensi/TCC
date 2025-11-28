"""
Funções de Visualização para Análise de Convergência

Este módulo fornece funções para visualizar a evolução das métricas de qualidade
durante a otimização, incluindo gráficos de evolução do R-Hypervolume.
"""

import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, Optional, List
import os
from datetime import datetime


def plot_convergence_evolution(history: Dict,
                               title: str = "Evolução da Convergência - R-NSGA2",
                               save_path: Optional[str] = None,
                               show_plot: bool = True,
                               figsize: tuple = (16, 10)) -> str:
    """
    Cria um gráfico completo mostrando a evolução de todas as métricas de convergência.
    """
    # Verifica se há dados
    if not history or 'generation' not in history or len(history['generation']) == 0:
        print("⚠️  Sem dados para visualizar")
        return None

    generations = history['generation']

    # Identifica qual tipo de hypervolume está sendo usado
    hv_key = 'r_hypervolume' if 'r_hypervolume' in history else 'hypervolume'
    hv_label = 'R-Hypervolume' if hv_key == 'r_hypervolume' else 'Hypervolume'

    # Cria figura com subplots
    fig, axes = plt.subplots(2, 2, figsize=figsize)
    fig.suptitle(title, fontsize=16, fontweight='bold')

    # 1. Evolução do R-Hypervolume / Hypervolume (PRINCIPAL)
    ax1 = axes[0, 0]
    hv_values = history[hv_key]
    ax1.plot(generations, hv_values, linewidth=2.5, color='#2E86AB', marker='o',
             markersize=5, label=hv_label, alpha=0.8)
    ax1.fill_between(generations, min(hv_values), hv_values, alpha=0.3, color='#2E86AB')
    ax1.set_xlabel('Geração', fontsize=11)
    ax1.set_ylabel(hv_label, fontsize=11)
    ax1.set_title(f'Evolução do {hv_label} ao Longo das Gerações', fontsize=12, fontweight='bold')
    ax1.grid(True, alpha=0.3, linestyle='--')
    ax1.legend(loc='lower right', fontsize=9)

    # Adiciona anotação com valor final
    final_hv = hv_values[-1]
    initial_hv = hv_values[0]
    improvement = ((final_hv - initial_hv) / initial_hv * 100) if initial_hv > 0 else 0
    ax1.annotate(f'Final: {final_hv:.6e}\nMelhoria: {improvement:+.1f}%',
                xy=(generations[-1], final_hv),
                xytext=(10, 10), textcoords='offset points',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.7),
                fontsize=9, fontweight='bold')

    # 2. Tamanho da Fronteira de Pareto
    ax2 = axes[0, 1]
    pareto_sizes = history['pareto_size']
    ax2.plot(generations, pareto_sizes, linewidth=2.5, color='#A23B72',
             marker='s', markersize=5, label='Tamanho da Fronteira', alpha=0.8)
    ax2.fill_between(generations, 0, pareto_sizes, alpha=0.3, color='#A23B72')
    ax2.set_xlabel('Geração', fontsize=11)
    ax2.set_ylabel('Número de Soluções', fontsize=11)
    ax2.set_title('Tamanho da Fronteira de Pareto', fontsize=12, fontweight='bold')
    ax2.grid(True, alpha=0.3, linestyle='--')
    ax2.legend(loc='best', fontsize=9)

    # Adiciona anotação
    final_size = pareto_sizes[-1]
    avg_size = np.mean(pareto_sizes)
    ax2.annotate(f'Final: {final_size}\nMédia: {avg_size:.1f}',
                xy=(generations[-1], final_size),
                xytext=(10, 10), textcoords='offset points',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='lightgreen', alpha=0.7),
                fontsize=9, fontweight='bold')

    # 3. Spread (Diversidade)
    ax3 = axes[1, 0]
    spreads = history['spread']
    ax3.plot(generations, spreads, linewidth=2.5, color='#F18F01',
             marker='^', markersize=5, label='Spread', alpha=0.8)
    ax3.fill_between(generations, min(spreads), spreads, alpha=0.3, color='#F18F01')
    ax3.set_xlabel('Geração', fontsize=11)
    ax3.set_ylabel('Spread', fontsize=11)
    ax3.set_title('Diversidade da Fronteira (Spread)', fontsize=12, fontweight='bold')
    ax3.grid(True, alpha=0.3, linestyle='--')
    ax3.legend(loc='best', fontsize=9)

    # Linha de média
    mean_spread = np.mean(spreads)
    ax3.axhline(y=mean_spread, color='red', linestyle='--', alpha=0.7,
                linewidth=1.5, label=f'Média: {mean_spread:.4f}')
    ax3.legend(loc='best', fontsize=9)

    # 4. Spacing (Uniformidade)
    ax4 = axes[1, 1]
    spacings = history['spacing']
    ax4.plot(generations, spacings, linewidth=2.5, color='#0EAD69',
             marker='d', markersize=5, label='Spacing', alpha=0.8)
    ax4.fill_between(generations, 0, spacings, alpha=0.3, color='#0EAD69')
    ax4.set_xlabel('Geração', fontsize=11)
    ax4.set_ylabel('Spacing', fontsize=11)
    ax4.set_title('Uniformidade da Distribuição (Spacing)', fontsize=12, fontweight='bold')
    ax4.grid(True, alpha=0.3, linestyle='--')
    ax4.legend(loc='best', fontsize=9)

    # Linha de média
    mean_spacing = np.mean(spacings)
    ax4.axhline(y=mean_spacing, color='red', linestyle='--', alpha=0.7,
                linewidth=1.5, label=f'Média: {mean_spacing:.6e}')
    ax4.legend(loc='best', fontsize=9)

    plt.tight_layout()

    # Salva o gráfico se caminho foi fornecido
    if save_path:
        # Garante que o diretório existe
        directory = os.path.dirname(save_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

        full_path = os.path.abspath(save_path)
        plt.savefig(full_path, dpi=300, bbox_inches='tight')
        print(f"\n✅ Gráfico de convergência salvo em: {full_path}")
    else:
        # Gera nome automático
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = f'convergence_evolution_{timestamp}.png'
        full_path = os.path.abspath(save_path)
        plt.savefig(full_path, dpi=300, bbox_inches='tight')
        print(f"\n✅ Gráfico de convergência salvo em: {full_path}")

    if show_plot:
        plt.show()
    else:
        plt.close()

    return full_path


def plot_hypervolume_only(history: Dict,
                         title: str = "Evolução do R-Hypervolume",
                         save_path: Optional[str] = None,
                         show_plot: bool = True,
                         figsize: tuple = (12, 7)) -> str:
    """
    Cria um gráfico focado apenas na evolução do R-Hypervolume/Hypervolume.
    """
    # Verifica se há dados
    if not history or 'generation' not in history or len(history['generation']) == 0:
        print("⚠️  Sem dados para visualizar")
        return None

    generations = history['generation']

    # Identifica qual tipo de hypervolume está sendo usado
    hv_key = 'r_hypervolume' if 'r_hypervolume' in history else 'hypervolume'
    hv_label = 'R-Hypervolume' if hv_key == 'r_hypervolume' else 'Hypervolume'

    hv_values = history[hv_key]

    # Cria figura
    fig, ax = plt.subplots(figsize=figsize)
    fig.suptitle(title, fontsize=16, fontweight='bold')

    # Plot principal
    ax.plot(generations, hv_values, linewidth=3, color='#2E86AB', marker='o',
            markersize=6, label=hv_label, alpha=0.9)
    ax.fill_between(generations, min(hv_values), hv_values, alpha=0.3, color='#2E86AB')

    # Configurações
    ax.set_xlabel('Geração', fontsize=13)
    ax.set_ylabel(hv_label, fontsize=13)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.legend(loc='lower right', fontsize=11)

    # Estatísticas
    initial_hv = hv_values[0]
    final_hv = hv_values[-1]
    max_hv = max(hv_values)
    improvement = ((final_hv - initial_hv) / initial_hv * 100) if initial_hv > 0 else 0

    # Adiciona anotações
    ax.annotate(f'Inicial: {initial_hv:.6e}',
                xy=(generations[0], initial_hv),
                xytext=(20, -30), textcoords='offset points',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='lightblue', alpha=0.8),
                fontsize=10, fontweight='bold',
                arrowprops=dict(arrowstyle='->', color='black', lw=1.5))

    ax.annotate(f'Final: {final_hv:.6e}\nMelhoria: {improvement:+.1f}%',
                xy=(generations[-1], final_hv),
                xytext=(-100, 30), textcoords='offset points',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.8),
                fontsize=10, fontweight='bold',
                arrowprops=dict(arrowstyle='->', color='black', lw=1.5))

    # Linha de máximo
    if max_hv > final_hv:
        max_gen = generations[hv_values.index(max_hv)]
        ax.axhline(y=max_hv, color='green', linestyle='--', alpha=0.5, linewidth=1.5)
        ax.annotate(f'Máximo: {max_hv:.6e} (gen {max_gen})',
                    xy=(max_gen, max_hv),
                    xytext=(10, 10), textcoords='offset points',
                    bbox=dict(boxstyle='round,pad=0.5', facecolor='lightgreen', alpha=0.7),
                    fontsize=9)

    plt.tight_layout()

    # Salva o gráfico
    if save_path:
        # Garante que o diretório existe
        directory = os.path.dirname(save_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

        full_path = os.path.abspath(save_path)
        plt.savefig(full_path, dpi=300, bbox_inches='tight')
        print(f"\n✅ Gráfico de {hv_label} salvo em: {full_path}")
    else:
        # Gera nome automático
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = f'{hv_key}_evolution_{timestamp}.png'
        full_path = os.path.abspath(save_path)
        plt.savefig(full_path, dpi=300, bbox_inches='tight')
        print(f"\n✅ Gráfico de {hv_label} salvo em: {full_path}")

    if show_plot:
        plt.show()
    else:
        plt.close()

    return full_path


def plot_multiple_runs_comparison(histories: List[Dict],
                                  labels: List[str],
                                  title: str = "Comparação de Múltiplas Execuções",
                                  save_path: Optional[str] = None,
                                  show_plot: bool = True,
                                  figsize: tuple = (14, 8)) -> str:
    """
    Compara a evolução do R-Hypervolume de múltiplas execuções em um único gráfico.
    """
    if not histories or len(histories) == 0:
        print("⚠️  Sem dados para visualizar")
        return None

    # Identifica qual tipo de hypervolume está sendo usado
    hv_key = 'r_hypervolume' if 'r_hypervolume' in histories[0] else 'hypervolume'
    hv_label = 'R-Hypervolume' if hv_key == 'r_hypervolume' else 'Hypervolume'

    # Cores para cada execução
    colors = ['#2E86AB', '#A23B72', '#F18F01', '#0EAD69', '#C73E1D', '#6A4C93']

    # Cria figura
    fig, ax = plt.subplots(figsize=figsize)
    fig.suptitle(title, fontsize=16, fontweight='bold')

    # Plot cada execução
    for i, (history, label) in enumerate(zip(histories, labels)):
        if not history or 'generation' not in history:
            continue

        generations = history['generation']
        hv_values = history[hv_key]
        color = colors[i % len(colors)]

        ax.plot(generations, hv_values, linewidth=2.5, color=color,
                marker='o', markersize=4, label=label, alpha=0.8)

    # Configurações
    ax.set_xlabel('Geração', fontsize=13)
    ax.set_ylabel(hv_label, fontsize=13)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.legend(loc='best', fontsize=10)

    plt.tight_layout()

    # Salva o gráfico
    if save_path:
        directory = os.path.dirname(save_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

        full_path = os.path.abspath(save_path)
        plt.savefig(full_path, dpi=300, bbox_inches='tight')
        print(f"\n✅ Gráfico de comparação salvo em: {full_path}")
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = f'comparison_{timestamp}.png'
        full_path = os.path.abspath(save_path)
        plt.savefig(full_path, dpi=300, bbox_inches='tight')
        print(f"\n✅ Gráfico de comparação salvo em: {full_path}")

    if show_plot:
        plt.show()
    else:
        plt.close()

    return full_path


def print_convergence_summary(history: Dict):
    """
    Imprime um resumo estatístico da convergência.
    """
    if not history or 'generation' not in history or len(history['generation']) == 0:
        print("⚠️  Sem dados para resumir")
        return

    # Identifica qual tipo de hypervolume está sendo usado
    hv_key = 'r_hypervolume' if 'r_hypervolume' in history else 'hypervolume'
    hv_label = 'R-Hypervolume' if hv_key == 'r_hypervolume' else 'Hypervolume'

    generations = history['generation']
    hv_values = history[hv_key]
    spreads = history['spread']
    spacings = history['spacing']
    pareto_sizes = history['pareto_size']

    print(f"\n{'='*70}")
    print(f"📊 RESUMO DA CONVERGÊNCIA")
    print(f"{'='*70}")

    print(f"\n📈 {hv_label}:")
    print(f"   Inicial:  {hv_values[0]:.6e}")
    print(f"   Final:    {hv_values[-1]:.6e}")
    print(f"   Máximo:   {max(hv_values):.6e} (geração {generations[hv_values.index(max(hv_values))]})")
    print(f"   Mínimo:   {min(hv_values):.6e} (geração {generations[hv_values.index(min(hv_values))]})")

    improvement = ((hv_values[-1] - hv_values[0]) / hv_values[0] * 100) if hv_values[0] > 0 else 0
    print(f"   Melhoria: {improvement:+.2f}%")

    print(f"\n📊 Tamanho da Fronteira de Pareto:")
    print(f"   Inicial:  {pareto_sizes[0]}")
    print(f"   Final:    {pareto_sizes[-1]}")
    print(f"   Média:    {np.mean(pareto_sizes):.1f}")
    print(f"   Máximo:   {max(pareto_sizes)}")

    print(f"\n🎯 Spread (Diversidade):")
    print(f"   Inicial:  {spreads[0]:.6f}")
    print(f"   Final:    {spreads[-1]:.6f}")
    print(f"   Média:    {np.mean(spreads):.6f}")

    print(f"\n📏 Spacing (Uniformidade):")
    print(f"   Inicial:  {spacings[0]:.6e}")
    print(f"   Final:    {spacings[-1]:.6e}")
    print(f"   Média:    {np.mean(spacings):.6e}")

    print(f"\n⏱️  Gerações:")
    print(f"   Total:    {len(generations)}")
    print(f"   Range:    {min(generations)} - {max(generations)}")

    print(f"\n{'='*70}\n")
