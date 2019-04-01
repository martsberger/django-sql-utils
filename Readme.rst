.. image:: https://travis-ci.org/martsberger/django-sql-utils.svg?branch=master
    :target: https://travis-ci.org/martsberger/django-sql-utils


Django SQL Utils
================

This package provides utilities for working with Django querysets so that
you can generate the SQL that you want.

Subquery Aggregates
-------------------

The `Count` aggregation in Django::

    Parent.objects.annotate(child_count=Count('child'))

generates SQL like the following::

    SELECT parent.*, Count(child.id) as child_count
    FROM parent
    JOIN child on child.parent_id = parent.id
    GROUP BY parent.id

In many cases, this is not as performant as doing the count in a SUBQUERY
instead of with a JOIN::

    SELECT parent.*,
           (SELECT Count(id)
            FROM child
            WHERE parent_id = parent.id) as child_count
    FROM parent

Django allows us to generate this SQL using The Subquery and OuterRef classes::


    subquery = Subquery(Child.objects.filter(parent_id=OuterRef('id')).order_by()
                        .values('parent').annotate(count=Count('pk'))
                        .values('count'), output_field=IntegerField())
    Parent.objects.annotate(child_count=Coalesce(subquery, 0))

Holy cow! It's not trivial to figure what everything is doing in the above
code and it's not particularly good for maintenance. SubqueryAggregates allows
you to forget all that complexity and generate the subquery count like this::

    Parent.objects.annotate(child_count=SubqueryCount('child'))

Phew! Much easier to read and understand. It's the same API as the original `Count`
just specifying the Subquery version.

In addition to `SubqueryCount`, this package provides `SubqueryMin` and
`SubqueryMax`. If you want to use other aggregates, you can use the
generic `SubqueryAggregate` class::

    from django.db.models import Avg, DecimalField

    aggregate = SubqueryAggregate('child__age', aggregate=Avg,
                                   output_field=DecimalField())
    Parent.objects.annotate(avg_child_age=aggregate)

Or subclass SubqueryAggregate::

    from django.db.models import Avg

    class SubqueryAvg(SubqueryAggregate)
        aggregate = Avg
        unordered = True

    Parent.objects.annotate(avg_child_age=SubqueryAvg('child__age')
