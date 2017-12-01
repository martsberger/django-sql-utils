Django SQL Utils
================

This package provides utilities for working with Django querysets so that
you can generate the SQL that you want.

Subquery Aggregates
-------------------

The `Count` aggregation in Django::

    Parent.objects.annotate(child_count=Count('child'))

generates SQL like the following::

    SELECT parent.*, Count(child.id)
    FROM parent
    JOIN child on child.parent_id = parent.id
    GROUP BY parent.id

In some cases, this is not as performant as doing the count in a SUBQUERY
instead of a JOIN::

    SELECT parent.*
           SELECT Count(id)
           FROM child
           WHERE parent_id = parent.id
    FROM parent

Django allows us to generate this SQL using The Subquery and OuterRef classes::


    subquery = Subquery(Child.objects.filter(parent_id=OuterRef('id')).order_by()
                        .values('parent').annotate(count=Count('pk'))
                        .values('count'), output_field=IntegerField())
    Parent.objects.annotate(child_count=Coalesce(subquery, 0))

Holy cow! It's not trivial to figure what everything is doing in the above
code and it's not particularly good for maintenance. SubqueryAggregates allows
you to forget all that complexity and generate the subquery count like this:

    Parent.objects.annotate(child_count=SubqueryCount('child', reverse='parent'))

Phew! Much easier to read and understand.

In addition to `SubqueryCount`, this package provides `SubqueryMin` and
`SubqueryMax`. If you want to use other aggregates, you can use the
generic `SubqueryAggregate` class::

    from django.db.models import Avg, DecimalField

    aggregate = SubqueryAggregate('child__age', aggregate=Avg, reverse='parent',
                                   output_field=DecimalField())
    Parent.objects.annotate(avg_child_age=aggregate)

