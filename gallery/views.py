from pathlib import Path
from uuid import uuid4
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.db import transaction, IntegrityError
from django.db.models import Count, Q, Sum
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from .forms import ReferenceForm, SignupForm, parse_tags
from .imaging import inspect_image
from .models import Folder, Reference, Tag

def gallery(request):
    if not request.user.is_authenticated:
        return render(request, "gallery/demo.html")
    owner = request.user
    view = request.GET.get("view", "all")
    if view not in ("all", "favorites", "unfiled", "trash"):
        view = "all"
    images = Reference.objects.filter(owner=owner, trashed=view == "trash")
    selected_folder = None
    if request.GET.get("folder"):
        try:
            selected_folder = get_object_or_404(Folder, pk=int(request.GET["folder"]), owner=owner)
        except ValueError:
            return redirect("gallery")
        images = images.filter(folder=selected_folder)
    if view == "favorites":
        images = images.filter(favorite=True)
    elif view == "unfiled":
        images = images.filter(folder__isnull=True)
    query = request.GET.get("q", "").strip()[:200]
    if query.startswith("#"):
        images = images.filter(tags__name__iexact=query[1:])
    elif query:
        images = images.filter(Q(title__icontains=query) | Q(tags__name__icontains=query) | Q(notes__icontains=query))
    tag = request.GET.get("tag", "")[:40]
    if tag:
        images = images.filter(tags__name=tag)
    sort = request.GET.get("sort", "newest")
    ordering = {"newest": "-created_at", "oldest": "created_at", "name": "title"}.get(sort, "-created_at")
    images = images.distinct().order_by(ordering, "id").prefetch_related("tags").select_related("folder")
    page = Paginator(images, 36).get_page(request.GET.get("page"))
    base = Reference.objects.filter(owner=owner, trashed=False)
    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "gallery/index.html", {
        "page": page, "folders": Folder.objects.filter(owner=owner).annotate(total=Count("images", filter=Q(images__trashed=False))),
        "tags": Tag.objects.filter(owner=owner).annotate(total=Count("images", filter=Q(images__trashed=False))),
        "selected_folder": selected_folder, "view": view, "query": query, "tag": tag, "sort": sort,
        "heading": selected_folder.name if selected_folder else {"all": "All references", "favorites": "Favorites", "unfiled": "Unfiled", "trash": "Trash"}[view],
        "total": base.count(), "favorite_count": base.filter(favorite=True).count(),
        "unfiled_count": base.filter(folder__isnull=True).count(),
        "trash_count": Reference.objects.filter(owner=owner, trashed=True).count(),
        "storage": Reference.objects.filter(owner=owner).aggregate(total=Sum("size"))["total"] or 0,
        "pagination_query": params.urlencode(),
    })

def signup(request):
    if request.user.is_authenticated:
        return redirect("gallery")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save()
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return redirect("gallery")
    return render(request, "registration/signup.html", {"form": form})

@login_required
@require_POST
def folder_create(request):
    name = request.POST.get("name", "").strip()
    if not name or len(name) > 80:
        messages.error(request, "Choose a folder name between 1 and 80 characters.")
        return redirect("gallery")
    folder, created = Folder.objects.get_or_create(owner=request.user, name=name)
    if not created:
        messages.info(request, "That folder already exists.")
    return redirect(f"/?folder={folder.pk}")

@login_required
@require_POST
def folder_edit(request, pk):
    folder = get_object_or_404(Folder, pk=pk, owner=request.user)
    if request.POST.get("action") == "delete":
        folder.delete()
        messages.success(request, "Folder removed. Its images are now in Unfiled.")
        return redirect("gallery")
    name = request.POST.get("name", "").strip()
    if not name or len(name) > 80:
        messages.error(request, "Choose a folder name between 1 and 80 characters.")
    elif Folder.objects.filter(owner=request.user, name=name).exclude(pk=pk).exists():
        messages.error(request, "A folder with that name already exists.")
    else:
        folder.name = name
        folder.save(update_fields=["name"])
    return redirect(f"/?folder={folder.pk}")

