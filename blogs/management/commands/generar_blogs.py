from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import random

from ...models import Author, Blog  # ajustá 'blog' si tu app tiene otro nombre


class Command(BaseCommand):
    help = "Genera 10 blogs de ejemplo con autores y categorías"

    def handle(self, *args, **options):
        authors_data = [
            {"name": "Franco Alberti", "image": "https://randomuser.me/api/portraits/men/75.jpg"},
            {"name": "Lucía Ramírez", "image": "https://randomuser.me/api/portraits/women/22.jpg"},
            {"name": "Tomás Herrera", "image": "https://randomuser.me/api/portraits/men/15.jpg"},
        ]

        categories = ["Ciencia", "Tecnología", "Emprendimiento", "IA", "Materiales", "Física"]
        titles = [
            "Nuevos avances en inteligencia artificial aplicada a materiales",
            "La revolución del hidrógeno verde en la industria metalúrgica",
            "Cómo la IA está transformando la productividad de los ingenieros",
            "Modelos de predicción en metalurgia: una nueva era de precisión",
            "El impacto del aprendizaje profundo en la ciencia de materiales",
            "Emprender en tecnología nuclear: desafíos y oportunidades",
            "Cómo combinar ingeniería y software para innovar",
            "Nuevas fronteras en el estudio de fluidos complejos",
            "La sinergia entre física computacional y machine learning",
            "Automatización y optimización en procesos industriales modernos"
        ]

        # Crear autores
        authors = []
        for data in authors_data:
            author, _ = Author.objects.get_or_create(name=data["name"], defaults={"image": data["image"]})
            authors.append(author)

        # Crear blogs
        for i in range(10):
            Blog.objects.create(
                title=titles[i],
                description=f"Un análisis detallado sobre {titles[i].lower()}.",
                body=(
                    f"{titles[i]} es un tema que está ganando relevancia en los últimos años. "
                    f"En este artículo exploramos cómo los avances recientes están cambiando "
                    f"la forma en que entendemos y aplicamos la ciencia moderna."
                ),
                author=random.choice(authors),
                category=random.choice(categories),
                date=timezone.now().date() - timedelta(days=random.randint(1, 365)),
                read_time=f"{random.randint(4, 10)} min read",
                image=f"https://picsum.photos/seed/{i}/800/400",
                is_featured=(i == 0)
            )

        self.stdout.write(self.style.SUCCESS("✅ Se generaron 10 blogs correctamente."))
