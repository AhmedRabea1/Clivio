from django import forms
from .models import Patient


class PatientForm(forms.ModelForm):
    class Meta:
        model  = Patient
        fields = (
            'first_name', 'last_name', 'date_of_birth',
            'mobile_number', 'clinic_location', 'doctor', 'status', 'visit_date',
            'medical_notes',
        )
        widgets = {
            'first_name':       forms.TextInput(attrs={'class': 'form-control'}),
            'last_name':        forms.TextInput(attrs={'class': 'form-control'}),
            'date_of_birth':    forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'mobile_number':    forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+20 100 000 0000'}),
            'clinic_location':  forms.Select(attrs={'class': 'form-select', 'id': 'id_clinic_location'}),
            'doctor':           forms.Select(attrs={'class': 'form-select', 'id': 'id_doctor'}),
            'status':           forms.Select(attrs={'class': 'form-select'}),
            'visit_date':       forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'medical_notes':    forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Enter any medical notes, allergies, or relevant history…'}),
        }

    def __init__(self, *args, clinic=None, **kwargs):
        super().__init__(*args, **kwargs)
        if clinic:
            from branches.models import Branch
            from accounts.models import User
            self.fields['clinic_location'].queryset = Branch.objects.filter(
                clinic=clinic, is_active=True
            )
            self.fields['doctor'].queryset = User.objects.filter(
                clinic=clinic, role='doctor', is_active=True
            )
        self.fields['doctor'].required = False
        self.fields['date_of_birth'].required = False
