from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

# Importa constantes externas: palavras-chave SQL, operadores suportados e o schema do banco
from metadata import KEYWORDS, OPERATORS, SCHEMA


# Exceção customizada lançada quando a query SQL é inválida
class SQLValidationError(Exception):
    pass


# Representa uma cláusula JOIN: tabela, seu alias e a condição ON
@dataclass
class JoinClause:
    table: str
    alias: str
    condition: str


# Armazena todos os dados estruturados extraídos da query SQL após o parsing
@dataclass
class QueryData:
    original_sql: str
    select_columns: List[str]       # Colunas do SELECT
    base_table: str                  # Tabela principal do FROM
    base_alias: str                  # Alias da tabela principal
    joins: List[JoinClause]          # Lista de JOINs encontrados
    where_conditions: List[str]      # Condições do WHERE separadas por AND
    alias_to_table: Dict[str, str]   # Mapeamento alias → nome real da tabela


# Nó da árvore de operadores relacionais (SELECT, PROJECT, JOIN, TABLE)
@dataclass
class OperatorNode:
    op: str                                          # Tipo do operador
    label: str                                       # Rótulo exibido na árvore
    children: List['OperatorNode'] = field(default_factory=list)
    x: float = 0.0   # Posição horizontal (usada no layout visual)
    y: float = 0.0   # Profundidade na árvore (nível)


