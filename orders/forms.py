from django import forms

from accounts.models import phone_validator


class CheckoutForm(forms.Form):
    full_name = forms.CharField(
        label='نام و نام خانوادگی گیرنده', max_length=120,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    phone_number = forms.CharField(
        label='شماره تماس', max_length=11, validators=[phone_validator],
        widget=forms.TextInput(attrs={'class': 'form-control', 'dir': 'ltr'}),
    )
    city = forms.CharField(
        label='شهر', max_length=80,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    address_line = forms.CharField(
        label='آدرس کامل', widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
    )
    postal_code = forms.CharField(
        label='کد پستی', max_length=10, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'dir': 'ltr'}),
    )
