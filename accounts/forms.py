from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import User, Configuration


class LoginForm(AuthenticationForm):
    username = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email address', 'autofocus': True}),
    )
    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}),
    )


class UserForm(forms.ModelForm):
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Leave blank to keep current'}),
        help_text='Leave blank to keep existing password.',
    )

    class Meta:
        model = User
        fields = ('name', 'email', 'role', 'phone', 'specialty', 'role_title', 'clinic', 'is_active')
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'specialty': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Dermatologist'}),
            'role_title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Senior Receptionist'}),
            'clinic': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            user.set_password(password)
        if commit:
            user.save()
        return user


class ConfigurationForm(forms.ModelForm):
    class Meta:
        model = Configuration
        fields = (
            'clinic_name',
            'logo', 'hero_image',
            'slogan', 'sub_slogan', 'footer_info',
            'linkedin_url', 'instagram_url', 'facebook_url', 'whatsapp_url',
            'primary_color', 'secondary_color',
        )
        widgets = {
            'clinic_name':     forms.TextInput(attrs={'class': 'form-control'}),
            'slogan':          forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Your skin, our care'}),
            'sub_slogan':      forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Expert dermatology since 2015'}),
            'footer_info':     forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'linkedin_url':    forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://linkedin.com/company/...'}),
            'instagram_url':   forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://instagram.com/...'}),
            'facebook_url':    forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://facebook.com/...'}),
            'whatsapp_url':    forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://wa.me/20100...'}),
            'primary_color':   forms.TextInput(attrs={'class': 'form-control form-control-color', 'type': 'color'}),
            'secondary_color': forms.TextInput(attrs={'class': 'form-control form-control-color', 'type': 'color'}),
        }
