from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from metadata import KEYWORDS, OPERATORS, SCHEMA


class SQLValidationError(Exception):
    pass


@dataclass
class JoinClause:
    table: str
    alias: str
    condition: str


@dataclass
class QueryData:
    original_sql: str
    select_columns: List[str]
    base_table: str
    base_alias: str
    joins: List[JoinClause]
    where_conditions: List[str]
    alias_to_table: Dict[str, str]


@dataclass
class OperatorNode:
    op: str
    label: str
    children: List['OperatorNode'] = field(default_factory=list)
    x: float = 0.0
    y: float = 0.0


class QueryProcessor:
    def __init__(self, schema: Dict[str, List[str]] | None = None):
        self.schema = schema or SCHEMA

    def process(self, sql: str) -> Dict[str, object]:
        normalized = self._normalize_sql(sql)
        parsed = self._parse_sql(normalized)
        self._validate_query(parsed)

        algebra = self._to_relational_algebra(parsed)
        original_graph = self._build_initial_tree(parsed)
        optimized_graph = self._build_optimized_tree(parsed)
        execution_plan = self._build_execution_plan(optimized_graph)

        return {
            'normalized_sql': normalized,
            'parsed': parsed,
            'relational_algebra': algebra,
            'original_graph': original_graph,
            'optimized_graph': optimized_graph,
            'execution_plan': execution_plan,
            'text_graph_original': self.render_text_tree(original_graph),
            'text_graph_optimized': self.render_text_tree(optimized_graph),
        }

    def _normalize_sql(self, sql: str) -> str:
        sql = sql.strip().rstrip(';')
        sql = re.sub(r'\s+', ' ', sql)
        return sql

    def _parse_sql(self, sql: str) -> QueryData:
        if not re.match(r'^select\s+', sql, flags=re.IGNORECASE):
            raise SQLValidationError('A consulta deve iniciar com SELECT.')

        lower = sql.lower()
        select_idx = lower.find('select ')
        from_idx = lower.find(' from ')
        if from_idx == -1:
            raise SQLValidationError('A consulta precisa conter FROM.')

        select_part = sql[select_idx + len('select '):from_idx].strip()
        remainder = sql[from_idx + len(' from '):].strip()
        if not select_part:
            raise SQLValidationError('Informe ao menos um atributo no SELECT.')

        where_part = ''
        where_match = re.search(r'\swhere\s', remainder, flags=re.IGNORECASE)
        if where_match:
            where_pos = where_match.start()
            from_and_joins = remainder[:where_pos].strip()
            where_part = remainder[where_match.end():].strip()
        else:
            from_and_joins = remainder

        base_section, join_sections = self._split_joins(from_and_joins)
        base_table, base_alias = self._parse_table_ref(base_section)

        joins: List[JoinClause] = []
        alias_to_table: Dict[str, str] = {base_alias: base_table}
        for section in join_sections:
            table_ref, condition = self._split_join_condition(section)
            table_name, alias = self._parse_table_ref(table_ref)
            if alias in alias_to_table:
                raise SQLValidationError(f'Alias duplicado encontrado: {alias}')
            alias_to_table[alias] = table_name
            joins.append(JoinClause(table=table_name, alias=alias, condition=condition))

        select_columns = [item.strip() for item in select_part.split(',') if item.strip()]
        if not select_columns:
            raise SQLValidationError('Não foi possível identificar os atributos do SELECT.')

        where_conditions = self._split_and_conditions(where_part) if where_part else []

        return QueryData(
            original_sql=sql,
            select_columns=select_columns,
            base_table=base_table,
            base_alias=base_alias,
            joins=joins,
            where_conditions=where_conditions,
            alias_to_table=alias_to_table,
        )

    def _split_joins(self, text: str) -> Tuple[str, List[str]]:
        parts = re.split(r'\sjoin\s', text, flags=re.IGNORECASE)
        base_section = parts[0].strip()
        join_sections = [p.strip() for p in parts[1:]]
        return base_section, join_sections

    def _split_join_condition(self, section: str) -> Tuple[str, str]:
        parts = re.split(r'\son\s', section, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) != 2:
            raise SQLValidationError('Todo JOIN precisa conter ON com condição de junção.')
        table_ref, condition = parts[0].strip(), parts[1].strip()
        if not condition:
            raise SQLValidationError('A condição do JOIN não pode ficar vazia.')
        return table_ref, condition

    def _parse_table_ref(self, text: str) -> Tuple[str, str]:
        tokens = text.split()
        if len(tokens) == 1:
            table = tokens[0]
            alias = table
        elif len(tokens) == 2:
            table, alias = tokens
        elif len(tokens) == 3 and tokens[1].lower() == 'as':
            table, _, alias = tokens
        else:
            raise SQLValidationError(f'Referência de tabela inválida: {text}')

        table_norm = table.lower()
        alias_norm = alias.lower()
        if table_norm not in self.schema:
            raise SQLValidationError(f'Tabela inexistente: {table}')
        return table_norm, alias_norm

    def _split_and_conditions(self, text: str) -> List[str]:
        if not text:
            return []
        parts = re.split(r'\sand\s', text, flags=re.IGNORECASE)
        conditions = [p.strip() for p in parts if p.strip()]
        if not conditions:
            raise SQLValidationError('A cláusula WHERE está vazia.')
        return conditions

    def _validate_query(self, query: QueryData) -> None:
        for column in query.select_columns:
            self._validate_column_reference(column, query, allow_star=True)

        for join in query.joins:
            self._validate_condition(join.condition, query)

        for condition in query.where_conditions:
            self._validate_condition(condition, query)

    def _validate_condition(self, condition: str, query: QueryData) -> None:
        operator = None
        for op in OPERATORS:
            if op in condition:
                operator = op
                break
        if operator is None:
            raise SQLValidationError(f'Condição inválida (operador não suportado): {condition}')

        left, right = [side.strip() for side in condition.split(operator, 1)]
        if not left or not right:
            raise SQLValidationError(f'Condição inválida: {condition}')

        self._validate_expression_side(left, query)
        self._validate_expression_side(right, query)

    def _validate_expression_side(self, side: str, query: QueryData) -> None:
        side = side.strip()
        side = side.strip('()')
        if self._is_literal(side):
            return
        self._validate_column_reference(side, query, allow_star=False)

    def _validate_column_reference(self, ref: str, query: QueryData, allow_star: bool = False) -> None:
        ref = ref.strip().strip('()')
        if allow_star and ref == '*':
            return

        if '.' in ref:
            alias, column = [part.strip().lower() for part in ref.split('.', 1)]
            if alias not in query.alias_to_table:
                raise SQLValidationError(f'Alias desconhecido: {alias}')
            table = query.alias_to_table[alias]
            if column not in self.schema[table]:
                raise SQLValidationError(f'Atributo inexistente: {ref}')
            return

        column = ref.lower()
        matched_tables = [table for table in query.alias_to_table.values() if column in self.schema[table]]
        if not matched_tables:
            raise SQLValidationError(f'Atributo inexistente: {ref}')
        if len(set(matched_tables)) > 1:
            raise SQLValidationError(f'Atributo ambíguo, use alias/tabela: {ref}')

    def _is_literal(self, value: str) -> bool:
        if re.match(r"^'.*'$", value):
            return True
        if re.match(r'^\d+(\.\d+)?$', value):
            return True
        return False

    def _to_relational_algebra(self, query: QueryData) -> str:
        join_text = query.base_table
        for join in query.joins:
            join_text = f'({join_text} ⋈_{{{join.condition}}} {join.table})'

        if query.where_conditions:
            predicates = ' ∧ '.join(query.where_conditions)
            join_text = f'σ_{{{predicates}}}({join_text})'

        projection = ', '.join(query.select_columns)
        return f'π_{{{projection}}}({join_text})'

    def _build_initial_tree(self, query: QueryData) -> OperatorNode:
        current = OperatorNode('TABLE', query.base_table)
        for join in query.joins:
            right = OperatorNode('TABLE', join.table)
            current = OperatorNode('JOIN', f'⋈ {join.condition}', [current, right])

        if query.where_conditions:
            current = OperatorNode('SELECT', f'σ {' AND '.join(query.where_conditions)}', [current])

        current = OperatorNode('PROJECT', f'π {", ".join(query.select_columns)}', [current])
        return current

    def _build_optimized_tree(self, query: QueryData) -> OperatorNode:
        local_filters: Dict[str, List[str]] = {alias: [] for alias in query.alias_to_table}
        cross_filters: List[str] = []

        for condition in query.where_conditions:
            aliases = self._aliases_in_expression(condition, query)
            if len(aliases) <= 1:
                alias = list(aliases)[0] if aliases else query.base_alias
                local_filters[alias].append(condition)
            else:
                cross_filters.append(condition)

        needed_columns: Dict[str, Set[str]] = {alias: set() for alias in query.alias_to_table}
        for column in query.select_columns:
            self._collect_column_usage(column, query, needed_columns)
        for condition in query.where_conditions:
            self._collect_condition_usage(condition, query, needed_columns)
        for join in query.joins:
            self._collect_condition_usage(join.condition, query, needed_columns)

        leaf_nodes: Dict[str, OperatorNode] = {}
        for alias, table in query.alias_to_table.items():
            node = OperatorNode('TABLE', f'{table} ({alias})' if alias != table else table)
            if local_filters[alias]:
                node = OperatorNode('SELECT', f'σ {' AND '.join(local_filters[alias])}', [node])
            if needed_columns[alias]:
                proj_cols = ', '.join(sorted(f'{alias}.{c}' for c in needed_columns[alias]))
                node = OperatorNode('PROJECT', f'π {proj_cols}', [node])
            leaf_nodes[alias] = node

        ordered_joins = sorted(
            query.joins,
            key=lambda j: (
                -(len(local_filters[j.alias]) + self._condition_complexity(j.condition)),
                j.table,
            ),
        )

        current_aliases = {query.base_alias}
        current = leaf_nodes[query.base_alias]
        pending = ordered_joins.copy()
        while pending:
            progressed = False
            for join in list(pending):
                aliases = self._aliases_in_expression(join.condition, query)
                if aliases & current_aliases:
                    current = OperatorNode('JOIN', f'⋈ {join.condition}', [current, leaf_nodes[join.alias]])
                    current_aliases.add(join.alias)
                    pending.remove(join)
                    progressed = True
            if not progressed:
                # fallback: connect remaining join to avoid cartesian product only if syntax provided one
                join = pending.pop(0)
                current = OperatorNode('JOIN', f'⋈ {join.condition}', [current, leaf_nodes[join.alias]])
                current_aliases.add(join.alias)

        if cross_filters:
            current = OperatorNode('SELECT', f'σ {' AND '.join(cross_filters)}', [current])

        current = OperatorNode('PROJECT', f'π {", ".join(query.select_columns)}', [current])
        return current

    def _condition_complexity(self, condition: str) -> int:
        score = 1
        for op in ('=', '<>', '<=', '>=', '>', '<'):
            if op in condition:
                score += 1
        return score

    def _aliases_in_expression(self, expression: str, query: QueryData) -> Set[str]:
        refs = re.findall(r'([A-Za-z_][\w]*)\.([A-Za-z_][\w]*)', expression)
        aliases = {alias.lower() for alias, _ in refs if alias.lower() in query.alias_to_table}
        return aliases

    def _collect_condition_usage(self, condition: str, query: QueryData, needed_columns: Dict[str, Set[str]]) -> None:
        refs = re.findall(r'([A-Za-z_][\w]*)\.([A-Za-z_][\w]*)', condition)
        for alias, column in refs:
            alias = alias.lower()
            column = column.lower()
            if alias in needed_columns:
                needed_columns[alias].add(column)

    def _collect_column_usage(self, ref: str, query: QueryData, needed_columns: Dict[str, Set[str]]) -> None:
        ref = ref.strip()
        if ref == '*':
            for alias, table in query.alias_to_table.items():
                needed_columns[alias].update(self.schema[table])
            return

        if '.' in ref:
            alias, column = [part.strip().lower() for part in ref.split('.', 1)]
            if alias in needed_columns:
                needed_columns[alias].add(column)
            return

        column = ref.lower()
        matches = []
        for alias, table in query.alias_to_table.items():
            if column in self.schema[table]:
                matches.append(alias)
        if len(matches) == 1:
            needed_columns[matches[0]].add(column)

    def _build_execution_plan(self, root: OperatorNode) -> List[str]:
        plan: List[str] = []

        def traverse(node: OperatorNode) -> None:
            for child in node.children:
                traverse(child)
            if node.op == 'TABLE':
                plan.append(f'Ler tabela {node.label}')
            elif node.op == 'SELECT':
                plan.append(f'Aplicar seleção {node.label}')
            elif node.op == 'PROJECT':
                plan.append(f'Aplicar projeção {node.label}')
            elif node.op == 'JOIN':
                plan.append(f'Executar junção {node.label}')

        traverse(root)
        return [f'{idx + 1}. {step}' for idx, step in enumerate(plan)]

    def render_text_tree(self, root: OperatorNode) -> str:
        lines: List[str] = []

        def visit(node: OperatorNode, prefix: str = '', is_last: bool = True) -> None:
            connector = '└── ' if is_last else '├── '
            lines.append(f'{prefix}{connector}{node.label}')
            next_prefix = prefix + ('    ' if is_last else '│   ')
            for idx, child in enumerate(node.children):
                visit(child, next_prefix, idx == len(node.children) - 1)

        visit(root)
        return '\n'.join(lines)


def layout_tree(root: OperatorNode) -> List[OperatorNode]:
    levels: Dict[int, List[OperatorNode]] = {}

    def assign(node: OperatorNode, depth: int, next_x: List[int]) -> None:
        for child in node.children:
            assign(child, depth + 1, next_x)
        if not node.children:
            node.x = next_x[0]
            next_x[0] += 1
        else:
            node.x = sum(child.x for child in node.children) / len(node.children)
        node.y = depth
        levels.setdefault(depth, []).append(node)

    assign(root, 0, [0])
    all_nodes: List[OperatorNode] = []
    for depth in sorted(levels):
        all_nodes.extend(levels[depth])
    return all_nodes
