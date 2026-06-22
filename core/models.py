from django.db import models
from django.db.models import Sum, Count
from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from decimal import Decimal


class EquipamentoQuerySet(models.QuerySet):
    def metricas_dashboard(self):
        return self.values('departamento__nome').annotate(
            total_itens=Count('id'),
            investimento_bruto=Sum('preco_aproximado')
        ).order_by('-total_itens')


class EquipamentoManager(models.Manager):
    def get_queryset(self):
        return EquipamentoQuerySet(self.model, using=self._db)

    def metricas_dashboard(self):
        return self.get_queryset().metricas_dashboard()


class Categoria(models.Model):
    nome = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nome


class Localizacao(models.Model):
    nome = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name = "Localização"
        verbose_name_plural = "Localizações"

    def __str__(self):
        return self.nome


class Departamento(models.Model):
    nome = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nome


class Equipamento(models.Model):
    class Situacao(models.TextChoices):
        DISPONIVEL = 'disponivel', 'Disponível'
        EM_USO = 'em_uso', 'Em Uso'
        MANUTENCAO = 'manutencao', 'Em Manutenção'
        DESCARTADO = 'descartado', 'Descartado'

    class Meta:
        verbose_name = "Equipamento"
        verbose_name_plural = "Equipamentos"
        permissions = [
            ("can_export_csv", "Pode exportar relatórios CSV de equipamentos"),
            ("can_print_label", "Pode imprimir etiquetas de equipamentos"),
        ]

    nome = models.CharField(max_length=200, verbose_name="Nome")
    marca = models.CharField(max_length=100, blank=True, default="", verbose_name="Marca")
    modelo = models.CharField(max_length=100, blank=True, default="", verbose_name="Modelo")
    numero_serie = models.CharField(max_length=100, unique=True, blank=True, null=True, verbose_name="Número de Série")
    data_entrada = models.DateField(verbose_name="Data de Entrada", default=timezone.now, db_index=True)
    preco_aproximado = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Preço Aproximado", blank=True,
                                           null=True)
    vida_util_anos = models.PositiveIntegerField(verbose_name="Vida Útil (Anos)", default=5,
                                                 help_text="Para cálculo de depreciação.")

    situacao = models.CharField(max_length=20, choices=Situacao.choices, default=Situacao.DISPONIVEL,
                                verbose_name="Situação", db_index=True)

    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name="equipamentos",
                                  verbose_name="Categoria", blank=True, null=True)
    localizacao = models.ForeignKey(Localizacao, on_delete=models.PROTECT, related_name="equipamentos",
                                    verbose_name="Localização", blank=True, null=True)
    departamento = models.ForeignKey(Departamento, on_delete=models.SET_NULL, related_name="equipamentos",
                                     verbose_name="Departamento", blank=True, null=True)

    data_saida = models.DateField(verbose_name="Data de Saída", blank=True, null=True)
    motivo_saida = models.TextField(verbose_name="Motivo de Saída", blank=True, default="")
    observacoes = models.TextField(verbose_name="Observações", blank=True, default="")

    codigo_patrimonio = models.CharField(max_length=20, unique=True, blank=True, editable=False,
                                         verbose_name="Código de Patrimônio")
    imagem = models.ImageField(upload_to='equipamentos_fotos/', blank=True, null=True,
                               verbose_name="Foto do Equipamento")

    objects = EquipamentoManager()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_situacao = self.__dict__.get('situacao')
        self._original_departamento_id = self.__dict__.get('departamento_id')


    @property
    def valor_depreciado(self):
        if not self.preco_aproximado or not self.data_entrada:
            return Decimal('0.00')

        ano_atual = timezone.now().date().year
        anos_passados = ano_atual - self.data_entrada.year

        if anos_passados <= 0:
            return self.preco_aproximado

        taxa_anual = self.preco_aproximado / Decimal(self.vida_util_anos)
        depreciacao_acumulada = taxa_anual * Decimal(anos_passados)
        valor_atual = self.preco_aproximado - depreciacao_acumulada

        return max(Decimal('0.00'), valor_atual)

    def __str__(self):
        return f"{self.nome} (Série: {self.numero_serie if self.numero_serie else 'N/A'})"

    def save(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        is_new = self.pk is None

        super().save(*args, **kwargs)

        if is_new and not self.codigo_patrimonio:
            self.codigo_patrimonio = f'INN-{self.id:06d}'
            super().save(update_fields=['codigo_patrimonio'])

        if is_new:
            HistoricoEquipamento.objects.create(
                equipamento=self,
                observacao="Equipamento cadastrado e patrimônio gerado.",
                usuario=user
            )
        else:
            if self._original_situacao != self.situacao:
                old_display = dict(self.Situacao.choices).get(self._original_situacao, self._original_situacao)
                HistoricoEquipamento.objects.create(
                    equipamento=self,
                    observacao=f"Situação alterada de '{old_display}' para '{self.get_situacao_display()}'.",
                    usuario=user
                )

            if self._original_departamento_id != self.departamento_id:
                depto_antigo = Departamento.objects.filter(id=self._original_departamento_id).first()
                nome_antigo = depto_antigo.nome if depto_antigo else "Nenhum"
                nome_novo = self.departamento.nome if self.departamento else "Nenhum"
                HistoricoEquipamento.objects.create(
                    equipamento=self,
                    observacao=f"Transferido do departamento '{nome_antigo}' para '{nome_novo}'.",
                    usuario=user
                )

        self._original_situacao = self.situacao
        self._original_departamento_id = self.departamento_id

    def get_absolute_url(self):
        return reverse('core:equipamento_detalhe', kwargs={'pk': self.pk})


class HistoricoEquipamento(models.Model):
    equipamento = models.ForeignKey('Equipamento', on_delete=models.CASCADE, related_name='historicos')
    observacao = models.CharField(max_length=255)
    data_registro = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                verbose_name="Usuário")

    class Meta:
        ordering = ['-data_registro']
        verbose_name = 'Histórico'
        verbose_name_plural = 'Históricos'

    def __str__(self):
        nome_usuario = self.usuario.username if self.usuario else "Sistema"
        return f"{self.data_registro.strftime('%d/%m/%Y %H:%M')} - {self.observacao} ({nome_usuario})"