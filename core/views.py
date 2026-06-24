import csv
import io
import json
from datetime import datetime
from decimal import Decimal

from django.utils import timezone
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import transaction
from django.db.models import Q, Count, Sum
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
)

from .forms import EquipamentoForm
from .models import Equipamento, Departamento, Categoria, Localizacao, HistoricoEquipamento
from .utils import gerar_qr_code_base64


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'core/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        dados_departamentos = Equipamento.objects.metricas_dashboard()

        chart_labels = [item['departamento__nome'] if item['departamento__nome'] else 'Sem Departamento' for item in
                        dados_departamentos]
        chart_values = [item['total_itens'] for item in dados_departamentos]

        base_colors = [
            'rgba(56, 189, 248, 0.8)', 'rgba(16, 185, 129, 0.8)', 'rgba(167, 139, 250, 0.8)',
            'rgba(245, 158, 11, 0.8)', 'rgba(244, 63, 94, 0.8)', 'rgba(14, 165, 233, 0.8)',
            'rgba(34, 197, 94, 0.8)', 'rgba(139, 92, 246, 0.8)', 'rgba(249, 115, 22, 0.8)',
            'rgba(236, 72, 153, 0.8)', 'rgba(6, 182, 212, 0.8)', 'rgba(234, 179, 8, 0.8)'
        ]
        chart_colors = [base_colors[i % len(base_colors)] for i in range(len(chart_labels))]
        dados_categorias = Equipamento.objects.values('categoria__nome').annotate(total=Count('id')).order_by('-total')

        cat_labels = [c['categoria__nome'] if c['categoria__nome'] else 'Sem Categoria' for c in dados_categorias]
        cat_values = [c['total'] for c in dados_categorias]
        cat_base_colors = [
            'rgba(245, 158, 11, 0.8)', 'rgba(239, 68, 68, 0.8)', 'rgba(139, 92, 246, 0.8)',
            'rgba(236, 72, 153, 0.8)', 'rgba(249, 115, 22, 0.8)', 'rgba(20, 184, 166, 0.8)'
        ]
        cat_colors = [cat_base_colors[i % len(cat_base_colors)] for i in range(len(cat_labels))]

        equipamentos_financeiro = Equipamento.objects.only('preco_aproximado', 'data_entrada', 'vida_util_anos')

        investimento_total = Decimal('0.00')
        valor_atual_patrimonio = Decimal('0.00')

        for eq in equipamentos_financeiro:
            if eq.preco_aproximado:
                investimento_total += Decimal(str(eq.preco_aproximado))
                valor_atual_patrimonio += Decimal(str(eq.valor_depreciado))

        context.update({
            'investimento_total': investimento_total,
            'valor_atual_patrimonio': valor_atual_patrimonio,
            'perda_depreciacao': investimento_total - valor_atual_patrimonio,
            'total_equipamentos': Equipamento.objects.count(),
            'em_manutencao': Equipamento.objects.filter(situacao='manutencao').count(),
            'disponiveis': Equipamento.objects.filter(situacao='disponivel').count(),
            'chart_labels': json.dumps(chart_labels),
            'chart_values': json.dumps(chart_values),
            'chart_colors': json.dumps(chart_colors),
            'cat_labels': json.dumps(cat_labels),
            'cat_values': json.dumps(cat_values),
            'cat_colors': json.dumps(cat_colors),
            'ultimos_adicionados': Equipamento.objects.select_related('departamento', 'categoria').order_by('-id')[:4],
            'ultimas_movimentacoes': HistoricoEquipamento.objects.select_related('equipamento', 'usuario')[:4]
        })

        return context


class EquipamentoListView(PermissionRequiredMixin, ListView):
    permission_required = 'core.view_equipamento'
    model = Equipamento
    template_name = 'core/lista_equipamentos.html'
    context_object_name = 'equipamentos'
    paginate_by = 50

    def get_base_queryset(self):
        queryset = Equipamento.objects.select_related('departamento', 'categoria', 'localizacao')

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

        return queryset

    def get_queryset(self):
        queryset = self.get_base_queryset()
        status_param = self.request.GET.get('status', '')
        if status_param:
            queryset = queryset.filter(situacao=status_param)

        return queryset.order_by('nome')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs_base = self.get_base_queryset()

        context.update({
            'total_equipamentos': qs_base.count(),
            'total_disponivel': qs_base.filter(situacao='disponivel').count(),
            'total_em_uso': qs_base.filter(situacao='em_uso').count(),
            'total_manutencao': qs_base.filter(situacao='manutencao').count(),
            'status_atual': self.request.GET.get('status', ''),
            'departamento_selecionado_id': self.request.GET.get('departamento', ''),
            'query_atual': self.request.GET.get('q', ''),
            'departamentos': Departamento.objects.all().order_by('nome'),
            'categorias': Categoria.objects.all().order_by('nome'),
        })

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

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.save(user=self.request.user)
        return HttpResponseRedirect(self.get_success_url())


