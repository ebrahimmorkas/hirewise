from django.utils.text import slugify


def unique_slug(instance, value: str, *, field: str = "slug", max_length: int = 120) -> str:
    """Slugify ``value`` and append ``-2``, ``-3``... until unique for the model."""
    model = type(instance)
    base = slugify(value)[: max_length - 6] or model._meta.model_name
    slug, counter = base, 2
    while model.objects.filter(**{field: slug}).exclude(pk=instance.pk).exists():
        slug = f"{base}-{counter}"
        counter += 1
    return slug
