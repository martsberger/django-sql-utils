from django.conf import settings
from django.db.models import DateTimeField, Q, OuterRef
from django.db.models.functions import Coalesce, Cast
from django.test import TestCase

from sql_util.tests.models import (Parent, Child, Author, Book, BookAuthor, BookEditor, Publisher, Catalog, Package,
                                   Purchase, CatalogInfo)
from sql_util.utils import SubqueryMin, SubqueryMax, SubqueryCount, Exists


class TestParentChild(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestParentChild, cls).setUpClass()
        parents = [
            Parent.objects.create(name='John'),
            Parent.objects.create(name='Jane')
        ]

        children = [
            Child.objects.create(parent=parents[0], name='Joe', timestamp='2017-06-01', other_timestamp=None),
            Child.objects.create(parent=parents[0], name='Jan', timestamp='2017-07-01', other_timestamp=None),
            Child.objects.create(parent=parents[0], name='Jan', timestamp='2017-05-01', other_timestamp='2017-08-01')
        ]

    def test_subquery_min(self):
        annotation = {
            'oldest_child_timestamp': SubqueryMin('child__timestamp',
                                                  output_field=DateTimeField())
        }

        parents = Parent.objects.filter(name='John').annotate(**annotation)

        oldest_child = Child.objects.filter(parent__name='John').order_by('timestamp')[0]

        self.assertEqual(parents[0].oldest_child_timestamp, oldest_child.timestamp)

    def test_subquery_max(self):
        annotation = {
            'youngest_child_timestamp': SubqueryMax('child__timestamp',
                                                    output_field=DateTimeField())
        }

        parents = Parent.objects.filter(name='John').annotate(**annotation)

        youngest_child = Child.objects.filter(parent__name='John').order_by('-timestamp')[0]

        self.assertEqual(parents[0].youngest_child_timestamp, youngest_child.timestamp)

    def test_subquery_count(self):
        annotation = {
            'child_count': SubqueryCount('child')
        }

        parents = Parent.objects.annotate(**annotation)

        counts = {parent.name: parent.child_count for parent in parents}

        self.assertEqual(counts, {'John': 3, 'Jane': 0})

    def test_subquery_count_filtered(self):
        annotation = {
            'child_count': SubqueryCount('child', filter=Q(name='Jan'))
        }

        parents = Parent.objects.annotate(**annotation)

        counts = {parent.name: parent.child_count for parent in parents}

        self.assertEqual(counts, {'John': 2, 'Jane': 0})

    def test_function(self):
        if settings.BACKEND == 'mysql':
            # Explicit cast for MySQL with Coalesce and Datetime
            # https://docs.djangoproject.com/en/2.1/ref/models/database-functions/#coalesce
            annotation = {
                'oldest_child_with_other': Cast(SubqueryMin(Coalesce('child__other_timestamp', 'child__timestamp'),
                                                            output_field=DateTimeField()), DateTimeField())
            }
        else:
            annotation = {
                'oldest_child_with_other': SubqueryMin(Coalesce('child__other_timestamp', 'child__timestamp'),
                                                       output_field=DateTimeField())
            }

        parents = Parent.objects.filter(name='John').annotate(**annotation)

        oldest_child = Child.objects.filter(parent__name='John').order_by(Coalesce('other_timestamp', 'timestamp').asc())[0]

        self.assertEqual(parents[0].oldest_child_with_other, oldest_child.other_timestamp or oldest_child.timestamp)


