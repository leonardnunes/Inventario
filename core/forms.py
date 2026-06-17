from django import forms
from .models import Equipamento


class EquipamentoForm(forms.ModelForm):
    class Meta:
        model = Equipamento
        fields = [
            'nome', 'marca', 'modelo', 'numero_serie', 'categoria',
            'localizacao', 'departamento', 'situacao', 'data_entrada',
            'preco_aproximado', 'imagem', 'data_saida', 'motivo_saida',
            'observacoes'
        ]

        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'marca': forms.TextInput(attrs={'class': 'form-control'}),
            'modelo': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_serie': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: YMH-123456'}),
            'preco_aproximado': forms.NumberInput(
                attrs={'class': 'form-control', 'placeholder': 'Ex: 1500.50', 'min': '0'}),

            'data_entrada': forms.DateInput(
                attrs={'class': 'form-control', 'type': 'date'},
                format='%Y-%m-%d'
            ),
            'data_saida': forms.DateInput(
                attrs={'class': 'form-control', 'type': 'date'},
                format='%Y-%m-%d'
            ),

            'situacao': forms.Select(attrs={'class': 'form-select'}),
            'categoria': forms.Select(attrs={'class': 'form-select'}),
            'localizacao': forms.Select(attrs={'class': 'form-select'}),
            'departamento': forms.Select(attrs={'class': 'form-select'}),
            'motivo_saida': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'imagem': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def clean(self):
        cleaned_data = super().clean()

        data_entrada = cleaned_data.get('data_entrada')
        data_saida = cleaned_data.get('data_saida')
        preco_aproximado = cleaned_data.get('preco_aproximado')

        if data_entrada and data_saida:
            if data_saida < data_entrada:
                self.add_error('data_saida', 'A data de saída não pode ser anterior à data de entrada.')

        if preco_aproximado and preco_aproximado < 0:
            self.add_error('preco_aproximado', 'O preço aproximado não pode ser um valor negativo.')

        return cleaned_data