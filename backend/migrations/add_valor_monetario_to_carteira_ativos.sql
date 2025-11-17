-- Migration: Adicionar coluna valor_monetario à tabela carteira_ativos
-- Data: 2025-11-17
-- Descrição: Adiciona coluna para armazenar o valor monetário alocado em cada ativo da carteira

ALTER TABLE carteira_ativos
ADD COLUMN valor_monetario NUMERIC(15, 2);

-- Comentário explicando o propósito da coluna
COMMENT ON COLUMN carteira_ativos.valor_monetario IS 'Valor monetário alocado no ativo (calculado como capital_usado * peso)';
