from django import forms

from .models import StaffProfile


class StaffProfileForm(forms.ModelForm[StaffProfile]):
    class Meta:
        model = StaffProfile
        fields = ["first_name", "last_name", "avatar"]
