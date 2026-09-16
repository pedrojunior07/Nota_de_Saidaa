# Automação da Nota de Saída

Este projeto tem como objetivo digitalizar e automatizar o processo de emissão da Nota de Saída para entrega de equipamentos e acessórios aos colaboradores do banco. A solução pretende reduzir o uso de papel, agilizar o fluxo de aprovação e centralizar o registro das entregas em um ambiente mais rastreável e seguro.

## Contexto

Atualmente, a Direção de Informática utiliza um processo manual para controlar a entrega de equipamentos aos colaboradores. Sempre que um computador ou outro acessório é atribuído a um funcionário, é emitida uma Nota de Saída em papel contendo informações sobre o equipamento, o colaborador e os intervenientes do processo.

O documento é impresso e assinado por diferentes partes antes da entrega do equipamento, o que torna o processo burocrático, demorado e dependente de arquivos físicos.

## Problema Identificado

O processo atual apresenta algumas limitações, entre elas:

- dependência de documentos em papel;
- fluxo burocrático e moroso;
- necessidade de recolha manual de assinaturas;
- preenchimento manual de informações;
- dificuldade de consulta ao histórico das entregas;
- dependência de arquivo físico para auditoria e controle.

## Objetivo da Automação

A automação do processo de Nota de Saída tem como finalidade:

- registrar digitalmente os dados da entrega;
- associar o ticket do Remedy ao processo;
- identificar o colaborador destinatário;
- registrar os equipamentos e acessórios entregues;
- registrar a data da entrega;
- armazenar observações ou motivos da atribuição;
- implementar o fluxo de aprovações existente;
- gerar uma versão digital da Nota de Saída;
- manter um histórico para consulta e auditoria.

## Fluxo Proposto

O fluxo digital da Nota de Saída prevê as seguintes etapas:

1. Criação/identificação do ticket no Remedy;
2. Preenchimento da Nota de Saída;
3. Aprovação pelos responsáveis;
4. Confirmação do receptor;
5. Validação da Segurança, quando aplicável;
6. Registo final da entrega e armazenamento digital.

## Funcionalidades Esperadas

A solução deverá permitir:

- criação e gestão de notas de saída digitais;
- associação de tickets do Remedy;
- cadastro de colaboradores e equipamentos;
- registro de múltiplos itens por entrega;
- aprovação por etapas do processo;
- geração de documento digital da nota;
- histórico e consulta das entregas realizadas.
