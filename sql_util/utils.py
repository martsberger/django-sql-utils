from django.db.models import Q, F
from django.db.models import Subquery, OuterRef, IntegerField, Min, Max, Count


class SubqueryAggregate(Subquery):
    aggregate = None  # Must be set by the subclass, or passed as kwarg
    unordered = None

    def __init__(self, expression, reverse, *args, **kwargs):
        if not hasattr(expression, 'resolve_expression'):
            expression = F(expression)
        self.expression = expression
        self.reverse = reverse
        self.filter = kwargs.pop('filter', Q())
        self.aggregate = kwargs.pop('aggregate', self.aggregate)
        assert self.aggregate is not None, "Error: Attempt to instantiate a " \
                                           "SubqueryAggregate with no aggregate function"
        self.unordered = kwargs.pop('unordered', self.unordered)
        super(SubqueryAggregate, self).__init__(None, *args, **kwargs)

    def resolve_expression(self, query=None, allow_joins=True, reuse=None, summarize=False, for_save=False):
        self.queryset = self.get_queryset(query.clone(), allow_joins, reuse, summarize)
        return super(SubqueryAggregate, self).resolve_expression(query, allow_joins, reuse, summarize, for_save)

    def get_queryset(self, query, allow_joins, reuse, summarize):
        resolved_expression = self.expression.resolve_expression(query, allow_joins, reuse, summarize)
        annotation = {
            'aggregation': self.aggregate(resolved_expression.field.name)
        }
        model = resolved_expression.field.model

        q = self.filter & Q(**{self.reverse: OuterRef('pk')})
        queryset = model._default_manager.filter(q)
        if self.unordered:
            queryset = queryset.order_by()
        return queryset.values(self.reverse).annotate(**annotation).values('aggregation')


class SubqueryCount(SubqueryAggregate):
    template = 'COALESCE((%(subquery)s), 0)'
    aggregate = Count
    unordered = True

    def __init__(self, expression, reverse='', *args, **kwargs):
        kwargs['output_field'] = kwargs.get('output_field', IntegerField())
        super(SubqueryCount, self).__init__(expression, reverse=reverse, *args, **kwargs)


class SubqueryMin(SubqueryAggregate):
    aggregate = Min
    unordered = True


class SubqueryMax(SubqueryAggregate):
    aggregate = Max
    unordered = True