class EquipamentoUpdateView(PermissionRequiredMixin, UpdateView):
    permission_required = 'core.change_equipamento'
    model = Equipamento
    form_class = EquipamentoForm
    template_name = 'core/equipamento_form.html'

    def get_success_url(self):
        return reverse('core:equipamento_detalhe', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.save(user=self.request.user)
        return HttpResponseRedirect(self.get_success_url())


class EquipamentoDeleteView(PermissionRequiredMixin, DeleteView):
    permission_required = 'core.delete_equipamento'
    model = Equipamento
    template_name = 'core/equipamento_confirm_delete.html'
    success_url = reverse_lazy('core:lista_equipamentos')


@login_required
def exportar_csv(request):
    response = HttpResponse(
        content_type='text/csv',
        headers={'Content-Disposition': 'attachment; filename="Inventario_patrimonio.csv"'},
    )
    response.write(u'\ufeff'.encode('utf8'))
    writer = csv.writer(response, delimiter=';')

    writer.writerow(['ID', 'Código de Patrimônio', 'Nome', 'Marca', 'Modelo', 'Número de Série', 'Categoria',
                     'Localização', 'Departamento', 'Situação', 'Data de Entrada', 'Data de Saída',
                     'Preço Aproximado', 'Observações'])

    equipamentos = Equipamento.objects.select_related('categoria', 'localizacao', 'departamento').all()

    for eq in equipamentos:
        writer.writerow([
            eq.id, eq.codigo_patrimonio, eq.nome, eq.marca, eq.modelo, eq.numero_serie,
            eq.categoria.nome if eq.categoria else '',
            eq.localizacao.nome if eq.localizacao else '',
            eq.departamento.nome if eq.departamento else '',
            eq.get_situacao_display(),
            eq.data_entrada.strftime('%d/%m/%Y') if eq.data_entrada else '',
            eq.data_saida.strftime('%d/%m/%Y') if eq.data_saida else '',
            eq.preco_aproximado, eq.observacoes
        ])

    return response


@login_required
@permission_required('core.add_equipamento', raise_exception=True)
def importar_csv(request):
    SITUACAO_MAP = {display: value for value, display in Equipamento.Situacao.choices}

    if request.method == 'GET':
        return render(request, 'core/importar_equipamentos.html')

    csv_file = request.FILES.get('csv_file')

    if not csv_file or not csv_file.name.endswith('.csv'):
        messages.error(request, 'Arquivo inválido. Por favor, envie um formato .csv.')
        return redirect('core:importar_csv')

    criados_count, atualizados_count, erros = 0, 0, []

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

                    situacao_valor = SITUACAO_MAP.get(situacao_display, 'disponivel')
                    data_entrada = datetime.strptime(data_entrada_str, '%d/%m/%Y').date() if data_entrada_str else None
                    data_saida = datetime.strptime(data_saida_str, '%d/%m/%Y').date() if data_saida_str else None
                    preco_aproximado = Decimal(preco_str.replace(',', '.')) if preco_str else None

                    categoria_obj, _ = Categoria.objects.get_or_create(nome=categoria_nome) if categoria_nome else (
                        None, False)
                    localizacao_obj, _ = Localizacao.objects.get_or_create(
                        nome=localizacao_nome) if localizacao_nome else (None, False)
                    departamento_obj, _ = Departamento.objects.get_or_create(
                        nome=departamento_nome) if departamento_nome else (None, False)

                    defaults = {
                        'nome': nome, 'marca': marca, 'modelo': modelo,
                        'categoria': categoria_obj, 'localizacao': localizacao_obj,
                        'departamento': departamento_obj, 'situacao': situacao_valor,
                        'data_entrada': data_entrada, 'data_saida': data_saida,
                        'preco_aproximado': preco_aproximado, 'observacoes': observacoes,
                    }

                    if not numero_serie:
                        Equipamento.objects.create(**defaults)
                        criados_count += 1
                    else:
                        obj, created = Equipamento.objects.update_or_create(numero_serie=numero_serie,
                                                                            defaults=defaults)
                        if created:
                            criados_count += 1
                        else:
                            atualizados_count += 1

                except Exception as e:
                    erros.append(f"Linha {linha_num} ({row[2]}): {e}")

    except Exception as e:
        messages.error(request, f"Erro fatal ao ler o arquivo: {e}")
        return redirect('core:importar_csv')

    if criados_count > 0: messages.success(request, f'{criados_count} equipamentos criados com sucesso.')
    if atualizados_count > 0: messages.info(request, f'{atualizados_count} equipamentos atualizados.')
    if erros: messages.warning(request, f"Ocorreram {len(erros)} erros. Verifique o terminal para detalhes.")

    return redirect('core:importar_csv')


@permission_required('core.can_print_label', raise_exception=True)
def etiqueta_equipamento(request, pk):
    equipamento = get_object_or_404(Equipamento, pk=pk)
    url_details = request.build_absolute_uri(equipamento.get_absolute_url())
    context = {'equipamento': equipamento, 'qr_code_image': gerar_qr_code_base64(url_details)}
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
    total_solicitado = equipamentos_qs.count()

    LIMITE_MAXIMO = 500
    if total_solicitado > LIMITE_MAXIMO:
        messages.warning(request, f"Limite de segurança: tente gerar menos de {LIMITE_MAXIMO} etiquetas por vez.")
        return redirect('core:lista_equipamentos')
    elif total_solicitado == 0:
        messages.info(request, "Nenhum equipamento foi encontrado para este intervalo.")
        return redirect('core:lista_equipamentos')

    equipamentos_com_qr = [
        {'equipamento': eq, 'qr_code_image': gerar_qr_code_base64(request.build_absolute_uri(eq.get_absolute_url()))}
        for eq in equipamentos_qs]

    return render(request, 'core/etiquetas_massa.html', {'equipamentos_com_qr': equipamentos_com_qr})


class RelatorioInventarioView(PermissionRequiredMixin, ListView):
    permission_required = 'core.view_equipamento'
    model = Equipamento
    template_name = 'core/relatorio_inventario.html'
    context_object_name = 'equipamentos'

    def get(self, request, *args, **kwargs):
        quantidade_itens = self.get_queryset().count()
        limite_seguro = 1000
        if quantidade_itens > limite_seguro:
            messages.warning(request,
                             f"Relatório muito extenso ({quantidade_itens} itens). Filtre por Departamento ou Categoria.")
            return redirect('core:lista_equipamentos')
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset().select_related('departamento', 'categoria', 'localizacao')
        query = self.request.GET.get('q', '')
        departamento_id = self.request.GET.get('departamento', '')
        status_param = self.request.GET.get('status', '')
        categoria_id = self.request.GET.get('categoria', '')

        if query:
            queryset = queryset.filter(
                Q(nome__icontains=query) | Q(marca__icontains=query) |
                Q(modelo__icontains=query) | Q(codigo_patrimonio__icontains=query) |
                Q(departamento__nome__icontains=query)
            )
        if departamento_id: queryset = queryset.filter(departamento__id=departamento_id)
        if status_param: queryset = queryset.filter(situacao=status_param)
        if categoria_id: queryset = queryset.filter(categoria__id=categoria_id)

        return queryset.order_by('nome')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()
        investimento_total = Decimal('0.00')
        patrimonio_liquido = Decimal('0.00')

        for item in queryset:
            preco = Decimal(str(item.preco_aproximado or 0))
            investimento_total += preco
            patrimonio_liquido += Decimal(str(item.valor_depreciado))

        context.update({
            'data_geracao': timezone.now(),
            'total_itens': queryset.count(),
            'valor_total': investimento_total,
            'total_valor_depreciado': patrimonio_liquido
        })
        return context


@require_POST
@permission_required('core.add_departamento', raise_exception=True)
def adicionar_departamento_ajax(request):
    try:
        nome = json.loads(request.body).get('nome', '').strip()
        if not nome:
            return JsonResponse({'sucesso': False, 'erro': 'O nome do departamento é obrigatório.'}, status=400)
        departamento = Departamento.objects.create(nome=nome)
        return JsonResponse({'sucesso': True, 'id': departamento.id, 'nome': departamento.nome})
    except Exception as e:
        return JsonResponse({'sucesso': False, 'erro': str(e)}, status=500)


@require_POST
@permission_required('core.add_categoria', raise_exception=True)
def adicionar_categoria_ajax(request):
    try:
        nome = json.loads(request.body).get('nome', '').strip()
        if not nome:
            return JsonResponse({'sucesso': False, 'erro': 'O nome da categoria é obrigatório.'}, status=400)
        categoria = Categoria.objects.create(nome=nome)
        return JsonResponse({'sucesso': True, 'id': categoria.id, 'nome': categoria.nome})
    except Exception as e:
        return JsonResponse({'sucesso': False, 'erro': str(e)}, status=500)


dashboard = DashboardView.as_view()
lista_equipamentos = EquipamentoListView.as_view()
equipamento_detalhe = EquipamentoDetailView.as_view()
equipamento_novo = EquipamentoCreateView.as_view()
equipamento_editar = EquipamentoUpdateView.as_view()
equipamento_excluir = EquipamentoDeleteView.as_view()