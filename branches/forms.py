from django import forms
from .models import Branch, UserBranchAssignment
from accounts.models import User


class BranchForm(forms.ModelForm):
    class Meta:
        model = Branch
        fields = ('name', 'address', 'phone', 'from_time', 'to_time', 'vacation_days', 'is_active')
        widgets = {
            'name':      forms.TextInput(attrs={'class': 'form-control'}),
            'address':   forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'phone':     forms.TextInput(attrs={'class': 'form-control'}),
            'from_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'to_time':   forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    VACATION_CHOICES = [
        (0, 'Saturday'), (1, 'Sunday'), (2, 'Monday'),
        (3, 'Tuesday'), (4, 'Wednesday'), (5, 'Thursday'), (6, 'Friday'),
    ]
    vacation_days = forms.MultipleChoiceField(
        choices=VACATION_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.vacation_days:
            self.initial['vacation_days'] = [str(d) for d in self.instance.vacation_days]

    def clean_vacation_days(self):
        return [int(d) for d in self.cleaned_data.get('vacation_days', [])]


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
