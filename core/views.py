import csv
import io
import json
from datetime import datetime
from decimal import Decimal
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import transaction
from django.db.models import Q, Count, Sum
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
    TemplateView
)

from .forms import EquipamentoForm
from .models import Equipamento, Departamento, Categoria, Localizacao, HistoricoEquipamento
from .utils import gerar_qr_code_base64


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'core/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['total_equipamentos'] = Equipamento.objects.count()
        context['em_manutencao'] = Equipamento.objects.filter(situacao='manutencao').count()
        context['disponiveis'] = Equipamento.objects.filter(situacao='disponivel').count()
        context['ultimos_adicionados'] = Equipamento.objects.order_by('-id')[:5]
        context['valor_total'] = Equipamento.objects.aggregate(total=Sum('preco_aproximado'))['total'] or 0
        context['ultimas_movimentacoes'] = HistoricoEquipamento.objects.all()[:8]

        chart_data_queryset = Equipamento.objects.values('categoria__nome').annotate(total=Count('id')).order_by(
            'categoria__nome')

        chart_labels = [item['categoria__nome'] if item['categoria__nome'] else 'Sem Categoria' for item in
                        chart_data_queryset]
        chart_values = [item['total'] for item in chart_data_queryset]

        base_colors = [
            'rgba(56, 189, 248, 0.8)',
            'rgba(16, 185, 129, 0.8)',
            'rgba(167, 139, 250, 0.8)',
            'rgba(245, 158, 11, 0.8)',
            'rgba(244, 63, 94, 0.8)',
            'rgba(14, 165, 233, 0.8)',
            'rgba(34, 197, 94, 0.8)',
            'rgba(139, 92, 246, 0.8)',
            'rgba(249, 115, 22, 0.8)',
            'rgba(236, 72, 153, 0.8)',
            'rgba(6, 182, 212, 0.8)',
            'rgba(234, 179, 8, 0.8)'
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
        queryset = super().get_queryset().select_related('departamento', 'categoria', 'localizacao')
        query = self.request.GET.get('q', '')
        departamento_id = self.request.GET.get('departamento', '')
        status_param = self.request.GET.get('status', '')

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

        if status_param:
            queryset = queryset.filter(situacao=status_param)

        return queryset.order_by('nome')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        query = self.request.GET.get('q', '')
        departamento_id = self.request.GET.get('departamento', '')
        qs_contagem = Equipamento.objects.all()

        if query:
            qs_contagem = qs_contagem.filter(
                Q(nome__icontains=query) |
                Q(marca__icontains=query) |
                Q(modelo__icontains=query) |
                Q(codigo_patrimonio__icontains=query) |
                Q(departamento__nome__icontains=query)
            )

        if departamento_id:
            qs_contagem = qs_contagem.filter(departamento__id=departamento_id)

        context['total_equipamentos'] = qs_contagem.count()
        context['total_disponivel'] = qs_contagem.filter(situacao='disponivel').count()
        context['total_em_uso'] = qs_contagem.filter(situacao='em_uso').count()
        context['total_manutencao'] = qs_contagem.filter(situacao='manutencao').count()
        context['status_atual'] = self.request.GET.get('status', '')
        context['departamentos'] = Departamento.objects.all().order_by('nome')
        context['departamento_selecionado_id'] = departamento_id
        context['query_atual'] = query

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

    equipamentos = Equipamento.objects.select_related('categoria', 'localizacao', 'departamento').all()

    for equipamento in equipamentos:
        writer.writerow([
            equipamento.id,
            equipamento.codigo_patrimonio,
            equipamento.nome,
            equipamento.marca,
            equipamento.modelo,
            equipamento.numero_serie,
            equipamento.categoria.nome if equipamento.categoria else '',
            equipamento.localizacao.nome if equipamento.localizacao else '',
            equipamento.departamento.nome if equipamento.departamento else '',
            equipamento.get_situacao_display(),
            equipamento.data_entrada.strftime('%d/%m/%Y') if equipamento.data_entrada else '',
            equipamento.data_saida.strftime('%d/%m/%Y') if equipamento.data_saida else '',
            equipamento.preco_aproximado,
            equipamento.observacoes
        ])

    return response


@login_required
@permission_required('core.add_equipamento', raise_exception=True)
def importar_csv(request):
    SITUACAO_MAP = {
        display: value
        for value, display in Equipamento.Situacao.choices
    }

    if request.method == 'GET':
        return render(request, 'core/importar_equipamentos.html')

    csv_file = request.FILES.get('csv_file')

    if not csv_file:
        messages.error(request, 'Nenhum arquivo selecionado.')
        return redirect('core:importar_csv')

    if not csv_file.name.endswith('.csv'):
        messages.error(request, 'Formato de arquivo inválido. Por favor, envie um .csv')
        return redirect('core:importar_csv')

    criados_count = 0
    atualizados_count = 0
    erros = []

    try:
        data_set = csv_file.read().decode('utf-8-sig')
        io_string = io.StringIO(data_set)
        next(io_string)

        reader = csv.reader(io_string, delimiter=';')
        with transaction.atomic():
            for i, row in enumerate(reader):
                linha_num = i + 2

                if not any(row):
                    continue

                try:
                    nome = row[2].strip()
                    marca = row[3].strip() or None
                    modelo = row[4].strip() or None
                    numero_serie = row[5].strip() or None

                    categoria_nome = row[6].strip()
                    localizacao_nome = row[7].strip()
                    departamento_nome = row[8].strip()

                    situacao_display = row[9].strip()
                    data_entrada_str = row[10].strip()
                    data_saida_str = row[11].strip()
                    preco_str = row[12].strip()
                    observacoes = row[13].strip() or None

                    situacao_valor = SITUACAO_MAP.get(situacao_display)
                    if not situacao_valor and situacao_display:
                        raise ValueError(f"Situação '{situacao_display}' inválida.")
                    elif not situacao_valor:
                        situacao_valor = 'disponivel'

                    data_entrada = datetime.strptime(data_entrada_str, '%d/%m/%Y').date() if data_entrada_str else None
                    data_saida = datetime.strptime(data_saida_str, '%d/%m/%Y').date() if data_saida_str else None

                    preco_aproximado = Decimal(preco_str.replace(',', '.')) if preco_str else None

                    categoria_obj = None
                    if categoria_nome:
                        categoria_obj, _ = Categoria.objects.get_or_create(nome=categoria_nome)

                    localizacao_obj = None
                    if localizacao_nome:
                        localizacao_obj, _ = Localizacao.objects.get_or_create(nome=localizacao_nome)

                    departamento_obj = None
                    if departamento_nome:
                        departamento_obj, _ = Departamento.objects.get_or_create(nome=departamento_nome)

                    defaults = {
                        'nome': nome,
                        'marca': marca,
                        'modelo': modelo,
                        'categoria': categoria_obj,
                        'localizacao': localizacao_obj,
                        'departamento': departamento_obj,
                        'situacao': situacao_valor,
                        'data_entrada': data_entrada,
                        'data_saida': data_saida,
                        'preco_aproximado': preco_aproximado,
                        'observacoes': observacoes,
                    }

                    if not numero_serie:
                        Equipamento.objects.create(**defaults)
                        criados_count += 1
                    else:
                        obj, created = Equipamento.objects.update_or_create(
                            numero_serie=numero_serie,
                            defaults=defaults
                        )
                        if created:
                            criados_count += 1
                        else:
                            atualizados_count += 1

                except Exception as e:
                    erros.append(f"Linha {linha_num}: Erro ao processar '{row[2]}'. Detalhe: {e}")

    except Exception as e:
        messages.error(request, f"Erro fatal ao ler o arquivo: {e}")
        return redirect('core:importar_csv')

    if criados_count > 0:
        messages.success(request, f'{criados_count} equipamentos foram criados com sucesso.')
    if atualizados_count > 0:
        messages.info(request, f'{atualizados_count} equipamentos foram atualizados.')
    if erros:
        erros_preview = "; ".join(erros[:5])
        messages.warning(request,
                         f"Ocorreram {len(erros)} erros. Ex: [{erros_preview}... (veja o console do servidor para mais detalhes)]")

        print("--- ERROS DE IMPORTAÇÃO CSV ---")
        for erro in erros:
            print(erro)
        print("-------------------------------")

    return redirect('core:importar_csv')



@permission_required('core.can_print_label', raise_exception=True)
def etiqueta_equipamento(request, pk):
    equipamento = get_object_or_404(Equipamento, pk=pk)
    url_details = request.build_absolute_uri(equipamento.get_absolute_url())

    qr_code_image = gerar_qr_code_base64(url_details)

    context = {
        'equipamento': equipamento,
        'qr_code_image': qr_code_image,
    }
    return render(request, 'core/etiqueta.html', context)



@permission_required('core.can_print_label', raise_exception=True)
def imprimir_etiquetas_massa(request):
    inicio = request.GET.get('inicio')
    fim = request.GET.get('fim')
    departamento_id = request.GET.get('departamento')
    equipamentos_qs = Equipamento.objects.select_related('departamento', 'localizacao', 'categoria').all()

    if inicio and fim:
        equipamentos_qs = equipamentos_qs.filter(codigo_patrimonio__gte=inicio, codigo_patrimonio__lte=fim)
    elif departamento_id:
        equipamentos_qs = equipamentos_qs.filter(departamento__id=departamento_id)

    equipamentos_qs = equipamentos_qs.order_by('codigo_patrimonio')

    LIMITE_MAXIMO = 100
    total_solicitado = equipamentos_qs.count()

    if total_solicitado > LIMITE_MAXIMO:
        messages.warning(
            request,
            f"Você tentou gerar {total_solicitado} etiquetas. O limite de segurança do sistema é de {LIMITE_MAXIMO} por lote para evitar travamentos. Por favor, diminua o intervalo."
        )
        return redirect('core:lista_equipamentos')

    elif total_solicitado == 0:
        messages.info(request, "Nenhum equipamento foi encontrado para este intervalo.")
        return redirect('core:lista_equipamentos')

    equipamentos_com_qr = []
    for equipamento in equipamentos_qs:
        url_details = request.build_absolute_uri(equipamento.get_absolute_url())
        qr_code_image = gerar_qr_code_base64(url_details)

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



class RelatorioInventarioView(PermissionRequiredMixin, ListView):
    permission_required = 'core.view_equipamento'
    model = Equipamento
    template_name = 'core/relatorio_inventario.html'
    context_object_name = 'equipamentos'

    def get_queryset(self):
        queryset = super().get_queryset().select_related('departamento', 'categoria', 'localizacao')
        query = self.request.GET.get('q', '')
        departamento_id = self.request.GET.get('departamento', '')
        status_param = self.request.GET.get('status', '')

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

        if status_param:
            queryset = queryset.filter(situacao=status_param)

        return queryset.order_by('nome')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['data_geracao'] = timezone.now()
        context['total_itens'] = self.get_queryset().count()

        return context


@require_POST
@permission_required('core.add_departamento', raise_exception=True)
def adicionar_departamento_ajax(request):
    try:
        dados = json.loads(request.body)
        nome = dados.get('nome', '').strip()

        if not nome:
            return JsonResponse({'sucesso': False, 'erro': 'O nome do departamento é obrigatório.'}, status=400)

        departamento = Departamento.objects.create(nome=nome)

        return JsonResponse({
            'sucesso': True,
            'id': departamento.id,
            'nome': departamento.nome
        })
    except Exception as e:
        return JsonResponse({'sucesso': False, 'erro': str(e)}, status=500)


@require_POST
@permission_required('core.add_categoria', raise_exception=True)
def adicionar_categoria_ajax(request):
    try:
        dados = json.loads(request.body)
        nome = dados.get('nome', '').strip()

        if not nome:
            return JsonResponse({'sucesso': False, 'erro': 'O nome da categoria é obrigatório.'}, status=400)

        categoria = Categoria.objects.create(nome=nome)

        return JsonResponse({
            'sucesso': True,
            'id': categoria.id,
            'nome': categoria.nome
        })
    except Exception as e:
        return JsonResponse({'sucesso': False, 'erro': str(e)}, status=500)