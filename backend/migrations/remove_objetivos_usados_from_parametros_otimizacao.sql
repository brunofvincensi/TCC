-- Migration: Remover coluna objetivos_usados da tabela parametros_otimizacao
-- Data: 2025-11-17
-- Descrição: Remove a coluna objetivos_usados que não está mais sendo utilizada

ALTER TABLE parametros_otimizacao
DROP COLUMN IF EXISTS objetivos_usados;
