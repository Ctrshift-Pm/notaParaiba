from __future__ import annotations

import json
import re
from dataclasses import dataclass
from io import BytesIO
from typing import Any

from django.conf import settings
from pypdf import PdfReader


@dataclass
class ExtractionResult:
    data: dict
    provider: str
    fallback_reason: str | None = None


class PdfExtractionAgent:
    def extract(self, uploaded_file) -> ExtractionResult:
        pdf_text = self._perceive(uploaded_file)
        return self._process_and_interpret(pdf_text)

    def _perceive(self, uploaded_file) -> str:
        return self._read_pdf_text(uploaded_file)

    def _process_and_interpret(self, pdf_text: str) -> ExtractionResult:
        gemini_api_key = str(getattr(settings, "GEMINI_API_KEY", "") or "").strip()
        if gemini_api_key:
            try:
                return ExtractionResult(
                    data=self._extract_with_gemini(pdf_text),
                    provider="gemini",
                )
            except Exception as exc:
                return ExtractionResult(
                    data=self._mock_data(pdf_text),
                    provider="mock",
                    fallback_reason=self._safe_fallback_reason(exc),
                )

        return ExtractionResult(
            data=self._mock_data(pdf_text),
            provider="mock",
            fallback_reason="GEMINI_API_KEY nao foi configurada.",
        )

    def _read_pdf_text(self, uploaded_file) -> str:
        uploaded_file.seek(0)
        payload = uploaded_file.read()
        uploaded_file.seek(0)
        try:
            reader = PdfReader(BytesIO(payload), strict=False)
            pages = [page.extract_text() or "" for page in reader.pages]
            text = "\n".join(pages).strip()
        except Exception as exc:
            raise ValueError("Falha ao ler PDF. Envie um arquivo PDF valido e nao corrompido.") from exc

        if not text:
            raise ValueError("Nao foi possivel extrair texto do PDF enviado.")

        return text

    def _extract_with_gemini(self, pdf_text: str) -> dict:
        from google import genai

        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=self._prompt(pdf_text),
        )
        return self._parse_json(response.text or "")

    def _prompt(self, pdf_text: str) -> str:
        contract = """
Formato esperado do contrato (apenas JSON):
{
  "fornecedor": {
    "razao_social":"", "fantasia":"", "cnpj":"",
    "inscricao_estadual":"", "endereco":"", "cidade":"", "uf":""
  },
  "faturado": {
    "nome_completo":"", "cpf":"", "cnpj":"",
    "endereco":"", "cidade":"", "uf":""
  },
  "numero_nota_fiscal":"", "data_emissao":"YYYY-MM-DD",
  "serie":"", "chave_acesso":"", "natureza_operacao":"",
  "produtos":[{
    "descricao":"", "quantidade":0, "unidade":"",
    "valor_unitario":0.0, "valor_total":0.0, "ncm":"", "cfop":""
  }],
  "parcelas":[{"numero":1, "data_vencimento":"YYYY-MM-DD", "valor":0.0, "forma_pagamento":""}],
  "valor_produtos":0.0, "valor_desconto":0.0, "valor_frete":0.0, "valor_icms":0.0, "valor_ipi":0.0,
  "valor_total":0.0,
  "classificacoes_despesa":[{"categoria":"", "justificativa":""}]
}
"""
        return f"""
Extraia os dados de uma DANFE/NF-e e devolva SOMENTE JSON valido, sem texto adicional, sem explicacoes e sem markdown.
Entrada: texto cru da nota fiscal:
\"\"\"{pdf_text[:12000]}\"\"\"

{contract}
Regras:
- Extrair `fornecedor` como emitente da nota.
- Extrair `faturado` como destinatario da nota.
- Extrair `numero_nota_fiscal`, `data_emissao`, `serie`, `chave_acesso` e `natureza_operacao` quando existirem.
- Extrair `produtos` a partir de itens da nota fiscal.
- Quando possivel, incluir `unidade`, `valor_unitario`, `valor_total`, `ncm` e `cfop` em cada item.
- Extrair `parcelas` com os dados de vencimento, duplicatas e incluir `forma_pagamento` quando disponivel.
- Extrair `inscricao_estadual`, `endereco`, `cidade` e `uf` de fornecedor e faturado quando disponiveis.
- Extrair `valor_produtos`, `valor_desconto`, `valor_frete`, `valor_icms`, `valor_ipi` e `valor_total` quando estiverem no documento.
- Use listas para `produtos`, `parcelas` e `classificacoes_despesa`, mesmo com 1 item.
- Classifique a despesa usando apenas as categorias oficiais:
  - INSUMOS AGRICOLAS
  - MANUTENCAO E OPERACAO
  - RECURSOS HUMANOS
  - SERVICOS OPERACIONAIS
  - INFRAESTRUTURA E UTILIDADES
  - ADMINISTRATIVAS
  - SEGUROS E PROTECAO
  - IMPOSTOS E TAXAS
  - INVESTIMENTOS
- `classificacoes_despesa` precisa ser um objeto com `categoria` e `justificativa`, com categoria oficialmente valida.
- Se algum campo faltar, use string vazia, lista vazia ou 0.
- Nunca use markdown.
"""

    def _parse_json(self, text: str) -> dict:
        fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if fenced:
            text = fenced.group(1)

        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("Gemini nao retornou JSON.")

        try:
            parsed: dict[str, Any] = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ValueError("Gemini retornou um texto que nao e JSON valido.") from exc

        if not isinstance(parsed, dict):
            raise ValueError("Gemini nao retornou objeto JSON.")

        return parsed

    def _safe_fallback_reason(self, exc: Exception) -> str:
        message = str(exc).strip() or exc.__class__.__name__
        gemini_api_key = str(getattr(settings, "GEMINI_API_KEY", "") or "").strip()
        if gemini_api_key:
            message = message.replace(gemini_api_key, "[redacted]")
        message = re.sub(r"AIza[0-9A-Za-z_-]{20,}", "[redacted]", message)
        message = re.sub(r"\s+", " ", message)[:240]
        return f"Falha ao usar Gemini ({exc.__class__.__name__}): {message}"

    def _mock_data(self, pdf_text: str) -> dict:
        lowered = pdf_text.lower()
        product = "Oleo Diesel S10" if "diesel" in lowered or not lowered else "Material Hidraulico"
        return {
            "fornecedor": {
                "razao_social": "EMPRESA FORNECEDORA LTDA",
                "fantasia": "FORNECEDORA",
                "cnpj": "12.345.678/0001-90",
                "inscricao_estadual": "123456789",
                "endereco": "Rodovia BR 230, KM 12",
                "cidade": "Campina Grande",
                "uf": "PB",
            },
            "faturado": {
                "nome_completo": "CLIENTE EXEMPLO",
                "cpf": "123.456.789-00",
                "cnpj": "",
                "endereco": "Rua das Flores, 100",
                "cidade": "Joao Pessoa",
                "uf": "PB",
            },
            "numero_nota_fiscal": "000123456",
            "data_emissao": "2024-01-15",
            "serie": "1",
            "chave_acesso": "25240112345678000190550010001234561000012345",
            "natureza_operacao": "Venda de mercadoria",
            "produtos": [
                {
                    "descricao": product,
                    "quantidade": 100,
                    "unidade": "LT",
                    "valor_unitario": 15.0,
                    "valor_total": 1500.0,
                    "ncm": "27101921",
                    "cfop": "5102",
                }
            ],
            "parcelas": [
                {
                    "numero": 1,
                    "data_vencimento": "2024-02-15",
                    "valor": 1500.0,
                    "forma_pagamento": "Boleto",
                }
            ],
            "valor_produtos": 1500.0,
            "valor_desconto": 0.0,
            "valor_frete": 0.0,
            "valor_icms": 270.0,
            "valor_ipi": 0.0,
            "valor_total": 1500.0,
            "classificacoes_despesa": [],
        }
