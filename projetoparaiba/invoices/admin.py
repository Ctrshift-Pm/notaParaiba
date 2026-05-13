from django.contrib import admin

from .models import Classificacao, InvoiceExtraction, MovimentoContas, ParcelaContas, Pessoa


@admin.register(InvoiceExtraction)
class InvoiceExtractionAdmin(admin.ModelAdmin):
    list_display = ("file_name", "status", "provider", "created_at")
    list_filter = ("status", "provider", "created_at")
    search_fields = ("file_name",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Pessoa)
class PessoaAdmin(admin.ModelAdmin):
    list_display = ("id", "razao_social", "tipo", "documento", "cidade", "uf")
    list_filter = ("tipo", "uf")
    search_fields = ("razao_social", "documento")


@admin.register(Classificacao)
class ClassificacaoAdmin(admin.ModelAdmin):
    list_display = ("id", "descricao", "tipo")
    list_filter = ("tipo",)
    search_fields = ("descricao",)


@admin.register(MovimentoContas)
class MovimentoContasAdmin(admin.ModelAdmin):
    list_display = ("id", "tipo", "fornecedor", "faturado", "classificacao", "valor_total", "created_at")
    list_filter = ("tipo", "created_at")
    search_fields = ("numero_nota_fiscal", "fornecedor__razao_social", "faturado__razao_social")


@admin.register(ParcelaContas)
class ParcelaContasAdmin(admin.ModelAdmin):
    list_display = ("id", "identificacao", "movimento", "numero_parcela", "valor", "data_vencimento")
    search_fields = ("identificacao",)
