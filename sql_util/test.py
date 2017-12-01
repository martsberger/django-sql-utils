from django.db.models import DateTimeField
from django.test import TestCase

# Create your tests here.
from sql_util.tests.models import Parent, Child
from sql_util.utils import SubqueryMin, SubqueryMax, SubqueryCount


class Tests(TestCase):

    @classmethod
    def setUpClass(cls):
        super(Tests, cls).setUpClass()
        parents = [
            Parent.objects.create(name='John'),
            Parent.objects.create(name='Jane')
        ]

        children = [
            Child.objects.create(parent=parents[0], name='Joe', timestamp='2017-06-01'),
            Child.objects.create(parent=parents[0], name='Jan', timestamp='2017-07-01'),
            Child.objects.create(parent=parents[0], name='Jan', timestamp='2017-05-01')
        ]

    def test_subquery_min(self):
        annotation = {
            'oldest_child_timestamp': SubqueryMin('child__timestamp', reverse='parent',
                                                  output_field=DateTimeField())
        }

        parents = Parent.objects.filter(name='John').annotate(**annotation)

        oldest_child = Child.objects.filter(parent__name='John').order_by('timestamp')[0]

        self.assertEqual(parents[0].oldest_child_timestamp, oldest_child.timestamp)

    def test_subquery_max(self):
        annotation = {
            'youngest_child_timestamp': SubqueryMax('child__timestamp', reverse='parent',
                                                    output_field=DateTimeField())
        }

        parents = Parent.objects.filter(name='John').annotate(**annotation)

        youngest_child = Child.objects.filter(parent__name='John').order_by('-timestamp')[0]

        self.assertEqual(parents[0].youngest_child_timestamp, youngest_child.timestamp)

    def test_subquery_count(self):
        annotation = {
            'child_count': SubqueryCount('child', reverse='parent')
        }

        parents = Parent.objects.annotate(**annotation)

        counts = {parent.name: parent.child_count for parent in parents}

        self.assertEqual(counts, {'John': 3, 'Jane': 0})
