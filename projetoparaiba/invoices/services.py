from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
import re
import unicodedata
from uuid import uuid4

from django.db import transaction

from .agents import (
    ExpenseClassificationAgent,
    PdfExtractionAgent,
    PersistenceAgent,
    ValidationAgent,
)
from .models import Classificacao, InvoiceExtraction, MovimentoContas, ParcelaContas, Pessoa


class InvoiceExtractionService:
    def __init__(self) -> None:
        self.pdf_agent = PdfExtractionAgent()
        self.classification_agent = ExpenseClassificationAgent()
        self.validation_agent = ValidationAgent()
        self.persistence_agent = PersistenceAgent()
        self.registration_service = InvoiceRegistrationService()

    def extract(self, uploaded_file) -> dict:
        extraction = self.pdf_agent.extract(uploaded_file)
        data = self.validation_agent.normalize(extraction.data)

        if not self._should_preserve_gemini_classification(extraction.data):
            data["classificacoes_despesa"] = self.classification_agent.classify(data["produtos"])

        data = self.validation_agent.normalize(data)
        record = self.persistence_agent.save_success(uploaded_file, data, extraction.provider)
        registration = self.registration_service.processar_lancamento(record, data)

        payload = {
            "success": True,
            "id": record.id,
            "provider": extraction.provider,
            "data": data,
            "analysis": registration,
            "message": registration["mensagem"],
        }
        if extraction.fallback_reason:
            payload["fallback_reason"] = extraction.fallback_reason
        return payload

    def _should_preserve_gemini_classification(self, raw_data: object) -> bool:
        if not isinstance(raw_data, Mapping):
            return False

        classification = raw_data.get("classificacoes_despesa")
        if not isinstance(classification, list) or not classification:
            return False

        for item in classification:
            if not isinstance(item, Mapping):
                return False
            categoria = str(item.get("categoria", "")).strip()
            justificativa = str(item.get("justificativa", "")).strip()
            if not categoria or not justificativa:
                return False
            if not self.classification_agent.is_official_category(categoria):
                return False

        return True


