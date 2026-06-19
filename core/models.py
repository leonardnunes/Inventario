from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.conf import settings


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
    numero_serie = models.CharField(max_length=100, unique=True, blank=True, null=True,
                                    verbose_name="Número de Série")

    data_entrada = models.DateField(verbose_name="Data de Entrada", default=timezone.now)
    preco_aproximado = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Preço Aproximado", blank=True,
                                           null=True)
    situacao = models.CharField(max_length=20, choices=Situacao.choices, default=Situacao.DISPONIVEL,
                                verbose_name="Situação")

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

    def __str__(self):
        return f"{self.nome} (Série: {self.numero_serie if self.numero_serie else 'N/A'})"

    def save(self, *args, **kwargs):
        user = kwargs.pop('user', None)

        is_new = self.pk is None
        old_obj = None

        if not is_new:
            try:
                old_obj = Equipamento.objects.get(pk=self.pk)
            except Equipamento.DoesNotExist:
                old_obj = None

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
        elif old_obj:
            if old_obj.situacao != self.situacao:
                HistoricoEquipamento.objects.create(
                    equipamento=self,
                    observacao=f"Situação alterada de '{old_obj.get_situacao_display()}' para '{self.get_situacao_display()}'.",
                    usuario=user
                )

            if old_obj.departamento != self.departamento:
                depto_antigo = old_obj.departamento.nome if old_obj.departamento else "Nenhum"
                depto_novo = self.departamento.nome if self.departamento else "Nenhum"
                HistoricoEquipamento.objects.create(
                    equipamento=self,
                    observacao=f"Transferido do departamento '{depto_antigo}' para '{depto_novo}'.",
                    usuario=user
                )

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