# ─────────────────────────────────────────────
# Classe principal: orquestra todo o pipeline
# ─────────────────────────────────────────────
class QueryProcessor:
    def __init__(self, schema: Dict[str, List[str]] | None = None):
        # Usa o schema importado por padrão, mas permite injetar um customizado
        self.schema = schema or SCHEMA

    # Ponto de entrada: recebe SQL bruto e retorna todos os artefatos gerados
    def process(self, sql: str) -> Dict[str, object]:
        normalized = self._normalize_sql(sql)       # 1. Normaliza espaços e remove ';'
        parsed = self._parse_sql(normalized)         # 2. Faz o parsing estrutural da query
        self._validate_query(parsed)                 # 3. Valida tabelas, colunas e condições

        algebra = self._to_relational_algebra(parsed)          # 4. Gera álgebra relacional textual
        original_graph = self._build_initial_tree(parsed)      # 5. Árvore sem otimizações
        optimized_graph = self._build_optimized_tree(parsed)   # 6. Árvore com pushdown de seleções/projeções
        execution_plan = self._build_execution_plan(optimized_graph)  # 7. Plano de execução passo a passo

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

    # ── NORMALIZAÇÃO ──────────────────────────────────────────────────────────

    def _normalize_sql(self, sql: str) -> str:
        sql = sql.strip().rstrip(';')        # Remove espaços externos e ponto-e-vírgula final
        sql = re.sub(r'\s+', ' ', sql)       # Colapsa múltiplos espaços em um único
        return sql

    # ── PARSING ───────────────────────────────────────────────────────────────

    def _parse_sql(self, sql: str) -> QueryData:
        # Garante que a query começa com SELECT
        if not re.match(r'^select\s+', sql, flags=re.IGNORECASE):
            raise SQLValidationError('A consulta deve iniciar com SELECT.')

        lower = sql.lower()
        select_idx = lower.find('select ')
        from_idx = lower.find(' from ')
        if from_idx == -1:
            raise SQLValidationError('A consulta precisa conter FROM.')

        # Extrai a lista de colunas entre SELECT e FROM
        select_part = sql[select_idx + len('select '):from_idx].strip()
        remainder = sql[from_idx + len(' from '):].strip()
        if not select_part:
            raise SQLValidationError('Informe ao menos um atributo no SELECT.')

        # Separa a parte do WHERE (se existir) do restante (FROM + JOINs)
        where_part = ''
        where_match = re.search(r'\swhere\s', remainder, flags=re.IGNORECASE)
        if where_match:
            where_pos = where_match.start()
            from_and_joins = remainder[:where_pos].strip()
            where_part = remainder[where_match.end():].strip()
        else:
            from_and_joins = remainder

        # Separa a tabela base das cláusulas JOIN
        base_section, join_sections = self._split_joins(from_and_joins)
        base_table, base_alias = self._parse_table_ref(base_section)

        # Processa cada JOIN, extraindo tabela, alias e condição ON
        joins: List[JoinClause] = []
        alias_to_table: Dict[str, str] = {base_alias: base_table}
        for section in join_sections:
            table_ref, condition = self._split_join_condition(section)
            table_name, alias = self._parse_table_ref(table_ref)
            if alias in alias_to_table:
                raise SQLValidationError(f'Alias duplicado encontrado: {alias}')
            alias_to_table[alias] = table_name
            joins.append(JoinClause(table=table_name, alias=alias, condition=condition))

        # Divide as colunas do SELECT por vírgula
        select_columns = [item.strip() for item in select_part.split(',') if item.strip()]
        if not select_columns:
            raise SQLValidationError('Não foi possível identificar os atributos do SELECT.')

        # Divide condições do WHERE por AND
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

    # Divide o trecho FROM/JOINs usando a palavra-chave JOIN como delimitador
    def _split_joins(self, text: str) -> Tuple[str, List[str]]:
        parts = re.split(r'\sjoin\s', text, flags=re.IGNORECASE)
        base_section = parts[0].strip()
        join_sections = [p.strip() for p in parts[1:]]
        return base_section, join_sections

    # Separa "tabela ON condição" em duas partes
    def _split_join_condition(self, section: str) -> Tuple[str, str]:
        parts = re.split(r'\son\s', section, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) != 2:
            raise SQLValidationError('Todo JOIN precisa conter ON com condição de junção.')
        table_ref, condition = parts[0].strip(), parts[1].strip()
        if not condition:
            raise SQLValidationError('A condição do JOIN não pode ficar vazia.')
        return table_ref, condition

    # Interpreta "tabela alias" ou "tabela AS alias" ou só "tabela"
    def _parse_table_ref(self, text: str) -> Tuple[str, str]:
        tokens = text.split()
        if len(tokens) == 1:
            table = tokens[0]
            alias = table           # Sem alias: usa o próprio nome da tabela
        elif len(tokens) == 2:
            table, alias = tokens
        elif len(tokens) == 3 and tokens[1].lower() == 'as':
            table, _, alias = tokens
        else:
            raise SQLValidationError(f'Referência de tabela inválida: {text}')

        table_norm = table.lower()
        alias_norm = alias.lower()
        # Verifica se a tabela existe no schema
        if table_norm not in self.schema:
            raise SQLValidationError(f'Tabela inexistente: {table}')
        return table_norm, alias_norm

    # Quebra condições do WHERE no operador AND
    def _split_and_conditions(self, text: str) -> List[str]:
        if not text:
            return []
        parts = re.split(r'\sand\s', text, flags=re.IGNORECASE)
        conditions = [p.strip() for p in parts if p.strip()]
        if not conditions:
            raise SQLValidationError('A cláusula WHERE está vazia.')
        return conditions

    # ── VALIDAÇÃO ─────────────────────────────────────────────────────────────

    # Valida colunas do SELECT, condições dos JOINs e do WHERE
    def _validate_query(self, query: QueryData) -> None:
        for column in query.select_columns:
            self._validate_column_reference(column, query, allow_star=True)

        for join in query.joins:
            self._validate_condition(join.condition, query)

        for condition in query.where_conditions:
            self._validate_condition(condition, query)

    # Valida que uma condição contém operador suportado e lados válidos
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

    # Valida um lado de uma expressão: literal ou referência de coluna
    def _validate_expression_side(self, side: str, query: QueryData) -> None:
        side = side.strip()
        side = side.strip('()')
        if self._is_literal(side):
            return   # Literais (strings e números) são sempre válidos
        self._validate_column_reference(side, query, allow_star=False)

    # Verifica se alias e coluna existem no schema; detecta ambiguidade sem alias
    def _validate_column_reference(self, ref: str, query: QueryData, allow_star: bool = False) -> None:
        ref = ref.strip().strip('()')
        if allow_star and ref == '*':
            return

        if '.' in ref:
            # Referência qualificada: alias.coluna
            alias, column = [part.strip().lower() for part in ref.split('.', 1)]
            if alias not in query.alias_to_table:
                raise SQLValidationError(f'Alias desconhecido: {alias}')
            table = query.alias_to_table[alias]
            if column not in self.schema[table]:
                raise SQLValidationError(f'Atributo inexistente: {ref}')
            return

        # Referência sem alias: busca em todas as tabelas e verifica ambiguidade
        column = ref.lower()
        matched_tables = [table for table in query.alias_to_table.values() if column in self.schema[table]]
        if not matched_tables:
            raise SQLValidationError(f'Atributo inexistente: {ref}')
        if len(set(matched_tables)) > 1:
            raise SQLValidationError(f'Atributo ambíguo, use alias/tabela: {ref}')

    # Retorna True para strings entre aspas simples ou números (inteiros/decimais)
    def _is_literal(self, value: str) -> bool:
        if re.match(r"^'.*'$", value):
            return True
        if re.match(r'^\d+(\.\d+)?$', value):
            return True
        return False

    # ── ÁLGEBRA RELACIONAL ────────────────────────────────────────────────────

    # Gera a expressão textual em notação de álgebra relacional
    def _to_relational_algebra(self, query: QueryData) -> str:
        # Monta os JOINs de fora para dentro (esquerda para direita)
        join_text = query.base_table
        for join in query.joins:
            join_text = f'({join_text} ⋈_{{{join.condition}}} {join.table})'

        # Envolve com σ (seleção) se houver WHERE
        if query.where_conditions:
            predicates = ' ∧ '.join(query.where_conditions)
            join_text = f'σ_{{{predicates}}}({join_text})'

        # Envolve com π (projeção) para as colunas do SELECT
        projection = ', '.join(query.select_columns)
        return f'π_{{{projection}}}({join_text})'

    # ── ÁRVORES DE OPERADORES ─────────────────────────────────────────────────

    # Árvore inicial (sem otimização): PROJECT → SELECT → JOINs → TABLEs
    def _build_initial_tree(self, query: QueryData) -> OperatorNode:
        current = OperatorNode('TABLE', query.base_table)
        for join in query.joins:
            right = OperatorNode('TABLE', join.table)
            current = OperatorNode('JOIN', f'⋈ {join.condition}', [current, right])

        if query.where_conditions:
            current = OperatorNode('SELECT', f'σ {' AND '.join(query.where_conditions)}', [current])

        current = OperatorNode('PROJECT', f'π {", ".join(query.select_columns)}', [current])
        return current

    # Árvore otimizada: aplica pushdown de seleções e projeções para cada tabela
    def _build_optimized_tree(self, query: QueryData) -> OperatorNode:
        # Classifica cada condição WHERE: local (uma tabela) ou cruzada (várias tabelas)
        local_filters: Dict[str, List[str]] = {alias: [] for alias in query.alias_to_table}
        cross_filters: List[str] = []

        for condition in query.where_conditions:
            aliases = self._aliases_in_expression(condition, query)
            if len(aliases) <= 1:
                # Condição afeta apenas uma tabela → pode ser aplicada antes do JOIN
                alias = list(aliases)[0] if aliases else query.base_alias
                local_filters[alias].append(condition)
            else:
                # Condição cruza tabelas → precisa ficar após o JOIN
                cross_filters.append(condition)

        # Descobre quais colunas cada tabela realmente precisa fornecer
        needed_columns: Dict[str, Set[str]] = {alias: set() for alias in query.alias_to_table}
        for column in query.select_columns:
            self._collect_column_usage(column, query, needed_columns)
        for condition in query.where_conditions:
            self._collect_condition_usage(condition, query, needed_columns)
        for join in query.joins:
            self._collect_condition_usage(join.condition, query, needed_columns)

        # Constrói um nó folha para cada tabela com seus filtros e projeções locais
        leaf_nodes: Dict[str, OperatorNode] = {}
        for alias, table in query.alias_to_table.items():
            node = OperatorNode('TABLE', f'{table} ({alias})' if alias != table else table)
            if local_filters[alias]:
                node = OperatorNode('SELECT', f'σ {' AND '.join(local_filters[alias])}', [node])
            if needed_columns[alias]:
                proj_cols = ', '.join(sorted(f'{alias}.{c}' for c in needed_columns[alias]))
                node = OperatorNode('PROJECT', f'π {proj_cols}', [node])
            leaf_nodes[alias] = node

        # Ordena JOINs: prioriza tabelas com mais filtros locais (reduzem mais linhas)
        ordered_joins = sorted(
            query.joins,
            key=lambda j: (
                -(len(local_filters[j.alias]) + self._condition_complexity(j.condition)),
                j.table,
            ),
        )

        # Monta a árvore de JOINs conectando folhas na ordem otimizada
        current_aliases = {query.base_alias}
        current = leaf_nodes[query.base_alias]
        pending = ordered_joins.copy()
        while pending:
            progressed = False
            for join in list(pending):
                aliases = self._aliases_in_expression(join.condition, query)
                if aliases & current_aliases:
                    # Conecta o JOIN apenas quando a tabela esquerda já está disponível
                    current = OperatorNode('JOIN', f'⋈ {join.condition}', [current, leaf_nodes[join.alias]])
                    current_aliases.add(join.alias)
                    pending.remove(join)
                    progressed = True
            if not progressed:
                # Fallback: conecta o próximo JOIN pendente para evitar loop infinito
                join = pending.pop(0)
                current = OperatorNode('JOIN', f'⋈ {join.condition}', [current, leaf_nodes[join.alias]])
                current_aliases.add(join.alias)

        # Aplica filtros cruzados (que dependem de múltiplas tabelas) após todos os JOINs
        if cross_filters:
            current = OperatorNode('SELECT', f'σ {' AND '.join(cross_filters)}', [current])

        # Projeção final: mantém apenas as colunas pedidas no SELECT
        current = OperatorNode('PROJECT', f'π {", ".join(query.select_columns)}', [current])
        return current

    # Pontuação heurística de complexidade de uma condição (mais operadores = mais seletiva)
    def _condition_complexity(self, condition: str) -> int:
        score = 1
        for op in ('=', '<>', '<=', '>=', '>', '<'):
            if op in condition:
                score += 1
        return score

    # Extrai todos os aliases referenciados em uma expressão (ex: "a.id = b.id" → {"a", "b"})
    def _aliases_in_expression(self, expression: str, query: QueryData) -> Set[str]:
        refs = re.findall(r'([A-Za-z_][\w]*)\.([A-Za-z_][\w]*)', expression)
        aliases = {alias.lower() for alias, _ in refs if alias.lower() in query.alias_to_table}
        return aliases

    # Registra colunas usadas em uma condição no dicionário de colunas necessárias
    def _collect_condition_usage(self, condition: str, query: QueryData, needed_columns: Dict[str, Set[str]]) -> None:
        refs = re.findall(r'([A-Za-z_][\w]*)\.([A-Za-z_][\w]*)', condition)
        for alias, column in refs:
            alias = alias.lower()
            column = column.lower()
            if alias in needed_columns:
                needed_columns[alias].add(column)

    # Registra colunas usadas no SELECT (inclui "*" que expande todas as colunas)
    def _collect_column_usage(self, ref: str, query: QueryData, needed_columns: Dict[str, Set[str]]) -> None:
        ref = ref.strip()
        if ref == '*':
            # SELECT *: todas as colunas de todas as tabelas são necessárias
            for alias, table in query.alias_to_table.items():
                needed_columns[alias].update(self.schema[table])
            return

        if '.' in ref:
            alias, column = [part.strip().lower() for part in ref.split('.', 1)]
            if alias in needed_columns:
                needed_columns[alias].add(column)
            return

        # Coluna sem alias: encontra a tabela que a contém
        column = ref.lower()
        matches = []
        for alias, table in query.alias_to_table.items():
            if column in self.schema[table]:
                matches.append(alias)
        if len(matches) == 1:
            needed_columns[matches[0]].add(column)

    # ── PLANO DE EXECUÇÃO ─────────────────────────────────────────────────────

    # Percorre a árvore otimizada em pós-ordem e gera os passos do plano de execução
    def _build_execution_plan(self, root: OperatorNode) -> List[str]:
        plan: List[str] = []

        def traverse(node: OperatorNode) -> None:
            for child in node.children:
                traverse(child)   # Filhos primeiro (pós-ordem = ordem de execução real)
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

    # ── RENDERIZAÇÃO TEXTUAL ──────────────────────────────────────────────────

    # Renderiza a árvore como texto com conectores ASCII (├── / └──)
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


# ── LAYOUT VISUAL ─────────────────────────────────────────────────────────────

# Calcula as coordenadas (x, y) de cada nó para renderização gráfica da árvore.
# x é distribuído horizontalmente pelas folhas; y representa a profundidade.
def layout_tree(root: OperatorNode) -> List[OperatorNode]:
    levels: Dict[int, List[OperatorNode]] = {}

    def assign(node: OperatorNode, depth: int, next_x: List[int]) -> None:
        for child in node.children:
            assign(child, depth + 1, next_x)
        if not node.children:
            # Folha: ocupa a próxima posição horizontal disponível
            node.x = next_x[0]
            next_x[0] += 1
        else:
            # Nó interno: centraliza sobre seus filhos
            node.x = sum(child.x for child in node.children) / len(node.children)
        node.y = depth
        levels.setdefault(depth, []).append(node)

    assign(root, 0, [0])
    # Retorna todos os nós ordenados por nível (topo → folhas)
    all_nodes: List[OperatorNode] = []
    for depth in sorted(levels):
        all_nodes.extend(levels[depth])
    return all_nodes