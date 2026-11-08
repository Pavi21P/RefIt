from django.contrib.auth import views as auth
from django.urls import path

from gallery import views

urlpatterns = [
    path("", views.gallery, name="gallery"),
    path("accounts/signup/", views.signup, name="signup"),
    path("accounts/login/", auth.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("accounts/logout/", auth.LogoutView.as_view(), name="logout"),
    path(
        "accounts/password/",
        auth.PasswordChangeView.as_view(template_name="registration/password.html", success_url="/"),
        name="password_change",
    ),
    path("folders/", views.folder_create, name="folder_create"),
    path("folders/<int:pk>/", views.folder_edit, name="folder_edit"),
    path("tags/", views.tag_create, name="tag_create"),
    path("upload/", views.upload, name="upload"),
    path("images/<uuid:pk>/", views.detail, name="detail"),
    path("images/<uuid:pk>/edit/", views.image_edit, name="image_edit"),
    path("images/<uuid:pk>/state/", views.image_state, name="image_state"),
    path("images/<uuid:pk>/file/<str:variant>/", views.image_file, name="image_file"),
]
