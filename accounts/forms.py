from django import forms

from .models import phone_validator

# نگاشت ارقام فارسی/عربی به لاتین — بدون این، کاربری که ۰۹۱۲... تایپ کند رد می‌شد.
PERSIAN_DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')


def normalize_digits(value: str) -> str:
    return (value or '').translate(PERSIAN_DIGITS)


class NormalizedDigitsField(forms.CharField):
    """ارقام فارسی/عربی را قبل از اجرای validatorها به لاتین تبدیل می‌کند.
    (قبلاً validator روی مقدار خام اجرا می‌شد و «۰۹۱۲...» همیشه رد می‌شد.)"""

    def to_python(self, value):
        value = super().to_python(value)
        return ''.join(normalize_digits(value).split())


class PhoneNumberForm(forms.Form):
    phone_number = NormalizedDigitsField(
        label='شماره موبایل',
        max_length=11,
        validators=[phone_validator],
        widget=forms.TextInput(attrs={
            'placeholder': '09xxxxxxxxx',
            'inputmode': 'numeric',
            'autocomplete': 'tel',
            'maxlength': 11,
            'autofocus': True,
            'dir': 'ltr',
            'class': 'form-control form-control-lg text-center',
        }),
    )

    def clean_phone_number(self):
        # ⚠️ اصلاح: نرمال‌سازی ارقام فارسی/عربی + حذف همه‌ی جداکننده‌ها و کاراکترهای کنترلی
        value = normalize_digits(self.cleaned_data['phone_number'])
        value = ''.join(value.split())
        # فقط رقم؛ اگر کاراکتر غیررقمی تزریق شده باشد، همین‌جا رد می‌شود.
        if not value.isdigit():
            raise forms.ValidationError('شماره موبایل فقط باید رقم باشد.')
        return value


class OTPVerifyForm(forms.Form):
    code = NormalizedDigitsField(
        label='کد تایید',
        max_length=8,
        min_length=4,
        widget=forms.TextInput(attrs={
            'placeholder': '۱۲۳۴۵۶',
            'inputmode': 'numeric',
            'autocomplete': 'one-time-code',
            'maxlength': 8,
            'autofocus': True,
            'dir': 'ltr',
            'class': 'form-control form-control-lg text-center otp-input',
        }),
    )

    def clean_code(self):
        # ⚠️ اصلاح: ارقام فارسی پذیرفته می‌شود ولی فقط رقم مجاز است
        # (جلوگیری از ارسال کدهای جعلی/کاراکترهای یونیکد به لایه‌ی مقایسه)
        value = normalize_digits(self.cleaned_data['code']).strip()
        if not value.isdigit():
            raise forms.ValidationError('کد تایید فقط باید رقم باشد.')
        return value


class ProfileForm(forms.Form):
    full_name = forms.CharField(
        label='نام و نام خانوادگی',
        max_length=120,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'maxlength': 120}),
    )

    def clean_full_name(self):
        value = normalize_digits(self.cleaned_data.get('full_name') or '').strip()
        value = ''.join(ch for ch in value if ch.isprintable())
        return ' '.join(value.split())


class AddressForm(forms.Form):
    title = forms.CharField(label='عنوان آدرس', max_length=80, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    recipient_name = forms.CharField(label='نام گیرنده', max_length=120, widget=forms.TextInput(attrs={'class': 'form-control'}))
    phone_number = forms.CharField(
        label='شماره تماس گیرنده',
        max_length=11,
        validators=[phone_validator],
        widget=forms.TextInput(attrs={'class': 'form-control', 'dir': 'ltr', 'inputmode': 'numeric'}),
    )
    province = forms.CharField(label='استان', max_length=80, widget=forms.TextInput(attrs={'class': 'form-control'}))
    city = forms.CharField(label='شهر', max_length=80, widget=forms.TextInput(attrs={'class': 'form-control'}))
    address_line = forms.CharField(label='آدرس کامل', widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}))
    postal_code = forms.CharField(label='کد پستی', max_length=10, required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'dir': 'ltr'}))
    plate = forms.CharField(label='پلاک', max_length=20, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    unit = forms.CharField(label='واحد', max_length=20, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    notes = forms.CharField(label='توضیحات اضافی', max_length=300, required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}))
    is_default = forms.BooleanField(label='انتخاب به‌عنوان آدرس پیش‌فرض', required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))

    def clean_phone_number(self):
        value = normalize_digits(self.cleaned_data['phone_number']).strip()
        if not value.isdigit():
            raise forms.ValidationError('شماره تماس فقط باید رقم باشد.')
        return value

    def clean_postal_code(self):
        value = normalize_digits(self.cleaned_data.get('postal_code') or '').strip()
        if value and not value.isdigit():
            raise forms.ValidationError('کد پستی فقط باید رقم باشد.')
        return value

    def clean_title(self):
        value = (self.cleaned_data.get('title') or '').strip()
        return ' '.join(value.split()) or 'آدرس اصلی'

    def clean_recipient_name(self):
        value = (self.cleaned_data.get('recipient_name') or '').strip()
        value = ''.join(ch for ch in value if ch.isprintable())
        return ' '.join(value.split())

    def clean_address_line(self):
        value = (self.cleaned_data.get('address_line') or '').strip()
        value = ''.join(ch for ch in value if ch.isprintable())
        return ' '.join(value.split())

    def clean_province(self):
        value = (self.cleaned_data.get('province') or '').strip()
        return ' '.join(value.split())

    def clean_city(self):
        value = (self.cleaned_data.get('city') or '').strip()
        return ' '.join(value.split())
