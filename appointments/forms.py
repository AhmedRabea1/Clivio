from django import forms
from .models import Patient


class PatientForm(forms.ModelForm):
    class Meta:
        model  = Patient
        fields = ('first_name', 'last_name', 'date_of_birth', 'mobile_number', 'medical_notes')
        widgets = {
            'first_name':    forms.TextInput(attrs={'class': 'form-control'}),
            'last_name':     forms.TextInput(attrs={'class': 'form-control'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'mobile_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+20 100 000 0000'}),
            'medical_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }
