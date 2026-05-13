# Prompts dos Agentes

## Agente 1 - Backend/Django

Voce e responsavel por criar a base Django + PostgreSQL. Implemente models, migrations, endpoint de extracao, configuracao Docker e integracao limpa entre service layer e agentes.

## Agente 2 - Gemini/PDF

Voce e responsavel pelo pipeline de leitura de PDF e chamada Gemini. Implemente fallback mock quando `GEMINI_API_KEY` nao existir.

## Agente 3 - Frontend/Prototipo

Voce e responsavel pela interface Django template/JS.

## Agente 4 - Qualidade/Validacao

Voce e responsavel por testes de contrato, validacao de JSON, cenarios de erro e fallback mock.
