from django.db import models

class Member(models.Model):
    name = models.CharField(max_length=100)
    surname = models.CharField(max_length=100)
    user = models.OneToOneField("auth.User", on_delete=models.CASCADE, related_name="member", null=True, blank=True)
    company = models.ForeignKey("Company", on_delete=models.SET_NULL, null=True, blank=True, related_name="members")

    def __str__(self):
        return f"{self.name} {self.surname}"

class Company(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    image = models.ImageField(upload_to="company_logos/", blank=True, null=True)
    
    def __str__(self):
        return self.name