class TestManyToMany(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestManyToMany, cls).setUpClass()
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

    def test_subquery_count_forward(self):
        annotation = {
            'author_count': SubqueryCount('authors')
        }
        books = Book.objects.annotate(**annotation).order_by('id')

        counts = {book.title: book.author_count for book in books}
        self.assertEqual(counts, {'Book 1': 1, 'Book 2': 2, 'Book 3': 2, 'Book 4': 1})

    def test_subquery_count_reverse(self):
        annotation = {
            'book_count': SubqueryCount('authored_books')
        }
        authors = Author.objects.annotate(**annotation).order_by('id')

        counts = {author.name: author.book_count for author in authors}
        self.assertEqual(counts, {'Author 1': 1,
                                  'Author 2': 1,
                                  'Author 3': 2,
                                  'Author 4': 1,
                                  'Author 5': 1,
                                  'Author 6': 0})

    def test_subquery_count_reverse_explicit(self):
        # The two queries are the same, one just passes a long version of joining from author to books,
        # this test verifies that the automatic reverse of the joins handles both cases.
        # The annotation is a bit non-sensical, taking the Max over titles, but that isn't the point
        annotation = {
            'max_book_title': SubqueryMax('bookauthor__book__title')
        }
        authors = Author.objects.annotate(**annotation).order_by('id')

        titles = {author.name: author.max_book_title for author in authors}
        self.assertEqual(titles, {'Author 1': 'Book 1',
                                  'Author 2': 'Book 2',
                                  'Author 3': 'Book 3',
                                  'Author 4': 'Book 3',
                                  'Author 5': 'Book 4',
                                  'Author 6': None})

        annotation = {
            'max_book_title': SubqueryMax('authored_books__title')
        }
        authors = Author.objects.annotate(**annotation).order_by('id')

        titles = {author.name: author.max_book_title for author in authors}
        self.assertEqual(titles, {'Author 1': 'Book 1',
                                  'Author 2': 'Book 2',
                                  'Author 3': 'Book 3',
                                  'Author 4': 'Book 3',
                                  'Author 5': 'Book 4',
                                  'Author 6': None})

    def test_subquery_min_through_m2m_and_foreign_key(self):

        annotation = {
            'max_publisher_number': SubqueryMax('authored_books__publisher__number')
        }
        authors = Author.objects.annotate(**annotation)

        numbers = {author.name: author.max_publisher_number for author in authors}
        self.assertEqual(numbers, {'Author 1': 1,
                                   'Author 2': 1,
                                   'Author 3': 2,
                                   'Author 4': 2,
                                   'Author 5': 2,
                                   'Author 6': None})

    def test_self_join(self):
        annotation = {
            'book_author_count': SubqueryCount('book__bookauthor')
        }

        book_authors = BookAuthor.objects.annotate(**annotation)

        counts = {ba.id: ba.book_author_count for ba in book_authors}

        self.assertEqual(counts, {1: 1,
                                  2: 2,
                                  3: 2,
                                  4: 2,
                                  5: 2,
                                  6: 1})


class TestReverseForeignKey(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestReverseForeignKey, cls).setUpClass()
        catalogs = [
            Catalog.objects.create(number='A'),
            Catalog.objects.create(number='B')
        ]

        infos = [
            CatalogInfo.objects.create(catalog=catalogs[0], info='cat A info', id=3),
            CatalogInfo.objects.create(catalog=catalogs[1], info='cat B info', id=4)
        ]

        packages = [
            Package.objects.create(name='Box', quantity=10, catalog=catalogs[0]),
            Package.objects.create(name='Case', quantity=24, catalog=catalogs[1]),
        ]

        purchases = [
            Purchase.objects.create(price=5, pack=packages[0]),
            Purchase.objects.create(price=6, pack=packages[0]),
            Purchase.objects.create(price=4, pack=packages[0]),
            Purchase.objects.create(price=11, pack=packages[1]),
            Purchase.objects.create(price=12, pack=packages[1]),
        ]

    def test_reverse_foreign_key(self):
        annotations = {
            'max_price': SubqueryMax('package__purchase__price'),
            'min_price': SubqueryMin('package__purchase__price')
        }
        catalogs = Catalog.objects.annotate(**annotations)

        prices = {catalog.number: (catalog.max_price, catalog.min_price) for catalog in catalogs}

        self.assertEqual(prices, {'A': (6, 4),
                                  'B': (12, 11)})

    def test_forward_and_reverse_foreign_keys(self):
        annotations = {
            'max_price': SubqueryMax('catalog__package__purchase__price'),
            'min_price': SubqueryMin('catalog__package__purchase__price')
        }

        catalog_infos = CatalogInfo.objects.annotate(**annotations)

        extremes = {info.info: (info.max_price, info.min_price) for info in catalog_infos}

        self.assertEqual(extremes, {'cat A info': (6, 4),
                                    'cat B info': (12, 11)})


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
        ps = Parent.objects.annotate(has_children=Exists('child')).order_by('pk')
        ps = list(ps)

        self.assertEqual(ps[0].has_children, True)
        self.assertEqual(ps[1].has_children, False)

    def test_negated_exists(self):
        ps = Parent.objects.annotate(has_children=~Exists(Child.objects.filter(parent=OuterRef('pk')))).order_by('pk')
        ps = list(ps)

        self.assertEqual(ps[0].has_children, False)
        self.assertEqual(ps[1].has_children, True)

    def test_easy_negated_exists(self):
        ps = Parent.objects.annotate(has_children=~Exists('child')).order_by('pk')
        ps = list(ps)

        self.assertEqual(ps[0].has_children, False)
        self.assertEqual(ps[1].has_children, True)


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
