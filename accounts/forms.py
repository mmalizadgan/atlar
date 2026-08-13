from django import forms

from .models import phone_validator


class PhoneNumberForm(forms.Form):
    phone_number = forms.CharField(
        label='شماره موبایل',
        max_length=11,
        validators=[phone_validator],
        widget=forms.TextInput(attrs={
            'placeholder': '09xxxxxxxxx',
            'inputmode': 'numeric',
            'autofocus': True,
            'dir': 'ltr',
            'class': 'form-control form-control-lg text-center',
        }),
    )

    def clean_phone_number(self):
        value = self.cleaned_data['phone_number'].strip()
        value = value.replace(' ', '')
        return value


class OTPVerifyForm(forms.Form):
    code = forms.CharField(
        label='کد تایید',
        max_length=8,
        widget=forms.TextInput(attrs={
            'placeholder': '۱۲۳۴۵',
            'inputmode': 'numeric',
            'autofocus': True,
            'dir': 'ltr',
            'class': 'form-control form-control-lg text-center otp-input',
        }),
    )


class ProfileForm(forms.Form):
    first_name = forms.CharField(label='نام', max_length=60, required=False,
                                  widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(label='نام خانوادگی', max_length=60, required=False,
                                 widget=forms.TextInput(attrs={'class': 'form-control'}))
