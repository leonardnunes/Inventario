from django import forms
from .models import Equipamento

class EquipamentoForm(forms.ModelForm):
    class Meta:
        model = Equipamento
        fields = [
            'nome', 'marca', 'modelo', 'numero_serie', 'categoria',
            'localizacao', 'situacao', 'data_entrada', 'preco_aproximado',
            'imagem', 'data_saida', 'motivo_saida', 'observacoes',
            'departamento'
        ]


        widgets = {

            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'marca': forms.TextInput(attrs={'class': 'form-control'}),
            'modelo': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_serie': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: YMH-123456'}),
            'preco_aproximado': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 1500.50'}),


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