import sqlparse


def pretty_print_sql(queryset, **options):
    print(sqlparse.format(str(queryset.query), reindent=True, indent_width=4, **options))
