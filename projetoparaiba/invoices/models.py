from __future__ import annotations

from django.db import models


class InvoiceExtraction(models.Model):
    class Status(models.TextChoices):
        SUCCESS = "success", "Sucesso"
        ERROR = "error", "Erro"

    file_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(default=0)
    provider = models.CharField(max_length=32, default="mock")
    status = models.CharField(max_length=16, choices=Status.choices)
    result_json = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.file_name} ({self.status})"


class Pessoa(models.Model):
    class Tipo(models.TextChoices):
        CLIENTE_FORNECEDOR = "CLIENTE-FORNECEDOR", "Cliente-Fornecedor"
        FATURADO = "FATURADO", "Faturado"

    tipo = models.CharField(max_length=32, choices=Tipo.choices)
    razao_social = models.CharField(max_length=255)
    documento = models.CharField(max_length=32, blank=True, db_index=True)
    inscricao_estadual = models.CharField(max_length=32, blank=True)
    endereco = models.CharField(max_length=255, blank=True)
    cidade = models.CharField(max_length=120, blank=True)
    uf = models.CharField(max_length=2, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "PESSOAS"
        ordering = ["razao_social", "id"]

    def __str__(self) -> str:
        return f"{self.razao_social} ({self.tipo})"


class Classificacao(models.Model):
    class Tipo(models.TextChoices):
        DESPESA = "DESPESA", "Despesa"

    tipo = models.CharField(max_length=32, choices=Tipo.choices)
    descricao = models.CharField(max_length=255, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "CLASSIFICACAO"
        ordering = ["descricao", "id"]

    def __str__(self) -> str:
        return f"{self.descricao} ({self.tipo})"


class MovimentoContas(models.Model):
    class Tipo(models.TextChoices):
        APAGAR = "APAGAR", "A Pagar"

    tipo = models.CharField(max_length=16, choices=Tipo.choices, default=Tipo.APAGAR)
    fornecedor = models.ForeignKey(Pessoa, on_delete=models.PROTECT, related_name="movimentos_fornecedor")
    faturado = models.ForeignKey(Pessoa, on_delete=models.PROTECT, related_name="movimentos_faturado")
    classificacao = models.ForeignKey(Classificacao, on_delete=models.PROTECT, related_name="movimentos")
    invoice_extraction = models.ForeignKey(InvoiceExtraction, on_delete=models.SET_NULL, null=True, blank=True, related_name="movimentos")
    numero_nota_fiscal = models.CharField(max_length=64, blank=True)
    serie = models.CharField(max_length=32, blank=True)
    data_emissao = models.CharField(max_length=32, blank=True)
    valor_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    observacao = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "MOVIMENTOCONTAS"
        ordering = ["-id"]

    def __str__(self) -> str:
        return f"Movimento {self.id} - {self.tipo}"


class ParcelaContas(models.Model):
    movimento = models.ForeignKey(MovimentoContas, on_delete=models.CASCADE, related_name="parcelas")
    identificacao = models.CharField(max_length=64, unique=True)
    numero_parcela = models.PositiveIntegerField(default=1)
    data_vencimento = models.CharField(max_length=32, blank=True)
    valor = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    forma_pagamento = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "PARCELACONTAS"
        ordering = ["movimento_id", "numero_parcela", "id"]

    def __str__(self) -> str:
        return self.identificacao
