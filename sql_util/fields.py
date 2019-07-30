import types


def deprecate_field(field):
    """
    This function wraps a model field so that Django will stop selecting it in ORM queries, but
    not drop the database column. E.g.,

    class MyModel(models.Model):
        name = deprecate_field(CharField(max_length=25))

    This is useful for two step deploys where in the first deploy the column is deprecated and
    in the second it is dropped.

    :param field: A Model Field that we would like to deprecate
    :return: The same Field, but changed to null=True if necessary and concrete=False so that it is not selected or written to
    """

    field.original_set_attributes_from_name = field.set_attributes_from_name

    def set_attributes_from_name(self, name):
        field.original_set_attributes_from_name(name)
        self.concrete = False

    field.set_attributes_from_name = types.MethodType(set_attributes_from_name, field)

    field.null = True

    return field
