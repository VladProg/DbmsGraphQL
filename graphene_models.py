import graphene
from decimal import Decimal
import typing

from graphql import GraphQLError


class ColorValue(graphene.ObjectType):
    r: int = graphene.Int(required=True)
    g: int = graphene.Int(required=True)
    b: int = graphene.Int(required=True)


class IntegerValue(graphene.ObjectType):
    integer: int = graphene.BigInt(required=True)


class RealValue(graphene.ObjectType):
    real: Decimal = graphene.Float(required=True)


class StringValue(graphene.ObjectType):
    string: str = graphene.String(required=True)


class Value(graphene.Union):
    class Meta:
        types = (IntegerValue, RealValue, StringValue, ColorValue)


class Type(str, graphene.Enum):
    Integer = 'Integer'
    Real = 'Real'
    Char = 'Char'
    String = 'String'
    Color = 'Color'
    ColorInvl = 'ColorInvl'


class Column(graphene.ObjectType):
    name: str = graphene.String(required=True)
    type: Type = graphene.Field(Type, required=True)
    r_min: typing.Optional[int] = graphene.Int()
    r_max: typing.Optional[int] = graphene.Int()
    g_min: typing.Optional[int] = graphene.Int()
    g_max: typing.Optional[int] = graphene.Int()
    b_min: typing.Optional[int] = graphene.Int()
    b_max: typing.Optional[int] = graphene.Int()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.check()

    def check(self):
        if self.type == Type.ColorInvl:
            if None in [self.r_min, self.r_max, self.g_min, self.g_max, self.b_min, self.b_max]:
                raise ValueError('Column: if type="ColorInvl", fields "r_min", "r_max", "g_min", "g_max", "b_min", '
                                 '"b_max" must be also provided')
            for field in 'rgb':
                if getattr(self, f'{field}_min') > getattr(self, f'{field}_max'):
                    raise ValueError(f'{field}_min must be less or equal that {field}_max')
        else:
            if not (self.r_min is self.r_max is self.g_min is self.g_max is self.b_min is self.b_max is None):
                raise ValueError(f'Column: if type="{self.type}", fields "r_min", "r_max", "g_min", "g_max", '
                                 f'"b_min", "b_max" must not be provided')
        return self

    def type_str(self) -> str:
        if self.type != Type.ColorInvl:
            return self.type
        else:
            return f'ColorInvl (R∈[{self.r_min}..{self.r_max}], G∈[{self.g_min}..{self.g_max}], B∈[{self.b_min}..{self.b_max}])'

    def check_value(self, value):
        try:
            if self.type == Type.Integer:
                assert isinstance(value, IntegerValue)
            elif self.type == Type.Real:
                assert isinstance(value, IntegerValue) or isinstance(value, RealValue)
            elif self.type == Type.Char:
                assert isinstance(value, StringValue) and len(value.string) == 1
            elif self.type == Type.String:
                assert isinstance(value, StringValue)
            elif self.type == Type.Color:
                assert isinstance(value, ColorValue)
            elif self.type == Type.ColorInvl:
                assert (isinstance(value, ColorValue) and
                        self.r_min <= value.r <= self.r_max and
                        self.g_min <= value.g <= self.g_max and
                        self.b_min <= value.b <= self.b_max)
            else:
                assert False
        except AssertionError:
            raise ValueError(f"{self.type_str()} expected but {type(value).__name__} value '{value}' found")

    def get_type(self, name: str = "") -> 'Column':
        return Column(name=name,
                      type=self.type,
                      r_min=self.r_min, r_max=self.r_max,
                      g_min=self.r_min, g_max=self.r_max,
                      b_min=self.r_min, b_max=self.r_max)


class Row(graphene.ObjectType):
    id: int = graphene.Int(required=True)
    cells: list[Value] = graphene.List(Value, required=True)


class Table(graphene.ObjectType):
    id: int = graphene.Int(required=True)
    name: str = graphene.String(required=True)
    columns: list[Column] = graphene.List(Column, required=True)
    rows: list[Row] = graphene.List(Row, required=True)
    get_row_by_id: Row = graphene.Field(Row, row_id=graphene.Int(required=True))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rows: dict[int, Row] = {}
        self._next_id: int = 0

    def add_row(self, cells: list[Value]) -> Row:
        if len(cells) != len(self.columns):
            raise ValueError("Row length must be the same as number of columns")
        for i in range(len(self.columns)):
            self.columns[i].check_value(cells[i])
        row = Row(id=self._next_id, cells=cells)
        self._rows[self._next_id] = row
        self._next_id += 1
        return row

    def remove_row(self, id):
        if id in self._rows:
            del self._rows[id]

    def contains_row(self, row) -> bool:
        return any(row.cells == value.cells for value in self._rows.values())

    def __sub__(left: 'Table', right: 'Table') -> 'TableDifference':
        if len(left.columns) != len(right.columns):
            raise ValueError("Table difference: tables have different column counts")
        if any(l.get_type() != r.get_type() for l, r in zip(left.columns, right.columns)):
            raise ValueError("Table difference: tables have different column types")
        columns = [l.get_type(l.name if l.name == r.name else f"'{l.name}' / '{r.name}'")
                   for l, r in zip(left.columns, right.columns)]
        rows = []
        for row in left._rows.values():
            if not right.contains_row(row):
                rows.append(row)
        return TableDifference(
            left_table=left,
            right_table=right,
            columns=columns,
            rows=rows
        )

    def resolve_rows(root, info):
        return root._rows.values()

    def resolve_get_row_by_id(root, info, row_id: int):
        try:
            return root._rows[row_id]
        except KeyError:
            return None


class TableDifference(graphene.ObjectType):
    left_table: Table = graphene.Field(Table, required=True)
    right_table: Table = graphene.Field(Table, required=True)
    columns: list[Column] = graphene.List(Column, required=True)
    rows: list[Row] = graphene.List(Row, required=True)


class Database(graphene.ObjectType):
    name: str = graphene.String(required=True)
    tables: list[Table] = graphene.List(Table, required=True)
    get_table_by_id: Table = graphene.Field(Table, table_id=graphene.Int(required=True))
    table_difference: TableDifference = graphene.Field(
        TableDifference,
        left_table_id=graphene.Int(required=True),
        right_table_id=graphene.Int(required=True)
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._tables: dict[int, Table] = {}
        self._next_id: int = 0

    def resolve_tables(root, info):
        return root._tables.values()

    def add_table(self, name: str, columns: list[Column]):
        table = Table(id=self._next_id, name=name, columns=columns)
        self._tables[self._next_id] = table
        self._next_id += 1
        return table

    def remove_table(self, id):
        if id in self.tables:
            del self.tables[id]

    def resolve_get_table_by_id(root, info, table_id: int):
        try:
            return root._tables[table_id]
        except KeyError:
            return None

    def resolve_table_difference(root, info, left_table_id: int, right_table_id: int):
        try:
            left_table = root._tables[left_table_id]
            right_table = root._tables[right_table_id]
        except KeyError as err:
            raise GraphQLError("Table not found")
        try:
            return left_table - right_table
        except ValueError as err:
            raise GraphQLError(str(err))
