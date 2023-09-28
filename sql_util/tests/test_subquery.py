from django.conf import settings
from django.db.models import DateTimeField, Q
from django.db.models.functions import Coalesce, Cast
from django.test import TestCase

from sql_util.aggregates import SubqueryAvg, SubquerySum
from sql_util.tests.models import (Parent, Child, Author, Book, BookAuthor, BookEditor, Publisher, Catalog, Package,
                                   Purchase, CatalogInfo, Store, Seller, Sale, Player, Team, Game, Brand, Product)
from sql_util.utils import SubqueryMin, SubqueryMax, SubqueryCount


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
            'oldest_child_timestamp': SubqueryMin('da_child__timestamp',
                                                  output_field=DateTimeField())
        }

        parents = Parent.objects.filter(name='John').annotate(**annotation)

        oldest_child = Child.objects.filter(parent__name='John').order_by('timestamp')[0]

        self.assertEqual(parents[0].oldest_child_timestamp, oldest_child.timestamp)

    def test_subquery_max(self):
        annotation = {
            'youngest_child_timestamp': SubqueryMax('da_child__timestamp',
                                                    output_field=DateTimeField())
        }

        parents = Parent.objects.filter(name='John').annotate(**annotation)

        youngest_child = Child.objects.filter(parent__name='John').order_by('-timestamp')[0]

        self.assertEqual(parents[0].youngest_child_timestamp, youngest_child.timestamp)

    def test_subquery_count(self):
        annotation = {
            'child_count': SubqueryCount('da_child')
        }

        parents = Parent.objects.annotate(**annotation)

        counts = {parent.name: parent.child_count for parent in parents}

        self.assertEqual(counts, {'John': 3, 'Jane': 0})

    def test_subquery_count_filtered(self):
        annotation = {
            'child_count': SubqueryCount('da_child', filter=Q(name='Jan'))
        }

        parents = Parent.objects.annotate(**annotation)

        counts = {parent.name: parent.child_count for parent in parents}

        self.assertEqual(counts, {'John': 2, 'Jane': 0})

    def test_function(self):
        if settings.BACKEND == 'mysql':
            # Explicit cast for MySQL with Coalesce and Datetime
            # https://docs.djangoproject.com/en/2.1/ref/models/database-functions/#coalesce
            annotation = {
                'oldest_child_with_other': Cast(SubqueryMin(Coalesce('da_child__other_timestamp', 'da_child__timestamp'),
                                                            output_field=DateTimeField()), DateTimeField())
            }
        else:
            annotation = {
                'oldest_child_with_other': SubqueryMin(Coalesce('da_child__other_timestamp', 'da_child__timestamp'),
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


class TestForeignKey(TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestForeignKey, cls).setUpClass()
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

    def test_aggregate_foreign_key(self):
        bookauthors = BookAuthor.objects.annotate(min_publisher_id=SubqueryMin('book__publisher_id'))

        bookauthors = {bookauthor.id: bookauthor.min_publisher_id for bookauthor in bookauthors}

        publisher1_id = Publisher.objects.get(name='Publisher 1').id
        publisher2_id = Publisher.objects.get(name='Publisher 2').id

        self.assertEqual(bookauthors, {1: publisher1_id,
                                       2: publisher1_id,
                                       3: publisher1_id,
                                       4: publisher2_id,
                                       5: publisher2_id,
                                       6: publisher2_id})


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


class TestUpdate(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        store = Store.objects.create(name='A Store')

        sellers = [
            Seller.objects.create(store=store, name='Seller 1'),
            Seller.objects.create(store=store, name='Seller 2'),
        ]

        sales = [
            Sale.objects.create(seller=sellers[0], date='2020-01-01', revenue=1.1, expenses=0.2),
            Sale.objects.create(seller=sellers[0], date='2020-01-03', revenue=2.3, expenses=0.3),
            Sale.objects.create(seller=sellers[0], date='2020-01-06', revenue=1.7, expenses=0.4),
            Sale.objects.create(seller=sellers[0], date='2020-01-08', revenue=5.4, expenses=0.1),
            Sale.objects.create(seller=sellers[1], date='2020-01-08', revenue=1.4, expenses=0.6),
            Sale.objects.create(seller=sellers[1], date='2020-01-08', revenue=2.4, expenses=0.5),
        ]

    def test_update_count(self):
        Seller.objects.update(total_sales=SubqueryCount('sale'))

        sellers = list(Seller.objects.values('name', 'total_sales').order_by('name'))

        self.assertEqual(sellers,
                         [{'name': 'Seller 1', 'total_sales': 4},
                          {'name': 'Seller 2', 'total_sales': 2}
                          ])

    def test_update_avg(self):
        Seller.objects.update(average_revenue=Coalesce(SubqueryAvg('sale__revenue'), 0.0))

        sellers = list(Seller.objects.values('name', 'average_revenue').order_by('name'))

        self.assertEqual(sellers,
                         [{'name': 'Seller 1', 'average_revenue': 2.625},
                          {'name': 'Seller 2', 'average_revenue': 1.9}
                          ])

class TestForeignKeyToField(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestForeignKeyToField, cls).setUpClass()
        brand = Brand.objects.create(name='Python', company_id=1337)
        products = [
            Product.objects.create(brand=brand, num_purchases=1),
            Product.objects.create(brand=brand, num_purchases=3)
        ]

    def test_foreign_key_to_field(self):
        brands = Brand.objects.annotate(
            purchase_sum=SubquerySum('products__num_purchases')
        )
        self.assertEqual(brands.first().purchase_sum, 4)


class TestMultipleForeignKeyToTheSameModel(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestMultipleForeignKeyToTheSameModel, cls).setUpClass()

        player1 = Player.objects.create(nickname='Player 1')
        player2 = Player.objects.create(nickname='Player 2')
        player3 = Player.objects.create(nickname='Player 3')
        player4 = Player.objects.create(nickname='Player 4')
        player5 = Player.objects.create(nickname='Player 5')
        player6 = Player.objects.create(nickname='Player 6')

        team1 = Team.objects.create(name='Team 1')
        team2 = Team.objects.create(name='Team 2')
        team3 = Team.objects.create(name='Team 3')

        team1.players.add(player1, player2, player3)
        team2.players.add(player4, player5)
        team3.players.add(player6)

        game1 = Game.objects.create(team1=team1, team2=team2, played='2021-02-10')
        game2 = Game.objects.create(team1=team1, team2=team3, played='2021-02-13')
        game3 = Game.objects.create(team1=team1, team2=team2, played='2021-02-16')
        game4 = Game.objects.create(team1=team2, team2=team3, played='2021-02-19')
        game5 = Game.objects.create(team1=team2, team2=team3, played='2021-02-22')

    def test_player_count(self):
        team1_count_subquery_count = SubqueryCount('team1__players')
        team2_count_subquery_count = SubqueryCount('team2__players')

        games = Game.objects.annotate(team1_count=team1_count_subquery_count,
                                      team2_count=team2_count_subquery_count)

        for g in games:
            self.assertEqual(g.team1_count, g.team1.players.count())
            self.assertEqual(g.team2_count, g.team2.players.count())
