from django.db import models


class Parent(models.Model):
    name = models.CharField(max_length=32)


class Child(models.Model):
    name = models.CharField(max_length=32)
    parent = models.ForeignKey(Parent)
    timestamp = models.DateTimeField()