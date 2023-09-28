from django.db.models import Q, OuterRef
from django.test import TestCase

from sql_util.tests.models import (Parent, Child, Author, Book, BookAuthor, BookEditor, Publisher,
                                   Category, Collection, Item, ItemCollectionM2M, Bit, Dog, Cat,
                                   Owner)
from sql_util.utils import Exists

class TestExists(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestExists, cls).setUpClass()

        parents = [
            Parent.objects.create(name='John'),
            Parent.objects.create(name='Jane')
        ]

        children = [
            Child.objects.create(parent=parents[0], name='Joe', timestamp='2017-06-01', other_timestamp=None),
            Child.objects.create(parent=parents[0], name='Jan', timestamp='2017-07-01', other_timestamp=None),
            Child.objects.create(parent=parents[0], name='Jan', timestamp='2017-05-01', other_timestamp='2017-08-01')
        ]

    def test_original_exists(self):
        ps = Parent.objects.annotate(has_children=Exists(Child.objects.filter(parent=OuterRef('pk')))).order_by('pk')
        ps = list(ps)

        self.assertEqual(ps[0].has_children, True)
        self.assertEqual(ps[1].has_children, False)

    def test_easy_exists(self):
        ps = Parent.objects.annotate(has_children=Exists('da_child')).order_by('pk')
        ps = list(ps)

        self.assertEqual(ps[0].has_children, True)
        self.assertEqual(ps[1].has_children, False)

    def test_negated_exists(self):
        ps = Parent.objects.annotate(has_children=~Exists(Child.objects.filter(parent=OuterRef('pk')))).order_by('pk')
        ps = list(ps)

        self.assertEqual(ps[0].has_children, False)
        self.assertEqual(ps[1].has_children, True)

    def test_easy_negated_exists(self):
        ps = Parent.objects.annotate(has_children=~Exists('da_child')).order_by('pk')
        ps = list(ps)

        self.assertEqual(ps[0].has_children, False)
        self.assertEqual(ps[1].has_children, True)


class TestExistsFilter(TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestExistsFilter, cls).setUpClass()
        publishers = [
            Publisher.objects.create(name='Publisher 1', number=1),
            Publisher.objects.create(name='Publisher 2', number=2)
        ]

        authors = [
            Author.objects.create(name='Author 1'),
            Author.objects.create(name='Author 2'),
            Author.objects.create(name='Author 3'),
            Author.objects.create(name='Author 4'),
            Author.objects.create(name='Author 5'),
        ]

        books = [
            Book.objects.create(title='Book 1', publisher=publishers[0]),
            Book.objects.create(title='Book 2', publisher=publishers[0]),
            Book.objects.create(title='Book 3', publisher=publishers[1]),
            Book.objects.create(title='Book 4', publisher=publishers[1]),
        ]

        book_authors = [
            BookAuthor.objects.create(author=authors[0], book=books[0], id=1),
            BookAuthor.objects.create(author=authors[1], book=books[1], id=2),
            BookAuthor.objects.create(author=authors[2], book=books[1], id=3),
            BookAuthor.objects.create(author=authors[2], book=books[2], id=4),
        ]

        book_editors = [
            BookEditor.objects.create(editor=authors[4], book=books[3]),
        ]

    def test_filter_on_exists(self):
        exists = Exists('authored_books')
        authors = Author.objects.filter(exists)

        self.assertEqual({author.id for author in authors},
                         {1, 2, 3})

    def test_filter_on_negated_exists(self):
        exists = ~Exists('authored_books')
        authors = Author.objects.filter(exists)

        self.assertEqual({author.id for author in authors},
                         {4, 5})

    def test_filter_exists_with_or(self):
        exists = Exists('authored_books') | Exists('edited_books')
        authors = Author.objects.filter(exists)

        self.assertEqual({author.id for author in authors},
                         {1, 2, 3, 5})


