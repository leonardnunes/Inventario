import csv
from django.http import HttpResponse
import json
import qrcode
import io
import base64
from django.shortcuts import render, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
    TemplateView
)
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Q, Count
from .models import Equipamento, Departamento
from .forms import EquipamentoForm


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'core/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_equipamentos'] = Equipamento.objects.count()
        context['em_manutencao'] = Equipamento.objects.filter(situacao='manutencao').count()
        context['disponiveis'] = Equipamento.objects.filter(situacao='disponivel').count()
        context['ultimos_adicionados'] = Equipamento.objects.order_by('-id')[:5]
        chart_data_queryset = Equipamento.objects.values('categoria__nome').annotate(total=Count('id')).order_by(
            'categoria__nome')
        chart_labels = [item['categoria__nome'] for item in chart_data_queryset]
        chart_values = [item['total'] for item in chart_data_queryset]
        base_colors = [
            'rgba(255, 99, 132, 0.8)', 'rgba(54, 162, 235, 0.8)', 'rgba(255, 206, 86, 0.8)',
            'rgba(75, 192, 192, 0.8)', 'rgba(153, 102, 255, 0.8)', 'rgba(255, 159, 64, 0.8)'
        ]
        chart_colors = [base_colors[i % len(base_colors)] for i in range(len(chart_labels))]
        context['chart_labels'] = json.dumps(chart_labels)
        context['chart_values'] = json.dumps(chart_values)
        context['chart_colors'] = json.dumps(chart_colors)
        return context


class EquipamentoListView(PermissionRequiredMixin, ListView):
    permission_required = 'core.view_equipamento'
    model = Equipamento
    template_name = 'core/lista_equipamentos.html'
    context_object_name = 'equipamentos'
    paginate_by = 50

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.GET.get('q', '')
        departamento_id = self.request.GET.get('departamento', '')

        if query:
            queryset = queryset.filter(
                Q(nome__icontains=query) |
                Q(marca__icontains=query) |
                Q(modelo__icontains=query) |
                Q(codigo_patrimonio__icontains=query) |
                Q(departamento__nome__icontains=query)
            )

        if departamento_id:
            queryset = queryset.filter(departamento__id=departamento_id)

        return queryset.order_by('nome')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['departamentos'] = Departamento.objects.all().order_by('nome')
        context['departamento_selecionado_id'] = self.request.GET.get('departamento', '')
        context['query_atual'] = self.request.GET.get('q', '')
        return context


class EquipamentoDetailView(PermissionRequiredMixin, DetailView):
    permission_required = 'core.view_equipamento'
    model = Equipamento
    template_name = 'core/equipamento_detalhe.html'
    context_object_name = 'equipamento'


class EquipamentoCreateView(PermissionRequiredMixin, CreateView):
    permission_required = 'core.add_equipamento'
    model = Equipamento
    form_class = EquipamentoForm
    template_name = 'core/equipamento_form.html'
    success_url = reverse_lazy('core:lista_equipamentos')


class EquipamentoUpdateView(PermissionRequiredMixin, UpdateView):
    permission_required = 'core.change_equipamento'
    model = Equipamento
    form_class = EquipamentoForm
    template_name = 'core/equipamento_form.html'

    def get_success_url(self):
        return reverse('core:equipamento_detalhe', kwargs={'pk': self.object.pk})


class EquipamentoDeleteView(PermissionRequiredMixin, DeleteView):
    permission_required = 'core.delete_equipamento'
    model = Equipamento
    template_name = 'core/equipamento_confirm_delete.html'
    success_url = reverse_lazy('core:lista_equipamentos')

@permission_required('core.can_print_label', raise_exception=True)
def etiqueta_equipamento(request, pk):
    equipamento = get_object_or_404(Equipamento, pk=pk)
    url_details = request.build_absolute_uri(equipamento.get_absolute_url())


    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=6,
        border=2,
    )
    qr.add_data(url_details)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    # --- FIM DA ALTERAÇÃO ---

    buffer = io.BytesIO()
    qr_img.save(buffer, format='PNG')
    qr_code_image = base64.b64encode(buffer.getvalue()).decode()
    context = {
        'equipamento': equipamento,
        'qr_code_image': qr_code_image,
    }
    return render(request, 'core/etiqueta.html', context)


@login_required
def exportar_csv(request):
    response = HttpResponse(
        content_type='text/csv',
        headers={'Content-Disposition': 'attachment; filename="Inventario_inventario.csv"'},
    )
    response.write(u'\ufeff'.encode('utf8'))
    writer = csv.writer(response, delimiter=';')


    writer.writerow(['ID', 'Código de Patrimônio', 'Nome', 'Marca', 'Modelo', 'Número de Série', 'Categoria',
                     'Localização', 'Departamento', 'Situação', 'Data de Entrada', 'Data de Saída',
                     'Preço Aproximado', 'Observações'])

    equipamentos = Equipamento.objects.all()
    for equipamento in equipamentos:
        writer.writerow(
            [equipamento.id, equipamento.codigo_patrimonio, equipamento.nome, equipamento.marca, equipamento.modelo,
             equipamento.numero_serie,
             equipamento.categoria.nome if equipamento.categoria else '',
             equipamento.localizacao.nome if equipamento.localizacao else '',
             equipamento.departamento.nome if equipamento.departamento else '',
             equipamento.get_situacao_display(),
             equipamento.data_entrada.strftime('%d/%m/%Y') if equipamento.data_entrada else '',
             equipamento.data_saida.strftime('%d/%m/%Y') if equipamento.data_saida else '',
             equipamento.preco_aproximado,
             equipamento.observacoes])

    return response


@permission_required('core.can_print_label', raise_exception=True)
def imprimir_etiquetas_massa(request):
    inicio = request.GET.get('inicio')
    fim = request.GET.get('fim')

    departamento_id = request.GET.get('departamento')

    equipamentos_qs = Equipamento.objects.all()

    if inicio and fim:
        equipamentos_qs = equipamentos_qs.filter(codigo_patrimonio__gte=inicio, codigo_patrimonio__lte=fim)
    elif departamento_id:
        equipamentos_qs = equipamentos_qs.filter(departamento__id=departamento_id)

    equipamentos_com_qr = []
    for equipamento in equipamentos_qs.order_by('codigo_patrimonio'):
        url_details = request.build_absolute_uri(equipamento.get_absolute_url())

        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=6, border=2)
        qr.add_data(url_details)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")

        buffer = io.BytesIO()
        qr_img.save(buffer, format='PNG')
        qr_code_image = base64.b64encode(buffer.getvalue()).decode()

        equipamentos_com_qr.append({
            'equipamento': equipamento,
            'qr_code_image': qr_code_image
        })

    context = {
        'equipamentos_com_qr': equipamentos_com_qr
    }
    return render(request, 'core/etiquetas_massa.html', context)

dashboard = DashboardView.as_view()
lista_equipamentos = EquipamentoListView.as_view()
equipamento_detalhe = EquipamentoDetailView.as_view()
equipamento_novo = EquipamentoCreateView.as_view()
equipamento_editar = EquipamentoUpdateView.as_view()
equipamento_excluir = EquipamentoDeleteView.as_view()
