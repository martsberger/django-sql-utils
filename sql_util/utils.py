from django.db.models import Q, F
from django.db.models import Subquery, OuterRef, IntegerField, Min, Max, Count
from django.db.models.constants import LOOKUP_SEP


class SubqueryAggregate(Subquery):
    aggregate = None  # Must be set by the subclass, or passed as kwarg
    unordered = None

    def __init__(self, expression, filter=Q(), aggregate=None, distinct=None, outer_ref=None, unordered=None,
                 output_field=None, **extra):
        if not hasattr(expression, 'resolve_expression'):
            expression = F(expression)
        self.expression = expression
        self.filter = filter
        self.aggregate = aggregate or self.aggregate
        self.distinct = distinct
        self.outer_ref = outer_ref
        assert self.aggregate is not None, "Error: Attempt to instantiate a " \
                                           "SubqueryAggregate with no aggregate function"
        self.unordered = unordered or self.unordered
        # Have to pass non None output_field to super
        super(SubqueryAggregate, self).__init__(None, output_field='', **extra)
        self._output_field = output_field

    def resolve_expression(self, query=None, allow_joins=True, reuse=None, summarize=False, for_save=False):
        self.queryset = self.get_queryset(query.clone(), allow_joins, reuse, summarize)
        return super(SubqueryAggregate, self).resolve_expression(query, allow_joins, reuse, summarize, for_save)

    def get_queryset(self, query, allow_joins, reuse, summarize):
        resolved_expression = self.expression.resolve_expression(query, allow_joins, reuse, summarize)
        model = self._get_model_from_resolved_expression(resolved_expression)
        queryset = model._default_manager.all()

        # resolved_expression was resolved in the outer query to get the model
        # target_expression is resolved in the subquery to get the field to aggregate
        target_expression = self._resolve_to_target(resolved_expression, queryset.query, allow_joins, reuse,
                                                    summarize)

        # Add test for output_field, distinct, and when resolved_expression.field.name isn't what we're aggregating

        if not self.output_field:
            self.output_field = target_expression.field
        if self.distinct is not None:
            aggregation = self.aggregate(target_expression, distinct=self.distinct)
        else:
            aggregation = self.aggregate(target_expression)
        annotation = {
            'aggregation': aggregation
        }

        reverse, outer_ref = self._get_reverse_outer_ref_from_expression(model, query)

        outer_ref = self.outer_ref or outer_ref
        q = self.filter & Q(**{reverse: OuterRef(outer_ref)})
        queryset = queryset.filter(q)
        if self.unordered:
            queryset = queryset.order_by()
        return queryset.values(reverse).annotate(**annotation).values('aggregation')

    def _get_model_from_resolved_expression(self, resolved_expression):
        """
        Retrieve the correct model from the resolved_expression.

        For simple expressions like F('child__field_name'), both of these are equivalent and correct:
        resolved_expression.field.model
        resolved_expression.target.model

        For many to many relations, resolved_expression.field.model goes one table deeper than
        necessary. We get more efficient SQL only going as far as we need. In this case only
        resolved_expression.target.model is correct.

        For functions of multiple columns like Coalesce, there is no resolved_expression.target,
        we have to recursively go through the source_expressions until we get to the bottom and
        get the target from there.
        """
        def get_target(res_expr):
            for expression in res_expr.get_source_expressions():
                return get_target(expression)
            return res_expr.target
        return get_target(resolved_expression).model

    def _get_fields_model_from_path(self, path, model):
        # We want the paths reversed because we have the forward join info
        # and we need the string that tells us how to go back
        paths = path[::-1]
        # import pdb; pdb.set_trace()

        fields = []
        # If the first path doesn't have join_field.field, ignore it.
        if hasattr(paths[0].join_field, 'field'):
            fields.append(paths[0].join_field.field.name)
            model = paths[0].from_opts.model

        for path in paths[1:]:
            # If the path is already for the current model, we can skip it
            if path.to_opts.model != model:
                fields.append(path.join_field.name)
                model = path.to_opts.model

        # If the last path also has join_field.field, we need the name of that too
        if hasattr(paths[-1].join_field, 'field'):
            fields.append(paths[-1].join_field.field.name)
            model = paths[-1].from_opts.model

        return fields, model

    def _get_reverse_outer_ref_from_expression(self, model, query):
        source = self.expression
        while hasattr(source, 'get_source_expressions'):
            source = source.get_source_expressions()[0]
        field_list = source.name.split(LOOKUP_SEP)
        path, _, _, _ = query.names_to_path(field_list, query.get_meta(), allow_many=True, fail_on_missing=True)

        if len(path) == 1:
            reverse = path[0].join_field.field.name
            outer_ref = 'pk'
        else:
            fields, model = self._get_fields_model_from_path(path, model)
            reverse = LOOKUP_SEP.join(fields)

            if model == query.model:
                outer_ref = 'pk'
            else:
                outer_ref = path[0].join_field.name

        return reverse, outer_ref

    def _resolve_to_target(self, resolved_expression, query, allow_joins, reuse, summarize):
        if resolved_expression.get_source_expressions():
            c = resolved_expression.copy()
            c.is_summary = summarize
            new_source_expressions = [self._resolve_to_target(source_expressions, query, allow_joins, reuse, summarize)
                                      for source_expressions in resolved_expression.get_source_expressions()]
            c.set_source_expressions(new_source_expressions)
            return c

        else:
            if hasattr(resolved_expression, 'target'):
                return F(resolved_expression.target.name).resolve_expression(query, allow_joins, reuse, summarize)
            else:
                return resolved_expression


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
