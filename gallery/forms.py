import re

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Folder, Reference


def parse_tags(value):
    names = list(
        dict.fromkeys(
            t.lstrip("#").strip().lower() for t in re.split(r"[,\s]+", value.strip()) if t.lstrip("#").strip()
        )
    )
    if len(names) > 20 or any(len(t) > 40 or not re.fullmatch(r"[\w-]+", t) for t in names):
        raise forms.ValidationError(
            "Use up to 20 tags, 40 characters each: letters, numbers, underscores or hyphens."
        )
    return names


class SignupForm(UserCreationForm):
    class Meta:
        model = User
        fields = ["username"]

    def clean_username(self):
        name = self.cleaned_data["username"].lower()
        if User.objects.filter(username__iexact=name).exists():
            raise forms.ValidationError("This username is already taken.")
        return name


class ReferenceForm(forms.ModelForm):
    tag_names = forms.CharField(
        label="Tags",
        required=False,
        max_length=820,
        help_text="Separate with spaces or commas, e.g. #anatomy #hands",
    )

    class Meta:
        model = Reference
        fields = ["title", "folder", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["folder"].queryset = Folder.objects.filter(owner=owner)
        self.fields["folder"].label_from_instance = lambda obj: obj.name
        self.fields["folder"].empty_label = "Unfiled"
        if self.instance.pk:
            self.fields["tag_names"].initial = " ".join("#" + t.name for t in self.instance.tags.all())

    def clean_tag_names(self):
        return parse_tags(self.cleaned_data["tag_names"])
