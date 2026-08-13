from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from cart.models import Cart

from .forms import OTPVerifyForm, PhoneNumberForm, ProfileForm
from .models import OTP
from .services.sms import SMSSendError, send_otp_sms

User = get_user_model()

SESSION_PHONE_KEY = 'otp_phone_number'
SESSION_NEXT_KEY = 'otp_next_url'
SESSION_GUEST_CART_KEY = 'guest_cart_session_key'


def _migrate_guest_cart_to_session(request):
    guest_session_key = request.session.get(SESSION_GUEST_CART_KEY)
    if not guest_session_key:
        return

    guest_cart = Cart.objects.filter(session_key=guest_session_key).first()
    if not guest_cart:
        request.session.pop(SESSION_GUEST_CART_KEY, None)
        return

    current_session_key = request.session.session_key
    if not current_session_key or guest_session_key == current_session_key:
        request.session.pop(SESSION_GUEST_CART_KEY, None)
        return

    current_cart = Cart.objects.filter(session_key=current_session_key).first()
    if current_cart and current_cart.pk != guest_cart.pk:
        for item in guest_cart.items.all():
            target, created = current_cart.items.get_or_create(
                variant=item.variant,
                defaults={'quantity_meters': item.quantity_meters},
            )
            if not created:
                target.quantity_meters += item.quantity_meters
                target.save(update_fields=['quantity_meters'])
            item.delete()
        guest_cart.delete()
    else:
        guest_cart.session_key = current_session_key
        guest_cart.save(update_fields=['session_key'])

    request.session.pop(SESSION_GUEST_CART_KEY, None)


def _recent_otp_cooldown_remaining(phone_number):
    """اگر یک کد هنوز در بازه‌ی خنک‌سازی باشه، ثانیه‌های باقی‌مانده رو برمی‌گردونه، وگرنه None."""
    last_otp = OTP.objects.filter(phone_number=phone_number).order_by('-created_at').first()
    if not last_otp:
        return None
    elapsed = (timezone.now() - last_otp.created_at).total_seconds()
    remaining = settings.OTP_RESEND_COOLDOWN_SECONDS - elapsed
    return int(remaining) if remaining > 0 else None


def _issue_otp(phone_number):
    otp = OTP.objects.create(phone_number=phone_number)
    send_otp_sms(phone_number, otp.code)
    return otp


@require_http_methods(['GET', 'POST'])
def login_request_view(request):
    if request.user.is_authenticated:
        return redirect(settings.LOGIN_REDIRECT_URL)

    if request.method == 'POST':
        form = PhoneNumberForm(request.POST)
        if form.is_valid():
            phone_number = form.cleaned_data['phone_number']
            remaining = _recent_otp_cooldown_remaining(phone_number)
            if remaining:
                messages.warning(request, f'کد قبلی هنوز معتبره. {remaining} ثانیه دیگه دوباره تلاش کن.')
            else:
                try:
                    _issue_otp(phone_number)
                except SMSSendError:
                    messages.error(request, 'ارسال پیامک با مشکل مواجه شد. کمی بعد دوباره تلاش کن.')
                    return render(request, 'accounts/login_request.html', {'form': form})
                request.session[SESSION_PHONE_KEY] = phone_number
            return redirect('accounts:verify')
    else:
        form = PhoneNumberForm()

    return render(request, 'accounts/login_request.html', {'form': form})


@require_http_methods(['GET', 'POST'])
def login_verify_view(request):
    phone_number = request.session.get(SESSION_PHONE_KEY)
    if not phone_number:
        return redirect('accounts:login')

    if request.method == 'POST':
        form = OTPVerifyForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['code']
            user = authenticate(request, phone_number=phone_number, otp_code=code)
            if user is not None:
                guest_session_key = request.session.session_key
                request.session[SESSION_GUEST_CART_KEY] = guest_session_key
                login(request, user, backend='accounts.backends.OTPBackend')
                _migrate_guest_cart_to_session(request)
                del request.session[SESSION_PHONE_KEY]
                next_url = request.session.pop(SESSION_NEXT_KEY, None)
                messages.success(request, 'خوش اومدی به آتلار 🌿')
                return redirect(next_url or settings.LOGIN_REDIRECT_URL)
            messages.error(request, 'کد وارد شده اشتباه یا منقضی‌شده است.')
    else:
        form = OTPVerifyForm()

    cooldown = _recent_otp_cooldown_remaining(phone_number) or 0
    return render(request, 'accounts/login_verify.html', {
        'form': form,
        'phone_number': phone_number,
        'cooldown': cooldown,
    })


@require_http_methods(['POST'])
def resend_otp_view(request):
    phone_number = request.session.get(SESSION_PHONE_KEY)
    if not phone_number:
        return redirect('accounts:login')

    remaining = _recent_otp_cooldown_remaining(phone_number)
    if remaining:
        messages.warning(request, f'{remaining} ثانیه دیگه می‌تونی دوباره درخواست بدی.')
    else:
        try:
            _issue_otp(phone_number)
            messages.success(request, 'کد جدید پیامک شد.')
        except SMSSendError:
            messages.error(request, 'ارسال پیامک با مشکل مواجه شد.')
    return redirect('accounts:verify')


@require_http_methods(['GET', 'POST'])
def logout_view(request):
    logout(request)
    return redirect('core:home')


@login_required
def profile_view(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST)
        if form.is_valid():
            request.user.first_name = form.cleaned_data['first_name']
            request.user.last_name = form.cleaned_data['last_name']
            request.user.save(update_fields=['first_name', 'last_name'])
            messages.success(request, 'اطلاعات با موفقیت ذخیره شد.')
            return redirect('accounts:profile')
    else:
        form = ProfileForm(initial={
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
        })
    return render(request, 'accounts/profile.html', {'form': form})
