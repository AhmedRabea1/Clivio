from django import forms
from .models import Branch, UserBranchAssignment
from accounts.models import User


class BranchForm(forms.ModelForm):
    class Meta:
        model = Branch
        fields = ('name', 'address', 'phone', 'is_active')
        widgets = {
            'name':    forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'phone':   forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class UserBranchAssignmentForm(forms.Form):
    user = forms.ModelChoiceField(
        queryset=User.objects.filter(role__in=['doctor', 'assistant'], is_active=True),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Staff Member',
    )
    branch = forms.ModelChoiceField(
        queryset=Branch.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Branch',
    )
