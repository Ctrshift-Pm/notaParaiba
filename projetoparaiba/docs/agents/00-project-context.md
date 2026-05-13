# Contexto do Projeto

## Objetivo

Implementar a Etapa 1 do projeto administrativo-financeiro N2: uma aplicacao web que recebe PDF de nota fiscal, extrai dados de contas a pagar com Gemini ou fallback mock, classifica a despesa e mostra o JSON ao usuario.

## Stack

- Backend: Django.
- Banco: PostgreSQL via Docker Compose.
- Desenvolvimento local: SQLite permitido quando `DATABASE_URL` nao estiver definido.
- LLM: Gemini quando `GEMINI_API_KEY` existir; mock local quando nao existir.
- Frontend: templates Django, CSS e JavaScript simples.

## Escopo da Etapa 1

- Upload de PDF.
- Botao para extrair dados.
- Agentes para extracao, classificacao, validacao e persistencia.
- JSON exibido na tela.
- Classificacao de despesa interpretada a partir dos produtos da nota fiscal.

## Ciclo de Agentes exigido pelo PPTX

Sequencia operacional obrigatoria no backend:

- Perceber: `PdfExtractionAgent`
  - receber o arquivo PDF
  - extrair texto da nota
  - disparar interpretacao com Gemini quando disponivel, com fallback local quando nao disponivel
- Processar/Interpretar: `PdfExtractionAgent` + `ValidationAgent`
  - converter o texto extraido em estrutura JSON do contrato
  - normalizar chaves e tipos esperados
- Decidir: `ExpenseClassificationAgent`
  - inferir `classificacoes_despesa` a partir de `produtos`
  - garantir que somente categorias oficiais sejam usadas
- Agir: `PersistenceAgent`
  - persistir o resultado processado para trilha de auditoria e retorno da extracao

O `InvoiceExtractionService` orquestra esse fluxo em sequencia explicita:
`Usuario -> PdfExtractionAgent -> ValidationAgent -> ExpenseClassificationAgent -> PersistenceAgent`.
