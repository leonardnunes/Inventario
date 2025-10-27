
from django.contrib import admin
from .models import Categoria, Localizacao, Equipamento, Departamento

class EquipamentoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'marca', 'modelo', 'codigo_patrimonio')

    readonly_fields = ('codigo_patrimonio',)

admin.site.register(Equipamento, EquipamentoAdmin)

admin.site.register(Categoria)
admin.site.register(Localizacao)
admin.site.register(Departamento)