class TestManyToManyExists(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestManyToManyExists, cls).setUpClass()
        publishers = [
            Publisher.objects.create(name='Publisher 1', number=1),
            Publisher.objects.create(name='Publisher 2', number=2)
        ]

        authors = [
            Author.objects.create(name='Author 1'),
            Author.objects.create(name='Author 2'),
            Author.objects.create(name='Author 3'),
            Author.objects.create(name='Author 4'),
            Author.objects.create(name='Author 5'),
            Author.objects.create(name='Author 6')
        ]

        books = [
            Book.objects.create(title='Book 1', publisher=publishers[0]),
            Book.objects.create(title='Book 2', publisher=publishers[0]),
            Book.objects.create(title='Book 3', publisher=publishers[1]),
            Book.objects.create(title='Book 4', publisher=publishers[1])
        ]

        book_authors = [
            BookAuthor.objects.create(author=authors[0], book=books[0], id=1),
            BookAuthor.objects.create(author=authors[1], book=books[1], id=2),
            BookAuthor.objects.create(author=authors[2], book=books[1], id=3),
            BookAuthor.objects.create(author=authors[2], book=books[2], id=4),
            BookAuthor.objects.create(author=authors[3], book=books[2], id=5),
            BookAuthor.objects.create(author=authors[4], book=books[3], id=6),
        ]

        book_editors = [
            BookEditor.objects.create(editor=authors[5], book=books[3]),
            BookEditor.objects.create(editor=authors[5], book=books[3]),
        ]

    def test_forward(self):
        books = Book.objects.annotate(has_authors=Exists('authors')).order_by('id')
        for book in books:
            self.assertTrue(book.has_authors)

        # Only book 4 has editors
        books = Book.objects.annotate(has_editors=Exists('editors')).order_by('id')
        editors = {book.title: book.has_editors for book in books}

        self.assertEqual(editors, {'Book 1': False,
                                   'Book 2': False,
                                   'Book 3': False,
                                   'Book 4': True})

    def test_reverse(self):
        authors = Author.objects.annotate(has_books=Exists('authored_books')).order_by('id')
        books = {author.name: author.has_books for author in authors}

        self.assertEqual(books, {'Author 1': True,
                                 'Author 2': True,
                                 'Author 3': True,
                                 'Author 4': True,
                                 'Author 5': True,
                                 'Author 6': False})

    def test_two_joins(self):
        authors = Author.objects.annotate(has_editors=Exists('authored_books__editors')).order_by('id')

        # Only author 5 has written a book with editors

        editors = {author.name: author.has_editors for author in authors}

        self.assertEqual(editors, {'Author 1': False,
                                   'Author 2': False,
                                   'Author 3': False,
                                   'Author 4': False,
                                   'Author 5': True,
                                   'Author 6': False})

    def test_filter(self):
        publisher_id = Publisher.objects.get(name='Publisher 1').id
        authors = Author.objects.annotate(published_by_1=Exists('authored_books', filter=Q(book__publisher_id=publisher_id)))

        authors = {author.name: author.published_by_1 for author in authors}

        self.assertEqual(authors, {'Author 1': True,
                                   'Author 2': True,
                                   'Author 3': True,
                                   'Author 4': False,
                                   'Author 5': False,
                                   'Author 6': False})

    def test_filter_last_join(self):
        publisher_id = Publisher.objects.get(name='Publisher 1').id
        authors = Author.objects.annotate(
            published_by_1=Exists('authored_books__publisher', filter=Q(id=publisher_id)))

        authors = {author.name: author.published_by_1 for author in authors}

        self.assertEqual(authors, {'Author 1': True,
                                   'Author 2': True,
                                   'Author 3': True,
                                   'Author 4': False,
                                   'Author 5': False,
                                   'Author 6': False})


class TestExistsReverseNames(TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestExistsReverseNames, cls).setUpClass()
        categories = [
            Category.objects.create(name='cat one'),
            Category.objects.create(name='cat two'),
            Category.objects.create(name='cat three'),
        ]

        collections = [
            Collection.objects.create(name='coll one', the_category=categories[0]),
            Collection.objects.create(name='coll two', the_category=categories[0]),
            Collection.objects.create(name='coll three', the_category=categories[1]),
            Collection.objects.create(name='coll four', the_category=categories[1]),
            Collection.objects.create(name='coll five', the_category=categories[2]),
        ]

        items = [
            Item.objects.create(name='item one'),
            Item.objects.create(name='item two'),
            Item.objects.create(name='item three'),
            Item.objects.create(name='item four'),
            Item.objects.create(name='item five'),
            Item.objects.create(name='item six'),
        ]

        m2ms = [
            ItemCollectionM2M.objects.create(thing=items[0], collection_key=collections[0]),
            ItemCollectionM2M.objects.create(thing=items[1], collection_key=collections[1])
        ]

        bits = [
            Bit.objects.create(name="bit one")
        ]

        collections[0].bits.add(bits[0])

    def test_name_doesnt_match(self):
        annotation = {
            'has_category': Exists('collection_key__the_category')
        }

        items = Item.objects.annotate(**annotation)

        items = {item.name: item.has_category for item in items}

        self.assertEqual(items, {'item one': True,
                                 'item two': True,
                                 'item three': False,
                                 'item four': False,
                                 'item five': False,
                                 'item six': False,
                                 })

    def test_name_doesnt_match_m2m(self):
        annotation = {
            'has_bits': Exists('collection_key__bits')
        }

        items = Item.objects.annotate(**annotation)

        items = {item.name: item.has_bits for item in items}

        self.assertEqual(items, {'item one': True,
                                 'item two': False,
                                 'item three': False,
                                 'item four': False,
                                 'item five': False,
                                 'item six': False,
                                 })


class TestGenericForeignKey(TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestGenericForeignKey, cls).setUpClass()
        dogs = [
            Dog.objects.create(name="Fido"),
            Dog.objects.create(name="Snoopy"),
            Dog.objects.create(name="Otis")
        ]

        cats = [
            Cat.objects.create(name="Muffin"),
            Cat.objects.create(name="Grumpy"),
            Cat.objects.create(name="Garfield")
        ]

        owners = [
            Owner.objects.create(name="Jon", pet=cats[2])
        ]

    def test_exists(self):
        annotation = {'has_an_owner': Exists('owner')}

        cats = Cat.objects.annotate(**annotation)

        cats = {cat.name: cat.has_an_owner for cat in cats}

        self.assertEqual(cats, {'Muffin': False,
                                'Grumpy': False,
                                'Garfield': True})
