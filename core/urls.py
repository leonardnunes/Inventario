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
    importar_csv  # Importação da nova view
)


app_name = 'core'

urlpatterns = [
    path('dashboard/', dashboard, name='dashboard'),
    path('', dashboard, name='home'),  # <-- AQUI ESTAVA O ERRO
    path('equipamentos/', lista_equipamentos, name='lista_equipamentos'),
    path('<int:pk>/', equipamento_detalhe, name='equipamento_detalhe'),
    path('novo/', equipamento_novo, name='equipamento_novo'),
    path('<int:pk>/editar/', equipamento_editar, name='equipamento_editar'),
    path('<int:pk>/excluir/', equipamento_excluir, name='equipamento_excluir'),
    path('<int:pk>/etiqueta/', etiqueta_equipamento, name='etiqueta_equipamento'),
    path('exportar/csv/', exportar_csv, name='exportar_csv'),
    path('etiquetas/massa/', imprimir_etiquetas_massa, name='imprimir_etiquetas_massa'),
    path('importar/csv/', importar_csv, name='importar_csv'),
]