@login_required
@require_POST
def tag_create(request):
    try:
        names = parse_tags(request.POST.get("name", "")[:820])
        if not names:
            raise ValidationError("Enter at least one tag.")
        for name in names:
            Tag.objects.get_or_create(owner=request.user, name=name)
        messages.success(request, "Tags created. Add them to a reference when uploading or editing.")
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    return redirect("gallery")

@login_required
@require_POST
def upload(request):
    file = request.FILES.get("image")
    if file is None:
        return JsonResponse({"error": "Choose an image to upload."}, status=400)
    folder = None
    if request.POST.get("folder"):
        try:
            folder = Folder.objects.get(pk=int(request.POST["folder"]), owner=request.user)
        except (ValueError, Folder.DoesNotExist):
            return JsonResponse({"error": "This folder is not available."}, status=400)
    try:
        names = parse_tags(request.POST.get("tags", "")[:820])
        info = inspect_image(file)
    except ValidationError as exc:
        return JsonResponse({"error": exc.messages[0]}, status=400)
    reference = Reference(owner=request.user, folder=folder, title=Path(file.name).stem[:180] or "Untitled reference",
                          size=file.size, width=info["width"], height=info["height"], mime_type=info["mime_type"])
    try:
        # Storage writes are not transactional; remove new files if the DB write fails.
        reference.original.save(f"{uuid4().hex}.{info['extension']}", file, save=False)
        reference.thumbnail.save(f"{uuid4().hex}.webp", ContentFile(info["thumbnail"]), save=False)
        with transaction.atomic():
            reference.save()
            reference.tags.set([Tag.objects.get_or_create(owner=request.user, name=name)[0] for name in names])
    except Exception:
        reference.original.delete(save=False)
        reference.thumbnail.delete(save=False)
        raise
    return JsonResponse({"id": str(reference.pk), "title": reference.title}, status=201)

@login_required
def detail(request, pk):
    reference = get_object_or_404(Reference.objects.prefetch_related("tags").select_related("folder"), pk=pk, owner=request.user)
    return render(request, "gallery/detail.html", {"reference": reference, "form": ReferenceForm(instance=reference, owner=request.user)})

@login_required
@require_POST
def image_edit(request, pk):
    reference = get_object_or_404(Reference, pk=pk, owner=request.user)
    form = ReferenceForm(request.POST, instance=reference, owner=request.user)
    if form.is_valid():
        with transaction.atomic():
            form.save()
            reference.tags.set([Tag.objects.get_or_create(owner=request.user, name=name)[0] for name in form.cleaned_data["tag_names"]])
        messages.success(request, "Reference updated.")
        return redirect("detail", pk=pk)
    return render(request, "gallery/detail.html", {"reference": reference, "form": form}, status=400)

@login_required
@require_POST
def image_state(request, pk):
    reference = get_object_or_404(Reference, pk=pk, owner=request.user)
    action = request.POST.get("action")
    if action == "favorite":
        reference.favorite = not reference.favorite
        reference.save(update_fields=["favorite"])
    elif action in ("trash", "restore"):
        reference.trashed = action == "trash"
        reference.save(update_fields=["trashed"])
    else:
        return JsonResponse({"error": "Unknown action."}, status=400)
    if request.headers.get("Accept") == "application/json":
        return JsonResponse({"favorite": reference.favorite, "trashed": reference.trashed})
    if action == "trash":
        messages.success(request, "Moved to Trash. You can restore it any time.")
        return redirect("gallery")
    return redirect("detail", pk=pk)

@login_required
def image_file(request, pk, variant):
    reference = get_object_or_404(Reference, pk=pk, owner=request.user)
    if variant not in ("original", "thumbnail", "download"):
        from django.http import Http404
        raise Http404
    field = reference.thumbnail if variant == "thumbnail" else reference.original
    try:
        stream = field.open("rb")
    except FileNotFoundError:
        from django.http import Http404
        raise Http404("Image file is missing from storage.")
    response = FileResponse(stream, content_type="image/webp" if variant == "thumbnail" else reference.mime_type,
                            as_attachment=variant == "download", filename=reference.title + Path(field.name).suffix)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
