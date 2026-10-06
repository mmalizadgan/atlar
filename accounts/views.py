from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods

from cart.models import Cart

from .forms import AddressForm, OTPVerifyForm, PhoneNumberForm, ProfileForm
from .models import Address
from .services import otp as otp_service
from .services.sms import SMSSendError, send_otp_sms

SESSION_PHONE_KEY = 'otp_phone_number'
SESSION_NEXT_KEY = 'otp_next_url'
SESSION_GUEST_CART_KEY = 'guest_cart_session_key'


def _safe_next_url(request):
    """
    ⚠️ اصلاح: `next` فقط اگر آدرس داخلی باشد پذیرفته می‌شود (جلوگیری از Open Redirect).
    """
    candidate = request.POST.get('next') or request.GET.get('next')
    if not candidate:
        return None
    if url_has_allowed_host_and_scheme(
        candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return candidate
    return None


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


def _masked_phone(phone_number):
    """شماره در UI نیمه‌پوشان نشان داده می‌شود (کاهش نشت اطلاعات در اسکرین‌شات‌ها)."""
    if len(phone_number) < 7:
        return phone_number
    return f'{phone_number[:4]}•••{phone_number[-3:]}'


def _issue_and_send(request, phone_number):
    """
    صادر کردن کد + ارسال پیامک، با مدیریت کامل خطاها.
    همیشه None برمی‌گرداند؛ پیام‌ها از طریق messages ثبت می‌شوند.
    """
    # نشست باید از قبل وجود داشته باشد تا کد به آن گره بخورد (session binding).
    if not request.session.session_key:
        request.session.create()

    try:
        otp = otp_service.issue_otp(
            phone_number=phone_number,
            session_key=request.session.session_key or '',
            ip_address=otp_service.get_client_ip(request),
        )
    except otp_service.OTPCooldownError as exc:
        # ⚠️ اصلاح: قبلاً شماره در نشست ذخیره نمی‌شد → کاربر به صفحه‌ی لاگین برمی‌گشت
        # و راهی برای واردکردن کدِ هنوز معتبر نداشت.
        request.session[SESSION_PHONE_KEY] = phone_number
        messages.warning(request, f'کد قبلی هنوز معتبره؛ همون رو وارد کن. ارسال مجدد تا {exc.remaining_seconds} ثانیه دیگه.')
        return
    except otp_service.OTPLockedOutError as exc:
        minutes = max(1, exc.remaining_seconds // 60)
        messages.error(request, f'به دلیل تلاش‌های ناموفق، این شماره {minutes} دقیقه قفل شده. بعداً تلاش کن.')
        return
    except otp_service.OTPThrottledError as exc:
        messages.error(request, str(exc) or 'تعداد درخواست کد زیاد است. کمی بعد دوباره تلاش کن.')
        return

    # ارسال کد خام (فقط همین‌جا وجود دارد و در دیتابیس ذخیره نمی‌شود)
    try:
        send_otp_sms(phone_number, otp.plain_code)
    except SMSSendError:
        # کد را می‌سوزانیم تا مهاجم نتواند از خطای ارسال سوءاستفاده کند.
        otp.is_used = True
        otp.save(update_fields=['is_used'])
        messages.error(request, 'ارسال پیامک با مشکل مواجه شد. کمی بعد دوباره تلاش کن.')
        return

    request.session[SESSION_PHONE_KEY] = phone_number
    messages.info(request, 'کد تایید پیامک شد.')


@require_http_methods(['GET', 'POST'])
def login_request_view(request):
    if request.user.is_authenticated:
        return redirect(settings.LOGIN_REDIRECT_URL)

    if request.method == 'POST':
        form = PhoneNumberForm(request.POST)
        if form.is_valid():
            phone_number = form.cleaned_data['phone_number']
            next_url = _safe_next_url(request)
            if next_url:
                request.session[SESSION_NEXT_KEY] = next_url
            _issue_and_send(request, phone_number)
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
            try:
                user = authenticate(request, phone_number=phone_number, otp_code=code)
            except otp_service.OTPLockedOutError as exc:
                minutes = max(1, exc.remaining_seconds // 60)
                messages.error(request, f'تلاش‌های ناموفق زیاد بود. {minutes} دقیقه دیگر دوباره امتحان کن.')
                return redirect('accounts:login')
            except otp_service.OTPThrottledError:
                messages.error(request, 'تعداد تلاش‌ها زیاد است. کمی صبر کن و دوباره تلاش کن.')
                return redirect('accounts:verify')
            except otp_service.OTPError:
                messages.error(request, 'کد وارد شده اشتباه یا منقضی‌شده است.')
                form = OTPVerifyForm()
            else:
                if user is not None:
                    guest_session_key = request.session.session_key
                    request.session[SESSION_GUEST_CART_KEY] = guest_session_key
                    login(request, user, backend='accounts.backends.OTPBackend')
                    _migrate_guest_cart_to_session(request)
                    request.session.pop(SESSION_PHONE_KEY, None)
                    next_url = request.session.pop(SESSION_NEXT_KEY, None)
                    messages.success(request, 'خوش اومدی به آتلار 🌿')
                    return redirect(next_url or settings.LOGIN_REDIRECT_URL)
                messages.error(request, 'کد وارد شده اشتباه یا منقضی‌شده است.')
                form = OTPVerifyForm()
    else:
        form = OTPVerifyForm()

    cooldown = otp_service.cooldown_remaining(phone_number)
    lockout = otp_service.phone_lockout_remaining(phone_number)
    return render(request, 'accounts/login_verify.html', {
        'form': form,
        'phone_number': phone_number,
        'masked_phone_number': _masked_phone(phone_number),
        'cooldown': cooldown,
        'lockout': lockout,
    })


@require_http_methods(['POST'])
def resend_otp_view(request):
    phone_number = request.session.get(SESSION_PHONE_KEY)
    if not phone_number:
        return redirect('accounts:login')

    _issue_and_send(request, phone_number)
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
            full_name = form.cleaned_data['full_name']
            name_parts = full_name.split(maxsplit=1)
            request.user.first_name = name_parts[0] if name_parts else ''
            request.user.last_name = name_parts[1] if len(name_parts) > 1 else ''
            request.user.save(update_fields=['first_name', 'last_name'])
            messages.success(request, 'اطلاعات با موفقیت ذخیره شد.')
            return redirect('accounts:profile')
    else:
        form = ProfileForm(initial={'full_name': request.user.get_full_name()})

    orders = request.user.orders.all().order_by('-created_at')[:5]
    orders_count = request.user.orders.count()
    total_spend = sum((order.total for order in request.user.orders.all()), 0)
    default_address = request.user.addresses.filter(is_default=True).first()
    addresses = request.user.addresses.all()

    return render(request, 'accounts/profile.html', {
        'form': form,
        'orders': orders,
        'orders_count': orders_count,
        'total_spend': total_spend,
        'addresses': addresses,
        'default_address': default_address,
        'address_form': AddressForm(),
    })


@login_required
def address_create_view(request):
    if request.method == 'POST':
        form = AddressForm(request.POST)
        if form.is_valid():
            address = Address.objects.create(
                user=request.user,
                title=form.cleaned_data['title'],
                recipient_name=form.cleaned_data['recipient_name'],
                phone_number=form.cleaned_data['phone_number'],
                province=form.cleaned_data['province'],
                city=form.cleaned_data['city'],
                address_line=form.cleaned_data['address_line'],
                postal_code=form.cleaned_data['postal_code'],
                plate=form.cleaned_data['plate'],
                unit=form.cleaned_data['unit'],
                notes=form.cleaned_data['notes'],
                is_default=form.cleaned_data['is_default'],
            )
            messages.success(request, 'آدرس جدید با موفقیت اضافه شد.')
            return redirect('accounts:profile')
    else:
        form = AddressForm()
    return render(request, 'accounts/address_form.html', {'form': form, 'title': 'افزودن آدرس'})


@login_required
def address_edit_view(request, pk):
    address = get_object_or_404(Address.objects.filter(user=request.user), pk=pk)
    if request.method == 'POST':
        form = AddressForm(request.POST)
        if form.is_valid():
            address.title = form.cleaned_data['title']
            address.recipient_name = form.cleaned_data['recipient_name']
            address.phone_number = form.cleaned_data['phone_number']
            address.province = form.cleaned_data['province']
            address.city = form.cleaned_data['city']
            address.address_line = form.cleaned_data['address_line']
            address.postal_code = form.cleaned_data['postal_code']
            address.plate = form.cleaned_data['plate']
            address.unit = form.cleaned_data['unit']
            address.notes = form.cleaned_data['notes']
            address.is_default = form.cleaned_data['is_default']
            address.save()
            messages.success(request, 'آدرس با موفقیت ویرایش شد.')
            return redirect('accounts:profile')
    else:
        form = AddressForm(initial={
            'title': address.title,
            'recipient_name': address.recipient_name,
            'phone_number': address.phone_number,
            'province': address.province,
            'city': address.city,
            'address_line': address.address_line,
            'postal_code': address.postal_code,
            'plate': address.plate,
            'unit': address.unit,
            'notes': address.notes,
            'is_default': address.is_default,
        })
    return render(request, 'accounts/address_form.html', {'form': form, 'title': 'ویرایش آدرس', 'address': address})


@login_required
def address_delete_view(request, pk):
    address = get_object_or_404(Address.objects.filter(user=request.user), pk=pk)
    if request.method == 'POST':
        with transaction.atomic():
            was_default = address.is_default
            address.delete()
            if was_default:
                fallback = request.user.addresses.order_by('-created_at').first()
                if fallback:
                    fallback.is_default = True
                    fallback.save(update_fields=['is_default'])
        messages.success(request, 'آدرس حذف شد.')
    return redirect('accounts:profile')


@login_required
def address_set_default_view(request, pk):
    address = get_object_or_404(Address.objects.filter(user=request.user), pk=pk)
    with transaction.atomic():
        request.user.addresses.filter(is_default=True).exclude(pk=pk).update(is_default=False)
        address.is_default = True
        address.save(update_fields=['is_default'])
    messages.success(request, 'آدرس پیش‌فرض تغییر کرد.')
    return redirect('accounts:profile')
