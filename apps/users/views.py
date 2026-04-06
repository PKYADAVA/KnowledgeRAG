"""User authentication views."""
import logging
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods

from .forms import LoginForm, RegisterForm, ProfileForm

logger = logging.getLogger(__name__)


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect("documents:dashboard")

    form = LoginForm(request, data=request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            logger.info(f"User logged in: {user.email}")
            next_url = request.GET.get("next", "documents:dashboard")
            return redirect(next_url)
        else:
            messages.error(request, "Invalid email or password.")

    return render(request, "users/login.html", {"form": form})


@require_http_methods(["GET", "POST"])
def register_view(request):
    if request.user.is_authenticated:
        return redirect("documents:dashboard")

    form = RegisterForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            user = form.save()
            login(request, user)
            logger.info(f"New user registered: {user.email}")
            messages.success(request, f"Welcome, {user.display_name}!")
            return redirect("documents:dashboard")
        else:
            messages.error(request, "Please fix the errors below.")

    return render(request, "users/register.html", {"form": form})


@login_required
@require_http_methods(["POST"])
def logout_view(request):
    logger.info(f"User logged out: {request.user.email}")
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("users:login")


@login_required
@require_http_methods(["GET", "POST"])
def profile_view(request):
    form = ProfileForm(
        request.POST or None,
        request.FILES or None,
        instance=request.user,
    )
    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect("users:profile")
        else:
            messages.error(request, "Please fix the errors below.")

    return render(request, "users/profile.html", {"form": form})
