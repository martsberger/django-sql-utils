from django.db import models
from django.db.models import CASCADE


# Simple parent-child model
class Parent(models.Model):
    name = models.CharField(max_length=32)


class Child(models.Model):
    name = models.CharField(max_length=32)
    parent = models.ForeignKey(Parent, on_delete=CASCADE)
    timestamp = models.DateTimeField()
    other_timestamp = models.DateTimeField(null=True)


# Books, Authors, Editors, there are more than 1 way Book/Author are m2m
# With publisher, there are multiple depths of traversal
class Author(models.Model):
    name = models.CharField(max_length=32)


class Publisher(models.Model):
    name = models.CharField(max_length=32)
    number = models.IntegerField()


class Book(models.Model):
    title = models.CharField(max_length=128)
    authors = models.ManyToManyField(Author, through='BookAuthor', related_name='authored_books')
    editors = models.ManyToManyField(Author, through='BookEditor', related_name='edited_books')
    publisher = models.ForeignKey(Publisher, on_delete=CASCADE)


class BookAuthor(models.Model):
    book = models.ForeignKey(Book, on_delete=CASCADE)
    author = models.ForeignKey(Author, on_delete=CASCADE)


class BookEditor(models.Model):
    book = models.ForeignKey(Book, on_delete=CASCADE)
    editor = models.ForeignKey(Author, on_delete=CASCADE)


class Catalog(models.Model):
    number = models.CharField(max_length=50)


class CatalogInfo(models.Model):
    catalog = models.ForeignKey(Catalog, on_delete=CASCADE)
    info = models.TextField()


class Package(models.Model):
    name = models.CharField(max_length=12)
    quantity = models.SmallIntegerField()
    catalog = models.ForeignKey(Catalog, on_delete=CASCADE)


class Purchase(models.Model):
    price = models.DecimalField(decimal_places=2, max_digits=10)
    pack = models.ForeignKey(Package, on_delete=CASCADE)
