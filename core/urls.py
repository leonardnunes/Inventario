from django.urls import path
from .views import (
    dashboard,
    lista_equipamentos,
    equipamento_detalhe,
    equipamento_novo,
    equipamento_editar,
    equipamento_excluir,
    etiqueta_equipamento,
    exportar_csv,
    imprimir_etiquetas_massa,
    importar_csv,
    RelatorioInventarioView,
    adicionar_departamento_ajax,
    adicionar_categoria_ajax,
)

app_name = 'core'

urlpatterns = [
    path('', dashboard, name='home'),
    path('dashboard/', dashboard, name='dashboard'),
    path('equipamentos/', lista_equipamentos, name='lista_equipamentos'),
    path('equipamento/novo/', equipamento_novo, name='equipamento_novo'),
    path('equipamento/<int:pk>/', equipamento_detalhe, name='equipamento_detalhe'),
    path('equipamento/<int:pk>/editar/', equipamento_editar, name='equipamento_editar'),
    path('equipamento/<int:pk>/excluir/', equipamento_excluir, name='equipamento_excluir'),
    path('equipamento/<int:pk>/etiqueta/', etiqueta_equipamento, name='etiqueta_equipamento'),
    path('etiquetas/massa/', imprimir_etiquetas_massa, name='imprimir_etiquetas_massa'),
    path('relatorio/', RelatorioInventarioView.as_view(), name='gerar_relatorio'),
    path('exportar/csv/', exportar_csv, name='exportar_csv'),
    path('importar/csv/', importar_csv, name='importar_csv'),
    path('api/departamento/adicionar/', adicionar_departamento_ajax, name='api_adicionar_departamento'),
    path('api/categoria/adicionar/', adicionar_categoria_ajax, name='api_adicionar_categoria'),
]