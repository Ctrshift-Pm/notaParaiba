# Contrato de Dados

## JSON de Saida

```json
{
  "fornecedor": {
    "razao_social": "EMPRESA FORNECEDORA LTDA",
    "fantasia": "FORNECEDORA",
    "cnpj": "12.345.678/0001-90"
  },
  "faturado": {
    "nome_completo": "CLIENTE EXEMPLO",
    "cpf": "123.456.789-00"
  },
  "numero_nota_fiscal": "000123456",
  "data_emissao": "2024-01-15",
  "produtos": [
    {
      "descricao": "Oleo Diesel S10",
      "quantidade": 100
    }
  ],
  "parcelas": [
    {
      "numero": 1,
      "data_vencimento": "2024-02-15",
      "valor": 1500.0
    }
  ],
  "valor_total": 1500.0,
  "classificacoes_despesa": [
    {
      "categoria": "MANUTENCAO E OPERACAO",
      "justificativa": "Produto relacionado a combustiveis e lubrificantes."
    }
  ]
}
```

## Regras

- Campos obrigatorios: `fornecedor`, `faturado`, `numero_nota_fiscal`, `data_emissao`, `produtos`, `parcelas`, `valor_total`, `classificacoes_despesa`.
- Listas sempre devem ser retornadas para `produtos`, `parcelas` e `classificacoes_despesa`.
- Para `GEMINI_API_KEY` ausente ou falha do Gemini: retornar mock local compativel com o mesmo contrato.
- O Gemini deve retornar somente JSON valido, sem texto extra.
- A classificacao final deve usar somente categorias oficiais.

## Categorias de Despesa

- INSUMOS AGRICOLAS
- MANUTENCAO E OPERACAO
- RECURSOS HUMANOS
- SERVICOS OPERACIONAIS
- INFRAESTRUTURA E UTILIDADES
- ADMINISTRATIVAS
- SEGUROS E PROTECAO
- IMPOSTOS E TAXAS
- INVESTIMENTOS