class InvoiceRegistrationService:
    @transaction.atomic
    def processar_lancamento(self, extraction_record: InvoiceExtraction, data: dict) -> dict:
        fornecedor_match = self.consultar_fornecedor(data)
        fornecedor = fornecedor_match or self.criar_fornecedor(data)

        faturado_match = self.consultar_faturado(data)
        faturado = faturado_match or self.criar_faturado(data)

        despesa_match = self.consultar_despesa(data)
        despesa = despesa_match or self.criar_despesa(data)

        movimento = self.criar_movimento(extraction_record, data, fornecedor, faturado, despesa)
        parcelas = [self.criar_parcela(movimento, parcela, data) for parcela in data.get("parcelas", [])]

        return {
            "fornecedor": self.exibir_resultado_consulta_fornecedor(data, fornecedor_match, fornecedor),
            "faturado": self.exibir_resultado_consulta_faturado(data, faturado_match, faturado),
            "despesa": self.exibir_resultado_consulta_despesa(data, despesa_match, despesa),
            "movimento": {
                "id": movimento.id,
                "tipo": movimento.tipo,
                "status_texto": f"MOVIMENTO APAGAR criado - ID: {movimento.id}",
            },
            "parcelas": [
                {
                    "id": parcela.id,
                    "identificacao": parcela.identificacao,
                    "numero_parcela": parcela.numero_parcela,
                    "valor": float(parcela.valor),
                    "data_vencimento": parcela.data_vencimento,
                }
                for parcela in parcelas
            ],
            "mensagem": "Registro lançado com sucesso.",
        }

    # Requisito da atividade: consultar fornecedor por documento e, se necessário, por razão social.
    def consultar_fornecedor(self, data: dict) -> Pessoa | None:
        fornecedor = data.get("fornecedor", {})
        return self._consultar_pessoa(
            tipo=Pessoa.Tipo.CLIENTE_FORNECEDOR,
            documento=fornecedor.get("cnpj") or fornecedor.get("cpf"),
            razao_social=fornecedor.get("razao_social"),
        )

    # Requisito da atividade: consultar faturado por documento e, se necessário, por razão social.
    def consultar_faturado(self, data: dict) -> Pessoa | None:
        faturado = data.get("faturado", {})
        return self._consultar_pessoa(
            tipo=Pessoa.Tipo.FATURADO,
            documento=faturado.get("cpf") or faturado.get("cnpj"),
            razao_social=faturado.get("nome_completo"),
        )

    # Requisito da atividade: consultar despesa na tabela CLASSIFICACAO.
    def consultar_despesa(self, data: dict) -> Classificacao | None:
        descricao = self._descricao_despesa(data)
        if not descricao:
            return None
        return (
            Classificacao.objects.filter(tipo=Classificacao.Tipo.DESPESA)
            .filter(descricao__iexact=descricao.strip())
            .order_by("id")
            .first()
        )

    # Requisito da atividade: criar fornecedor apenas quando não existir.
    def criar_fornecedor(self, data: dict) -> Pessoa:
        fornecedor = data.get("fornecedor", {})
        return Pessoa.objects.create(
            tipo=Pessoa.Tipo.CLIENTE_FORNECEDOR,
            razao_social=self._coalesce(fornecedor.get("razao_social"), "FORNECEDOR NAO INFORMADO"),
            documento=self._clean_document(fornecedor.get("cnpj") or fornecedor.get("cpf")),
            inscricao_estadual=self._string(fornecedor.get("inscricao_estadual")),
            endereco=self._string(fornecedor.get("endereco")),
            cidade=self._string(fornecedor.get("cidade")),
            uf=self._string(fornecedor.get("uf"))[:2],
        )

    # Requisito da atividade: criar faturado apenas quando não existir.
    def criar_faturado(self, data: dict) -> Pessoa:
        faturado = data.get("faturado", {})
        return Pessoa.objects.create(
            tipo=Pessoa.Tipo.FATURADO,
            razao_social=self._coalesce(faturado.get("nome_completo"), "FATURADO NAO INFORMADO"),
            documento=self._clean_document(faturado.get("cpf") or faturado.get("cnpj")),
            endereco=self._string(faturado.get("endereco")),
            cidade=self._string(faturado.get("cidade")),
            uf=self._string(faturado.get("uf"))[:2],
        )

    # Requisito da atividade: criar despesa apenas quando não existir.
    def criar_despesa(self, data: dict) -> Classificacao:
        return Classificacao.objects.create(
            tipo=Classificacao.Tipo.DESPESA,
            descricao=self._coalesce(self._descricao_despesa(data), "DESPESA NAO INFORMADA"),
        )

    # Requisito da atividade: criar MOVIMENTOCONTAS com tipo APAGAR.
    def criar_movimento(
        self,
        extraction_record: InvoiceExtraction,
        data: dict,
        fornecedor: Pessoa,
        faturado: Pessoa,
        despesa: Classificacao,
    ) -> MovimentoContas:
        # Se o banco real exigir mais campos obrigatórios, preencher aqui.
        return MovimentoContas.objects.create(
            tipo=MovimentoContas.Tipo.APAGAR,
            fornecedor=fornecedor,
            faturado=faturado,
            classificacao=despesa,
            invoice_extraction=extraction_record,
            numero_nota_fiscal=self._string(data.get("numero_nota_fiscal")),
            serie=self._string(data.get("serie")),
            data_emissao=self._string(data.get("data_emissao")),
            valor_total=self._decimal(data.get("valor_total")),
            observacao=self._build_observacao(data),
        )

    # Requisito da atividade: criar PARCELACONTAS com identificacao única.
    def criar_parcela(self, movimento: MovimentoContas, parcela_data: dict, data: dict) -> ParcelaContas:
        # Se o banco real exigir mais campos obrigatórios, preencher aqui.
        return ParcelaContas.objects.create(
            movimento=movimento,
            identificacao=self._gerar_identificacao_parcela(data, parcela_data),
            numero_parcela=int(parcela_data.get("numero") or 1),
            data_vencimento=self._string(parcela_data.get("data_vencimento")),
            valor=self._decimal(parcela_data.get("valor")),
            forma_pagamento=self._string(parcela_data.get("forma_pagamento")),
        )

    # Requisito da atividade: exibir resultado da análise na tela.
    def exibir_resultado_consulta_fornecedor(self, data: dict, existente: Pessoa | None, final: Pessoa) -> dict:
        fornecedor = data.get("fornecedor", {})
        return self._build_analysis_result(
            titulo="FORNECEDOR",
            nome=self._coalesce(fornecedor.get("razao_social"), final.razao_social),
            documento=fornecedor.get("cnpj") or fornecedor.get("cpf") or final.documento,
            existente=existente,
            final=final,
        )

    def exibir_resultado_consulta_faturado(self, data: dict, existente: Pessoa | None, final: Pessoa) -> dict:
        faturado = data.get("faturado", {})
        return self._build_analysis_result(
            titulo="FATURADO",
            nome=self._coalesce(faturado.get("nome_completo"), final.razao_social),
            documento=faturado.get("cpf") or faturado.get("cnpj") or final.documento,
            existente=existente,
            final=final,
        )

    def exibir_resultado_consulta_despesa(self, data: dict, existente: Classificacao | None, final: Classificacao) -> dict:
        descricao = self._coalesce(self._descricao_despesa(data), final.descricao)
        existe = existente is not None
        return {
            "titulo": "DESPESA",
            "nome": descricao,
            "documento_label": "Tipo",
            "documento": Classificacao.Tipo.DESPESA,
            "existe": existe,
            "id": final.id,
            "acao": "reutilizado" if existe else "criado",
            "status_texto": f"EXISTE - ID: {final.id}" if existe else f"NAO EXISTE - criado ID: {final.id}",
        }

    def _consultar_pessoa(self, *, tipo: str, documento: object, razao_social: object) -> Pessoa | None:
        documento_limpo = self._clean_document(documento)
        if documento_limpo:
            pessoa = (
                Pessoa.objects.filter(tipo=tipo, documento=documento_limpo)
                .order_by("id")
                .first()
            )
            if pessoa:
                return pessoa

        nome_normalizado = self._normalize_text(razao_social)
        if nome_normalizado:
            for pessoa in Pessoa.objects.filter(tipo=tipo).order_by("id"):
                if self._normalize_text(pessoa.razao_social) == nome_normalizado:
                    return pessoa
        return None

    def _build_analysis_result(self, *, titulo: str, nome: str, documento: object, existente, final) -> dict:
        documento_str = self._string(documento)
        return {
            "titulo": titulo,
            "nome": nome,
            "documento_label": self._document_label(documento_str),
            "documento": documento_str,
            "existe": existente is not None,
            "id": final.id,
            "acao": "reutilizado" if existente else "criado",
            "status_texto": f"EXISTE - ID: {final.id}" if existente else f"NAO EXISTE - criado ID: {final.id}",
        }

    def _descricao_despesa(self, data: dict) -> str:
        classificacoes = data.get("classificacoes_despesa") or []
        if not classificacoes:
            return ""
        primeira = classificacoes[0] if isinstance(classificacoes[0], dict) else {}
        return self._string(primeira.get("categoria"))

    def _build_observacao(self, data: dict) -> str:
        partes = []
        natureza = self._string(data.get("natureza_operacao"))
        if natureza:
            partes.append(f"Natureza da operacao: {natureza}")
        chave = self._string(data.get("chave_acesso"))
        if chave:
            partes.append(f"Chave de acesso: {chave}")
        if not partes:
            partes.append("Lancamento gerado automaticamente a partir da extracao da nota fiscal.")
        return " | ".join(partes)

    def _gerar_identificacao_parcela(self, data: dict, parcela_data: dict) -> str:
        numero_nota = self._slug(self._string(data.get("numero_nota_fiscal")) or "sem-nota")
        numero_parcela = int(parcela_data.get("numero") or 1)
        base = f"APAGAR-{numero_nota}-{numero_parcela}"
        identificacao = base
        while ParcelaContas.objects.filter(identificacao=identificacao).exists():
            identificacao = f"{base}-{uuid4().hex[:6].upper()}"
        return identificacao

    def _document_label(self, documento: str) -> str:
        digits = self._clean_document(documento)
        if len(digits) == 11:
            return "CPF"
        if len(digits) == 14:
            return "CNPJ"
        return "Documento"

    def _clean_document(self, value: object) -> str:
        return re.sub(r"\D", "", self._string(value))

    def _normalize_text(self, value: object) -> str:
        text = self._string(value).lower()
        normalized = unicodedata.normalize("NFKD", text)
        return "".join(char for char in normalized if not unicodedata.combining(char)).strip()

    def _slug(self, value: str) -> str:
        slug = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").upper()
        return slug or "SEM-VALOR"

    def _string(self, value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _coalesce(self, value: object, fallback: str) -> str:
        return self._string(value) or fallback

    def _decimal(self, value: object) -> Decimal:
        if value in (None, ""):
            return Decimal("0")
        try:
            return Decimal(str(value))
        except Exception:
            return Decimal("0")
