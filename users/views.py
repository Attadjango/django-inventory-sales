from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST
from django.contrib.auth.forms import UserCreationForm , AuthenticationForm
from django.contrib.auth import login as auth_login , logout as auth_logout
from django.contrib.auth.decorators import login_required , user_passes_test
from django.utils.http import url_has_allowed_host_and_scheme
# Create your views here.

@login_required
@user_passes_test(lambda u: u.is_staff)
def register(request):
    if request.method == "POST": 
        form = UserCreationForm(request.POST) 
        if form.is_valid(): 
            user = form.save() 
            auth_login(request, user)
            return redirect("inventory:inventory")
    else:
        form = UserCreationForm()
    content = {
        'title': 'Register a new user',
        'form': form
    }
    return render(request, 'users/register.html', content)

def login(request):
    if request.method == "POST": 
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            auth_login(request, form.get_user())
            next_url = request.POST.get('next', '')
            if next_url and url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)
            return redirect("inventory:inventory")
    else:
        form = AuthenticationForm()
    content = {
        'form': form,
        'title': 'Login',
    }
    return render(request, 'users/login.html', content)

@require_POST
def logout(request):
    auth_logout(request)
    return redirect("users:login")

