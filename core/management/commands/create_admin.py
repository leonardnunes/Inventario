from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
import os

class Command(BaseCommand):
    help = 'Cria o superusuário inicial a partir de variáveis de ambiente'

    def handle(self, *args, **options):
        username = os.environ.get('ADMIN_USER', 'admin')
        email = os.environ.get('ADMIN_EMAIL', 'admin@exemplo.com')
        password = os.environ.get('ADMIN_PASSWORD')

        if not password:
            self.stdout.write(self.style.ERROR('Variável ADMIN_PASSWORD não configurada!'))
            return

        if not User.objects.filter(username=username).exists():
            User.objects.create_superuser(username, email, password)
            self.stdout.write(self.style.SUCCESS(f'Usuário {username} criado com sucesso!'))
        else:
            self.stdout.write(self.style.WARNING(f'Usuário {username} já existe.'))